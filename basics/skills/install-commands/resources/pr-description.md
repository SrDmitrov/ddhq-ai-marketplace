---
description: Create a description for a future Pull Request based on the changes made in the current branch, or in the source branch given as argument.
argument-hint: [source-branch]
---

## 0. Determine the source branch

- If `$ARGUMENTS` is provided, it is the source branch. Otherwise, ask the user whether to use the current checked-out branch or another branch, and if another, which one.
- For another branch, verify it exists with `git rev-parse --verify <branch>`; if it is not found locally, try `origin/<branch>`. If neither exists, stop and ask the user.
- If the source branch is the current checked-out branch, run the steps below in the current working directory.
- Otherwise, do not check out the branch in the current working directory. Create a temporary worktree instead:
  - `dir=$(mktemp -d) && git worktree add --detach "$dir" <branch>`
  - Run all the steps below inside `$dir`, so documents and code are read as they are on the source branch.
  - When done, or if you stop early for any reason, remove it with `git worktree remove --force "$dir"`.
  - If the worktree cannot be created, stop and tell the user the error.

## 1. Get the task description

- Look for a `bugs/` or `proposals/` directory. They are expected under `{project_root}/docs/`, but that is only an assumption: if they are not there, search the rest of the project.
- If one exists, find the document that matches the source branch (by branch name, ticket ID, or topic) and extract the task description from it.
- If no description is available (neither directory exists, no document matches, or several match equally), stop and ask the user to provide the description of the task. Do not guess and do not continue without it.

## 2. Analyze the changes

- Identify the target branch: the project's main development branch. It is probably named `develop` or `development`, but it can be different. It is never `main` or `master`. Check the existing branches (`git branch -a`) and the project documentation. If it cannot be determined with confidence, stop and ask the user.
- Run `git diff <target>...<source>` and `git log <target>..<source>` to compare the source branch against the target branch.
- Treat it as a PR and create a description with bullet points about the changes.

## 3. Write the description

- Target is external reviewers without context of the project.
- The description must be self-contained: it will be pasted into the "Description" text box of a PR, so anything outside it will not be available to the reader. Do not reference external files (e.g. the `bugs/` or `proposals/` document); include the relevant content itself.
- Output in Spanish, in a single fenced Markdown block in the session, that follows the template exactly. Do not create a file (not even inside the temporary worktree) or open a PR.

<template>

```markdown
### Tarea

{{Descripción de la tarea, extraída de bugs/proposals o facilitada por el usuario.}}

### Descripción

{{Resumen de 3-4 líneas de los cambios realizados en la rama de origen comparada con la rama principal de desarrollo. Deben ir relacionados con la tarea y ser comprensibles para un revisor externo.}}

### Desarrollo

{{Bullet points detallando los cambios realizados, incluyendo nuevas funcionalidades, mejoras, correcciones de errores y cualquier otro cambio relevante. Máximo 1-2 líneas por bullet point.}}
```

</template>
