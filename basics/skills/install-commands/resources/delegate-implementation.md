---
description: Instructions for invoking a general purpose subagent with custom rules for implementation after approving a plan.
---

Invoke a subagent that uses `sonnet` model and delegate the plan implementation to it.

<guidelines>
- Main session must stay on the current model. 
- Give the invoked subagent a handoff prompt and full plan file.
- If the plan has phases, only one phase at a time should be handed off to the invoked subagent
- Proceed without compacting
</guidelines>