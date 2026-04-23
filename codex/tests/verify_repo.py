#!/usr/bin/env python3
"""Lightweight verification runner for the LeanContext Codex export."""

from __future__ import annotations

import ast
import filecmp
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def require(path: str) -> None:
    target = ROOT / path
    if not target.exists():
        raise SystemExit(f"missing required file: {target}")


def run(cmd: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(cmd, cwd=cwd or ROOT, text=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def parse_python(path: Path) -> None:
    ast.parse(path.read_text(), filename=str(path))


def main() -> int:
    for path in [
        "install.py",
        "uninstall.py",
        "codex/.codex-plugin/plugin.json",
        "codex/scripts/install_codex_local.py",
        "codex/scripts/doctor_codex_local.py",
        "plugins/leancontext/.codex-plugin/plugin.json",
        "plugins/leancontext/scripts/install_codex_local.py",
        "plugins/leancontext/scripts/doctor_codex_local.py",
    ]:
        require(path)

    parse_python(ROOT / "install.py")
    parse_python(ROOT / "uninstall.py")
    json.loads((ROOT / "codex/.codex-plugin/plugin.json").read_text())
    json.loads((ROOT / "plugins/leancontext/.codex-plugin/plugin.json").read_text())

    parse_python(ROOT / "codex" / "scripts" / "install_codex_local.py")
    parse_python(ROOT / "codex" / "scripts" / "doctor_codex_local.py")
    parse_python(ROOT / "plugins" / "leancontext" / "scripts" / "install_codex_local.py")
    parse_python(ROOT / "plugins" / "leancontext" / "scripts" / "doctor_codex_local.py")

    expected_skills = [
        "compress",
        "leancontext",
        "leancontext-commit",
        "leancontext-help",
        "leancontext-review",
        "quality-gate",
    ]
    codex_skills = ROOT / "codex" / "skills"
    plugin_skills = ROOT / "plugins" / "leancontext" / "skills"

    actual_codex = sorted(p.name for p in codex_skills.iterdir() if p.is_dir())
    actual_plugin = sorted(p.name for p in plugin_skills.iterdir() if p.is_dir())
    if actual_codex != expected_skills:
        raise SystemExit(f"unexpected codex skills: {actual_codex}")
    if actual_plugin != expected_skills:
        raise SystemExit(f"unexpected plugin skills: {actual_plugin}")

    for skill in expected_skills:
        left = codex_skills / skill / "SKILL.md"
        right = plugin_skills / skill / "SKILL.md"
        require(str(left.relative_to(ROOT)))
        require(str(right.relative_to(ROOT)))
        if not filecmp.cmp(left, right, shallow=False):
            raise SystemExit(f"skill mismatch: {left} != {right}")

    run(
        ["python3", "-m", "scripts", "--gate", "--source", "golden"],
        cwd=ROOT / "codex" / "skills" / "compress",
    )

    print("LeanContext Codex export OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
