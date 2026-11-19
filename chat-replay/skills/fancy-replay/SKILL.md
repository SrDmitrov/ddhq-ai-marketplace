---
name: fancy-replay
description: Turn a Claude Code /export .txt file into a published chat-replay artifact. Use when the user types /fancy-replay <export.txt>, or asks to make, build or publish a replay from a Claude Code export, even if they do not name the skill.
argument-hint: <export.txt>
---

# fancy-replay

Turn a Claude Code `/export` text file into a published replay artifact. Follow the steps in order. Do not work from memory.

Roles: the **main session** reads, asks, checks and publishes. A **worker** is a subagent that writes the `.chat` file (`general-purpose`, model `sonnet`, effort `medium`).

`<ws>` is the workspace `<tmp>/chat-replays/<name>/`. `<tmp>` is the session's scratchpad directory if your system prompt lists one, else `$TMPDIR`. Both are writable inside the sandbox. `<name>` is the export's file name without `.txt`. Always write `<ws>` as a full absolute path, also to workers.

## 0. Input

`$ARGUMENTS` is the path to the export.

- If it is missing or not a `.txt` file, stop and ask for it. Explain: run `/export <name>` in the session to replay. It writes `<name>.txt`.
- Run `node --version`. If it is lower than 18, stop and tell the user.

## 1. Workspace

The export holds private data. Never write it, or anything built from it, anywhere else.

1. Run `ls -l <tmp>/chat-replays`. Create the folder if it is missing.
2. Create `<ws>` and copy the export into it.

## 2. Import a draft

```sh
node "${CLAUDE_SKILL_DIR}/import-claude-code.mjs" <ws>/<name>.txt > <ws>/draft.chat
```

Read the whole draft and compare it with the export. Note:
- **Private data:** home directory and user name, company, client and project names, hostnames and URLs, ticket keys, emails, logins and passwords, tokens, GPS coordinates, session IDs and temp paths, plugin names that identify the setup.
- **Importer mistakes:** prompts read as `@slash`, answered questions that are not an `@ask`, wrapped lines that were not rejoined, tool output that became loose `@dim` lines.
- **Noise:** hook and plugin messages, compaction blocks, interrupted prompts, `Shell cwd was reset` lines, recap lines, long plans.

## 3. Ask once

Use AskUserQuestion, one round, with the defaults marked Recommended. Do not use plan mode. Do not ask for plan approval. After the answers, run to the end.

- **Replacement names.** Default: a consistent fictional brand (company, product, domain `*.example`, ticket prefix, `~/work/<product>` path, fake coordinates). Keep IDs and commit hashes that mean nothing outside.
- **How much to cut.** Default: cut the noise, keep every user turn, question cards, tool calls with their code diffs, and results.

Name the output `<ws>/<new-name>.chat` after the fictional product, never the real one.

## 4. Write the conversation

Spawn a worker. Give it the draft, the export, the name map, the cut list, the output path and the rules in step 5. Tell it to read `${CLAUDE_SKILL_DIR}/FORMAT.md` first. The worker hand-fixes importer mistakes.

## 5. Worker rules

The worker:
- Sets the settings: `title`, `window: <product>-<platform> — claude`, `status: <model>`. Leave `subtitle` and `footer` empty (minimal design).
- Replaces every private item with the agreed name map, also inside diffs, URLs, paths and tool arguments.
- Cuts the noise and shortens long plans to `## ` headings with a few bullets.
- Tidies: joins lines still broken by wrapping, adds backticks around paths, endpoints and identifiers in `@say` text, escapes body lines that start with `@` as `\@`.
- Keeps the wording of user prompts and replies otherwise unchanged.
- Writes `<ws>/<new-name>.chat` and runs `node "${CLAUDE_SKILL_DIR}/build.mjs" <ws>/<new-name>.chat`, which must succeed.

## 6. Build and check

1. **Privacy check.** Grep the `.chat` for every original name and for general patterns, and read each hit:
   ```sh
   grep -n -i -E "<real names>|/Users/|<user name>|<ticket key>" <ws>/<new-name>.chat
   grep -n -i -E "[a-z0-9._-]+@[a-z0-9.-]+\.[a-z]{2,}|password|token|lat=|https?://" <ws>/<new-name>.chat
   ```
   A real hit goes back to the worker. An endpoint such as `/users/me/` is not private.
2. **Build.** Run `node "${CLAUDE_SKILL_DIR}/build.mjs" <ws>/<new-name>.chat` again after any fix. It writes `<new-name>.html` and `<new-name>.artifact.html` into `<ws>`.

## 7. Publish

- **Artifact tool available:** publish `<ws>/<new-name>.artifact.html` as a new artifact (icon `terminal`, one-sentence description). Never publish the full `.html` as an artifact. Never publish the export.
- **No Artifact tool:** hand over `<ws>/<new-name>.html`. It is a full page for any static host.

## 8. Report

Report to the user: the link or the file path, the full path of `<ws>` (temporary: a reboot can clear it, so copy the `.chat` elsewhere to keep it), who can open it (new artifacts are private until shared), the name map, what was cut, the importer mistakes fixed by hand, and what was not verified (the replay is not viewed in a browser).

## Stop and ask

Stop and ask the user when:

- a tool fails twice,
- the privacy grep has a hit you cannot classify,
- the build still fails after one fix.

Never commit.
