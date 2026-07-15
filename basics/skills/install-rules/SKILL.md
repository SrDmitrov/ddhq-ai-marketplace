---
name: install-rules
description: Installs ddhq's basic rules and guidelines into the current project's .claude/rules/ directory.
---

# Install rules and guidelines

Follow these steps to install them.

## Steps

1. Check if `.claude/rules/` directory exists in the project. If not, create it.
2. Copy the files at `${CLAUDE_SKILL_DIR}/resources/` and paste them to `.claude/rules/`
3. Confirm to the user that the rules and guidelines have been installed and remind to fill in `conventions.md`.

### Update notes

- If source and destination already exist and the content is different, always ask the user whether to overwrite it (it may have been customized).