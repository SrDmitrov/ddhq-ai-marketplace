# Visual Style Reference

Uses Unicode box-drawing: `│`, `▼`, `┌`, `─`, `┐`, `└`, `┘`, `┬` and diagonal `/` `\` for branch splits.

---

## Node types

| Type | Rendering | Notes |
|---|---|---|
| Trigger / entry | `[ label ]` | Square brackets, **no box** |
| Decision node | bordered box, label ends with `?` | **Always bordered** |
| Action node | bordered box | **Always bordered** |
| Terminal | `[END]` or `[label]` | Square brackets, **no box** |

**Rule: every decision and action node MUST be surrounded by a box border. Only trigger and terminal labels use plain `[ ]`.**

---

## Connector conventions

### Downward flow
```
          │
          ▼
```

### Branch split — inverted-Y (mandatory)
Exit a decision box with `/` and `\`. YES is always left, NO is always right:
```
   └──────────────────┘
          /       \
        YES         NO
         │           │
         ▼           ▼
```
Position `/` under the left-center of the box, `\` under the right-center. Labels (`YES` / `NO`) go on the line immediately below the diagonals.

### Path merge
When a bypassed branch (NO) and a completed branch (YES action) both continue to the same next node, connect them with:
```
                │           │
                └─────┬─────┘
                      │
                      ▼
```

---

## Box sizing

- Pad content 1 space on each side: `│ content │`
- Width = longest content line + 2 spaces
- Multi-line boxes expand vertically; keep all lines left-aligned inside:
```
   ┌────────────────────┐
   │ saveApiCred()      │
   │ success Toast      │
   │ finish()           │
   └────────────────────┘
```

---

## Global shape rules

- **Always vertical-sequential** — the primary flow goes straight down the page
- **Forbidden: wide horizontal trees** — never lay out sibling checks side-by-side with equal weight
- **YES-left, NO-right** — always; never swap
- **Separate levels with a blank line** before each `▼` for readability

---

## Canonical example

The diagram below is the reference template. When in doubt, match its glyph-for-glyph style:

```
           [ Save Button Click ]
                    │
                    ▼
   ┌────────────────────────────────┐
   │  servValid && instanciaValid?  │
   └────────────────────────────────┘
              /               \
            YES                NO
             │                  │
             ▼                  ▼
   ┌──────────────────┐    ┌────────────────┐
   │ saveApiCred()    │    │  !servValid?   │
   │ success Toast    │    └────────────────┘
   │ finish()         │           /       \
   └──────────────────┘         YES        NO
             │                   │          │
           [END]                 ▼          │
                        ┌──────────────┐    │
                        │ servWSEt →   │    │
                        │ red URL err  │    │
                        │ Toast        │    │
                        └──────────────┘    │
                                │           │
                                └─────┬─────┘
                                      │
                                      ▼
                        ┌─────────────────────┐
                        │  !instanciaValid?   │
                        └─────────────────────┘
                                /         \
                              YES           NO
                               │             │
                               ▼           [END]
                     ┌──────────────────────┐
                     │ instanciaWSEt → red  │
                     │ instance err Toast   │
                     └──────────────────────┘
                               │
                             [END]
```

---

## Multi-branch (3+ outcomes)

```
   ┌────────────────────┐
   │     check role?    │
   └────────────────────┘
       /       |        \
    admin     user     guest
      │         │        │
     ...       ...      ...
```
