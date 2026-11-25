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
4. Ask the user which git operations Claude may run in this project:
   1. **No git writes** (default): `commit`, `push`, `checkout` and `branch` stay blocked. Change nothing.
   2. **Local only**: Claude may commit and switch or create branches (`commit`, `checkout`, `branch`), but never push.
      - Edit the **Git** constraint in `.claude/rules/critical-constraints.md` to remove `commit` from the forbidden commands.
      - Set `"DDHQ_ALLOW_GIT": "local"` in the project's `.claude/settings.json` (see below).
   3. **Local and remote**: Claude may also push (`commit`, `push`, `checkout`, `branch`).
      - Edit the **Git** constraint in `.claude/rules/critical-constraints.md` to remove `commit` and `push` from the forbidden commands.
      - Set `"DDHQ_ALLOW_GIT": "1"` in the project's `.claude/settings.json` (see below).

   Put `DDHQ_ALLOW_GIT` in the `env` object (create the file or the `env` object if missing, and keep all other settings). The `block_git_write_ops.py` hook reads it and unblocks the chosen commands for this project only.
5. Check for stale copies of the plugin hooks: run `/usr/bin/python3 "${CLAUDE_SKILL_DIR}/../../hooks/check_stale_hooks.py" --list` from the project root. If it prints anything, show the findings to the user, explain that these copies run next to the plugin's own hooks and can block commands the plugin allows, and ask whether to remove them. If the user agrees, delete each listed `.claude/hooks/` file and remove each listed hook entry from the settings file (drop a matcher group or event that becomes empty, and keep all other settings).
6. Confirm to the user that the rules and guidelines have been installed and remind to fill in `conventions.md`.

### Update notes

- If source and destination already exist and the content is different, always ask the user whether to overwrite it (it may have been customized).
- The git and file-ops hooks ship with the plugin and are never copied into the project. Projects set up with an older version (≤0.13) or by hand may still have `.claude/hooks/block-git-write-ops.sh` / `block-dangerous-file-ops.sh` registered in `.claude/settings.json`. A SessionStart check warns about them. To upgrade, rerun this skill (step 5 removes them) or delete the files and their settings entries by hand.