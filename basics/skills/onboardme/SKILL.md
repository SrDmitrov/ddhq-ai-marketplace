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

Onboarding must describe the latest code, usually the `develop` branch. A stale checkout makes
every finding stale, and the whole survey has to be redone. Before surveying:

1. Run `git fetch`. It is mandatory. When it fails (a sandbox that blocks SSH, missing
   credentials), ask the user to run `! git fetch` and wait for it.
2. Run `git status -sb` and `git log -1 --format='%h %cr %s'` to see the branch, how far it is
   behind its upstream, and the last commit.
3. If the branch is not `develop` (or the repo's main integration branch), or it is behind, ask with
   `AskUserQuestion` whether to switch and update first (the user runs `! git checkout develop` and
   `! git pull`) or to document this checkout as it is. Show the branch, the commits behind and
   the last commit in the question.

Delegate exploration to `Explore` subagents (`model: "haiku"`, `effort: "medium"`), split by area
so they run in parallel. Ask each for conclusions with `path:line` references, not file dumps:

- Stack and build: build files, where versions live, deprecated or commented-out dependencies.
- Structure: top-level packages/modules, architecture pattern, entry points, navigation or routing.
- Integrations and environments: external systems, HTTP/SDK clients, config and env keys per
  environment, CI and deploy scripts, build/test/lint commands.

Also read `.claude/rules/`, the user's `~/.claude/CLAUDE.md`, and any parent CLAUDE.md, so the new
files do not repeat them.

Check the parent directory for sibling repositories of the same product (backend, other mobile
apps). Their CLAUDE.md and `docs/knowledge/` show the conventions already in use and hold facts
this repo only consumes, such as backend behaviour. Name the siblings in the Project Overview and
link their docs instead of restating them. A sibling's claim about its own repo (release process,
build rules) does not carry over: confirm it in this repo's code or ask in step 3. Siblings often
live elsewhere (a backend under `Python/`, its apps under `Kotlin/` or `Swift/`): if the parent
directory holds none, ask in step 3 where the other repos of the product are, or whether there
are none.

Subagent `path:line` references are leads, not facts. Confirm each one with `grep -n` or `sed -n`
before it goes into a file.

### 2. Inventory existing context

Find every file that already guides agents or describes the project: `CLAUDE.md`,
`CLAUDE.local.md`, `AGENTS.md`, `.cursorrules`, `.github/copilot-instructions.md`,
`docs/knowledge/`, onboarding or "readme for agents" drafts anywhere under `docs/` (they often sit
in odd places such as `docs/tmp/`), the README and any project wiki. Skip this step only if none
exist.

List every factual claim in them (paths, line ranges, classes, commands, dependencies,
constraints). Verify each against the code as described in the writing guide
(§ Verifying existing content) and classify it as keep, fix, drop or ask. Old docs read as
authoritative, so an unchecked stale fact misleads every future session. Business rules that live in
a maintained wiki or doc stay there: link them, do not copy them.

Onboarding writes only CLAUDE.md and `docs/knowledge/`. Other files (README, `API_README.md`,
module READMEs, help text in a Makefile) are sources: never edit or delete them. For those, fix
means the new files carry the corrected fact, and drop means they leave it out. The stale file
itself goes into the report, or into `known-issues.md` if the user chose it.

### 3. Plan and confirm

Before planning, check where the output will land and whether git tracks it:

- `ls -l` on `docs/` and `docs/knowledge/`: a symlink may point outside the repository (a folder
  shared by several apps).
- `git check-ignore -v CLAUDE.md docs` and `git ls-files CLAUDE.md`: is CLAUDE.md tracked or local-only?

Show the user, before writing anything. Items 1 and 3 are always shown, even when step 2 found
no existing docs:

1. The proposed `docs/knowledge/` files in reading order, each with its one-line hook. Propose only
   topics with real content; a small project may need none (then CLAUDE.md inlines the detail).
   When the survey found defects or technical debt, offer `known-issues.md` and list what it
   would hold. Explain that it starts the project's technical-debt record (see the writing
   guide). It stays the user's choice, so do not mark it as recommended.
2. The keep / fix / drop table from step 2, with the reason for each fix and drop.
3. The proposed IMPORTANT NOTES bullets, each with its source (`path:line`, CI or deploy file). A
   rule you cannot back with this repo's code or config is a question, not a bullet. IMPORTANT
   NOTES changes how every future session behaves, so the user approves each bullet.
4. The questions for the `ask` claims, plus placement and tracking when they are unclear (symlink
   outside the repo, CLAUDE.md tracked although a doc says local-only).

Print items 1–3 as text, then in the same turn call `AskUserQuestion`. Never end the turn with the
plan and questions in prose: the user reads that as a finished run, and nothing gets written. Put
in the calls:

- approval of the plan, with options such as "Approve and write" and "Change the plan";
- whether to create `known-issues.md`, when it was offered;
- each `ask` claim and each placement or tracking question;
- the IMPORTANT NOTES bullets as one multi-select question, so the user approves each bullet.

One call holds at most four questions; make several calls in a row when there are more.

Before asking, check every part of the question the code can answer, and state those facts in it
(for example, whether shared code is a dependency or a copy). The user should decide, not
investigate.

When the user answers "not sure", leave the fact out of CLAUDE.md and the knowledge files, and list
it in the report with the command that would settle it. A suspected defect still goes into
`known-issues.md` (when the user chose it), marked `unverified`, with that command.

Adjust the plan to the answers. When an answer changes the plan materially, show the change and ask
again. Otherwise continue to step 4 in the same turn. To keep a file
local-only, add it to `.git/info/exclude`, not to the shared `.gitignore`. Write `/docs`, not
`/docs/`: a pattern with a trailing slash does not match a symlink.

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

Tell the user, briefly:

- the branch and commit the files describe;
- files created or changed, including any edit to `.git/info/exclude`;
- facts fixed or dropped, with the reason;
- claims left unverified, with the exact command the user can run (`! <command>`) to check them;
- security findings, such as committed secrets or keystores: location only, never the values;
- possible bugs and technical debt noticed during the survey. List them, or put them in
  `known-issues.md` if the user chose it. Do not fix them as part of onboarding;
- open questions.

Do not commit; the user reviews the files first.
