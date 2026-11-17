# adbmm backlog

## Open: fixes and upgrades
- [ ] **F12: the element cap is used up by unlabelled layout elements.** Drop elements with no label and no id that are only scrollable or focusable, or move them to the end, before applying the cap. Otherwise real items hide behind layout noise.
- [ ] **F3: widget state.** Add `[checked]`, `[selected]` and `[disabled]` flags. Include disabled clickable nodes, marked `[disabled]`. Today checkbox and selection state is not visible.
- [ ] **F9: dedup drops meaningful values.** Remove only consecutive duplicates, and suppress only exact label matches, not substrings. Today the `Text:` line can lose amounts next to their labels.
- [ ] **F5: diacritic-insensitive matching** (NFD, then strip combining marks) in tiers 1 and 2. Today a query without accents returns candidates only.
- [ ] **F7: `Package:`/`Activity:` header lags the screen.** Derive these from the dump's root package, or flag the mismatch.
- [ ] **F6: label merge and unlabelled icon buttons.** Cap merged labels for containers that are also scrollable. Give unlabelled buttons context from their nearest labelled ancestor, for example `id=button_add in "Item name"`.
- [ ] **Unknown `mode` value:** error (current) or silent fallback to `optimal`? Decision pending.
- [ ] `ui_tree` still cuts labels at 80 characters. Decide whether it should be uncut, as the "full detail" tool.
- [ ] Unit test for the element-list cap and the `- ... (+N more)` line in `get_state`.

## Phase 2: new features
- [ ] **F2: loading awareness.** Add a `Loading:` hint to `get_state` (progress bars, empty lists, loader ids, the UI changing between two quick dumps).
- [ ] **`wait_for(selector | activity, timeout_s <= 15)`** to replace the blind `wait`.
- [ ] **F8: `observe` on actions.** A tap reports dispatch, not effect. Candidate shape: a one-line delta. Constraint: no big responses unless clearly justified.

## Deferred
- [ ] F1: payment and credential redaction for unlabelled Compose fields. Out of scope while the tool is used only on dev builds.
