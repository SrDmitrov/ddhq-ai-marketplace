---
description: Instructions for invoking a subagent to implement an approved plan under custom rules.
---

Invoke a subagent with this type and model: `Agent(subagent_type: "general-purpose", model: "sonnet", ...)`. It's task is to implement the plan. Keep the main session on the current model. Provide the subagent with a handoff prompt, the complete plan file, and all relevant project rules and conventions. If the plan has phases, delegate only one phase at a time. Proceed without compacting.