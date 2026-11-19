# chat-replay

Turns a conversation with an AI into an animated terminal replay: prompts type themselves, a spinner runs, tool calls and replies stream in. The output is one self-contained HTML page with playback controls (start, previous, play/pause, next, end, continuous play, 2×/4×) and a light/dark theme.

No dependencies. Needs Node 18 or newer.

## Install

```
/plugin marketplace add SrDmitrov/ddhq-ai-marketplace
/plugin install chat-replay@ddhq-mkpl
```

## Usage

1. In the Claude Code session to replay, run `/export <name>`. It writes `<name>.txt`.
2. In any project, run `/fancy-replay <path>/<name>.txt`.

Claude imports the export, asks how to rename private data and how much to cut, writes the conversation, checks it for private data, builds it and publishes it as an artifact. Everything it creates goes to a temporary workspace, `chat-replays/<name>/` in the session's scratchpad or `$TMPDIR`, which the sandbox allows. Claude reports its full path. A reboot can clear it, so copy the `.chat` elsewhere to keep it. Without an Artifact tool, you get a standalone `<new-name>.html` there.

## Manual use

Run the scripts from the plugin folder. Both are dependency-free.

```sh
node skills/fancy-replay/import-claude-code.mjs my-talk.txt > my-talk.chat   # export → draft
node skills/fancy-replay/build.mjs my-talk.chat                              # builds my-talk.html and my-talk.artifact.html
```

The build writes next to each input file:

| File | Use |
| --- | --- |
| `<name>.html` | Full HTML document. Open it locally or put it on any static host (GitHub Pages, Netlify, S3). |
| `<name>.artifact.html` | The same page without `<!doctype>`, `<head>` and `<body>`, which is the form a Claude artifact expects. |

The importer rejoins wrapped lines and recognizes prompts, tool calls, replies, answered questions and "done" lines. The draft needs a manual pass. The `.chat` format and that pass are in [`skills/fancy-replay/FORMAT.md`](skills/fancy-replay/FORMAT.md). Exports hold private data: keep them out of any git repo.

## Deploying

**Web page:** upload `<name>.html` to any static host. It loads two Google Fonts and nothing else.

**Claude artifact:** publish `<name>.artifact.html` with the Artifact tool. Never publish the full `.html` as an artifact. To update an artifact that already exists, give Claude its URL.

## Changing the look

- Colors and fonts: the tokens at the top of `skills/fancy-replay/src/player.css`. Light is Solarized Light, dark is One Dark. Dark values appear twice (OS setting and explicit toggle); keep the two blocks identical.
- Page structure: `skills/fancy-replay/src/page.html`. The terminal title bar shows the title, the `window` text and the turn counter.
- Typing speed, pauses and spinner: `skills/fancy-replay/src/player.js`.
- Start-up animation (a CRT powers on, `claude` is typed, the banner draws): `boot()` and `open()` in `skills/fancy-replay/src/player.js`; its colors are the `--crt-*` tokens.

## Changing the importer / player

- **Importer:** edit `skills/fancy-replay/import-claude-code.mjs`. Keep it dependency-free. Test on a real export and write to `$TMPDIR` only. Run the importer before and after the change, then diff the two drafts.
- **Player:** edit `skills/fancy-replay/src/`, then rebuild the examples: `node skills/fancy-replay/build.mjs examples/*.chat`. Keep the two dark-theme blocks in `player.css` identical.

## Layout

```
.claude-plugin/plugin.json          plugin manifest
skills/fancy-replay/SKILL.md        the /fancy-replay procedure
skills/fancy-replay/FORMAT.md       .chat format reference
skills/fancy-replay/build.mjs       .chat → .html and .artifact.html
skills/fancy-replay/import-claude-code.mjs   Claude Code /export → .chat draft
skills/fancy-replay/src/page.html   page markup with {{PLACEHOLDERS}}
skills/fancy-replay/src/player.css  styles and theme tokens
skills/fancy-replay/src/player.js   the player
examples/                           the three committed example replays
```
