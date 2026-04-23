#!/usr/bin/env python3
"""
LeanContext Memory Compression Orchestrator

Usage:
    python scripts/compress.py <filepath>
"""

import os
import re
import subprocess
import time
from json import JSONDecodeError, dumps, loads
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OUTER_FENCE_REGEX = re.compile(
    r"\A\s*(`{3,}|~{3,})[^\n]*\n(.*)\n\1\s*\Z", re.DOTALL
)
FENCE_OPEN_REGEX = re.compile(r"^(\s{0,3})(`{3,}|~{3,})(.*)$")
INLINE_CODE_SPAN_REGEX = re.compile(r"(?<!`)`[^`\n]+`(?!`)")

# Filenames and paths that almost certainly hold secrets or PII. Compressing
# them ships raw bytes to the configured LLM backend — a third-party data
# boundary developers on sensitive codebases cannot cross. detect.py already
# skips .env by extension, but credentials.md / secrets.txt / ~/.aws/credentials
# would slip through the natural-language filter. This is a hard refuse before
# read.
SENSITIVE_BASENAME_REGEX = re.compile(
    r"(?ix)^("
    r"\.env(\..+)?"
    r"|\.netrc"
    r"|credentials(\..+)?"
    r"|secrets?(\..+)?"
    r"|passwords?(\..+)?"
    r"|id_(rsa|dsa|ecdsa|ed25519)(\.pub)?"
    r"|authorized_keys"
    r"|known_hosts"
    r"|.*\.(pem|key|p12|pfx|crt|cer|jks|keystore|asc|gpg)"
    r")$"
)

SENSITIVE_PATH_COMPONENTS = frozenset({".ssh", ".aws", ".gnupg", ".kube", ".docker"})

SENSITIVE_NAME_TOKENS = (
    "secret", "credential", "password", "passwd",
    "apikey", "accesskey", "token", "privatekey",
)


def is_sensitive_path(filepath: Path) -> bool:
    """Heuristic denylist for files that must never be shipped to a third-party API."""
    name = filepath.name
    if SENSITIVE_BASENAME_REGEX.match(name):
        return True
    lowered_parts = {p.lower() for p in filepath.parts}
    if lowered_parts & SENSITIVE_PATH_COMPONENTS:
        return True
    # Normalize separators so "api-key" and "api_key" both match "apikey".
    lower = re.sub(r"[_\-\s.]", "", name.lower())
    return any(tok in lower for tok in SENSITIVE_NAME_TOKENS)


def strip_llm_wrapper(text: str) -> str:
    """Strip outer ```markdown ... ``` fence when it wraps the entire output."""
    m = OUTER_FENCE_REGEX.match(text)
    if m:
        return m.group(2)
    return text


def mask_inline_code(text: str) -> tuple[str, dict[str, str]]:
    replacements: dict[str, str] = {}
    counter = 0
    lines = text.splitlines(keepends=True)
    output = []
    fence_char = None
    fence_len = 0

    for line in lines:
        match = FENCE_OPEN_REGEX.match(line.rstrip("\n"))
        if match:
            marker = match.group(2)
            marker_char = marker[0]
            marker_len = len(marker)
            if fence_char is None:
                fence_char = marker_char
                fence_len = marker_len
            elif marker_char == fence_char and marker_len >= fence_len and match.group(3).strip() == "":
                fence_char = None
                fence_len = 0
            output.append(line)
            continue

        if fence_char is not None:
            output.append(line)
            continue

        def repl(m: re.Match[str]) -> str:
            nonlocal counter
            token = f"LEANCONTEXT_INLINE_{counter}_TOKEN"
            replacements[token] = m.group(0)
            counter += 1
            return token

        output.append(INLINE_CODE_SPAN_REGEX.sub(repl, line))

    return "".join(output), replacements


def unmask_inline_code(text: str, replacements: dict[str, str]) -> str:
    for token, original in replacements.items():
        text = text.replace(token, original)
    return text


def post_compress_cleanup(text: str) -> str:
    lines = text.splitlines()
    output = []
    fence_char = None
    fence_len = 0

    for line in lines:
        match = FENCE_OPEN_REGEX.match(line)
        if match:
            marker = match.group(2)
            marker_char = marker[0]
            marker_len = len(marker)
            if fence_char is None:
                fence_char = marker_char
                fence_len = marker_len
            elif marker_char == fence_char and marker_len >= fence_len and match.group(3).strip() == "":
                fence_char = None
                fence_len = 0
            output.append(line)
            continue

        if fence_char is not None or line.lstrip().startswith("#") or line.lstrip().startswith("|"):
            output.append(line)
            continue

        cleaned = line
        cleaned = re.sub(r"^(\s*)Team ([A-Z]{2,}-\d+\b)", r"\1\2", cleaned)

        if len(re.findall(r"\bdocs\b", cleaned, flags=re.IGNORECASE)) > 1:
            seen_docs = False

            def drop_extra_docs(m: re.Match[str]) -> str:
                nonlocal seen_docs
                if not seen_docs:
                    seen_docs = True
                    return m.group(0)
                return ""

            cleaned = re.sub(r"\bdocs\b\s*", drop_extra_docs, cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

        output.append(cleaned)

    return "\n".join(output)


def extract_placeholder_tokens(text: str, ordered_tokens: list[str]) -> list[str]:
    found = []
    for token in ordered_tokens:
        if token in text:
            found.append(token)
    return found


def enforce_placeholder_sequence(text: str, ordered_tokens: list[str]) -> str:
    if not ordered_tokens:
        return text

    if extract_placeholder_tokens(text, ordered_tokens) == ordered_tokens:
        return text

    for token in ordered_tokens:
        text = text.replace(token, "")

    lines = text.splitlines()
    insertion = " " + " ".join(ordered_tokens)

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines[idx] = re.sub(r"\s{2,}", " ", line.rstrip()) + insertion
        return "\n".join(lines)

    if text and not text.endswith("\n"):
        text += "\n"
    return text + " ".join(ordered_tokens)

from .detect import should_compress
from .validate import validate

MAX_RETRIES = 2
MAX_EXTRA_SHRINK_PASSES = 2
OPENROUTER_MAX_RETRIES = 3
OPENROUTER_MAX_CONTINUATIONS = 4
CLAUDE_CONFIG_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))
LOCAL_SECRET_PATH = CLAUDE_CONFIG_DIR / "leancontext-openrouter.json"


# ---------- Backend Calls ----------

_LOCAL_SECRET_CACHE: Optional[Dict[str, str]] = None


def load_local_secrets() -> Dict[str, str]:
    global _LOCAL_SECRET_CACHE
    if _LOCAL_SECRET_CACHE is not None:
        return _LOCAL_SECRET_CACHE

    if not LOCAL_SECRET_PATH.exists():
        _LOCAL_SECRET_CACHE = {}
        return _LOCAL_SECRET_CACHE

    try:
        payload = loads(LOCAL_SECRET_PATH.read_text())
    except Exception:
        _LOCAL_SECRET_CACHE = {}
        return _LOCAL_SECRET_CACHE

    if not isinstance(payload, dict):
        _LOCAL_SECRET_CACHE = {}
        return _LOCAL_SECRET_CACHE

    secrets: Dict[str, str] = {}
    for key, value in payload.items():
        if isinstance(key, str) and isinstance(value, str):
            secrets[key] = value
    _LOCAL_SECRET_CACHE = secrets
    return _LOCAL_SECRET_CACHE


def setting(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name)
    if value:
        return value
    return load_local_secrets().get(name, default)


def target_savings_pct() -> float:
    raw = setting("LEANCONTEXT_TARGET_SAVINGS_PCT", "50")
    try:
        return max(0.0, float(raw or "0"))
    except ValueError:
        return 50.0


def openrouter_max_tokens() -> int:
    raw = setting("LEANCONTEXT_OPENROUTER_MAX_TOKENS", "8192")
    try:
        value = int(raw or "8192")
    except ValueError:
        return 8192
    return max(256, value)


def token_count(text: str) -> int:
    try:
        from .benchmark import count_tokens as count_tokens_impl
    except ImportError:
        from benchmark import count_tokens as count_tokens_impl

    return count_tokens_impl(text)


def savings_pct(original_text: str, compressed_text: str) -> float:
    original_tokens = token_count(original_text)
    compressed_tokens = token_count(compressed_text)
    if original_tokens <= 0:
        return 0.0
    return 100.0 * (original_tokens - compressed_tokens) / original_tokens


def get_backend() -> str:
    forced = (setting("LEANCONTEXT_BACKEND", "") or "").strip().lower()
    if forced == "auto":
        forced = ""

    if forced:
        valid = {"openrouter", "anthropic", "claude", "claude-cli"}
        if forced not in valid:
            raise RuntimeError(
                f"Unsupported LEANCONTEXT_BACKEND={forced!r}. Use one of: auto, openrouter, anthropic, claude-cli."
            )
        if forced == "openrouter" and not setting("OPENROUTER_API_KEY"):
            raise RuntimeError("LEANCONTEXT_BACKEND=openrouter but OPENROUTER_API_KEY is not set.")
        if forced == "anthropic" and not setting("ANTHROPIC_API_KEY"):
            raise RuntimeError("LEANCONTEXT_BACKEND=anthropic but ANTHROPIC_API_KEY is not set.")
        return "claude-cli" if forced in {"claude", "claude-cli"} else forced

    if setting("OPENROUTER_API_KEY"):
        return "openrouter"
    if setting("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "claude-cli"


def get_backend_label() -> str:
    backend = get_backend()
    if backend == "openrouter":
        model = setting("OPENROUTER_MODEL") or setting(
            "LEANCONTEXT_OPENROUTER_MODEL", "openrouter/elephant-alpha"
        )
        return f"OpenRouter ({model})"
    if backend == "anthropic":
        model = setting("LEANCONTEXT_MODEL", "claude-sonnet-4-5")
        return f"Anthropic API ({model})"
    return "Claude CLI"


def is_transient_openrouter_error(exc: Exception) -> bool:
    if isinstance(exc, HTTPError):
        return exc.code in {408, 409, 425, 429, 500, 502, 503, 504}

    if isinstance(exc, URLError):
        reason = exc.reason
        if isinstance(reason, TimeoutError):
            return True
        if isinstance(reason, OSError) and getattr(reason, "errno", None) in {54, 60, 61, 104, 110, 111}:
            return True
        if isinstance(reason, str):
            lowered = reason.lower()
            return (
                "timed out" in lowered
                or "timeout" in lowered
                or "connection reset" in lowered
                or "temporarily unavailable" in lowered
            )
        return False

    if isinstance(exc, OSError):
        return getattr(exc, "errno", None) in {54, 60, 61, 104, 110, 111}

    return False


def extract_openrouter_text(content) -> str:
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        content = "".join(parts)

    if not isinstance(content, str):
        raise RuntimeError(
            f"OpenRouter returned unsupported content shape: {type(content).__name__}"
        )

    return strip_llm_wrapper(content.strip())


def merge_continuation(existing: str, continuation: str) -> str:
    if not continuation:
        return existing

    if not existing:
        return continuation

    max_overlap = min(len(existing), len(continuation), 512)
    for overlap in range(max_overlap, 0, -1):
        if existing.endswith(continuation[:overlap]):
            return existing + continuation[overlap:]

    if continuation in existing[-1024:]:
        return existing

    return existing + continuation


def call_openrouter_api(headers: Dict[str, str], payload: Dict[str, object]) -> Dict[str, object]:
    request = Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    last_error: Optional[Exception] = None
    raw = ""
    for attempt in range(OPENROUTER_MAX_RETRIES):
        try:
            with urlopen(request, timeout=120) as response:
                raw = response.read().decode("utf-8")
            break
        except HTTPError as e:
            last_error = e
            body = e.read().decode("utf-8", errors="replace")
            if attempt < OPENROUTER_MAX_RETRIES - 1 and is_transient_openrouter_error(e):
                time.sleep(1.0 * (attempt + 1))
                continue
            raise RuntimeError(f"OpenRouter call failed ({e.code}): {body}") from e
        except URLError as e:
            last_error = e
            if attempt < OPENROUTER_MAX_RETRIES - 1 and is_transient_openrouter_error(e):
                time.sleep(1.0 * (attempt + 1))
                continue
            raise RuntimeError(f"OpenRouter call failed: {e.reason}") from e
        except OSError as e:
            last_error = e
            if attempt < OPENROUTER_MAX_RETRIES - 1 and is_transient_openrouter_error(e):
                time.sleep(1.0 * (attempt + 1))
                continue
            raise RuntimeError(f"OpenRouter call failed: {e}") from e
    else:
        raise RuntimeError(f"OpenRouter call failed after retries: {last_error}")

    try:
        data = loads(raw)
    except JSONDecodeError as e:
        raise RuntimeError(f"OpenRouter returned invalid JSON: {raw[:500]}") from e

    if not isinstance(data, dict):
        raise RuntimeError(f"OpenRouter returned unsupported response shape: {type(data).__name__}")

    return data


def call_openrouter(prompt: str) -> str:
    api_key = setting("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set.")

    model = setting("OPENROUTER_MODEL") or setting(
        "LEANCONTEXT_OPENROUTER_MODEL", "openrouter/elephant-alpha"
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": setting(
            "OPENROUTER_HTTP_REFERER", "https://github.com/allytag/LeanContext"
        ),
        "X-Title": setting("OPENROUTER_APP_NAME", "LeanContext"),
    }
    max_tokens = openrouter_max_tokens()
    messages: List[Dict[str, str]] = [{"role": "user", "content": prompt}]
    content = ""

    for continuation_idx in range(OPENROUTER_MAX_CONTINUATIONS + 1):
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
        }
        data = call_openrouter_api(headers, payload)

        try:
            choice = data["choices"][0]
            piece = extract_openrouter_text(choice["message"]["content"])
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(
                f"OpenRouter response missing assistant content: {str(data)[:500]}"
            ) from e

        finish_reason = choice.get("finish_reason")
        content = merge_continuation(content, piece)

        if finish_reason != "length":
            return content

        if continuation_idx >= OPENROUTER_MAX_CONTINUATIONS:
            raise RuntimeError(
                "OpenRouter response hit output limit repeatedly. "
                "Increase LEANCONTEXT_OPENROUTER_MAX_TOKENS or compress a smaller file."
            )

        messages = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": content},
            {
                "role": "user",
                "content": (
                    "Continue exactly from next character only. "
                    "Do not restart, summarize, explain, or repeat prior text."
                ),
            },
        ]

    raise RuntimeError("OpenRouter continuation loop exited unexpectedly.")


def call_claude(prompt: str) -> str:
    api_key = setting("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model=setting("LEANCONTEXT_MODEL", "claude-sonnet-4-5"),
                max_tokens=8192,
                messages=[{"role": "user", "content": prompt}],
            )
            return strip_llm_wrapper(msg.content[0].text.strip())
        except ImportError:
            pass  # anthropic not installed, fall back to CLI
    # Fallback: use claude CLI (handles desktop auth)
    try:
        result = subprocess.run(
            ["claude", "--print"],
            input=prompt,
            text=True,
            capture_output=True,
            check=True,
        )
        return strip_llm_wrapper(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        details = (e.stderr or e.stdout or "").strip()
        if not details:
            details = f"exit code {e.returncode}"
        raise RuntimeError(f"Claude call failed:\n{details}")


def call_backend(prompt: str) -> str:
    backend = get_backend()
    if backend == "openrouter":
        return call_openrouter(prompt)
    return call_claude(prompt)


def build_compress_prompt(original: str) -> str:
    return f"""
Compress this markdown into LeanContext format.

STRICT RULES:
- Reduce token count by at least 30% when possible without breaking preservation rules
- Use LeanContext-style fragments, not polished full sentences
- Prefer short commands and noun phrases
- Remove articles, filler, hedging, and connective fluff
- Prefer periods over em dashes or decorative punctuation
- Do NOT modify anything inside ``` code blocks
- Do NOT modify anything inside inline backticks
- Preserve placeholder tokens like `LEANCONTEXT_INLINE_0_TOKEN` exactly
- Preserve ALL URLs exactly
- Preserve ALL headings exactly
- Preserve file paths and commands
- Return ONLY the compressed markdown body — do NOT wrap the entire output in a ```markdown fence or any other fence. Inner code blocks from the original stay as-is; do not add a new outer fence around the whole file.

Only compress natural language.

STYLE EXAMPLES:
- "Before every deploy we need to run migration in order to avoid schema drift" -> "Run migration before deploy. Prevent schema drift."
- "It is worth noting that responders should not rewrite stack traces" -> "Do not rewrite stack traces."

TEXT:
{original}
"""


def build_fix_prompt(original: str, compressed: str, errors: List[str]) -> str:
    errors_str = "\n".join(f"- {e}" for e in errors)
    return f"""You are fixing a LeanContext-compressed markdown file. Specific validation errors were found.

CRITICAL RULES:
- DO NOT recompress or rephrase the file
- ONLY fix the listed errors — leave everything else exactly as-is
- The ORIGINAL is provided as reference only (to restore missing content)
- Preserve LeanContext style in all untouched sections

ERRORS TO FIX:
{errors_str}

HOW TO FIX:
- Missing URL: find it in ORIGINAL, restore it exactly where it belongs in COMPRESSED
- Code block mismatch: find the exact code block in ORIGINAL, restore it in COMPRESSED
- Inline code mismatch: restore exact backticked spans from ORIGINAL, including backticks, case, punctuation, and spacing
- Placeholder mismatch: restore exact `LEANCONTEXT_INLINE_*_TOKEN` markers from ORIGINAL
- Heading mismatch: restore the exact heading text from ORIGINAL into COMPRESSED
- Do not touch any section not mentioned in the errors

ORIGINAL (reference only):
{original}

COMPRESSED (fix this):
{compressed}

Return ONLY the fixed compressed file. No explanation.
"""


def build_shrink_prompt(current: str) -> str:
    return f"""
Compress this markdown further.

STRICT RULES:
- Input already compressed. Shrink harder.
- Target fewer tokens than input while preserving technical meaning.
- Keep heading text exactly.
- Keep placeholder tokens like `LEANCONTEXT_INLINE_0_TOKEN` exactly.
- Keep URLs, commands, file paths, numbers, versions, and proper nouns exactly.
- Prefer LeanContext fragments over full sentences.
- Remove articles, helper verbs, filler, and repeated context.
- Merge nearby short sentences when meaning stays same.
- Return ONLY markdown body.

STYLE EXAMPLES:
- "Run migration before deploy. Prevent schema drift." -> "Run migration before deploy. Prevent drift."
- "Do not rewrite stack traces. Do not paraphrase payloads." -> "Do not rewrite stack traces or paraphrase payloads."

TEXT:
{current}
"""


def compress_text_with_retries(original_text: str) -> str:
    masked_original, replacements = mask_inline_code(original_text)
    ordered_tokens = list(replacements.keys())
    compressed = call_backend(build_compress_prompt(masked_original))
    compressed = enforce_placeholder_sequence(compressed, ordered_tokens)
    compressed = unmask_inline_code(compressed, replacements)
    compressed = post_compress_cleanup(compressed)

    for attempt in range(MAX_RETRIES):
        validation = validate_text_pair(original_text, compressed)
        if validation.is_valid:
            best = compressed
            break

        if attempt == MAX_RETRIES - 1:
            raise RuntimeError(
                "Validation failed after retries: " + "; ".join(validation.errors)
            )

        masked_compressed = compressed
        for token, original in replacements.items():
            masked_compressed = masked_compressed.replace(original, token)
        compressed = call_backend(
            build_fix_prompt(masked_original, masked_compressed, validation.errors)
        )
        compressed = enforce_placeholder_sequence(compressed, ordered_tokens)
        compressed = unmask_inline_code(compressed, replacements)
        compressed = post_compress_cleanup(compressed)
    else:
        best = compressed

    target = target_savings_pct()
    if target <= 0:
        return best

    best_savings = savings_pct(original_text, best)
    if best_savings >= target:
        return best

    for _ in range(MAX_EXTRA_SHRINK_PASSES):
        candidate = shrink_text_with_retries(original_text, best)
        candidate_savings = savings_pct(original_text, candidate)
        if candidate_savings <= best_savings:
            break
        best = candidate
        best_savings = candidate_savings
        if best_savings >= target:
            break

    return best


def shrink_text_with_retries(original_text: str, current_text: str) -> str:
    masked_original, replacements = mask_inline_code(original_text)
    ordered_tokens = list(replacements.keys())
    masked_current = current_text
    for token, original in replacements.items():
        masked_current = masked_current.replace(original, token)

    compressed = call_backend(build_shrink_prompt(masked_current))
    compressed = enforce_placeholder_sequence(compressed, ordered_tokens)
    compressed = unmask_inline_code(compressed, replacements)
    compressed = post_compress_cleanup(compressed)

    for attempt in range(MAX_RETRIES):
        validation = validate_text_pair(original_text, compressed)
        if validation.is_valid:
            return compressed

        if attempt == MAX_RETRIES - 1:
            return current_text

        masked_compressed = compressed
        for token, original in replacements.items():
            masked_compressed = masked_compressed.replace(original, token)
        compressed = call_backend(
            build_fix_prompt(masked_original, masked_compressed, validation.errors)
        )
        compressed = enforce_placeholder_sequence(compressed, ordered_tokens)
        compressed = unmask_inline_code(compressed, replacements)
        compressed = post_compress_cleanup(compressed)

    return current_text


def validate_text_pair(original_text: str, compressed_text: str):
    import tempfile

    with tempfile.TemporaryDirectory(prefix="leancontext-validate-") as td:
        tmp = Path(td)
        orig_path = tmp / "fixture.original.md"
        comp_path = tmp / "fixture.md"
        orig_path.write_text(original_text)
        comp_path.write_text(compressed_text)
        return validate(orig_path, comp_path)


# ---------- Core Logic ----------


def compress_file(filepath: Path) -> bool:
    # Resolve and validate path
    filepath = filepath.resolve()
    MAX_FILE_SIZE = 500_000  # 500KB
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    if filepath.stat().st_size > MAX_FILE_SIZE:
        raise ValueError(f"File too large to compress safely (max 500KB): {filepath}")

    # Refuse files that look like they contain secrets or PII. Compressing ships
    # the raw bytes to the configured backend, so we fail loudly rather than
    # silently exfiltrate credentials or keys. Override is intentional: the user
    # must rename the file if the heuristic is wrong.
    if is_sensitive_path(filepath):
        raise ValueError(
            f"Refusing to compress {filepath}: filename looks sensitive "
            "(credentials, keys, secrets, or known private paths). "
            "Compression sends file contents to the configured LLM backend. "
            "Rename the file if this is a false positive."
        )

    print(f"Processing: {filepath}")

    if not should_compress(filepath):
        print("Skipping (not natural language)")
        return False

    original_text = filepath.read_text(errors="ignore")
    backup_path = filepath.with_name(filepath.stem + ".original.md")

    # Check if backup already exists to prevent accidental overwriting
    if backup_path.exists():
        print(f"⚠️ Backup file already exists: {backup_path}")
        print("The original backup may contain important content.")
        print("Aborting to prevent data loss. Please remove or rename the backup file if you want to proceed.")
        return False

    try:
        print(f"Compressing with {get_backend_label()}...")
        compressed = compress_text_with_retries(original_text)
    except Exception as exc:
        print(f"❌ Compression/validation failed: {exc}")
        return False

    backup_path.write_text(original_text)
    filepath.write_text(compressed)
    print("Validation passed")
    return True
