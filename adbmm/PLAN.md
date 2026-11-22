# adbmm Session Token Reduction & Skill Lazy-Loading Plan

## Goal

Reduce the session-start token overhead of the adbmm MCP server by:
1. **Extracting the usage guide to `HOW_TO_USE.md`** in `adbmm/` root, serving as the body for a future lazy-loaded skill (`how-to-use-adbmm`).
2. **Trimming the server `INSTRUCTIONS` block** down to a minimal pointer (~4 lines), avoiding unneeded context in sessions that do not interact with Android emulators.
3. **Trimming tool docstrings** across the 15 most verbose tools to be concise, surgical, and non-redundant.

---

## Background & Rationale

- **Current always-loaded overhead**: FastMCP injects the server `INSTRUCTIONS` (75 lines) and all 33 tool docstrings (~180 lines total) into the model's context at the start of every session (~3,000 tokens).
- **Lazy-loading solution**: Antigravity/agent skills are discovered via lightweight metadata (name + description) and loaded on-demand. By moving the detailed harness, rules, edge cases, and workflows into a standalone guide/skill, sessions that do not use the emulator pay zero overhead, and emulator sessions load instructions only when needed.

---

## Audit: Overlap and Redundancy

### Repeated Concepts Across INSTRUCTIONS and Tool Docstrings

| Concept | Appears in | Occurrences |
|---|---|---|
| "Bash sandbox can't reach adb server" | `INSTRUCTIONS`, `list_devices`, `get_state` | 3 |
| Selector matching rules (exact → substring → fuzzy) | `INSTRUCTIONS`, `tap`, `long_press`, `wait_for`, `run_steps` | 5 |
| `resource_id` matching ("by suffix after `:id/`") | `INSTRUCTIONS`, `tap`, `run_steps` | 3 |
| Credential field redaction & screenshot refusal | `INSTRUCTIONS`, `screenshot`, `screenshot_masked` | 3 |
| Emulator lifecycle (reuse, headless, kill confirmation) | `INSTRUCTIONS`, `start_emulator`, `stop_emulator`, `kill_emulator` | 4 |
| `run_steps` action list | `run_steps` docstring, `RUN_STEPS.md` | 2 |
| Build retry rule (fix once, stop on second failure) | `INSTRUCTIONS`, `build_install` | 2 |
| `get_state` modes (optimal/full, line truncation) | `INSTRUCTIONS`, `get_state` | 2 |
| Compose label merging behavior | `INSTRUCTIONS`, `get_state` | 2 |
| `trace_flow` protocol (once per flow, scratchpad dir) | `INSTRUCTIONS`, `trace_flow` | 2 |
| `Package:` / `Activity:` semantics & focus lag | `INSTRUCTIONS`, `get_state` | 2 |

### Tools Already Concise (No Changes Needed)

`use_device`, `list_avds`, `swipe`, `scroll`, `input_text`, `clear_text`, `press_key`, `unlock`, `wait`, `stop_app`, `uninstall_app`, `current_activity`, `notifications`, `dumpsys`, `trace_end`, `trace_status`, `device_info`, `list_app_activities`, `launch_app`, `launch_activity`.

### Tools to Trim (15 Tools)

`get_state`, `tap`, `long_press`, `screenshot`, `screenshot_masked`, `start_emulator`, `build_install`, `run_steps`, `trace_flow`, `http_calls`, `wait_for`, `list_devices`, `logcat`, `network`, `trace_save`, `ui_tree`.

---

## Specification of Changes

### 1. New Usage Guide (`adbmm/HOW_TO_USE.md`)

Create `HOW_TO_USE.md` in the root of `adbmm` containing the consolidated guide:
- **Rules**: Exclusive tool usage; CLI/Bash sandbox restrictions.
- **Tool Roles**: `get_state` as primary observation; `screenshot` as orientative; `tap`/`long_press` selector-first; `run_steps` batching.
- **Selector Matching**: Exact (tier 1) → Substring (tier 2) → Fuzzy candidate listing (tier 3); suffix matching for `resource_id`; tap vs `wait_for` handling.
- **Coordinate System**: Device pixels; scaling factor calculations.
- **`get_state` Details**: Output lines, flags, Compose child merging, `optimal` vs `full` modes, lockscreen detection.
- **Credential Safety**: Redaction rules, `screenshot_masked` consent flow, unlabelled Compose limits.
- **Emulator Lifecycle**: Auto-reuse vs headless cleanup, kill confirmations.
- **Build and Deploy**: Sequential workflow, debug-only restriction, 2-failure retry rule.
- **Trace and Logging**: `trace_flow` lifecycle, tagging, HTTP logging inspection, sanitized persistence via `trace_save`.
- **`run_steps` Scripting**: Overview of batching format, linking to `RUN_STEPS.md`.

### 2. Trimmed Server `INSTRUCTIONS` (`adbmm/server/adbmm.py`)

Replace lines 42–116 with:

```python
INSTRUCTIONS = """\
adb emulator control for Android emulators only. \
Read the `how-to-use-adbmm` skill / HOW_TO_USE.md before first use — it covers \
tool roles, selector matching, credential safety, emulator lifecycle, \
build/deploy, trace workflows, and run_steps scripting. \
Critical: never use `adb` or `emulator` from Bash; the sandbox cannot reach \
the adb server.\
"""
```

### 3. Trimmed Tool Docstrings (`adbmm/server/adbmm.py`)

- **`get_state`**:
  ```python
  """Primary observation: package, activity, interactive elements, static text. One call.

  mode="optimal" (default): max 10 entries, 80-char cut. mode="full": max 20, uncut.
  Element lines carry center=(x,y) in device pixels. See the skill for format details.
  """
  ```
- **`tap`**:
  ```python
  """Tap by selector (takes its own UI dump) or raw x, y. Verify the reported pkg.

  One exact/substring hit -> tap. Multiple or fuzzy -> candidates, nothing tapped.
  """
  ```
- **`long_press`**:
  ```python
  """Long-press; same selector and coordinate rules as tap."""
  ```
- **`screenshot`**:
  ```python
  """Orientative screenshot, downscaled by `scale` (1-4, default 2). Prefer get_state for text.

  Refuses if credential fields are visible — use screenshot_masked. save_as persists to
  screenshots/<name>.png.
  """
  ```
- **`screenshot_masked`**:
  ```python
  """Screenshot with credential fields blacked out. Use after screenshot refused.

  Requires user approval (keep out of the permission allowlist).
  """
  ```
- **`start_emulator`**:
  ```python
  """Start an emulator (or reuse a running one) and set it as session device. Waits for boot.

  headless=True: no window, killed on server exit. reuse=False: force a new instance.
  """
  ```
- **`build_install`**:
  ```python
  """Build a debug variant with Gradle and install on the emulator. Log goes to temp dir.

  Only debug variants accepted. After 2nd consecutive failure: stop and report the log.
  """
  ```
- **`run_steps`**:
  ```python
  """Batch actions in one call; stops at first failure. Max 50. See the skill / RUN_STEPS.md.

  Steps: [{"action": "<tool>", ...args}]. No `device` per step. Validated before execution.
  On failure, appends get_state of the screen.
  """
  ```
- **`trace_flow`**:
  ```python
  """Record logcat of one QA flow into trace_dir/logcat-<title>.log. One call per flow.

  tags/package filter the log. trace_dir must be absolute, inside /tmp. Ends on trace_end
  or next trace_flow. See the skill for the full trace workflow.
  """
  ```
- **`http_calls`**:
  ```python
  """Summarize OkHttp calls of a flow or log file: one line per call, then totals.

  source: flow title, or .log/.txt/.logcat file. marker_tags: interleave navigation lines.
  """
  ```
- **`wait_for`**:
  ```python
  """Wait until a selector appears (gone=True: disappears). Polls up to timeout_s (max 15).

  timeout_s=0 checks once (assertion). Any number of exact/substring hits counts.
  """
  ```
- **`list_devices`**:
  ```python
  """List connected devices/emulators (state == 'device')."""
  ```
- **`network`**:
  ```python
  """Toggle airplane/wifi/data on/off, then report states. Omitted toggles unchanged."""
  ```
- **`logcat`**:
  ```python
  """Dump recent logcat (snapshot, not stream). Capped at 500 lines. tag filters by tag name."""
  ```
- **`trace_save`**:
  ```python
  """Copy flow logs to dest_dir with secrets masked. dest_dir must be absolute."""
  ```
- **`ui_tree`**:
  ```python
  """Full UI hierarchy dump. Prefer get_state unless the full tree is needed."""
  ```

---

## Token Impact

| Component | Before (est. tokens) | After (est. tokens) | Savings |
|---|---|---|---|
| INSTRUCTIONS block | ~1,800 | ~80 | ~1,720 |
| Tool docstrings (15 trimmed tools) | ~1,200 | ~400 | ~800 |
| **Total Always-Loaded** | **~3,000** | **~480** | **~2,520 (~84%)** |
| `HOW_TO_USE.md` (on-demand) | 0 | ~1,500 (when activated) | — |

---

## Verification Plan

1. **Automated Unit Tests**:
   ```bash
   cd adbmm/server
   uv run --with pytest --with "pillow>=10,<12" --with mcp==1.28.1 pytest -q test_adbmm.py
   ```
2. **Content Parity**: Verify that all operational rules, security restrictions, and syntax guides previously in `INSTRUCTIONS` exist in `HOW_TO_USE.md`.
3. **Stand-alone Usability**: Confirm trimmed docstrings contain sufficient guidance for straightforward tool invocations without requiring the skill for simple tasks.
