# LeanContext V4 For Codex

LeanContext V4 keeps the live Codex behavior you already use, keeps `/leancontext:compress`, and hardens the plugin against Codex desktop app updates that refresh bundled marketplaces.

## Source Of Truth

- Plugin source: `<repo>/codex`
- Stable home-local marketplace: `~/.agents/plugins/marketplace.json`
- Stable local plugin path resolved by Codex: `~/plugins/leancontext`

Do not treat `~/.codex/.tmp/*` or bundled marketplaces as the source of truth. Those paths are app-managed and can change during in-app updates.

## What V4 Changes

- Moves LeanContext ownership to a stable home-local marketplace entry.
- Enables `leancontext@local` in Codex config and disables the fragile `leancontext@openai-curated` toggle.
- Keeps live `/leancontext` purpose the same: cut filler, preserve technical substance.
- Adds thin-core anti-replay guardrails to main `/leancontext` chat behavior so follow-ups answer delta-first and work updates stay ultra-short without V4.5 prompt bloat.
- Adds optional OpenRouter backend support for `/leancontext:compress` and live quality-gate runs.
- Adds a savings-floor shrink pass for `/leancontext:compress` so weak first-pass outputs get tightened without changing main LeanContext chat behavior.
- Retries transient OpenRouter resets/timeouts so live compression is more stable on the budget default backend.
- Continues OpenRouter compression automatically when a response hits the provider output cap, instead of silently returning a truncated result.
- Adds local install + doctor tooling for fast repair after app updates.
- Tightens the compression validator for inline code, numbered lists, and markdown table shape.

## Install / Repair

Run from the plugin root:

```bash
python3 scripts/install_codex_local.py
python3 scripts/doctor_codex_local.py
```

`install_codex_local.py` ensures:

- `~/.agents/plugins/marketplace.json` contains `leancontext`
- `~/.codex/config.toml` enables `leancontext@local`
- `~/.codex/config.toml` disables `leancontext@openai-curated`
- `~/.codex/plugins/cache/local/leancontext/<version>` is synced from the source plugin

`doctor_codex_local.py` verifies:

- plugin manifest exists and is readable
- local marketplace entry exists and points at `./plugins/leancontext`
- Codex config enables the local plugin
- curated toggle is disabled so app refreshes do not reclaim ownership
- Codex cache contains the current source version
- `/leancontext:compress` backend path still exists
- live backend auth readiness for OpenRouter, Anthropic API, or Claude CLI

## Live Backend Auth

`/leancontext:compress` and `--gate --source live` use this backend priority:

- `OPENROUTER_API_KEY` -> OpenRouter
- `ANTHROPIC_API_KEY` -> Anthropic API
- otherwise -> `claude --print`

Optional overrides:

```bash
export LEANCONTEXT_BACKEND=openrouter
export OPENROUTER_MODEL=openrouter/elephant-alpha
export LEANCONTEXT_OPENROUTER_MAX_TOKENS=8192
export LEANCONTEXT_TARGET_SAVINGS_PCT=50
```

Codex-local secret file also works:

```json
{
  "LEANCONTEXT_BACKEND": "openrouter",
  "OPENROUTER_API_KEY": "...",
  "OPENROUTER_MODEL": "openrouter/elephant-alpha",
  "LEANCONTEXT_OPENROUTER_MAX_TOKENS": "8192",
  "LEANCONTEXT_TARGET_SAVINGS_PCT": "50"
}
```

Save as `~/.codex/leancontext-openrouter.json` for desktop launches that do not inherit shell env.

## Quality Gate

Compression benchmark and gate still live under:

```bash
cd <repo>/codex/skills/compress
python3 -m scripts --gate --source golden --report-json leancontext-gate-report.json
python3 -m scripts --benchmark
```
