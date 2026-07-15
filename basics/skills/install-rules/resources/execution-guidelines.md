# Execution Guidelines

These guidelines dictate how the AI should approach implementing tasks and writing code.

1. **Prioritize Project Rules**: When project rules/conventions/docs collide with the existing codebase, always prioritize the project's rules over the existing codebase's patterns.
2. **Respect Architecture**: Any decision regarding new feature placement must strictly follow the architectural guidelines of the project (if any).
3. **Simplicity First**: Write the minimum code needed. Avoid speculative features, abstractions, or "flexibility" that wasn't requested.
4. **Surgical Changes**: Touch only what you must. Do not refactor unrelated code, match existing styles, and clean up only the unused code created by your changes.
5. **Goal-Driven Execution**: Define verifiable success criteria. Formulate tasks as testable steps and loop independently until verified.
6. **Divide et Impera**: When planning or exploring, assess whether the work can be divided into
   self-contained subtasks and run independent ones in parallel. Do not explore the codebase inline;
   delegate scoped codebase searches and exploration to the builtin Explorer subagent using `haiku`,
   while keeping the main session on its current model.
