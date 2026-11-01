---
name: install-rules
description: Installs ddhq's basic rules and guidelines into the current project's .claude/rules/ directory.
---

# Install rules and guidelines

Install ddhq's custom rules and guidelines into the current project's `.claude/rules/` directory.

## Steps

1. Check if `.claude/rules/` directory exists in the project. If not, create it.
2. Read the user's global `~/.claude/CLAUDE.md` (if it exists) and compare it with the rules in `${CLAUDE_SKILL_DIR}/resources/`. If any rule is already there, list the overlapping rules and ask the user whether to still install them (they would be duplicated). Skip the overlapping rules if the user declines.
3. Copy the files at `${CLAUDE_SKILL_DIR}/resources/` and paste them to `.claude/rules/`
4. Ask the user whether Claude may commit, push to remote, and switch or create branches (`commit`, `push`, `checkout`, `branch`) in this project. If yes:
   - Edit the **Git** constraint in `.claude/rules/critical-constraints.md` to remove `commit` and `push` from the forbidden commands.
   - Add `"DDHQ_ALLOW_GIT": "1"` to the `env` object in the project's `.claude/settings.json` (create the file or the `env` object if missing, and keep all other settings). This unblocks those four commands in the `block-git-write-ops.sh` hook for this project only.
5. Confirm to the user that the rules and guidelines have been installed and remind to fill in `conventions.md`.

### Update notes

- If source and destination already exist and the content is different, always ask the user whether to overwrite it (it may have been customized).