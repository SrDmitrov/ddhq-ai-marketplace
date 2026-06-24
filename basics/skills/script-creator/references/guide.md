# Bash Script Templates Guide

This guide explains three levels of bash script complexity using the coffee-making analogy. Choose the template that matches your needs and experience level.

## Overview: Three Complexity Levels

### Simple (Junior's First Scripts)
- **When to use**: Quick automation tasks, personal scripts, one-off operations
- **Target user**: Junior dev writing their first few scripts
- **Key trait**: NO error handling, just straightforward commands
- **Time to write**: 5-15 minutes
- **Risk**: Low - simple scripts fail fast and visibly
- **Example**: `simple_example.sh`

### Intermediate (Senior's Team Tools)
- **When to use**: Team automation, repeated tasks, deployment helpers
- **Target user**: Senior dev automating for their team
- **Key trait**: Organized functions, basic error handling, user-friendly
- **Time to write**: 30-60 minutes
- **Risk**: Medium - failures are caught but not recovered
- **Example**: `intermediate_example.sh`

### Advanced (Production Team Automation)
- **When to use**: Production deployments, critical operations, complex automation
- **Target user**: Team deploying to production with safety nets
- **Key trait**: Full error recovery, state tracking, rollback capability
- **Time to write**: 2-4 hours
- **Risk**: Low - failures are caught, logged, and rolled back
- **Example**: `advanced_example.sh`

---

## SIMPLE LEVEL - No Error Handling

### When to Choose Simple

Choose simple when:
- Writing a quick automation script for yourself
- The script doesn't have critical side effects
- Failure is obvious and easily manually fixed
- Development speed matters more than robustness
- You're learning bash scripting

**Don't choose simple if:**
- This script will be used by others
- It modifies important files/systems
- It's part of a larger process
- You need to recover from partial failures

### Simple Script Structure

```
┌─────────────────────────────┐
│ Shebang & variables         │
├─────────────────────────────┤
│ Simple echo announcements   │
├─────────────────────────────┤
│ if/else for basic checks    │
├─────────────────────────────┤
│ for loops for repetition    │
├─────────────────────────────┤
│ Direct command execution    │
├─────────────────────────────┤
│ Final echo "Done!"          │
└─────────────────────────────┘
```

### Key Characteristics

- ✅ **Variables**: Basic parameter handling with `${VAR:-default}`
- ✅ **Conditionals**: Simple `if [ test ]` checks
- ✅ **Loops**: Basic `for` and `while` loops
- ✅ **Echo**: Just `echo` statements to announce steps
- ❌ **Error handling**: NONE - script fails visibly if anything goes wrong
- ❌ **Functions**: Not used
- ❌ **Logging**: No structured logging
- ❌ **Recovery**: No rollback or recovery

---

## INTERMEDIATE LEVEL - Basic Error Handling + Functions

### When to Choose Intermediate

Choose intermediate when:
- Creating scripts for your team
- The script automates important (but recoverable) tasks
- You want to organize logic into reusable functions
- Failure should be caught and reported clearly
- You want to ask users for input/confirmation

### Key Characteristics

- ✅ **Error handling**: `set -euo pipefail` at the top
  - `set -e`: Exit on any error
  - `set -u`: Exit on undefined variables
  - `set -o pipefail`: Detect errors in pipe chains
- ✅ **Functions**: Organized into logical steps
- ✅ **Logging**: Simple echo-based with prefixes
- ✅ **Main pattern**: Orchestration via `main()` function
- ✅ **Input handling**: `read` for user input, argument validation
- ✅ **Conditional execution**: `if command1 && command2 && command3`
- ❌ **State tracking**: No tracking of what's been done
- ❌ **Rollback**: No recovery from partial failures
- ❌ **Colored output**: Just basic echo messages

---

## ADVANCED LEVEL - Production-Grade Automation

### When to Choose Advanced

Choose advanced when:
- Deploying to production or critical systems
- Operations have important side effects that need rollback
- You need detailed logging for compliance/debugging
- Failure in the middle requires recovery to a known state
- Team needs to understand what happened if it fails

### Key Characteristics

- ✅ **Everything from Intermediate**, PLUS:
- ✅ **Colored logging**: Distinct colors for INFO/SUCCESS/WARNING/ERROR
- ✅ **Structured logging**: All output goes to both console and log file
- ✅ **State tracking**: Variables track what's been completed
- ✅ **Backup before critical ops**: Save state before modifications
- ✅ **Rollback mechanism**: Restore from backups if anything fails
- ✅ **Trap handlers**: Cleanup function called on exit
- ✅ **User confirmation**: Ask before critical operations
- ✅ **Progress tracking**: "Step 1/5", "Step 2/5", etc.
- ✅ **Atomic operations**: All-or-nothing (success or full rollback)
- ✅ **SCRIPT_DIR detection**: Find script location dynamically

---

## Decision Matrix

| Aspect | Simple | Intermediate | Advanced |
|--------|--------|--------------|----------|
| **Error handling** | None | Basic (set -e) | Full (trap, rollback) |
| **Functions** | None | Yes (organized) | Yes (organized + complex) |
| **Logging** | echo only | echo + prefixes | colored + file logging |
| **State tracking** | None | None | Yes (for rollback) |
| **Rollback** | None | None | Yes (full recovery) |
| **User confirmation** | None | Maybe | Yes (critical ops) |
| **Development time** | 5-15 min | 30-60 min | 2-4 hours |
| **Safe for team** | ❌ | ✅ | ✅✅ |
| **Safe for production** | ❌ | ⚠️ | ✅ |
| **Learning curve** | Easy | Medium | Hard |
