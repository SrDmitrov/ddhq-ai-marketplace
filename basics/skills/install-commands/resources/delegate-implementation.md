---
description: Instructions for invoking a subagent to implement an approved plan under custom rules. Main-session only; subagents must never invoke this command.
---

Invoke a subagent that uses `sonnet` model to implement the plan. Keep the main session on the current model. Provide the subagent with a handoff prompt, the complete plan file, and all relevant project rules and conventions. If the plan has phases, delegate only one phase at a time. Proceed without compacting.