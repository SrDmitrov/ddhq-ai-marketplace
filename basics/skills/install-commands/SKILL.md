---
name: install-commands
description: Installs ddhq's custom commands into the current project's .claude/commands/ directory.
---

# Install commands

Delegate this task to a subagent with this type and model: `Agent(subagent_type: "general-purpose", model: "haiku", ...)` and instruct it to follow these installation steps.

## Steps

1. Check if `.claude/commands/` directory exists in the project. If not, create it.
2. Copy the files at `${CLAUDE_SKILL_DIR}/resources/` and paste them to `.claude/commands/`
3. Confirm to the user that the commands have been installed.

### Update notes

- If source and destination already exist and the content is different, always ask the user whether to overwrite it (it may have been customized).
