# LeanContext Compress Quality Gate

This gate validates compression outputs with deterministic fixtures and machine-readable reporting.

## What it validates

- Required rule sections exist in LeanContext skills.
- Fixtures load and metadata is present.
- Outputs preserve structural safety checks via existing validator (headings/code blocks/URLs).
- Required technical tokens remain present.
- Token savings meet configured thresholds.
- JSON report is generated with pass/fail summary.

## What it does NOT prove

- It does **not** prove zero semantic loss across all possible prompts.
- It does **not** guarantee model behavior for every external backend/runtime configuration.

## Commands

Run deterministic golden gate:

```bash
cd <repo>/claude/skills/compress
python3 -m scripts --gate --source golden --report-json /tmp/leancontext-gate-report.json
```

Run live backend gate (requires API/CLI auth):

```bash
cd <repo>/claude/skills/compress
python3 -m scripts --gate --source live --report-json /tmp/leancontext-gate-live-report.json
```

Run benchmark table from single entrypoint:

```bash
cd <repo>/claude/skills/compress
python3 -m scripts --benchmark
```

## Fixture layout

- `fixtures/<id>.original.md`: original uncompressed fixture
- `fixtures/<id>.meta.json`: fixture metadata (`required_tokens`, `min_savings_pct`)
- `golden/<id>.md`: deterministic expected compressed output
