#!/usr/bin/env python3
"""Check whether LeanContext is installed through Codex's stable local marketplace."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

PLUGIN_NAME = "leancontext"
HOME = Path.home()
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
COMPRESS_BACKEND_PATH = PLUGIN_ROOT / "skills" / "compress" / "scripts" / "compress.py"
MARKETPLACE_PATH = HOME / ".agents" / "plugins" / "marketplace.json"
HOME_PLUGIN_PATH = HOME / "plugins" / PLUGIN_NAME
CONFIG_PATH = HOME / ".codex" / "config.toml"
PLUGIN_CACHE_ROOT = HOME / ".codex" / "plugins" / "cache" / "local" / PLUGIN_NAME
LOCAL_SECRET_PATH = HOME / ".codex" / "leancontext-openrouter.json"

SECTION_RE = re.compile(r'^\[plugins\."([^"]+)"\]\s*$')
ENABLED_RE = re.compile(r"^\s*enabled\s*=\s*(true|false)\s*$")


def plugin_enabled(plugin_key: str) -> bool | None:
    if not CONFIG_PATH.exists():
        return None

    lines = CONFIG_PATH.read_text().splitlines()
    current = None

    for line in lines:
        section = SECTION_RE.match(line.strip())
        if section:
            current = section.group(1)
            continue
        enabled = ENABLED_RE.match(line)
        if enabled and current == plugin_key:
            return enabled.group(1) == "true"

    return None


def claude_auth_status() -> tuple[bool | None, str | None]:
    try:
        result = subprocess.run(
            ["claude", "auth", "status"],
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return None, "claude CLI not found"

    payload = (result.stdout or "").strip()
    if not payload:
        return None, "claude auth status returned no output"

    try:
        status = json.loads(payload)
    except json.JSONDecodeError:
        return None, f"unparseable claude auth status: {payload}"

    return bool(status.get("loggedIn")), status.get("authMethod")


def backend_readiness() -> tuple[str, str | None]:
    secrets = {}
    if LOCAL_SECRET_PATH.exists():
        try:
            payload = json.loads(LOCAL_SECRET_PATH.read_text())
            if isinstance(payload, dict):
                secrets = {k: v for k, v in payload.items() if isinstance(k, str) and isinstance(v, str)}
        except Exception:
            secrets = {}

    def value(name: str, default: str | None = None) -> str | None:
        return os.environ.get(name) or secrets.get(name, default)

    if value("OPENROUTER_API_KEY"):
        model = value("OPENROUTER_MODEL") or value(
            "LEANCONTEXT_OPENROUTER_MODEL", "openrouter/elephant-alpha"
        )
        return "openrouter", model
    if value("ANTHROPIC_API_KEY"):
        model = value("LEANCONTEXT_MODEL", "claude-sonnet-4-5")
        return "anthropic", model

    logged_in, auth_method = claude_auth_status()
    if logged_in is True:
        return "claude-cli", auth_method
    if logged_in is False:
        return "claude-cli-missing-auth", None
    return "claude-cli-unknown", auth_method


def manifest_version() -> str | None:
    if not MANIFEST_PATH.exists():
        return None
    manifest = json.loads(MANIFEST_PATH.read_text())
    version = manifest.get("version")
    return str(version) if version else None


def main() -> int:
    failures = []
    warnings = []

    source_version = manifest_version()

    if not MANIFEST_PATH.exists():
        failures.append(f"missing manifest: {MANIFEST_PATH}")
    else:
        print(f"[OK] manifest version: {source_version}")

    if not HOME_PLUGIN_PATH.exists():
        failures.append(f"missing home plugin path: {HOME_PLUGIN_PATH}")
    elif HOME_PLUGIN_PATH.resolve() != PLUGIN_ROOT.resolve():
        failures.append(
            f"home plugin path points elsewhere: {HOME_PLUGIN_PATH.resolve()} != {PLUGIN_ROOT.resolve()}"
        )
    else:
        print(f"[OK] home plugin path: {HOME_PLUGIN_PATH}")

    if not MARKETPLACE_PATH.exists():
        failures.append(f"missing marketplace file: {MARKETPLACE_PATH}")
    else:
        payload = json.loads(MARKETPLACE_PATH.read_text())
        entry = next((p for p in payload.get("plugins", []) if p.get("name") == PLUGIN_NAME), None)
        if not entry:
            failures.append(f"missing marketplace entry for {PLUGIN_NAME}")
        elif entry.get("source", {}).get("path") != f"./plugins/{PLUGIN_NAME}":
            failures.append(f"unexpected marketplace path: {entry.get('source', {}).get('path')}")
        else:
            print(f"[OK] marketplace entry: {MARKETPLACE_PATH}")

    local_enabled = plugin_enabled("leancontext@local")
    curated_enabled = plugin_enabled("leancontext@openai-curated")

    if local_enabled is not True:
        failures.append("leancontext@local is not enabled in ~/.codex/config.toml")
    else:
        print("[OK] config enables leancontext@local")

    if curated_enabled is True:
        warnings.append("leancontext@openai-curated is still enabled; local install can be shadowed on app refresh")
    else:
        print("[OK] curated ownership disabled")

    if not source_version:
        failures.append("plugin source version missing")
    else:
        cache_path = PLUGIN_CACHE_ROOT / source_version
        cache_manifest_path = cache_path / ".codex-plugin" / "plugin.json"
        if not cache_manifest_path.exists():
            failures.append(
                f"codex cache missing current plugin version: {cache_path} "
                "(run install_codex_local.py to sync the active cache)"
            )
        else:
            cache_manifest = json.loads(cache_manifest_path.read_text())
            cache_version = str(cache_manifest.get("version"))
            if cache_version != source_version:
                failures.append(
                    f"cache version mismatch: {cache_version} != {source_version}"
                )
            else:
                print(f"[OK] cache synced: {cache_path}")

    if not COMPRESS_BACKEND_PATH.exists():
        failures.append(f"missing /leancontext:compress backend: {COMPRESS_BACKEND_PATH}")
    else:
        backend_text = COMPRESS_BACKEND_PATH.read_text()
        if "def call_claude(" not in backend_text:
            warnings.append("call_claude() missing from compress backend")
        else:
            print("[OK] /leancontext:compress backend present")
            if "def call_openrouter(" not in backend_text:
                warnings.append("call_openrouter() missing from compress backend")
            status, detail = backend_readiness()
            if status == "openrouter":
                print(f"[OK] openrouter backend auth ready ({detail})")
            elif status == "anthropic":
                print(f"[OK] anthropic API backend ready ({detail})")
            elif status == "claude-cli":
                print(f"[OK] claude backend auth ready ({detail})")
            elif status == "claude-cli-missing-auth":
                warnings.append(
                    "no OpenRouter/Anthropic key detected in env or ~/.codex/leancontext-openrouter.json, and claude CLI is not logged in; /leancontext:compress live runs will fail until backend auth is configured"
                )
            elif detail:
                warnings.append(f"claude backend auth status unknown: {detail}")
            target = os.environ.get("LEANCONTEXT_TARGET_SAVINGS_PCT")
            if not target and LOCAL_SECRET_PATH.exists():
                try:
                    payload = json.loads(LOCAL_SECRET_PATH.read_text())
                    if isinstance(payload, dict):
                        raw = payload.get("LEANCONTEXT_TARGET_SAVINGS_PCT")
                        if isinstance(raw, str):
                            target = raw
                except Exception:
                    pass
            print(f"[OK] target savings floor: {target or '50'}%")

    for warning in warnings:
        print(f"[WARN] {warning}")
    for failure in failures:
        print(f"[FAIL] {failure}")

    if failures:
        return 2

    print("[PASS] LeanContext V4 local install looks healthy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
