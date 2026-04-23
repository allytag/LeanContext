#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
from typing import Iterable

# Support both direct execution and module import
try:
    from .validate import validate
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from validate import validate

try:
    import tiktoken
    _enc = tiktoken.get_encoding("o200k_base")
except ImportError:
    _enc = None


def count_tokens(text: str) -> int:
    if _enc is None:
        return len(text.split())  # fallback: word count
    return len(_enc.encode(text))


def benchmark_pair(orig_path: Path, comp_path: Path):
    orig_text = orig_path.read_text()
    comp_text = comp_path.read_text()

    orig_tokens = count_tokens(orig_text)
    comp_tokens = count_tokens(comp_text)
    saved = 100 * (orig_tokens - comp_tokens) / orig_tokens if orig_tokens > 0 else 0.0
    result = validate(orig_path, comp_path)

    return (comp_path.name, orig_tokens, comp_tokens, saved, result.is_valid)


def _find_tests_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        for candidate in (
            parent / "tests" / "shared" / "leancontext-compress",
            parent / "tests" / "leancontext-compress",
        ):
            if candidate.exists():
                return candidate
    raise FileNotFoundError("Tests dir not found: tests/shared/leancontext-compress")


def find_fixture_rows() -> list[tuple]:
    tests_dir = _find_tests_dir()

    rows = []
    for orig in sorted(tests_dir.glob("*.original.md")):
        comp = orig.with_name(orig.stem.removesuffix(".original") + ".md")
        if comp.exists():
            rows.append(benchmark_pair(orig, comp))
    return rows


def print_table(rows: Iterable[tuple]) -> None:
    print("\n| File | Original | Compressed | Saved % | Valid |")
    print("|------|----------|------------|---------|-------|")
    for r in rows:
        print(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]:.1f}% | {'✅' if r[4] else '❌'} |")


def run_benchmark(original: Path | None = None, compressed: Path | None = None) -> list[tuple]:
    if original is not None or compressed is not None:
        if original is None or compressed is None:
            raise ValueError("Both original and compressed paths are required")
        if not original.exists():
            raise FileNotFoundError(f"Not found: {original}")
        if not compressed.exists():
            raise FileNotFoundError(f"Not found: {compressed}")
        return [benchmark_pair(original.resolve(), compressed.resolve())]
    return find_fixture_rows()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if len(args) == 2:
        rows = run_benchmark(Path(args[0]), Path(args[1]))
    elif len(args) == 0:
        rows = run_benchmark()
    else:
        print("Usage: python3 -m scripts.benchmark [<original.md> <compressed.md>]")
        return 1

    if not rows:
        print("No compressed file pairs found.")
        return 1

    print_table(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
