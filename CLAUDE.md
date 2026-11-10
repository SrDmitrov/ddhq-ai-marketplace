# CLAUDE.md

## Finishing a change

When a change or update to a plugin is finished:

1. **Bump the version** in that plugin's `.claude-plugin/plugin.json` (e.g. `basics/.claude-plugin/plugin.json`), following semver:
   - patch: fixes and wording tweaks
   - minor: new rules, skills, hooks, or features
   - major: breaking changes

   Bump only once per plugin per session: further changes to the same plugin in the same session reuse that bump (raise its level if a later change warrants it). Exception: if the bump has been pushed and the session continues, the next change gets a new bump.
2. **Stage the change** with `git add` (only the files touched by the change, including the bumped `plugin.json`).
3. **Ask for confirmation** before running `git commit` or `git push`. Never commit or push without explicit approval.
