# CLAUDE.md

## Finishing a change

When a change or update to a plugin is finished:

1. **Bump the version** in that plugin's `.claude-plugin/plugin.json` (e.g. `basics/.claude-plugin/plugin.json`), following semver:
   - patch: fixes and wording tweaks
   - minor: new rules, skills, hooks, or features
   - major: breaking changes
2. **Stage the change** with `git add` (only the files touched by the change, including the bumped `plugin.json`).
3. **Ask for confirmation** before running `git commit` or `git push`. Never commit or push without explicit approval.
