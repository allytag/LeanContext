#!/usr/bin/env python3
"""One-command LeanContext installer for Codex and Claude Code."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from shlex import quote

PLUGIN_NAME = "leancontext"
CLAUDE_MARKETPLACE = "leancontext"
LOCAL_MARKETPLACE = "local"
CURATED_MARKETPLACE = "openai-curated"
REPO_SLUG = "allytag/LeanContext"
REPO_REF = "main"

SECTION_RE = re.compile(r'^\[plugins\."([^"]+)"\]\s*$')
ENABLED_RE = re.compile(r"^\s*enabled\s*=\s*(true|false)\s*$")


def repo_markers(root: Path) -> bool:
    return all(
        path.exists()
        for path in (
            root / "claude" / ".claude-plugin" / "plugin.json",
            root / "codex" / ".codex-plugin" / "plugin.json",
            root / "plugins" / "leancontext" / ".codex-plugin" / "plugin.json",
            root / "README.md",
        )
    )


def discover_repo_root() -> Path | None:
    candidates: list[Path] = [Path.cwd()]

    raw_file = globals().get("__file__")
    if raw_file:
        candidates.append(Path(raw_file).resolve().parent)

    for base in candidates:
        for candidate in (base, *base.parents):
            if repo_markers(candidate):
                return candidate
    return None


def data_root() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "LeanContext"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "LeanContext"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "leancontext"


def stage_repo_from_github(repo: str, ref: str, dry_run: bool) -> Path:
    target_root = data_root() / "source"
    staged_root = target_root / f"LeanContext-{ref}"
    url = f"https://github.com/{repo}/archive/refs/heads/{ref}.zip"

    print(f"[INFO] local repo not found. staging {repo}@{ref} into {staged_root}")
    print(f"[INFO] download: {url}")
    if dry_run:
        return staged_root

    target_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="leancontext-download-") as tmp:
        tmp_dir = Path(tmp)
        archive_path = tmp_dir / "repo.zip"
        with urllib.request.urlopen(url) as response, archive_path.open("wb") as handle:
            shutil.copyfileobj(response, handle)

        extracted_root = tmp_dir / "extracted"
        extracted_root.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(extracted_root)

        children = [child for child in extracted_root.iterdir() if child.is_dir()]
        if len(children) != 1 or not repo_markers(children[0]):
            raise SystemExit("downloaded archive did not contain expected LeanContext repo layout")

        if staged_root.exists():
            shutil.rmtree(staged_root)
        shutil.copytree(
            children[0],
            staged_root,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
        )

    return staged_root


def shell_join(cmd: list[str]) -> str:
    return " ".join(quote(part) for part in cmd)


def run(cmd: list[str], *, cwd: Path | None = None, dry_run: bool, allow_failure: bool = False) -> int:
    prefix = "[DRY-RUN]" if dry_run else "[RUN]"
    where = f" (cwd={cwd})" if cwd else ""
    print(f"{prefix} {shell_join(cmd)}{where}")
    if dry_run:
        return 0

    result = subprocess.run(cmd, cwd=cwd, text=True, check=False)
    if result.returncode != 0 and not allow_failure:
        raise SystemExit(result.returncode)
    return result.returncode


def require_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"missing {label}: {path}")


def plugin_manifest(path: Path) -> dict | None:
    manifest_path = path / ".codex-plugin" / "plugin.json"
    if not manifest_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text())
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def is_managed_plugin_path(path: Path) -> bool:
    target = path
    if path.is_symlink():
        try:
            target = path.resolve(strict=True)
        except FileNotFoundError:
            return False
        except OSError:
            return False

    manifest = plugin_manifest(target)
    return bool(manifest and manifest.get("name") == PLUGIN_NAME)


def load_marketplace(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {
        "name": LOCAL_MARKETPLACE,
        "interface": {"displayName": "Local Plugins"},
        "plugins": [],
    }


def upsert_plugin_enabled(text: str, plugin_key: str, enabled: bool) -> str:
    header = f'[plugins."{plugin_key}"]'
    enabled_line = f"enabled = {'true' if enabled else 'false'}"
    lines = text.splitlines()
    i = 0

    while i < len(lines):
        if lines[i].strip() != header:
            i += 1
            continue

        j = i + 1
        while j < len(lines):
            stripped = lines[j].strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                break
            j += 1

        for k in range(i + 1, j):
            if ENABLED_RE.match(lines[k]):
                lines[k] = enabled_line
                return "\n".join(lines) + "\n"

        lines.insert(i + 1, enabled_line)
        return "\n".join(lines) + "\n"

    if lines and lines[-1].strip():
        lines.extend(["", header, enabled_line])
    else:
        lines.extend([header, enabled_line])

    return "\n".join(lines) + "\n"


def install_codex(repo_root: Path, dry_run: bool) -> None:
    payload_root = repo_root / "plugins" / "leancontext"
    manifest_path = payload_root / ".codex-plugin" / "plugin.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        version = str(manifest.get("version") or "")
        if not version:
            raise SystemExit(f"missing version in {manifest_path}")
    elif dry_run:
        print(f"[DRY-RUN] assume Codex plugin manifest at {manifest_path}")
        version = "<version>"
    else:
        raise SystemExit(f"missing Codex plugin manifest: {manifest_path}")

    home = Path.home()
    home_plugin_path = home / "plugins" / PLUGIN_NAME
    marketplace_path = home / ".agents" / "plugins" / "marketplace.json"
    config_path = home / ".codex" / "config.toml"
    cache_root = home / ".codex" / "plugins" / "cache" / LOCAL_MARKETPLACE / PLUGIN_NAME / version

    require_exists(config_path, "Codex config")

    print(f"[INFO] Codex install source: {payload_root}")
    print(f"[INFO] Codex local payload: {home_plugin_path}")

    if dry_run:
        print("[DRY-RUN] remove existing local LeanContext payload if present")
    else:
        if home_plugin_path.exists() or home_plugin_path.is_symlink():
            if not is_managed_plugin_path(home_plugin_path):
                raise SystemExit(
                    f"refusing to overwrite unmanaged path: {home_plugin_path}"
                )
            if home_plugin_path.is_symlink():
                home_plugin_path.unlink()
            else:
                shutil.rmtree(home_plugin_path)
        home_plugin_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            payload_root,
            home_plugin_path,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

    marketplace = load_marketplace(marketplace_path)
    marketplace.setdefault("name", LOCAL_MARKETPLACE)
    marketplace.setdefault("interface", {})
    marketplace["interface"].setdefault("displayName", "Local Plugins")
    marketplace.setdefault("plugins", [])

    entry = {
        "name": PLUGIN_NAME,
        "source": {
            "source": "local",
            "path": f"./plugins/{PLUGIN_NAME}",
        },
        "policy": {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        },
        "category": "Productivity",
    }

    replaced = False
    for index, plugin in enumerate(marketplace["plugins"]):
        if plugin.get("name") == PLUGIN_NAME:
            marketplace["plugins"][index] = entry
            replaced = True
            break
    if not replaced:
        marketplace["plugins"].append(entry)

    config_text = config_path.read_text()
    config_text = upsert_plugin_enabled(config_text, f"{PLUGIN_NAME}@{CURATED_MARKETPLACE}", False)
    config_text = upsert_plugin_enabled(config_text, f"{PLUGIN_NAME}@{LOCAL_MARKETPLACE}", True)

    if dry_run:
        print(f"[DRY-RUN] write marketplace entry to {marketplace_path}")
        print(f"[DRY-RUN] enable {PLUGIN_NAME}@{LOCAL_MARKETPLACE} and disable {PLUGIN_NAME}@{CURATED_MARKETPLACE} in {config_path}")
        print(f"[DRY-RUN] sync cache to {cache_root}")
        return

    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text(json.dumps(marketplace, indent=2) + "\n")
    config_path.write_text(config_text)

    cache_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(cache_root, ignore_errors=True)
    shutil.copytree(
        payload_root,
        cache_root,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    print("[OK] Codex install complete. Payload copied locally and no longer depends on repo path.")


def install_claude(repo_root: Path, scope: str, dry_run: bool) -> None:
    plugin_root = repo_root / "claude"
    manifest_path = plugin_root / ".claude-plugin" / "plugin.json"
    if not manifest_path.exists():
        if dry_run:
            print(f"[DRY-RUN] assume Claude plugin manifest at {manifest_path}")
        else:
            raise SystemExit(f"missing Claude plugin manifest: {manifest_path}")
    if shutil.which("claude") is None:
        raise SystemExit("claude CLI not found in PATH")

    print(f"[INFO] Claude install source: {plugin_root}")

    run(["claude", "plugin", "validate", str(plugin_root)], cwd=repo_root, dry_run=dry_run)
    run(
        ["claude", "plugin", "marketplace", "remove", CLAUDE_MARKETPLACE],
        cwd=repo_root,
        dry_run=dry_run,
        allow_failure=True,
    )
    run(
        ["claude", "plugin", "marketplace", "add", str(plugin_root)],
        cwd=repo_root,
        dry_run=dry_run,
    )
    run(
        ["claude", "plugin", "uninstall", "--scope", scope, PLUGIN_NAME],
        cwd=repo_root,
        dry_run=dry_run,
        allow_failure=True,
    )
    run(
        ["claude", "plugin", "install", "--scope", scope, f"{PLUGIN_NAME}@{CLAUDE_MARKETPLACE}"],
        cwd=repo_root,
        dry_run=dry_run,
    )
    run(
        ["claude", "plugin", "enable", "--scope", scope, PLUGIN_NAME],
        cwd=repo_root,
        dry_run=dry_run,
    )

    print("[OK] Claude install complete. Plugin cached under Claude's local plugin store.")


def detect_targets(args: argparse.Namespace) -> list[str]:
    explicit = []
    if args.all:
        explicit = ["codex", "claude"]
    else:
        if args.codex:
            explicit.append("codex")
        if args.claude:
            explicit.append("claude")
    if explicit:
        return explicit

    detected = []
    if (Path.home() / ".codex" / "config.toml").exists():
        detected.append("codex")
    if shutil.which("claude") is not None:
        detected.append("claude")
    if not detected:
        raise SystemExit("no install target auto-detected. pass --codex, --claude, or --all")
    return detected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", action="store_true", help="install only for Codex")
    parser.add_argument("--claude", action="store_true", help="install only for Claude Code")
    parser.add_argument("--all", action="store_true", help="install for both Codex and Claude Code")
    parser.add_argument(
        "--scope",
        choices=("user", "project", "local"),
        default="user",
        help="Claude plugin scope (default: user)",
    )
    parser.add_argument("--dry-run", action="store_true", help="print planned actions without writing")
    parser.add_argument("--from-github", action="store_true", help="download repo snapshot instead of using local checkout")
    parser.add_argument("--repo", default=REPO_SLUG, help="GitHub repo for remote staging")
    parser.add_argument("--ref", default=REPO_REF, help="Git ref/branch for remote staging")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    targets = detect_targets(args)

    repo_root = None if args.from_github else discover_repo_root()
    if repo_root is None:
        repo_root = stage_repo_from_github(args.repo, args.ref, args.dry_run)
    else:
        print(f"[INFO] using local repo: {repo_root}")

    if "codex" in targets:
        install_codex(repo_root, args.dry_run)
    if "claude" in targets:
        install_claude(repo_root, args.scope, args.dry_run)

    if args.dry_run:
        print("[DONE] dry-run finished")
    else:
        print("[DONE] LeanContext install finished.")
        print("[NEXT] Restart Codex/Claude Code if the plugin UI does not refresh automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
