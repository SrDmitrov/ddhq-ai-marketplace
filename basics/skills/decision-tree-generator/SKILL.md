---
name: decision-tree-generator
description: >
  Generates visual ASCII decision tree diagrams from code snippets, logic descriptions, or verbal workflows.
  Use this skill whenever the user wants to visualize branching logic, understand a conditional flow,
  map out an algorithm's decision points, or turn code/pseudocode into a readable decision diagram.
  Trigger on phrases like "decision tree", "flow diagram", "visualize this logic", "map this flow",
  "show me the branches", "draw the decision", or when the user pastes code and asks to "understand",
  "explain", or "diagram" it.
---

# Decision Tree Generator

Produce a clear ASCII decision tree from code, pseudocode, or a natural-language description of logic.
Follow the four phases below in order. The output is the diagram — not a prose explanation of it.

## Phase 1 — Isolation (Scope)

Before drawing anything, identify:
- **Trigger**: what starts the logic (function call, event, condition check)
- **Boundaries**: where the flow starts and where each terminal outcome ends — avoid drifting into unrelated side effects
- **Inputs / State**: every variable, parameter, or external value that can affect branching (flags, DB values, env vars)

If inputs are ambiguous or the user gave partial information, ask one focused clarifying question rather than guessing.

## Phase 2 — Decomposition (Logic Breakdown)

Systematically extract:
- **Predicates**: every `if`, `switch`, `while`, `try/catch`, ternary — note whether branches are `AND`/`OR`/`XAND`/`XOR` combined or nested
- **Terminal actions**: `return`, `throw`, `exit`, UI render — these become leaf nodes
- **Side effects**: logging, flag mutation, intermediate state changes — annotate these inline on the path, don't make them branches unless they alter flow

## Phase 3 — Flow Mapping (Sequencing)

Trace these three layers in order:
1. **Happy path**: the most direct route from trigger to primary success terminal
2. **Alternative branches**: every `else`, `catch`, `default`, edge case
3. **Concurrency / mutual exclusivity**: note when one check short-circuits others (guard clauses, early returns)

Represent mutual exclusivity as a single branch point, not as two separate checks.

## Phase 4 — Visual Synthesis (Output)

Use the standard style defined in `references/visual-styles.md`. The canonical example in that file is the reference template — match it glyph-for-glyph.

### Layout rules (non-negotiable)
- **All decision and action nodes MUST use box borders** (`┌─┐ │ │ └─┘`). Only triggers and terminals use plain `[ ]`.
- **Branch splits use inverted-Y** (`/` left for YES, `\` right for NO). Never use vertical-only splits from decision boxes.
- **YES is always left, NO is always right.**
- **Always vertical-sequential** — primary flow goes straight down. Forbidden: wide horizontal trees with sibling checks side-by-side.
- **Path merges** use `└─────┬─────┘` when a bypassed branch rejoins the main flow.
- Add a blank line before each `▼` arrow for visual separation.

### Content rules
- Label every branch connector: `YES / NO`, `TRUE / FALSE`, or the literal condition value (e.g., `"admin"`, `404`)
- Keep node text ≤ 40 chars — truncate with `…` if needed
- After drawing, silently re-read the original source top-to-bottom and verify each branch is represented
- Wrap the diagram in a fenced code block

### Output format

```
## Decision Tree — [short title]

[diagram here]

**Inputs:** [comma-separated list of variables/params that drive the tree]
**Terminals:** [comma-separated list of all leaf outcomes]
```

If the user only asks for the diagram (no context), omit the Inputs/Terminals section.
