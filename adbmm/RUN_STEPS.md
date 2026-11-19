# Writing `run_steps` scripts

`run_steps` runs a scripted test: a list of actions in one tool call. It stops at the first failure.

## Format

The `steps` argument is a JSON array. Each step is an object:

- `action`: the name of one of the allowed tools (see below).
- The other keys: that tool's arguments.

Do not put `device` in a step. Set it once on `run_steps`, or leave it out to use the session default.

```json
[
  {"action": "launch_app", "package": "com.example.app"},
  {"action": "wait_for", "text": "Log in", "timeout_s": 10},
  {"action": "tap", "resource_id": "email"},
  {"action": "input_text", "text": "qa@example.com"},
  {"action": "press_key", "key": "TAB"},
  {"action": "input_text", "text": "secret"},
  {"action": "tap", "text": "Log in"},
  {"action": "wait_for", "text": "Welcome", "timeout_s": 10},
  {"action": "network", "airplane": true},
  {"action": "tap", "text": "Refresh"},
  {"action": "wait_for", "text": "No connection", "timeout_s": 0},
  {"action": "network", "airplane": false}
]
```

## Actions

| action | args |
|---|---|
| `tap` | `text`, `resource_id` or `content_desc`; or `x`, `y`. Optional `package`. |
| `long_press` | Same as `tap`, plus `duration_ms` (default 800). |
| `swipe` | `x1`, `y1`, `x2`, `y2`, `duration_ms` (default 300). |
| `scroll` | `direction` (`up`, `down`, `left`, `right`), `amount` (0.1 to 1.0, default 0.6). |
| `input_text` | `text`. Types into the focused field. |
| `clear_text` | None. Clears the focused field. |
| `press_key` | `key`: `BACK`, `HOME`, `ENTER`, `TAB`, `DEL`, `APP_SWITCH`, `MENU`, `SEARCH`, `DPAD_UP`, `DPAD_DOWN`, `DPAD_LEFT`, `DPAD_RIGHT`, `VOLUME_UP`, `VOLUME_DOWN`, `WAKEUP`. |
| `wait` | `seconds` (max 10). |
| `wait_for` | `text`, `resource_id` or `content_desc`; optional `package`, `gone` (default false), `timeout_s` (default 5, max 15). |
| `network` | `airplane`, `wifi`, `data`: `true` or `false`. Omitted toggles are left as they are. |
| `launch_app` | `package`. |
| `launch_activity` | `component` (`package/.Activity`), `force_stop` (default false). |
| `stop_app` | `package`. |

Destructive and lifecycle tools are not allowed in a script: `uninstall_app`, `build_install`, the emulator tools, screenshots and trace.

## Matching

Selectors match as `tap` does. Text is normalized (Unicode, whitespace, case). An exact match wins over a substring match. `resource_id` matches exactly or by the suffix after `:id/`.

- `tap` and `long_press` need exactly one match. Several matches, or only fuzzy matches, fail the step and list candidates. Nothing is tapped.
- `wait_for` accepts any number of matches. Fuzzy matches do not count.

## Assertions

`wait_for` is the assertion step:

- `{"action": "wait_for", "text": "Welcome"}` waits up to 5 seconds for the text to appear.
- `"timeout_s": 0` checks once, without waiting.
- `"gone": true` waits until no element matches, for example a loading message.

## Execution

1. All steps are validated first. An unknown action, an unknown argument or a `device` key stops the run before any step executes.
2. At most 50 steps per call.
3. Steps run in order. Each reports one line: `<n> ok <action>: <result>`.
4. On the first failure the run stops. The result shows `<n> FAIL <action>: <error>`, then the current screen as `get_state` shows it.
5. When every step passes, the last line is `All <n> step(s) passed.`

Steps are passed inline in the call. Loading them from a file is in `BACKLOG.md`.
