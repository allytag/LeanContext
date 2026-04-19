---
name: leancontext-help
description: >
  Quick-reference card for all LeanContext modes, skills, and commands.
  One-shot display, not a persistent mode. Trigger: /leancontext-help,
  "leancontext help", "what leancontext commands", "how do I use leancontext".
---

# LeanContext Help

Display this reference card when invoked. One-shot — do NOT change mode, write flag files, or persist anything. Output in LeanContext style.

## Modes

| Mode | Trigger | What change |
|------|---------|-------------|
| **Lite** | `/leancontext lite` | Drop filler. Keep sentence structure. |
| **Full** | `/leancontext` | Drop articles, filler, pleasantries, hedging. Fragments OK. Default. |
| **Ultra** | `/leancontext ultra` | Extreme compression. Bare fragments. Tables over prose. |
| **Wenyan-Lite** | `/leancontext wenyan-lite` | Classical Chinese style, light compression. |
| **Wenyan-Full** | `/leancontext wenyan` | Full 文言文. Maximum classical terseness. |
| **Wenyan-Ultra** | `/leancontext wenyan-ultra` | Extreme. Ancient scholar on a budget. |

Mode stick until changed or session end.

## Skills

| Skill | Trigger | What it do |
|-------|---------|-----------|
| **leancontext-commit** | `/leancontext-commit` | Terse commit messages. Conventional Commits. ≤50 char subject. |
| **leancontext-review** | `/leancontext-review` | One-line PR comments: `L42: bug: user null. Add guard.` |
| **leancontext-compress** | `/leancontext:compress <file>` | Compress .md files to LeanContext prose. Saves ~46% input tokens. |
| **leancontext-help** | `/leancontext-help` | This card. |

## Deactivate

Say "stop leancontext" or "normal mode". Resume anytime with `/leancontext`.

## Configure Default Mode

Default mode = `full`. Change it:

**Environment variable** (highest priority):
```bash
export LEANCONTEXT_DEFAULT_MODE=ultra
```

**Config file** (`~/.config/leancontext/config.json`):
```json
{ "defaultMode": "lite" }
```

Set `"off"` to disable auto-activation on session start. User can still activate manually with `/leancontext`.

Resolution: env var > config file > `full`.

## More

Full docs: https://github.com/YOUR_GITHUB/LeanContext
