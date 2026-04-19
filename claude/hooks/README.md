# LeanContext Hooks

These hooks are **bundled with the leancontext plugin** and activate automatically when the plugin is installed. No manual setup required.

If you installed leancontext standalone (without the plugin), you can use `bash hooks/install.sh` to wire them into your settings.json manually.

## What's Included

### `leancontext-activate.js` — SessionStart hook

- Runs once when Claude Code starts
- Writes `full` to `~/.claude/.leancontext-active` (flag file)
- Emits LeanContext rules as hidden SessionStart context
- Detects missing statusline config and emits setup nudge (Claude will offer to help)

### `leancontext-mode-tracker.js` — UserPromptSubmit hook

- Fires on every user prompt, checks for `/leancontext` commands
- Writes the active mode to the flag file when a leancontext command is detected
- Supports: `full`, `lite`, `ultra`, `wenyan`, `wenyan-lite`, `wenyan-ultra`, `commit`, `review`, `compress`

### `leancontext-statusline.sh` / `leancontext-statusline.ps1` — Statusline badge script

- Reads `~/.claude/.leancontext-active` and outputs a colored badge
- Shows `[LEANCONTEXT]`, `[LEANCONTEXT:ULTRA]`, `[LEANCONTEXT:WENYAN]`, etc.

## Statusline Badge

The statusline badge shows which LeanContext mode is active directly in your Claude Code status bar.

**Plugin users:** If you do not already have a `statusLine` configured, Claude will detect that on your first session after install and offer to set it up for you. Accept and you're done.

If you already have a custom statusline, leancontext does not overwrite it and Claude stays quiet. Add the badge snippet to your existing script instead.

**Standalone users:** `install.sh` / `install.ps1` wires the statusline automatically if you do not already have a custom statusline. If you do, the installer leaves it alone and prints the merge note.

**Manual setup:** If you need to configure it yourself, add one of these to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash /path/to/leancontext-statusline.sh"
  }
}
```

```json
{
  "statusLine": {
    "type": "command",
    "command": "powershell -ExecutionPolicy Bypass -File C:\\path\\to\\leancontext-statusline.ps1"
  }
}
```

Replace the path with the actual script location (e.g. `~/.claude/hooks/` for standalone installs, or the plugin install directory for plugin installs).

**Custom statusline:** If you already have a statusline script, add this snippet to it:

```bash
leancontext_text=""
leancontext_flag="$HOME/.claude/.leancontext-active"
if [ -f "$leancontext_flag" ]; then
  leancontext_mode=$(cat "$leancontext_flag" 2>/dev/null)
  if [ "$leancontext_mode" = "full" ] || [ -z "$leancontext_mode" ]; then
    leancontext_text=$'\033[38;5;172m[LEANCONTEXT]\033[0m'
  else
    leancontext_suffix=$(echo "$leancontext_mode" | tr '[:lower:]' '[:upper:]')
    leancontext_text=$'\033[38;5;172m[LEANCONTEXT:'"${leancontext_suffix}"$']\033[0m'
  fi
fi
```

Badge examples:
- `/leancontext` → `[LEANCONTEXT]`
- `/leancontext ultra` → `[LEANCONTEXT:ULTRA]`
- `/leancontext wenyan` → `[LEANCONTEXT:WENYAN]`
- `/leancontext-commit` → `[LEANCONTEXT:COMMIT]`
- `/leancontext-review` → `[LEANCONTEXT:REVIEW]`

## How It Works

```
SessionStart hook ──writes "full"──▶ ~/.claude/.leancontext-active ◀──writes mode── UserPromptSubmit hook
                                              │
                                           reads
                                              ▼
                                     Statusline script
                                    [LEANCONTEXT:ULTRA] │ ...
```

SessionStart stdout is injected as hidden system context — Claude sees it, users don't. The statusline runs as a separate process. The flag file is the bridge.

## Uninstall

If installed via plugin: disable the plugin — hooks deactivate automatically.

If installed via `install.sh`:
```bash
bash hooks/uninstall.sh
```

Or manually:
1. Remove `~/.claude/hooks/leancontext-activate.js`, `~/.claude/hooks/leancontext-mode-tracker.js`, and the matching statusline script (`leancontext-statusline.sh` on macOS/Linux or `leancontext-statusline.ps1` on Windows)
2. Remove the SessionStart, UserPromptSubmit, and statusLine entries from `~/.claude/settings.json`
3. Delete `~/.claude/.leancontext-active`
