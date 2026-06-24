# Interaction Rules

These rules govern when the AI should stop acting independently and consult the user.

1. **Resolve Ambiguity Early**: Inconsistencies and ambiguities must be resolved in the Plan phase.
2. **Present Architectural Choices**: The user must be given the option to make a decision when colliding architectural or design paths exist.
3. **Stop on Repeated Failures**: If a tool fails more than once (e.g., failing tests or linter errors after a change), stop making assumptions and ask the user to review the issue.
4. **Think Before Coding**: Don't assume or hide confusion. Explicitly state assumptions, surface tradeoffs, and ask clarifying questions before implementing.
