---
description: Create a description for a future Pull Request based on the changes made in the current branch, or in the source branch given as argument.
argument-hint: [source-branch]
---

## 0. Determine the source branch

- If `$ARGUMENTS` is provided, it is the source branch. Otherwise, ask the user whether to use the current checked-out branch or another branch, and if another, which one.
- For another branch, verify it exists with `git rev-parse --verify <branch>`; if it is not found locally, try `origin/<branch>`. If neither exists, stop and ask the user.
- Never check out the source branch or create a worktree: this command only reads. If the source branch is not the checked-out one, read it without a checkout, using `git diff`, `git log`, `git ls-tree -r --name-only <branch>` and `git show <branch>:<path>`.

## 1. Get the task description

- Look for a `bugs/` or `proposals/` directory. They are expected under `{project_root}/docs/`, but that is only an assumption: if they are not there, search the rest of the project. Search the current working copy first, because task documents are often not committed on the source branch. If the source branch is another branch, also search it with `git ls-tree`.
- If one exists, find the document that matches the source branch (by branch name, ticket ID, or topic) and extract the task description from it. A folder may have been named before a ticket existed, so a missing ticket ID in the name is not proof that no document matches.
- If no description is available (neither directory exists, no document matches, or several match equally), stop and ask the user to provide the description of the task. Do not guess and do not continue without it.

## 2. Analyze the changes

- Identify the target branch: the project's main development branch. It is probably named `develop` or `development`, but it can be different. It is never `main` or `master`. Check the existing branches (`git branch -a`) and the project documentation. If it cannot be determined with confidence, stop and ask the user.
- Run `git diff <target>...<source>` and `git log <target>..<source>` to compare the source branch against the target branch.
- Treat it as a PR and create a description with bullet points about the changes.

## 3. Write the description

- Target is external reviewers without context of the project.
- The description must be self-contained: it will be pasted into the "Description" text box of a PR, so anything outside it will not be available to the reader. Do not reference external files (e.g. the `bugs/` or `proposals/` document); include the relevant content itself.
- Start with a concise one-line title (no trailing period) summarizing the change for an external reviewer.
- Output in Spanish, in a single fenced Markdown block in the session, that follows the template exactly. Do not create a file or open a PR.

<template>

```markdown
## {{Título conciso de una línea que resuma el cambio.}}

### Tarea

{{Descripción de la tarea, extraída de bugs/proposals o facilitada por el usuario.}}

### Descripción

{{Resumen de 3-4 líneas de los cambios realizados en la rama de origen comparada con la rama principal de desarrollo. Deben ir relacionados con la tarea y ser comprensibles para un revisor externo.}}

### Desarrollo

{{Bullet points detallando los cambios realizados, incluyendo nuevas funcionalidades, mejoras, correcciones de errores y cualquier otro cambio relevante. Máximo 1-2 líneas por bullet point.}}
```

</template>
