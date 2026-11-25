---
name: onboardme
description: Builds or rewrites a project's CLAUDE.md and its docs/knowledge/ knowledge base following ddhq's template, verifying every existing fact against the code. Use instead of /init whenever the user wants to create, regenerate, update, clean up or audit a CLAUDE.md, onboard Claude to a repository, or document a codebase for AI agents, even if they do not mention the template.
---

# Onboard Claude to a repository

Produce a root `CLAUDE.md` that works as a short index plus a `docs/knowledge/` folder that holds
the detail. CLAUDE.md is loaded into every session, so it stays small and points to knowledge files
that Claude reads only when it works in that area.

Files in this skill:

- `${CLAUDE_SKILL_DIR}/assets/CLAUDE.template.md` — skeleton of the root CLAUDE.md.
- `${CLAUDE_SKILL_DIR}/assets/knowledge-doc.template.md` — skeleton of one knowledge file.
- `${CLAUDE_SKILL_DIR}/references/writing-guide.md` — rules for every section, sources of facts,
  verification of existing content, and the final self-check. Read it fully before step 3.

## Steps

### 1. Survey the repository

Delegate exploration to `Explore` subagents (`model: "haiku"`, `effort: "medium"`), split by area
so they run in parallel. Ask each for conclusions with `path:line` references, not file dumps:

- Stack and build: build files, where versions live, deprecated or commented-out dependencies.
- Structure: top-level packages/modules, architecture pattern, entry points, navigation or routing.
- Integrations and environments: external systems, HTTP/SDK clients, config and env keys per
  environment, CI and deploy scripts, build/test/lint commands.

Also read `.claude/rules/`, the user's `~/.claude/CLAUDE.md`, and any parent CLAUDE.md, so the new
files do not repeat them.

### 2. Inventory existing context

Skip if the project has no CLAUDE.md and no `docs/knowledge/`.

Otherwise list every factual claim in them (paths, line ranges, classes, commands, dependencies,
constraints). Verify each against the code as described in the writing guide
(§ Verifying existing content) and classify it as keep, fix, drop or ask. Old docs read as
authoritative, so an unchecked stale fact misleads every future session.

### 3. Plan and confirm

Show the user, before writing anything:

1. The proposed `docs/knowledge/` files in reading order, each with its one-line hook. Propose only
   topics with real content; a small project may need none (then CLAUDE.md inlines the detail).
2. The keep / fix / drop table from step 2, with the reason for each fix and drop.
3. The questions for the `ask` claims.

Wait for confirmation and answers. Adjust the plan to the user's feedback.

### 4. Write the knowledge files

Create `docs/knowledge/` if needed (check with `ls -l` first). Write one file per confirmed topic
from `knowledge-doc.template.md`, following § Format of the linked documents. Existing knowledge
files that are kept get rewritten into the same format with only verified facts.

### 5. Write CLAUDE.md

Fill `CLAUDE.template.md` following the writing guide. Replace the existing CLAUDE.md, carrying
over only keep and fix claims and the user's answers. Drop sections that would be empty.

### 6. Self-check

Run the checklist in § Self-check of the writing guide against every file you wrote. Verify paths
and line ranges with real lookups, not from memory. Fix each failure before reporting.

### 7. Report

Tell the user, briefly: files created or changed, facts fixed or dropped (with reason), and any
open question. Do not commit; the user reviews the files first.
