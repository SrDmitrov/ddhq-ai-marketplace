# CLAUDE.md

## Repository

This repository is a Claude Code plugin marketplace (`ddhq-mkpl`, see `.claude-plugin/marketplace.json`). Each plugin lives in its own directory:

- `basics/` (`basic-setup`): ddhq's general rules, guidelines, skills and hooks for AI agents.
- `adbmm/`: ADB middle man, an MCP server that lets the agent drive Android emulators for integration tests and QA.
- `chat-replay/`: turns a Claude Code `/export` into an animated terminal replay, published as an artifact or standalone HTML page.
- `backoffice/`: ddhq's backoffice plugin (placeholder, no content yet).
- `mods/masker/`: masks secrets before the model reads them, using env values and betterleaks-derived rules; refuses writes that carry a mask.
- `mods/poketokenbar-utils/`: makes the PokeTokenBar floating pet follow Claude Code activity (working, waiting for input, done).

## Finishing a change

When a change or update to a plugin is finished:

1. **Bump the version** in that plugin's `.claude-plugin/plugin.json` (e.g. `basics/.claude-plugin/plugin.json`), following semver:
   - patch: fixes and wording tweaks
   - minor: new rules, skills, hooks, or features
   - major: breaking changes

   Bump only once per plugin per session: further changes to the same plugin in the same session reuse that bump (raise its level if a later change warrants it). Exception: if the bump has been pushed and the session continues, the next change gets a new bump.
2. **Stage the change** with `git add` (only the files touched by the change, including the bumped `plugin.json`).
3. **Ask for confirmation** before running `git commit` or `git push`. Never commit or push without explicit approval.
