# Sub-agents

These rules govern how the AI should spawn and configure subagents.

1. **Explorer Subagents**: Delegate scoped codebase searches and exploration to the builtin Explore subagent, passing explicitly type, model and effort (they are NOT inherited): `Agent(subagent_type: "Explore", model: "haiku", effort: "medium", ...)`, while keeping the main session on its current model.
2. **Worker Subagents**: A subagent that creates or edits content (code or documents) based on a plan or instructions from the main session, rather than only exploring and reporting, is a worker. Spawn any worker (builtin or custom) passing explicitly model and effort (they are NOT inherited), by default `sonnet` and `medium`, e.g. `Agent(subagent_type: "general-purpose", model: "sonnet", effort: "medium", ...)`. Never go below these unless the user explicitly overrides them.
3. **Subagent Effort**: When spawning any subagent (including the builtin `general-purpose` and `Explore`), always set the `effort` parameter according to the size and complexity of the delegated task. The default is `effort: "medium"`.
