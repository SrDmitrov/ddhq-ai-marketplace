# Critical Constraints

These constraints are hard limits the AI must never break.

1. **Language**: Always respond in English unless explicitly asked otherwise.
2. **Git**: Never use `commit`, `push`, `merge`, `rebase`, or `reset` without explicit instruction.
3. **Filesystem**: Always run `ls -l` to verify a directory exists before creating it.
