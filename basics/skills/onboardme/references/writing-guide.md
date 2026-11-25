# Writing guide for CLAUDE.md and docs/knowledge/

How to fill [CLAUDE.template.md](../assets/CLAUDE.template.md) and
[knowledge-doc.template.md](../assets/knowledge-doc.template.md).

## Contents

- Global rules
- Section-by-section rules for CLAUDE.md
- Format of the linked documents
- Where facts come from
- What does not belong
- Verifying existing content
- Self-check

## Global rules

- The root `CLAUDE.md` is an index, not a manual: keep it under ~60 lines and push detail into
  `docs/knowledge/`. Anything a reader can get from the code itself does not belong here. CLAUDE.md
  is loaded into every session, so each line costs tokens on every request.
- H1 is the project name (`# El-Pibe`) or `# CLAUDE.md`. The line under it is always:
  `This file provides guidance to Claude Code when working with code in this repository.`
- No code snippets in `CLAUDE.md`. Reference code as `path/file.py:38-66` in backticks.
- Bold the things that must not be missed (external systems, MUST NOTs). Do not bold whole lines.
- Drop any section that would be empty. A project with no knowledge base inlines Key Technologies
  and Architecture instead of linking them.
- CLAUDE.md lives at the repository root, so every link into the knowledge base starts with
  `docs/knowledge/`. Links between knowledge files are relative (`other-file.md`).

## Project Overview

One paragraph, 2–5 lines. Answer, in order: what the system is, who uses it, what the user does with
it, and which external systems it depends on. Bold each external system on first mention
(**Stripe**, **Microsoft Dynamics NAV**). Name the language/framework and the module layout in the
same breath when it is unusual (`single-module Gradle project (app/) targeting API 27–29`).
No history, no roadmap.

## Key Technologies

Two accepted shapes — pick by size:

- **Bullets with bold labels** (few, heterogeneous items): `- **Networking:** …`. Sub-bullets name
  the library and what it is used for, including migrations in progress.
- **`Layer | Technology` table** (a full stack): one row per layer — API, Auth, Database, Queues,
  App server, Payments, Push, Email.

Close with where exact versions live (`requirements.txt`, `build.gradle`) and flag deprecated or
commented-out dependencies. Never list version numbers inline — they rot.

## Knowledge Base

Only if `docs/knowledge/` exists. One line of framing plus a flat bullet list, one bullet per file:

```
- [Key Technologies](docs/knowledge/key-technologies.md) — stack & key dependencies.
```

Rules: link text equals the target's H1; the hook after the em dash is a noun phrase, lower-case,
one line, ending in a period; order files by reading order (stack → integrations → architecture →
endpoints → flow → conventions); every file in the directory appears exactly once. Keep the
imperative `Read the relevant file before working in that area.` — it is what makes the section
work: Claude reads the file on demand instead of guessing.

## Architecture

1. **Pattern** — one bullet, one sentence, and say what is *not* used when a reader would assume it
   (`Activity-based MVC — no formal MVVM/MVP framework`).
2. **Package table** — heading names the root (`### Key packages under com.example.app`), columns
   `Package | Role`. Path in backticks with a trailing slash. Role says what lives there plus the
   one class that matters (`Utils.java — SharedPreferences keys`). One row per top-level package;
   do not recurse.
3. **Conventions** — short `###` subsections, 1–3 lines each, only for rules not derivable from the
   code: UI locale and string file, what drives navigation, mandated thread-safety pattern.

## IMPORTANT NOTES

Hard constraints only — a rule Claude can break destructively or expensively. Not style advice, not
conventions (those go above). Each bullet: bold subject, em dash, reason, then who does it instead.

- Use `MUST NOT` for forbidden actions, and always name the fallback: `Ask the user to run them and
  request feedback.`
- Include the environment facts that a local mental model gets wrong — where the database actually
  lives per environment, what is absent from the servers after deploy.
- Aim for 4–6 bullets. A long list means something belongs in `coding-conventions.md`.

## Format of the linked documents

Applies to every file under `docs/knowledge/`.

- **One topic per file**, kebab-case filename, H1 equal to the link text in `CLAUDE.md`. Under ~110
  lines. Do not repeat what `CLAUDE.md` already says.
- **Lead with the rule**, then the data. A routing table opens with how routes are generated; an
  integrations file opens with where all wrappers live and that they are mocked centrally.
- **Tables for enumerations**, always two or three columns: `Method | Path`, `App |
  Responsibility`, `Layer | Technology`, `Parameter | Value`, `Term | Meaning`. Group long tables
  under `##` headings by domain.
- **Fenced ```text blocks** for directory layouts and navigation graphs, with trailing `#` comments
  on the lines that need explaining.
- **Numbered lists for flows** — one step per hop, each naming the concrete class or endpoint. Start
  with a one-line pipeline (`Nginx → Gunicorn → Django → DRF ViewSet → …`), then the worked example.
- **Constraints as `DO NOT` / `MUST NOT`** under a `#### Constraints` heading, each with its reason.
- **Index documents** (Postman collections, request models) carry the collection UID and link at the
  top, a staleness warning, and a `✅`/`❌` status column. They index; they do not document.
- **Cross-link siblings** by relative path (`see [External Integrations](external-integrations.md)`)
  rather than restating them.
- **Business-context files** state their scope in the subtitle — `Complements the code; does not
  describe it.` — and stay free of class names.

Typical files, in reading order (create only those with real content):

| File                         | Covers |
|------------------------------|--------|
| `key-technologies.md`        | stack per layer, where versions live, migrations in progress |
| `external-integrations.md`   | third-party systems, wrappers, credentials location, mocks |
| `architecture.md`            | layers, module graph, request or navigation flow |
| `endpoints.md` / `navigation.md` | routes, screens, how they are generated |
| `<domain>-flow.md`           | one business flow, step by step |
| `coding-conventions.md`      | rules a reviewer enforces that the linter does not |

## Where facts come from

Read the source, not memory or the README alone. The README is often stale; treat it as a lead to
verify.

| Section | Primary sources |
|---------|-----------------|
| Project Overview | README, manifest/app name, main entry point, API clients |
| Key Technologies | `build.gradle*`, `package.json`, `requirements*.txt`, `pyproject.toml`, `go.mod`, `Dockerfile` |
| Architecture | top-level source tree, DI/module setup, router or navigation graph |
| External integrations | HTTP clients, SDK initialisation, env/config keys, `settings*.py`, `.env.example` |
| IMPORTANT NOTES | deploy scripts, CI config, per-environment settings, migrations, existing CLAUDE.md |
| Commands (build, test, lint) | CI workflow files, `Makefile`, `package.json` scripts, Gradle tasks |

## What does not belong

- Anything derivable by reading one file (class lists, method signatures, every dependency).
- Generic best practices ("write tests", "use meaningful names").
- Rules already in `.claude/rules/`, the user's global `~/.claude/CLAUDE.md`, or a parent CLAUDE.md.
  Duplicates drift apart; link or skip instead.
- Version numbers, dates, ticket numbers, history and roadmap.
- Secrets and credential values. Name where they live, never what they are.

## Verifying existing content

When the project already has a CLAUDE.md or `docs/knowledge/`, every claim is a hypothesis until
checked. Old docs are the most common source of confident wrong answers.

| Claim type | How to check |
|------------|--------------|
| Path / package | the file or directory exists at that path |
| Line range (`file:38-66`) | the range still holds the described code; update the numbers if it moved |
| Class / function | a search finds the symbol with that role |
| Command | the script, task or target exists in the build or CI files |
| Dependency / technology | declared in the build files and not commented out |
| Constraint / environment fact | backed by config, CI or deploy scripts; otherwise ask the user |

Classify each claim:

- **keep** — verified, carry it over as is.
- **fix** — the fact still holds but details changed (moved path, renamed class); carry the
  corrected version.
- **drop** — the code contradicts it, or it belongs in "What does not belong".
- **ask** — not verifiable from the repo (business rules, production environment facts). Ask the
  user; never keep or drop silently.

## Self-check

Run before reporting. Fix every failure.

- [ ] CLAUDE.md is ~60 lines or fewer and has no code snippets.
- [ ] H1 and the fixed guidance line are present.
- [ ] Every file in `docs/knowledge/` is linked exactly once, in reading order, with link text equal
      to its H1.
- [ ] Every path and line range mentioned in any file exists.
- [ ] No empty section, no placeholder `<…>` left.
- [ ] IMPORTANT NOTES has 4–6 hard constraints, each `MUST NOT` naming a fallback.
- [ ] Each knowledge file is under ~110 lines, one topic, rule first.
- [ ] No version numbers, secrets, or content duplicated from `.claude/rules/` or global CLAUDE.md.
