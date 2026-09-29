# Scenario 02 — simplification card on a plan mechanism, with the cluster section

Pins `../../../SKILL.md` step 8's component streak and **simplification
card** on the plan side: a plan mechanism as the component (identity is the
mechanism, never the D-number it sits under), two findings on one label in
one pass counting as **one** observation, a card whose per-finding
accounting resolves one of this pass's two same-label findings (→
`incorporated (by simplification)`) and not the other (→ an ordinary
fold), other labels folding meanwhile, *split the plan* in the escape-hatch
slot, and step 10's **cluster section** on the stall/cap card the same pass
reaches. Read, not run, per this directory's convention (`../README.md`).

Built from a real review — ResearchLogix_v2's CSRF hardening plan review
(2026-09-24), where the SQL-parsing classifier for the GET write lock drew
the architect's HIGH on passes 4, 5, 6, 8, 9 and 10 and was removed at pass
10 under a standing instruction from the human. Under this skill's card it
is presented at pass 6.

## Committed record — passes 4 and 5, as sealed in the plan

```
## Codex review pass 4 — answers … [HISTORICAL]
1. **SQL write classification lacks a fail-closed path** — HIGH · lens: architect: …
   → Editor: incorporated — inverted to a read allow-list … [introduced_by_pass: null] [component: get-lock-sql-classifier]

## Codex review pass 5 — answers … [HISTORICAL]
1. **Leading-keyword classifier does not prove SQL is read-only** — HIGH · lens: architect: …
   → Editor: incorporated — stated as syntactic; L1b read-only transaction added … [introduced_by_pass: 4] [component: get-lock-sql-classifier]
```

Committed streak for `get-lock-sql-classifier` after pass 5: **2**. The
label names the mechanism; D4 is where the plan *describes* it, and it
keeps the same label if D4 is renumbered.

**Lens responses, pass 6:** [`pass-6.architect.response.json`](pass-6.architect.response.json)
(one HIGH, one MEDIUM, one correction) and
[`pass-6.product-manager.response.json`](pass-6.product-manager.response.json)
(two HIGH). No FAILED lens.

## Pass 6 — merge and classification

| # | Finding | Sev · lens | Label |
|---|---|---|---|
| 1 | L2 rejects L1b's own read-only transaction command | HIGH · architect | `get-lock-sql-classifier` |
| 2 | Comment lexing is underspecified at a security boundary | MEDIUM · architect | `get-lock-sql-classifier` |
| 3 | Compliance sentence overstates pre-authentication protections | HIGH · product-manager | `compliance-sentence` |
| 4 | G3 contradicts the intentional console failure-state change | HIGH · product-manager | `g3-user-visible-change` |

Candidate streak for `get-lock-sql-classifier` = committed 2 + 1 = **3**
(findings 1 and 2 are **one** observation). The card is written before
either is folded; findings 3 and 4 fold meanwhile.

## Pass 6 — the card, pending then resolved

```markdown
### Decision cards

- **simplification** (`get-lock-sql-classifier`, pass 6, streak 3): streak findings — pass 4 #1 HIGH (architect, introduced_by_pass: null); pass 5 #1 HIGH (architect, introduced_by_pass: 4); pass 6 #1 HIGH (architect, introduced_by_pass: 5); pass 6 #2 MEDIUM (architect, introduced_by_pass: 4); 3 of this streak's 4 findings are fold-caused.
  recommendation — **simplify (remove)**: delete the SQL-parsing classifier (READ/WRITE/UNKNOWN model, read allow-list, comment lexing); make no read-vs-write judgement from SQL text. Guarantee lost: per-statement classification of what an unlisted GET runs. Covering layer: MySQL's read-only transaction (L1b) for single-statement reads, the GET script manifest pinning which scripts a GET may run, and the L2 test-time monitor. Per-finding: pass 4 #1 — resolves (nothing parses, so nothing fails open; MySQL decides); pass 5 #1 — resolves (the read-only transaction rejects writes whatever the leading keyword); pass 6 #1 — does not (L2 still observes L1b's own `SET` command and needs its own exemption); pass 6 #2 — resolves (no lexer remains to specify).
  alternatives — **fold once more** (specify the comment grammar and exempt L1b's command). · **split the plan**: move D4's GET write lock into its own plan and ship this one without it. · **simplify (narrow)**: classify single statements only and route every multi-statement script through the manifest. Guarantee lost: script-level classification. Covering layer: the manifest. Per-finding: pass 4 #1 — does not (unparseable single statements still need a fail-closed rule); pass 5 #1 — does not; pass 6 #1 — does not; pass 6 #2 — does not (the lexer stays).
  chosen: (pending)
```

Resolution write, then dispositions **by remove's accounting**:

```markdown
  chosen: simplify (remove) — classifier deleted from D4; single-statement reads go to MySQL's read-only transaction, scripts to the manifest.
retired: get-lock-sql-classifier (removed by simplification card, pass 6)

1. **L2 rejects L1b's own read-only transaction command** — HIGH · lens: architect: …
   → Editor: incorporated — L2 ignores a statement only when byte-identical to the one L1b constant, never by reclassifying SET (remove does not resolve this one, so it takes the ordinary fold). [introduced_by_pass: 5] [component: get-lock-sql-classifier]
2. **Comment lexing is underspecified at a security boundary** — MEDIUM · lens: architect: …
   → Editor: incorporated (by simplification) — no lexer remains; covered by the classifier's removal, no separate patch. [introduced_by_pass: 4] [component: get-lock-sql-classifier]
```

## Checkpoint — stall + cap, with the cluster section

HIGH+MEDIUM 4 → 5 → 5 (not strictly decreasing across two transitions)
and pass 6 is the last of the budget, so the loop hands back with the
non-convergence stall card. Its cluster section:

```
Cluster (HIGH/MEDIUM, passes 4–6, by component):
- get-lock-sql-classifier — p4 HIGH · p5 HIGH · p6 HIGH + MEDIUM — streak 3
- compliance-sentence — p6 HIGH — streak 1
- g3-user-visible-change — p6 HIGH — streak 1
- `get-lock-sql-classifier` at 3 — simplification card presented at pass 6, chosen: simplify (remove)
```

The stall card's own options are unchanged; the section only shows that
the mechanism behind the stall has already been decided on.

## What a wrong result looks like

| Wrong output | The misreading that produces it |
|---|---|
| Label `d4-get-write-lock`, or a new label after D4 is renumbered | Location defining identity; the label names the mechanism |
| Candidate streak 4 at pass 6 | Two same-label findings counted as two observations |
| No card until pass 10 | The streak reset by the stall card, or by pass 5's needs_human card — checkpoint events are never observations, and neither card is a card answer on this label |
| Finding 1 marked `incorporated (by simplification)` | Incorporation by association — remove's accounting says it does not resolve finding 1 |
| Finding 2 given its own patch after the removal | One implementation fold covers every finding the chosen operation resolves |
| *accept the risk* on the card | `iterate-plan`'s card offers *split the plan* in that slot |
| The stall card's options changed by the cluster section | The section is information; it changes no guardrail's condition or outcome |
