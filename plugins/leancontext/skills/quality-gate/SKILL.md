---
name: quality-gate
description: >
  Run deterministic compression quality gate for LeanContext with machine-readable output.
  Verifies required rules/sections, fixture integrity, token savings thresholds, and
  structural safety checks. Use before release claims on sensitive workflows.
---

# LeanContext Quality Gate

## Purpose

Provide release-confidence checks for compression behavior without claiming impossible guarantees.

## Trigger

Use when preparing release, validating regressions, or checking whether custom fork drifted.

## Run

```bash
cd <repo>/codex/skills/compress
python3 -m scripts --gate --source golden --report-json leancontext-gate-report.json
```

Optional live backend run (auth required):

```bash
cd <repo>/codex/skills/compress
python3 -m scripts --gate --source live --report-json leancontext-gate-live-report.json
```

Live backend priority matches `/leancontext:compress`:
- `OPENROUTER_API_KEY` -> OpenRouter
- `ANTHROPIC_API_KEY` -> Anthropic API
- otherwise -> Claude CLI auth

## Required output checks

- Gate exits zero only on PASS.
- JSON report exists and includes summary + per-fixture details.
- Required sections include `EXTENDED COMPRESSION (v0.3.0)`.
- Missing required tokens or savings threshold failures produce FAIL.

## Boundaries

- Gate validates structural safety and measurable compression characteristics.
- Gate does not prove universal semantic equivalence.
- For your workflows, add/maintain your own sensitive fixtures.
