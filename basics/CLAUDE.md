## General Guidelines

- If a query is ambiguous, explain why and suggest 1–3 clarifying questions instead of guessing.
- Follow KISS: prefer simple solutions over unnecessarily complex ones.
- Follow DRY: avoid duplicating code, logic, or data — every piece of knowledge should have one authoritative representation.
- If a tool fails more than once, stop and ask the user to review the issue.

### Critical Constraints

- **Language**: Always respond in English unless explicitly asked otherwise.
- **Git**: Never use `commit`, `push`, `merge`, `rebase`, or `reset` without explicit instruction.
- **Filesystem**: Always run `ls -l` to verify a directory exists before creating it.