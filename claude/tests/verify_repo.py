#!/usr/bin/env python3
"""Lightweight verification runner for the LeanContext Claude export."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: str) -> None:
    target = ROOT / path
    if not target.exists():
        raise SystemExit(f"missing required file: {target}")


def run(cmd: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(cmd, cwd=cwd or ROOT, text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    for path in [
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
        "commands/leancontext.toml",
        "hooks/leancontext-activate.js",
        "hooks/leancontext-config.js",
        "hooks/leancontext-mode-tracker.js",
        "hooks/leancontext-statusline.sh",
        "skills/leancontext/SKILL.md",
        "skills/compress/SKILL.md",
        "skills/quality-gate/SKILL.md",
    ]:
        require(path)

    json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())

    run(["node", "--check", "hooks/leancontext-config.js"])
    run(["node", "--check", "hooks/leancontext-activate.js"])
    run(["node", "--check", "hooks/leancontext-mode-tracker.js"])
    run(["bash", "-n", "hooks/leancontext-statusline.sh"])
    run(
        ["python3", "-m", "scripts", "--gate", "--source", "golden"],
        cwd=ROOT / "skills" / "compress",
    )

    print("LeanContext Claude export OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

