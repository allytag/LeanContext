# Contributing

Small focused changes are easiest to review.

## Main Files

- Edit `skills/leancontext/SKILL.md` for live chat behavior.
- Edit `skills/compress/` for memory-file compression behavior.
- Edit `hooks/` for Claude Code activation/statusline behavior.
- Edit `commands/` for slash command prompts.

## Pull Request Checklist

- Include before/after examples for prompt changes.
- Run `claude plugin validate ./claude`.
- Run `python3 -m scripts --gate --source golden` from `claude/skills/compress`.
- Do not commit real API keys, local secret files, or benchmark scratch output.

