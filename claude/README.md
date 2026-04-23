# LeanContext For Claude Code

LeanContext is a Claude Code plugin for token-efficient coding chat. It cuts filler, keeps technical identifiers exact, prevents replay loops, and includes compression tooling for memory files.

## Install

From repo root:

```bash
python3 install.py --claude
```

Restart Claude Code after install or update.

Manual equivalent:

```bash
claude plugin validate ./claude
claude plugin marketplace add ./claude
claude plugin install leancontext@leancontext
claude plugin enable leancontext@leancontext
```

## Uninstall

From repo root:

```bash
python3 uninstall.py --claude
```

## Commands

- `/leancontext` — enable default full mode.
- `/leancontext lite` — concise professional mode.
- `/leancontext full` — default terse technical fragments.
- `/leancontext ultra` — maximum compression.
- `/leancontext wenyan-lite|wenyan|wenyan-ultra` — classical Chinese compression variants.
- `/leancontext-commit` — terse Conventional Commit message.
- `/leancontext-review` — one-line code review findings.
- `/leancontext:compress <file>` — compress markdown/text memory file.

## Files

- `.claude-plugin/plugin.json` — Claude Code plugin manifest.
- `.claude-plugin/marketplace.json` — local marketplace manifest.
- `commands/` — slash command definitions.
- `hooks/` — session activation, mode tracking, and statusline helpers.
- `skills/leancontext/SKILL.md` — live chat behavior.
- `skills/compress/` — compression backend, fixtures, validator, quality gate.
- `skills/quality-gate/SKILL.md` — deterministic release check instructions.

## OpenRouter

Optional OpenRouter config for `/leancontext:compress`:

```bash
export OPENROUTER_API_KEY="sk-or-v1-REPLACE_ME"
export LEANCONTEXT_OPENROUTER_MODEL="openrouter/elephant-alpha"
```

Desktop-friendly secret file:

```bash
mkdir -p ~/.claude
chmod 700 ~/.claude
$EDITOR ~/.claude/leancontext-openrouter.json
```

```json
{
  "OPENROUTER_API_KEY": "sk-or-v1-REPLACE_ME",
  "LEANCONTEXT_OPENROUTER_MODEL": "openrouter/elephant-alpha"
}
```

Never commit real API keys.

## Quality Gate

```bash
cd skills/compress
python3 -m scripts --gate --source golden --report-json leancontext-claude-gate.json
```

Expected current result: `PASS 5/5`, avg savings around `53.26%`, min around `50.0%`.

## Notes

LeanContext affects visible assistant output and memory-file compression. It does not intentionally reduce the model reasoning path, code quality, or safety warnings.
