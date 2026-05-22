# claude-ctx-statusline

Shows context window usage in the Claude Code status line:

```
Ctx: 30k/200k (15%)
```

## Requirements

- Claude Code CLI
- Node.js (any recent version)

## Install

```powershell
.\install.ps1
```

Restart Claude Code. Done.

## What it does

`install.ps1`:
1. Copies `ctx-statusline.js` to `~/.claude/scripts/`
2. Patches `~/.claude/settings.json` with the `statusLine` command

## Manual install

Add to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "node \"C:\\Users\\YOU\\.claude\\scripts\\ctx-statusline.js\""
  }
}
```
