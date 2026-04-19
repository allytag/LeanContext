#!/usr/bin/env python3
"""Install LeanContext into Codex's stable home-local marketplace."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

PLUGIN_NAME = "leancontext"
LOCAL_MARKETPLACE = "local"
CURATED_MARKETPLACE = "openai-curated"

HOME = Path.home()
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HOME_PLUGIN_PATH = HOME / "plugins" / PLUGIN_NAME
MARKETPLACE_PATH = HOME / ".agents" / "plugins" / "marketplace.json"
CONFIG_PATH = HOME / ".codex" / "config.toml"
PLUGIN_CACHE_ROOT = HOME / ".codex" / "plugins" / "cache" / LOCAL_MARKETPLACE / PLUGIN_NAME

SECTION_RE = re.compile(r'^\[plugins\."([^"]+)"\]\s*$')
ENABLED_RE = re.compile(r"^\s*enabled\s*=\s*(true|false)\s*$")


def ensure_home_plugin_path() -> str:
    HOME_PLUGIN_PATH.parent.mkdir(parents=True, exist_ok=True)

    if HOME_PLUGIN_PATH.exists():
        if HOME_PLUGIN_PATH.resolve() != PLUGIN_ROOT.resolve():
            raise RuntimeError(
                f"{HOME_PLUGIN_PATH} already exists and does not point to {PLUGIN_ROOT}"
            )
        return "existing"

    HOME_PLUGIN_PATH.symlink_to(PLUGIN_ROOT)
    return "linked"


def load_marketplace() -> dict:
    if MARKETPLACE_PATH.exists():
        return json.loads(MARKETPLACE_PATH.read_text())
    return {
        "name": LOCAL_MARKETPLACE,
        "interface": {"displayName": "Local Plugins"},
        "plugins": [],
    }


def ensure_marketplace_entry() -> None:
    payload = load_marketplace()
    payload.setdefault("name", LOCAL_MARKETPLACE)
    payload.setdefault("interface", {})
    payload["interface"].setdefault("displayName", "Local Plugins")
    payload.setdefault("plugins", [])

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
    for idx, plugin in enumerate(payload["plugins"]):
        if plugin.get("name") == PLUGIN_NAME:
            payload["plugins"][idx] = entry
            replaced = True
            break

    if not replaced:
        payload["plugins"].append(entry)

    MARKETPLACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKETPLACE_PATH.write_text(json.dumps(payload, indent=2) + "\n")


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


def ensure_codex_config() -> None:
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"Codex config not found: {CONFIG_PATH}")

    text = CONFIG_PATH.read_text()
    text = upsert_plugin_enabled(text, f"{PLUGIN_NAME}@{CURATED_MARKETPLACE}", False)
    text = upsert_plugin_enabled(text, f"{PLUGIN_NAME}@{LOCAL_MARKETPLACE}", True)
    CONFIG_PATH.write_text(text)


def plugin_version() -> str:
    manifest_path = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text())
    version = manifest.get("version")
    if not version:
        raise RuntimeError(f"Missing version in {manifest_path}")
    return str(version)


def ensure_cache_sync() -> tuple[Path, str]:
    version = plugin_version()
    target = PLUGIN_CACHE_ROOT / version
    PLUGIN_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    status = "existing" if target.exists() else "synced"
    shutil.copytree(
        PLUGIN_ROOT,
        target,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    return target, status


def main() -> int:
    location_status = ensure_home_plugin_path()
    ensure_marketplace_entry()
    ensure_codex_config()
    cache_path, cache_status = ensure_cache_sync()

    print(f"[OK] plugin path: {HOME_PLUGIN_PATH} ({location_status})")
    print(f"[OK] marketplace: {MARKETPLACE_PATH}")
    print(f"[OK] config: {CONFIG_PATH}")
    print(f"[OK] cache: {cache_path} ({cache_status})")
    print("[NEXT] Restart Codex if LeanContext is not already visible in the Plugins UI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
