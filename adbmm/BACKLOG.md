# adbmm backlog

## Open: fixes and upgrades
- [ ] **Unknown `mode` value:** error (current) or silent fallback to `optimal`? Decision pending.
- [ ] `ui_tree` still cuts labels at 80 characters. Decide whether it should be uncut, as the "full detail" tool.

## Phase 2: new features
- [ ] **F2: loading awareness.** Add a `Loading:` hint to `get_state` (progress bars, empty lists, loader ids, the UI changing between two quick dumps).
- [ ] **`wait_for` by activity.** `wait_for` waits for a selector only. Add an `activity` option.
- [ ] **`run_steps` from a file.** Load the steps from a JSON file in the project, so test scripts can be kept and reused.
- [ ] **Maestro integration (future).** Run Maestro YAML flows (`maestro test <flow.yaml>`) on the emulator, as an alternative to `run_steps` for reusable, versioned test flows. It needs the Maestro CLI installed (a new external dependency), an emulator-only device guard (`--device emulator-<n>`), and a flow path restricted to the project root. Investigate install detection, output parsing, and the overlap with `run_steps`.
- [ ] **F8: `observe` on actions.** A tap reports dispatch, not effect. Candidate shape: a one-line delta. Constraint: no big responses unless clearly justified.

## Deferred
- [ ] F1: payment and credential redaction for unlabelled Compose fields. Out of scope while the tool is used only on dev builds.
