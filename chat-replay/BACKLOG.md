# Backlog

Top item is next. Move an item to the bottom section when it ships.

## Next

### Import `.jsonl` conversations
Claude Code stores every session as JSON Lines (`~/.claude/projects/<project>/<session-id>.jsonl`). Import from it as well as from the `/export` text.
- Why: the JSON is structured, so prompts, replies, tool calls with their full input and output, answered questions and timings come through exactly. The `/export` importer has to guess where the terminal wrapped lines (see the importer items below).
- Output: the same `.chat` draft on stdout, so the hand-edit and build steps stay the same.
- Open questions:
  - A new script, or one `import-claude-code.mjs` that picks the parser by file extension?
  - How much of each tool result to keep (full output vs. the first lines plus `… +N lines`, as the terminal shows it)?
  - How to show sidechains (subagent messages) and compaction summaries?
  - Where to get the `@done` time ("Baked for 17s") from the timestamps.
- Privacy: the JSONL holds more than the export (full tool output, file contents, environment details), so the private-data check before publishing matters even more.

## Later

### Importer (`/export` text)
- Plain tool-output wraps are not rejoined when the first line is one character short of the width (`…&restaurant` / `_id=4471…`, `Shell cwd was reset to …/Proj` / `ects/…`).
- Diff wraps are joined using a hard cut at `width - 7`. This was found from one export and is not documented by Claude Code; check it against more exports.
- `⏺ Updated plan` and `⏺ Approved Claude's plan` with their `⎿` blocks come through as one large `@say`.
- Multi-line `@dim` blocks (such as `Message from general-purpose`) are not unwrapped.
- A Write-tool wrap that starts with `-` right at the marker column, after a line starting with `- `, loses its first character.
- ASCII diagrams in a reply are flattened into one paragraph; wrap them in a ``` block by hand.
- A `/clear` with no `⎿` output comes through as `@user` instead of `@slash`.
- Hook/plugin `⏺` messages (e.g. `masker: …`) come through as `@say`; there is no `@note` detection.
- No regression fixture: the raw export for `coffe-break-with-questions.chat` is gone. Keep one raw `/export` text with its expected `.chat` to test importer changes.

### Project
- Automated playback test: the fake-DOM smoke test lives only in a temp folder. Move it into the repo.

## Done
- Animated player with presentation controls, CRT start-up, `@ask` cards, light/dark themes.
- `/export` importer; fixed: prompts read as slash commands, `Answered Claude's questions`, diff lines in tool output, extra `⎿` blocks, `· summary` tags.
- `/fancy-replay <export.txt>` skill, shipped as the `chat-replay` plugin.
