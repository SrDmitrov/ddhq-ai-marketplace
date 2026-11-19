# Backlog

Top item is next. Move an item to the bottom section when it ships.

## Next

### Code-block follow-ups (audit of 0.2.0)
Fixed and checked in Chrome: Bash output read as code, language from the wrong dot, blocking CDN script (now async with an integrity hash), unrecognized fences (```` ```c++ ````, trailing spaces), clipped diff tint, missing token colors, low contrast on the diff tints, `=>` ligature. Live playback follows a 200-line block to the end.

Open:
- **Not yet tested in a browser:** scrolling up during playback, then partway back down, must not turn following back on; Pause during the grow/fade must hold the animation; offline mode must show plain code.
- **Thinking glyph in Safari:** it cycles through CSS `content` keyframes. Check that Safari animates it; if not, it shows a still `✻`.
- **Tool output is highlighted line by line,** so block comments and template strings that span lines are colored wrong. Fenced blocks are highlighted as a whole and are fine.
- **No example has a code block or diff,** so a rebuild does not exercise this code. The `examples/` rule forbids new files: add a short TS diff and a fenced block to an existing example (needs the user's OK).

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

### Rewrite in TypeScript with a framework
Move the player and build scripts to TypeScript and a friendly framework with a simple architecture (MVVM is fine).
- Why: `player.js` mixes playback state, DOM building and animation in one file; typed models and views separate them.
- Open questions:
  - Which framework (light enough for a single-file, offline-capable page)?
  - Build output: still one self-contained `.html` per replay, and how the skill builds it without a manual install step.
  - Keep `CLAUDE.md`'s "no dependencies" rule, or replace it with a pinned, minimal toolchain.

### Project
- Automated playback test: the fake-DOM smoke test lives only in a temp folder. Move it into the repo.

## Done
- Animated player with presentation controls, CRT start-up, `@ask` cards, light/dark themes.
- `/export` importer; fixed: prompts read as slash commands, `Answered Claude's questions`, diff lines in tool output, extra `⎿` blocks, `· summary` tags.
- `/fancy-replay <export.txt>` skill, shipped as the `chat-replay` plugin.
- Diffs as tinted rows, syntax highlighting with highlight.js, tool output and code blocks revealed with a thinking glyph, grow and fade.
