---
name: install-statusline
description: Installs ddhq's statusline (branch, session, model, context, cache, rate limit, running Android emulators) into the user's ~/.claude/ configuration.
---

# Install statusline

Install ddhq's statusline into the user's `~/.claude/` configuration.

## Steps

1. Check that `jq` is available on `PATH`. If not, tell the user to install it (e.g. `brew install jq`) and stop.
2. Copy `${CLAUDE_SKILL_DIR}/resources/statusline-command.sh` to `~/.claude/statusline-command.sh`.
3. Set `statusLine` in `~/.claude/settings.json` to the value below (create the file if missing, and keep all other settings):
   ```json
   "statusLine": {
     "type": "command",
     "command": "sh ~/.claude/statusline-command.sh"
   }
   ```
4. Confirm to the user that the statusline has been installed and that it appears on the next interaction.

### Update notes

- If `~/.claude/statusline-command.sh` already exists and the content is different, always ask the user whether to overwrite it (it may have been customized).
- If `statusLine` is already set in `~/.claude/settings.json` to a different value, show the current value and ask the user whether to replace it.
