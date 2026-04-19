# LeanContext

**Token-efficient AI coding chat without making the model dumb.**

LeanContext is an advanced plugin for Codex and Claude Code that cuts filler, stops replay loops, compresses memory files, and keeps technical accuracy protected. It is built for long coding sessions where every token matters, but answer quality cannot drop.

## Why Developers Care

AI coding assistants waste budget on repeated context, polite padding, long recaps, and over-explaining obvious steps. Basic "be brief" prompts help a little, but they are fragile: the model drifts, repeats itself, or compresses the wrong thing.

LeanContext fixes that with a real system:

- **Thin live prompt** keeps chat concise without bloating every turn.
- **Delta-first follow-ups** answer only what changed instead of replaying prior state.
- **Protected technical tokens** preserve code, file paths, exact errors, API names, numbers, units, and versions.
- **Memory compression** shrinks `CLAUDE.md`, project notes, todos, and preference files with `/leancontext:compress`.
- **Quality gate** checks deterministic fixtures before release claims.
- **OpenRouter support** lets compression use budget-friendly models while Codex/Claude keep full power for coding.
- **Update-safe installs** keep local plugin ownership stable across app refreshes.

## Better Than Basic Terse Plugins

| Feature | Basic terse prompt | LeanContext |
|---|---:|---:|
| Shorter chat output | Yes | Yes |
| Anti-replay follow-up guardrails | No | Yes |
| Memory-file compression | No | Yes |
| Code/error/path preservation rules | Weak | Strong |
| Deterministic quality gate | No | Yes |
| OpenRouter compression backend | No | Yes |
| Truncation-safe continuation | No | Yes |
| Codex update-safe local installer | No | Yes |
| Claude Code hooks + statusline | Maybe | Yes |

LeanContext is not just "speak shorter." It is a token-control layer for serious coding workflows.

## Current Proof

Golden compression gate:

- `PASS 5/5`
- Average savings: `53.26%`
- Minimum fixture savings: `50.0%`

Claude live eval against older baseline:

- Current output tokens: `3291`
- Older baseline output tokens: `3482`
- Current saved `191` output tokens, about `5.49%`
- Current won output-token count on `6/10` prompts
- No quality regression observed in the 10-prompt sample

Important: LeanContext is designed to reduce average waste, especially long answers and replay-heavy follow-ups. It does not force every answer to be shorter when extra detail improves correctness.

## Repo Layout

```text
.
├── codex/   # Codex Desktop plugin build, v0.4.7-custom.0
├── claude/  # Claude Code plugin build, v0.4.7-custom.0
├── README.md
├── LICENSE
└── .gitignore
```

This export contains no local cache, no `.git` history, no API keys, and no old compatibility alias. Primary slug is `leancontext`; commands use `/leancontext`.

## Install For Codex

From repo root:

```bash
cd codex
python3 scripts/install_codex_local.py
```

Restart Codex Desktop if the plugin does not appear immediately.

Installer behavior:

- Symlinks plugin to `~/plugins/leancontext`.
- Adds/updates local marketplace entry in `~/.agents/plugins/marketplace.json`.
- Enables `leancontext@local`.
- Syncs cache under `~/.codex/plugins/cache/local/leancontext/<version>`.

Health check:

```bash
python3 scripts/doctor_codex_local.py
```

## Install For Claude Code

From repo root:

```bash
claude plugin validate ./claude
claude plugin marketplace add ./claude
claude plugin install leancontext@leancontext
claude plugin enable leancontext@leancontext
```

Restart Claude Code after install or update.

## Commands

- `/leancontext` — enable default full mode.
- `/leancontext lite` — concise professional mode.
- `/leancontext full` — terse technical fragments.
- `/leancontext ultra` — maximum compression.
- `/leancontext wenyan-lite|wenyan|wenyan-ultra` — classical Chinese compression variants.
- `/leancontext-commit` — terse Conventional Commit message.
- `/leancontext-review` — one-line code review findings.
- `/leancontext:compress <file>` — compress markdown/text memory file.

## OpenRouter Setup

OpenRouter is optional. It is used by `/leancontext:compress` when configured.

Never commit real API keys.

```bash
export OPENROUTER_API_KEY="sk-or-v1-REPLACE_ME"
export LEANCONTEXT_OPENROUTER_MODEL="openrouter/elephant-alpha"
```

Codex desktop secret file:

```bash
mkdir -p ~/.codex
chmod 700 ~/.codex
$EDITOR ~/.codex/leancontext-openrouter.json
```

Claude Code secret file:

```bash
mkdir -p ~/.claude
chmod 700 ~/.claude
$EDITOR ~/.claude/leancontext-openrouter.json
```

Example JSON:

```json
{
  "OPENROUTER_API_KEY": "sk-or-v1-REPLACE_ME",
  "LEANCONTEXT_OPENROUTER_MODEL": "openrouter/elephant-alpha",
  "LEANCONTEXT_TARGET_SAVINGS_PCT": "50"
}
```

## Quality Gate

Codex:

```bash
cd codex/skills/compress
python3 -m scripts --gate --source golden --report-json /tmp/leancontext-codex-gate.json
```

Claude:

```bash
cd claude/skills/compress
python3 -m scripts --gate --source golden --report-json /tmp/leancontext-claude-gate.json
```

The gate validates structure, required tokens, protected sections, and token savings thresholds. It does not claim impossible universal proof for every future prompt or domain.

## Safety Model

LeanContext does not compress protected technical material:

- Code blocks
- Backticked text
- File paths
- Commands
- Commit messages
- Exact error messages
- API names
- Technical identifiers
- Direct documentation quotes
- Numbers, units, and version strings

This is why it can save tokens without intentionally lowering coding quality.

## Publish Checklist

- Replace `YOUR_GITHUB/LeanContext` placeholders in manifests/docs.
- Keep `LICENSE`.
- Do not commit `.env`, local secret JSON files, or real API keys.
- Run Claude plugin validation.
- Run Codex quality gate.
- Run Claude quality gate.
- Confirm plugin appears in both apps after fresh restart.

Recommended first commit:

```bash
git init
git add .
git commit -m "Initial LeanContext release"
```

## Positioning

LeanContext is for developers who want longer sessions, lower token waste, and cleaner outputs without sacrificing the full coding power of Codex or Claude.

