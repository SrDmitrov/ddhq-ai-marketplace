# adbmm

ADB middle man. An MCP server that lets the agent drive Android emulators for integration tests and QA.

It is emulator-only by design. Serials must match `emulator-<n>`, so a plugged-in phone is never driven. Credential values are redacted from UI dumps. Screenshots of credential screens are refused or masked.

## Install

Install it per project, from the Android project root:

```
/plugin marketplace add <path-or-repo-of-this-marketplace>
/plugin install adbmm@ddhq-mkpl --scope project
```

Restart Claude Code. `/mcp` should list `plugin:adbmm:adbmm` as connected.

## Requirements

- `uv` (runs the server as a PEP 723 script and resolves its dependencies).
- Android SDK with `adb` and `emulator`.
- A JDK for `build_install`.
- `gradlew` at the project root. Run Claude Code from the Android project root.

The first start resolves dependencies with `uv`. If that is slow, raise `MCP_TIMEOUT` in your Claude Code env.

## Environment

The server inherits the Claude Code env. Set these in your shell or in `.claude/settings.json`:

```json
{
  "env": {
    "ANDROID_HOME": "/path/to/Android/sdk",
    "JAVA_HOME": "/path/to/jdk"
  }
}
```

`ANDROID_SDK_ROOT` works instead of `ANDROID_HOME`. If neither is set, `adb` and `emulator` must be on `PATH`.

The project root is `CLAUDE_PROJECT_DIR`, or the current directory if unset. Screenshots go to `<root>/screenshots`.

## Tools

Tool names are `mcp__plugin_adbmm_adbmm__<tool>`.

- Devices: `list_devices`, `use_device`, `list_avds`, `start_emulator`, `stop_emulator`, `kill_emulator`, `device_info`
- Build and app: `build_install`, `launch_app`, `launch_activity`, `stop_app`, `uninstall_app`, `list_app_activities`
- Observe: `get_state`, `screenshot`, `screenshot_masked`, `ui_tree`, `current_activity`, `notifications`, `logcat`, `dumpsys`
- Input: `tap`, `long_press`, `swipe`, `scroll`, `input_text`, `clear_text`, `press_key`, `unlock`, `wait`
- Trace: `trace_flow`, `trace_end`, `trace_status`, `trace_save`

`build_install(variant="debug", module="app")` runs `:<module>:install<Variant>`. Only debug variants are accepted, so release and signing tasks stay unreachable.

## Permissions

Suggested allowlist for the read-only tools, in `.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "mcp__plugin_adbmm_adbmm__list_devices",
      "mcp__plugin_adbmm_adbmm__list_avds",
      "mcp__plugin_adbmm_adbmm__device_info",
      "mcp__plugin_adbmm_adbmm__get_state",
      "mcp__plugin_adbmm_adbmm__ui_tree",
      "mcp__plugin_adbmm_adbmm__current_activity",
      "mcp__plugin_adbmm_adbmm__trace_status"
    ]
  }
}
```

## Tests

```
cd server
uv run --with pytest --with "pillow>=10,<12" --with mcp==1.28.1 pytest -q test_adbmm.py
```

See `BACKLOG.md` for open items.
