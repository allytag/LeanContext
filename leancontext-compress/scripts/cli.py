#!/usr/bin/env python3
"""
LeanContext Compress CLI

Usage:
    leancontext <filepath>
    leancontext --benchmark [--original <path> --compressed <path>]
    leancontext --gate [--source golden|live] [--report-json <path>]
"""

import argparse
import sys
from pathlib import Path

from . import benchmark as benchmark_mod
from .compress import compress_file
from .detect import detect_file_type, should_compress
from .quality_gate import run_quality_gate


def print_usage():
    print("Usage:")
    print("  leancontext <filepath>")
    print("  leancontext --benchmark [--original <path> --compressed <path>]")
    print("  leancontext --gate [--source golden|live] [--report-json <path>]")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("filepath", nargs="?")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--original")
    parser.add_argument("--compressed")
    parser.add_argument("--gate", action="store_true")
    parser.add_argument("--source", choices=["golden", "live"], default="golden")
    parser.add_argument("--report-json")
    parser.add_argument("--config")
    parser.add_argument("--fixtures-dir")
    parser.add_argument("--golden-dir")
    parser.add_argument("--help", action="store_true")
    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args(sys.argv[1:])

    if args.help:
        print_usage()
        sys.exit(0)

    if args.gate:
        config_path = (
            Path(args.config).resolve()
            if args.config
            else Path(__file__).resolve().parent.parent / "evals" / "gate_config.json"
        )
        fixtures_dir = Path(args.fixtures_dir).resolve() if args.fixtures_dir else None
        golden_dir = Path(args.golden_dir).resolve() if args.golden_dir else None
        report_json = Path(args.report_json).resolve() if args.report_json else None

        code, report = run_quality_gate(
            source=args.source,
            config_path=config_path,
            fixtures_dir=fixtures_dir,
            golden_dir=golden_dir,
            report_json=report_json,
        )
        summary = report["summary"]
        print(
            f"[QUALITY GATE] {report['status']} "
            f"({summary['passed']}/{summary['total']} fixtures, "
            f"avg savings {summary['avg_savings_pct']}%, "
            f"min savings {summary['min_savings_pct']}%)"
        )
        if report_json:
            print(f"[QUALITY GATE] JSON report: {report_json}")
        sys.exit(code)

    if args.benchmark:
        try:
            orig = Path(args.original).resolve() if args.original else None
            comp = Path(args.compressed).resolve() if args.compressed else None
            rows = benchmark_mod.run_benchmark(orig, comp)
        except Exception as e:
            print(f"❌ Benchmark error: {e}")
            sys.exit(1)

        benchmark_mod.print_table(rows)
        all_valid = all(r[4] for r in rows)
        sys.exit(0 if all_valid else 2)

    if not args.filepath:
        print_usage()
        sys.exit(1)

    filepath = Path(args.filepath)

    # Check file exists
    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        sys.exit(1)

    if not filepath.is_file():
        print(f"❌ Not a file: {filepath}")
        sys.exit(1)

    filepath = filepath.resolve()

    # Detect file type
    file_type = detect_file_type(filepath)

    print(f"Detected: {file_type}")

    # Check if compressible
    if not should_compress(filepath):
        print("Skipping: file is not natural language (code/config)")
        sys.exit(0)

    print("Starting LeanContext compression...\n")

    try:
        success = compress_file(filepath)

        if success:
            print("\nCompression completed successfully")
            backup_path = filepath.with_name(filepath.stem + ".original.md")
            print(f"Compressed: {filepath}")
            print(f"Original:   {backup_path}")
            sys.exit(0)
        else:
            print("\n❌ Compression failed after retries")
            sys.exit(2)

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
