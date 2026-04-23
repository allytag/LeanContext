#!/usr/bin/env python3
"""Deterministic quality gate for LeanContext compression fixtures."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from statistics import mean
from typing import Any

try:
    from .benchmark import count_tokens
    from .compress import compress_text_with_retries, get_backend_label
    from .validate import validate
except ImportError:
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    from benchmark import count_tokens
    from compress import compress_text_with_retries, get_backend_label
    from validate import validate


DEFAULT_LIMITATIONS = [
    "Gate checks structural fidelity (headings/code blocks/URLs) and required-token presence.",
    "Gate checks token savings thresholds and deterministic golden outputs.",
    "Gate does not prove zero semantic loss for all possible prompts or domains.",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _round2(value: float) -> float:
    return round(value, 2)


def _resolve_child(base: Path, candidate: str | None, default_name: str) -> Path:
    if candidate:
        path = Path(candidate)
        return path if path.is_absolute() else (base / path)
    return base / default_name


def _check_required_sections(skills_root: Path, required_sections: list[str]) -> dict[str, Any]:
    leancontext_skill = skills_root / "leancontext" / "SKILL.md"
    compress_skill = skills_root / "compress" / "SKILL.md"

    checks = []
    overall = True

    leancontext_text = leancontext_skill.read_text() if leancontext_skill.exists() else ""
    compress_text = compress_skill.read_text() if compress_skill.exists() else ""

    for section in required_sections:
        found = section in leancontext_text or section in compress_text
        checks.append({"section": section, "found": found})
        overall = overall and found

    return {
        "ok": overall,
        "files": {
            "leancontext": str(leancontext_skill),
            "compress": str(compress_skill),
        },
        "checks": checks,
    }


def _find_skills_root() -> Path:
    here = Path(__file__).resolve()
    candidates = [here.parents[2], here.parents[3], here.parents[4]]
    for cand in candidates:
        direct = cand
        nested = cand / "skills"
        if (direct / "leancontext" / "SKILL.md").exists() and (direct / "compress" / "SKILL.md").exists():
            return direct
        if (nested / "leancontext" / "SKILL.md").exists() and (nested / "compress" / "SKILL.md").exists():
            return nested
    # Fallback to current layout assumption (skills/compress/scripts)
    return here.parents[2]


def _validate_pair(original_text: str, compressed_text: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="leancontext-gate-") as td:
        tmp = Path(td)
        orig_path = tmp / "fixture.original.md"
        comp_path = tmp / "fixture.md"
        orig_path.write_text(original_text)
        comp_path.write_text(compressed_text)
        result = validate(orig_path, comp_path)
    return {
        "is_valid": result.is_valid,
        "errors": result.errors,
        "warnings": result.warnings,
    }


def run_quality_gate(
    *,
    source: str,
    config_path: Path,
    fixtures_dir: Path | None = None,
    golden_dir: Path | None = None,
    report_json: Path | None = None,
) -> tuple[int, dict[str, Any]]:
    config = _load_json(config_path)
    evals_root = config_path.parent
    fixtures_root = _resolve_child(evals_root, str(fixtures_dir) if fixtures_dir else None, "fixtures")
    golden_root = _resolve_child(evals_root, str(golden_dir) if golden_dir else None, "golden")

    required_sections = list(config.get("required_sections", []))
    default_min_savings = float(config.get("default_min_savings_pct", 25.0))

    skills_root = _find_skills_root()
    section_check = _check_required_sections(skills_root, required_sections)

    fixture_reports: list[dict[str, Any]] = []
    savings_values: list[float] = []
    pass_count = 0

    originals = sorted(fixtures_root.glob("*.original.md"))
    for original_path in originals:
        fixture_id = original_path.name.replace(".original.md", "")
        meta_path = fixtures_root / f"{fixture_id}.meta.json"
        golden_path = golden_root / f"{fixture_id}.md"

        fixture_report: dict[str, Any] = {
            "id": fixture_id,
            "original": str(original_path),
            "meta": str(meta_path),
            "source": source,
            "status": "FAIL",
        }

        if not meta_path.exists():
            fixture_report["errors"] = [f"Missing fixture metadata: {meta_path}"]
            fixture_reports.append(fixture_report)
            continue

        meta = _load_json(meta_path)
        required_tokens = list(meta.get("required_tokens", []))
        min_savings_pct = float(meta.get("min_savings_pct", default_min_savings))
        fixture_report["min_savings_pct"] = min_savings_pct

        original_text = original_path.read_text()
        compressed_text = ""
        generation_error: str | None = None

        if source == "golden":
            if not golden_path.exists():
                fixture_report["errors"] = [f"Missing golden output: {golden_path}"]
                fixture_reports.append(fixture_report)
                continue
            compressed_text = golden_path.read_text()
            fixture_report["compressed"] = str(golden_path)
        else:
            try:
                compressed_text = compress_text_with_retries(original_text)
            except Exception as exc:  # pragma: no cover - network/auth dependent
                generation_error = str(exc)
                compressed_text = ""
            fixture_report["compressed"] = f"live-generated:{get_backend_label()}"

        if generation_error:
            fixture_report["errors"] = [f"Live generation failed: {generation_error}"]
            fixture_reports.append(fixture_report)
            continue

        validation = _validate_pair(original_text, compressed_text)
        orig_tokens = count_tokens(original_text)
        comp_tokens = count_tokens(compressed_text)
        savings_pct = (
            100.0 * (orig_tokens - comp_tokens) / orig_tokens if orig_tokens > 0 else 0.0
        )
        savings_values.append(savings_pct)

        missing_required = [token for token in required_tokens if token not in compressed_text]
        fixture_ok = (
            validation["is_valid"]
            and not missing_required
            and savings_pct >= min_savings_pct
        )

        fixture_report.update(
            {
                "orig_tokens": orig_tokens,
                "compressed_tokens": comp_tokens,
                "savings_pct": _round2(savings_pct),
                "validation": validation,
                "missing_required_tokens": missing_required,
                "status": "PASS" if fixture_ok else "FAIL",
            }
        )
        if fixture_ok:
            pass_count += 1
        fixture_reports.append(fixture_report)

    total = len(fixture_reports)
    fail_count = total - pass_count
    overall_ok = (
        section_check["ok"]
        and total > 0
        and fail_count == 0
    )

    summary = {
        "total": total,
        "passed": pass_count,
        "failed": fail_count,
        "avg_savings_pct": _round2(mean(savings_values)) if savings_values else 0.0,
        "min_savings_pct": _round2(min(savings_values)) if savings_values else 0.0,
    }

    report = {
        "status": "PASS" if overall_ok else "FAIL",
        "source": source,
        "config_path": str(config_path),
        "fixtures_dir": str(fixtures_root),
        "golden_dir": str(golden_root),
        "checks": {
            "required_sections": section_check,
        },
        "summary": summary,
        "fixtures": fixture_reports,
        "limitations": list(config.get("limitations", DEFAULT_LIMITATIONS)),
    }

    if report_json:
        report_json.parent.mkdir(parents=True, exist_ok=True)
        report_json.write_text(json.dumps(report, indent=2) + "\n")

    return (0 if overall_ok else 2), report


def _print_summary(report: dict[str, Any], report_json: Path | None) -> None:
    summary = report["summary"]
    print(
        f"[QUALITY GATE] {report['status']} "
        f"({summary['passed']}/{summary['total']} fixtures, "
        f"avg savings {summary['avg_savings_pct']}%, "
        f"min savings {summary['min_savings_pct']}%)"
    )
    sections = report["checks"]["required_sections"]
    if not sections["ok"]:
        print("[QUALITY GATE] Missing required section(s):")
        for check in sections["checks"]:
            if not check["found"]:
                print(f"  - {check['section']}")
    for fixture in report["fixtures"]:
        if fixture["status"] == "FAIL":
            print(f"[QUALITY GATE] FAIL {fixture['id']}")
            for err in fixture.get("errors", []):
                print(f"  - {err}")
            for err in fixture.get("validation", {}).get("errors", []):
                print(f"  - {err}")
            missing = fixture.get("missing_required_tokens", [])
            if missing:
                print(f"  - Missing required tokens: {missing}")
    if report_json:
        print(f"[QUALITY GATE] JSON report: {report_json}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run LeanContext compression quality gate")
    parser.add_argument("--source", choices=["golden", "live"], default="golden")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--fixtures-dir", type=Path, default=None)
    parser.add_argument("--golden-dir", type=Path, default=None)
    parser.add_argument("--report-json", type=Path, default=None)
    args = parser.parse_args(argv)

    config_path = args.config or (Path(__file__).resolve().parent.parent / "evals" / "gate_config.json")
    code, report = run_quality_gate(
        source=args.source,
        config_path=config_path,
        fixtures_dir=args.fixtures_dir,
        golden_dir=args.golden_dir,
        report_json=args.report_json,
    )
    _print_summary(report, args.report_json)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
