# LeanContext

**Cuts AI coding chat tokens ~50–75% without dropping technical accuracy.**

Works in Claude Code, Codex, Gemini CLI, Cursor, Windsurf, Cline, Copilot, and 40+ other agents via `npx skills`.

---

## Before / After

**Without LeanContext**
> Sure! I'd be happy to help you understand what this function does. Let me walk you through it step by step. First, looking at the top of the file, we can see that the function takes two parameters...

**With LeanContext**
> `parseConfig(path, opts)` — reads JSON at `path`, merges with `opts`, returns validated config or throws `ConfigError`.

Same answer. Fraction of the tokens.

---

## What You Get

| Feature | Basic "be brief" | LeanContext |
|---|:---:|:---:|
| Shorter chat output | ✓ | ✓ |
| Delta-first follow-ups (no replay) | — | ✓ |
| Protected code / paths / errors | Weak | Strong |
| Memory-file compression | — | ✓ |
| Deterministic quality gate | — | ✓ |
| OpenRouter compression backend | — | ✓ |
| Multi-agent distribution | — | ✓ |
| Codex update-safe local install | — | ✓ |
| Claude Code hooks + statusline | — | ✓ |

---

## Results

Golden compression gate: **5/5 pass**, average savings **53.26%**, minimum **50.0%**.

Claude live eval (10-prompt sample):

| | Output tokens |
|---|---|
| Baseline | 3482 |
| LeanContext | 3291 |
| Saved | 191 (5.49%) |

LeanContext targets waste — long answers and replay-heavy follow-ups — not every word. Short precise answers stay short.

---

## Install

Fast path from a repo clone:

**macOS / Linux**
```bash
python3 install.py
```

**Windows PowerShell**
```powershell
py install.py
```

`install.py` auto-detects Codex + Claude Code, installs local independent copies, and can be undone with:

**macOS / Linux**
```bash
python3 uninstall.py
```

**Windows PowerShell**
```powershell
py uninstall.py
```

| Agent | Command |
|---|---|
| Claude Code | `python3 install.py --claude` |
| Codex | `python3 install.py --codex` |
| Gemini CLI | `gemini extensions install https://github.com/allytag/LeanContext` |
| Cursor | `npx skills add allytag/LeanContext -a cursor` |
| Windsurf | `npx skills add allytag/LeanContext -a windsurf` |
| Copilot | `npx skills add allytag/LeanContext -a github-copilot` |
| Cline | `npx skills add allytag/LeanContext -a cline` |
| Other agents | `npx skills add allytag/LeanContext` |

Claude Code, Gemini CLI, and Codex auto-activate when the repo is open. Cursor, Windsurf, Cline, and Copilot pick up the always-on rule files included in the repo.

No repo lock-in after install:
- Codex payload is copied to `~/plugins/leancontext`
- Claude Code caches plugin in `~/.claude/plugins`

One-command remote install:

**macOS / Linux**
```bash
curl -fsSL https://raw.githubusercontent.com/allytag/LeanContext/main/install.py | python3 - --all
```

**Windows PowerShell**
```powershell
irm https://raw.githubusercontent.com/allytag/LeanContext/main/install.py | py - --all
```

One-command uninstall:

**macOS / Linux**
```bash
curl -fsSL https://raw.githubusercontent.com/allytag/LeanContext/main/uninstall.py | python3 - --all
```

**Windows PowerShell**
```powershell
irm https://raw.githubusercontent.com/allytag/LeanContext/main/uninstall.py | py - --all
```

<details>
<summary>Claude Code — detailed install</summary>

From the repo root:

```bash
python3 install.py --claude
```

Standalone hooks (no plugin required):

```bash
bash hooks/install.sh
```

Restart Claude Code after install.

</details>

<details>
<summary>Codex — detailed install</summary>

From the repo root:

```bash
python3 install.py --codex
```

The installer copies the plugin to `~/plugins/leancontext`, adds a local marketplace entry, and syncs the cache. Repo can be deleted after install.

Health check:

```bash
python3 codex/scripts/doctor_codex_local.py
```

</details>

---

## Commands

| Command | Effect |
|---|---|
| `/leancontext` | Enable default (full) mode |
| `/leancontext lite` | Professional concise |
| `/leancontext full` | Terse technical fragments |
| `/leancontext ultra` | Maximum compression |
| `/leancontext wenyan-lite\|wenyan\|wenyan-ultra` | Classical Chinese variants |
| `/leancontext-commit` | Conventional Commit message, compressed |
| `/leancontext-review` | One-line code review findings |
| `/leancontext:compress <file>` | Compress a markdown memory file |

---

## Memory Compression

`/leancontext:compress` shrinks `CLAUDE.md`, project notes, todos, and preference files. Protected content (code blocks, file paths, error messages, API names, versions) is never touched.

---

## OpenRouter (Optional)

Used by `/leancontext:compress` for budget-friendly compression models.

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
export LEANCONTEXT_OPENROUTER_MODEL="openrouter/elephant-alpha"
```

Or store credentials in a local file (never committed):

**Claude Code:** `~/.claude/leancontext-openrouter.json`
**Codex:** `~/.codex/leancontext-openrouter.json`

```json
{
  "OPENROUTER_API_KEY": "sk-or-v1-...",
  "LEANCONTEXT_OPENROUTER_MODEL": "openrouter/elephant-alpha",
  "LEANCONTEXT_TARGET_SAVINGS_PCT": "50"
}
```

---

## Quality Gate

Validates compression structure, required tokens, and savings thresholds against deterministic fixtures.

```bash
# Claude
cd claude/skills/compress
python3 -m scripts --gate --source golden

# Codex
cd codex/skills/compress
python3 -m scripts --gate --source golden
```

## Uninstall

From a repo clone:

**macOS / Linux**
```bash
python3 uninstall.py
```

**Windows PowerShell**
```powershell
py uninstall.py
```

Target one host only:

**macOS / Linux**
```bash
python3 uninstall.py --claude
python3 uninstall.py --codex
```

**Windows PowerShell**
```powershell
py uninstall.py --claude
py uninstall.py --codex
```

---

## Safety

LeanContext never compresses:

- Code blocks and backtick spans
- File paths and shell commands
- Exact error messages
- API names and technical identifiers
- Numbers, units, and version strings
- Direct documentation quotes

---

## Repo Layout

```
.
├── skills/               # Unified skill definitions (Claude / Gemini / npx)
├── hooks/                # Standalone Claude Code hooks
├── commands/             # Claude Code slash commands
├── plugins/leancontext/  # Codex plugin payload
├── leancontext/          # npx skills entry
├── leancontext-compress/ # Compression skill (npx / Gemini)
├── .cursor/              # Cursor rule + skill
├── .windsurf/            # Windsurf rule + skill
├── .clinerules/          # Cline rule
├── .github/              # Copilot instructions
├── .codex/               # Codex auto-start hook
├── codex/                # Codex plugin build
├── claude/               # Claude Code plugin build
└── evals/                # Token-savings eval harness
```

---

## License

[MIT](LICENSE)
