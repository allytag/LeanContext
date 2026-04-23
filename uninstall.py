#!/usr/bin/env python3
"""One-command LeanContext uninstaller for Codex and Claude Code."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from shlex import quote

PLUGIN_NAME = "leancontext"
CLAUDE_MARKETPLACE = "leancontext"
LOCAL_MARKETPLACE = "local"
CURATED_MARKETPLACE = "openai-curated"

SECTION_RE = re.compile(r'^\[plugins\."([^"]+)"\]\s*$')
ENABLED_RE = re.compile(r"^\s*enabled\s*=\s*(true|false)\s*$")


def shell_join(cmd: list[str]) -> str:
    return " ".join(quote(part) for part in cmd)


def run(cmd: list[str], *, dry_run: bool, allow_failure: bool = False) -> int:
    prefix = "[DRY-RUN]" if dry_run else "[RUN]"
    print(f"{prefix} {shell_join(cmd)}")
    if dry_run:
        return 0
    result = subprocess.run(cmd, text=True, check=False)
    if result.returncode != 0 and not allow_failure:
        raise SystemExit(result.returncode)
    return result.returncode


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


def payload_manifest(path: Path) -> dict | None:
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

    manifest = payload_manifest(target)
    return bool(manifest and manifest.get("name") == PLUGIN_NAME)


def uninstall_codex(dry_run: bool, restore_curated: bool) -> None:
    home = Path.home()
    home_plugin_path = home / "plugins" / PLUGIN_NAME
    marketplace_path = home / ".agents" / "plugins" / "marketplace.json"
    config_path = home / ".codex" / "config.toml"
    cache_root = home / ".codex" / "plugins" / "cache" / LOCAL_MARKETPLACE / PLUGIN_NAME

    print(f"[INFO] Codex local payload: {home_plugin_path}")

    if home_plugin_path.is_symlink():
        if not is_managed_plugin_path(home_plugin_path):
            raise SystemExit(f"refusing to remove unmanaged path: {home_plugin_path}")
        if dry_run:
            print(f"[DRY-RUN] unlink {home_plugin_path}")
        else:
            home_plugin_path.unlink()
    elif home_plugin_path.exists():
        if is_managed_plugin_path(home_plugin_path):
            if dry_run:
                print(f"[DRY-RUN] remove directory {home_plugin_path}")
            else:
                shutil.rmtree(home_plugin_path)
        else:
            raise SystemExit(f"refusing to remove unmanaged path: {home_plugin_path}")

    if marketplace_path.exists():
        payload = json.loads(marketplace_path.read_text())
        plugins = payload.get("plugins", [])
        payload["plugins"] = [plugin for plugin in plugins if plugin.get("name") != PLUGIN_NAME]
        if dry_run:
            print(f"[DRY-RUN] update {marketplace_path} to remove {PLUGIN_NAME}")
        else:
            marketplace_path.write_text(json.dumps(payload, indent=2) + "\n")

    if config_path.exists():
        config_text = config_path.read_text()
        config_text = upsert_plugin_enabled(config_text, f"{PLUGIN_NAME}@{LOCAL_MARKETPLACE}", False)
        if restore_curated:
            config_text = upsert_plugin_enabled(config_text, f"{PLUGIN_NAME}@{CURATED_MARKETPLACE}", True)
        if dry_run:
            print(f"[DRY-RUN] update {config_path}")
        else:
            config_path.write_text(config_text)

    if cache_root.exists():
        if dry_run:
            print(f"[DRY-RUN] remove cache directory {cache_root}")
        else:
            shutil.rmtree(cache_root)

    print("[OK] Codex uninstall complete.")


def uninstall_claude(scope: str, dry_run: bool, keep_data: bool) -> None:
    if shutil.which("claude") is None:
        raise SystemExit("claude CLI not found in PATH")

    uninstall_cmd = ["claude", "plugin", "uninstall", "--scope", scope]
    if keep_data:
        uninstall_cmd.append("--keep-data")
    uninstall_cmd.append(PLUGIN_NAME)

    run(["claude", "plugin", "disable", "--scope", scope, PLUGIN_NAME], dry_run=dry_run, allow_failure=True)
    run(uninstall_cmd, dry_run=dry_run, allow_failure=True)
    run(
        ["claude", "plugin", "marketplace", "remove", CLAUDE_MARKETPLACE],
        dry_run=dry_run,
        allow_failure=True,
    )

    print("[OK] Claude uninstall complete.")


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
        raise SystemExit("no uninstall target auto-detected. pass --codex, --claude, or --all")
    return detected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", action="store_true", help="uninstall only from Codex")
    parser.add_argument("--claude", action="store_true", help="uninstall only from Claude Code")
    parser.add_argument("--all", action="store_true", help="uninstall from both Codex and Claude Code")
    parser.add_argument(
        "--scope",
        choices=("user", "project", "local"),
        default="user",
        help="Claude plugin scope (default: user)",
    )
    parser.add_argument("--keep-data", action="store_true", help="preserve Claude plugin data directory")
    parser.add_argument("--restore-curated", action="store_true", help="re-enable Codex curated plugin toggle")
    parser.add_argument("--dry-run", action="store_true", help="print planned actions without writing")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    targets = detect_targets(args)

    if "codex" in targets:
        uninstall_codex(args.dry_run, args.restore_curated)
    if "claude" in targets:
        uninstall_claude(args.scope, args.dry_run, args.keep_data)

    if args.dry_run:
        print("[DONE] dry-run finished")
    else:
        print("[DONE] LeanContext uninstall finished.")
        print("[NEXT] Restart Codex/Claude Code if the plugin UI does not refresh automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
