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

The server runs in a terminal, not in Android Studio, so it does not see the IDE's settings (SDK path, Gradle JDK). It inherits the Claude Code env and passes it to `gradlew`.

Set the env per project in `.claude/settings.local.json`. Claude Code keeps that file out of git. JDK and SDK paths differ per machine, and credentials must never be committed. Use absolute paths.

```json
{
  "env": {
    "JAVA_HOME": "/path/to/jdk-17",
    "ANDROID_HOME": "/path/to/Android/sdk"
  }
}
```

| Variable | Need | Purpose |
|---|---|---|
| `JAVA_HOME` | Required | JDK that runs Gradle. Match the project's Gradle JDK in Android Studio (for example Corretto 17). |
| `ANDROID_HOME` | Recommended | SDK location. Falls back to the OS default (see below). |
| `ANDROID_AVD_HOME` | Optional | AVD location, if not `~/.android/avd`. |
| `ADBMM_IDLE_SHUTDOWN_MIN` | Optional | Minutes without an adbmm tool call before a headless emulator started by the server is stopped (default 5, `0` disables). Its live flow ends first; the flow log stays in `trace_dir`. |
| `GRADLE_OPTS`, `ORG_GRADLE_PROJECT_<prop>` | Optional | Gradle JVM options and project properties, such as private repository credentials. |

On macOS, `/usr/libexec/java_home -V` lists the installed JDKs. A project JDK in `settings.local.json` overrides a system `JAVA_HOME`.

The server looks for `adb` and `emulator` in this order:

1. `ANDROID_HOME`, then `ANDROID_SDK_ROOT`. A leading `~` is expanded.
2. The OS default SDK path: `~/Library/Android/sdk` on macOS, `~/Android/Sdk` on Linux, `%LOCALAPPDATA%\Android\Sdk` on Windows.
3. `PATH`.

`JAVA_HOME` has no fallback. `build_install` fails if it is unset.

The project root is `CLAUDE_PROJECT_DIR`, or the current directory if unset. Screenshots go to `<root>/screenshots`.

## Tools

Tool names are `mcp__plugin_adbmm_adbmm__<tool>`. Agents must use these tools, not the `adb` CLI from Bash: the Bash sandbox cannot reach the adb server, and the CLI bypasses the emulator-only guard.

- Devices: `list_devices`, `use_device`, `list_avds`, `start_emulator`, `stop_emulator`, `kill_emulator`, `device_info`
- Build and app: `build_install`, `launch_app`, `launch_activity`, `stop_app`, `uninstall_app`, `list_app_activities`
- Observe: `get_state`, `screenshot`, `screenshot_masked`, `ui_tree`, `current_activity`, `notifications`, `logcat`, `dumpsys`
- Input: `tap`, `long_press`, `swipe`, `scroll`, `input_text`, `clear_text`, `press_key`, `unlock`, `wait`, `wait_for`
- Network: `network` (airplane mode, wifi, mobile data)
- Scripted test: `run_steps` (a list of actions in one call, stops at the first failure)
- Trace: `trace_flow`, `trace_end`, `trace_status`, `trace_save`, `http_calls`

`run_steps` runs a scripted test: a list of actions in one call. See [RUN_STEPS.md](RUN_STEPS.md) for the step format, the allowed actions and their arguments.

A headless emulator started by the server stops when it is idle (see `ADBMM_IDLE_SHUTDOWN_MIN`) and when the server exits. A windowed one is left running.

`trace_flow(title, trace_dir, tags=[...], package=...)` records only the given logcat tags and/or one app (by app uid, so an app restart keeps recording).

`http_calls(source, slow_ms=1500, marker_tags=[...])` summarizes the OkHttp calls of a flow: one line per call (time, method, path, status, ms, size, `SLOW`), then totals. `source` is a flow title, or a `.log`/`.txt` (`-v threadtime`) or `.logcat` (Android Studio export) file in the project or temp dir. `marker_tags` lines (for example the app's navigation tags) are shown between the calls. It needs the app's `HttpLoggingInterceptor` and never shows headers or bodies.

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
      "mcp__plugin_adbmm_adbmm__wait_for",
      "mcp__plugin_adbmm_adbmm__trace_status",
      "mcp__plugin_adbmm_adbmm__http_calls"
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
