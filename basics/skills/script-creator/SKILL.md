---
name: script-creator
description: Bash script generation following a three-level complexity system (Simple, Intermediate, Advanced). Use when the user explicitly asks to create or write a bash script. Default to 'Simple' if level is not specified. DO NOT use this skill if you (the agent) are creating a script for your own internal tasks; use standard tools instead.
---

# Script Creator

Follow this workflow when a user asks to create a bash script.

## Selection Logic

1. **Simple** (Default): Personal, one-off, or quick automation. No error handling.
2. **Intermediate**: Team tools, shared scripts. Uses functions and `set -euo pipefail`.
3. **Advanced**: Production automation, critical operations. Features rollbacks, colored logging, and state tracking.

If the user didn't specify a level, assume **Simple**.

## Implementation Workflow

1. **Consult the Guide**: Read `references/guide.md` to confirm the characteristics of each level.
2. **Review Examples**: 
   - Simple: `references/simple_example.sh`
   - Intermediate: `references/intermediate_example.sh`
   - Advanced: `references/advanced_example.sh`
3. **Use Skeletons**: Use the corresponding skeleton from `assets/` as your base:
   - `assets/simple_skeleton.sh`
   - `assets/intermediate_skeleton.sh`
   - `assets/advanced_skeleton.sh`
4. **Fulfill Request**: Adapt the skeleton to the user's specific requirements while maintaining the structural integrity and best practices of the chosen level.

## Critical Constraint

This skill is for fulfilling **user requests** for scripts. If you are an agent creating a script to solve a task autonomously (e.g., a data processing script you need for your own execution), skip this skill and use `write_file` directly with your own logic.
