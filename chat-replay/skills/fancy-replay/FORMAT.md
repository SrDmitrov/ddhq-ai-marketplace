# The .chat format

A `.chat` file is plain text: page settings first, then the conversation. See `examples/hello-world.chat` in the plugin for a minimal example to copy.

```
title: My Talk
subtitle: One line shown under the title. `backticks` become code.
window: my-app — claude — 100×40
status: Opus 5.5
footer: Shown under the terminal.

@banner
 ▐▛███▛█   **Claude Code** v2.1.322
▝▜██████▀  Opus 5.5 · Claude Team
@user is there an emulator running?
@tool! Bash(adb devices -l)
Error: Exit code 1
ADB server didn't ACK
@say
Yes, one emulator is running: `emulator-5554`.

- A bullet
1. A numbered item
## A bold heading
@done Worked for 12s · done 5:19 PM
```

All five settings are optional. Lines starting with `#` before the first directive are comments.

| Directive | Shows |
| --- | --- |
| `@banner` + lines | Start-up banner. Leading block characters are drawn as the logo. |
| `@user text` | A prompt, typed into the input box and then sent. |
| `@slash /cmd` + optional line | A slash command and its one-line result. |
| `@say` + lines | The assistant's reply, streamed. One paragraph per line; blank lines separate paragraphs. Supports `- ` bullets, `  - ` nested bullets, `1. ` items, `## ` headings, `` `code` ``, `**bold**`, box-drawing tables (shown as-is) and a ``` fenced block (shown verbatim, e.g. diagrams; ```ts, ```python, ```bash etc. adds syntax highlighting). |
| `@tool Name(args)` + lines | A tool call and its output. `@tool!` marks it as failed (red). Numbered lines (`12 …`, `12 +…`, `12 -…`) are shown as code, highlighted by the file extension in the call (highlight.js from cdnjs; plain text offline); `+`/`-` rows get a green/red tint. |
| `@ask` + lines | Answered questions (AskUserQuestion), one `Question → Answer` per line (`->` also works). A card asks each one and marks the answer, then folds into `User answered Claude's questions:`. |
| `@note text` | A dimmed system notice with a `⏺` marker. |
| `@dim text` | A dimmed line, such as `Wrote 2 memories (ctrl+o to expand)`. |
| `@done text` | Ends the turn, for example `Baked for 9s · done 5:33 PM`. |
| `@spin Verb` | Optional. Overrides the spinner word for the current turn. |

Playback works like a presentation. It opens on a small retro terminal with `claude` typed in and waits. Play, Next or a click on it opens Claude Code, which waits again at turn 0; Play then starts the conversation. Each turn is two steps, and Previous/Next move one step at a time: the user's prompt is typed into the input box, then it is sent and the agent replies.

The spinner starts after every prompt and stops at `@done`. Its word comes from the `@done` text ("Baked for 9s" gives "Baking…"); without a `@done` it says "Thinking…" until the next prompt.

To start a line inside `@say` or tool output with a literal `@`, write `\@`.

## Converting an import draft

The importer (`import-claude-code.mjs`) rejoins lines that the terminal wrapped and recognizes prompts, tool calls, replies, answered questions and "done" lines. The export is plain text, so some things are lost and need a manual pass:

- Fill in the settings at the top.
- Inline code and bold are gone. Add backticks and `**` where you want them back.
- Headings come through as plain or numbered lines. Prefix them with `## `.
- Diagrams are flattened. Wrap them in ``` lines by hand so they show verbatim.
- Hook and system notices come through as `@say`. Change them to `@note`.
- Replace anything private (home directory, project names, hostnames) before you publish.
