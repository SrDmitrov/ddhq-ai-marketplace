# poketokenbar-utils

Makes the [PokeTokenBar](https://github.com/chattymin/PokeTokenBar) floating pet follow Claude Code activity. It packages the hooks from the upstream [Agent activity](https://github.com/chattymin/PokeTokenBar#agent-activity) guide, so you do not need to edit `~/.claude/settings.json` by hand.

## Requirements

- macOS 14+ with PokeTokenBar installed and running (`brew install --cask chattymin/tap/poke-token-bar`).
- In PokeTokenBar: floating pet enabled, and **Settings → Floating Pet → React to agent activity** on.

When PokeTokenBar is not running (or on other platforms), the hook exits silently. A global install is safe on every machine.

## Install (all projects)

```
/plugin marketplace add <path-or-repo-of-ddhq-mkpl>
/plugin install poketokenbar-utils@ddhq-mkpl --scope user
```

## Behavior

| Claude Code event | Pet state |
|---|---|
| `UserPromptSubmit`, `PostToolUse` | `working` (bobs) |
| `PreToolUse` on `AskUserQuestion`, `Notification` (`permission_prompt`, `elicitation_dialog`) | `waiting` (speech bubble) |
| `Stop` | `done` (runs to cursor, then home) |
| `SessionEnd` | `idle` |

- Each session is labelled with its project folder name. Two sessions in the same folder share one label.
- The idle-reminder notification is skipped, so no "waiting" bubble appears after every turn.
- `Stop` does not fire when you interrupt a turn with Esc. The pet keeps working until the next event, the 10-minute timeout, or session end.
- If you set up the upstream manual hooks before, remove them from `~/.claude/settings.json` to avoid duplicate events.
