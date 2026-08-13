# Multi-lens merge fixtures

Worked examples for the merge half of the per-pass loop (`../../SKILL.md`
steps 11–14): semantic dedupe, worst-of verdict aggregation, `FAILED` handling,
lens attribution, and the single-checkpoint invariant.

## These are goldens, not tests

Selection routing is mechanical, so `../selection/` ships a script that runs it.
Merge is **Opus's semantic judgment by design** — the rule is "collapse findings
that target the same location and assert the same defect," and *same defect* is
not computable from the JSON. Scripting it would either re-implement judgment
badly or degrade the rule into the location-keyed dedupe the plan explicitly
rejected (Q3).

So these fixtures are read, not run. Their job is to make a regression
**recognisable**: each `expected-merge.md` ends with a "what a wrong result looks
like" table naming the specific misreading that produces each wrong output.

Use them by feeding the per-lens responses to a merge step and comparing against
the golden — during a live pass, when changing the shared machinery, or when
reviewing a change to either skill's merge prose.

## Scenarios

| Scenario | Verdicts in | Aggregate | Pins |
|---|---|---|---|
| [`01-dedupe-and-worst-of`](01-dedupe-and-worst-of/) | REVISE, REVISE, **APPROVE** | REVISE | Co-report collapses to one finding retaining both lens ids; two findings at the *same location* with *different defects* stay separate (R4, both directions); an approving lens does not pull the aggregate up |
| [`02-failed-lens-preserves-block`](02-failed-lens-preserves-block/) | **BLOCK**, **`FAILED`**, REVISE | BLOCK | `FAILED` is a REVISE **floor, not an assignment** — it must not downgrade a completed BLOCK; Converge unavailable; `(R)etry` offered; partial output from a failed lens is not salvaged |
| [`03-register-match-gates`](03-register-match-gates/) | REVISE | REVISE | `register_ref` validation's three gates (provenance, behavior, trust-boundary) evaluated **per-finding, not per-register-entry** — two findings sharing one `register_ref` get different dispositions; the complete-logical-bullet digest recipe, computed concretely, correctly changes when a wrapped continuation line is amended |
| [`04-accepted-risk-lifecycle`](04-accepted-risk-lifecycle/) | REVISE | REVISE | `accepted-risk` full lifecycle (`proposed`→`confirmed`/`rejected`→`reopened`, terminal re-disposition under a new id) against the accounting table state by state; design-shaped-fold escalation halts *immediately* (unlike accepted-risk's continue-and-batch), with mechanism/non-mechanism boundary cases including a genuinely-ambiguous one; posture-dependency digest invalidation is two-sided (a confirmation invalidates only when its *named* fields change, computed concretely with real sha256 values) |

Between them they cover every merge-side item in the plan's acceptance criteria:
dedupe, worst-of, `FAILED` handling, attribution, one HISTORICAL block, one
checkpoint, and both loop-mode halt conditions that depend on merge output.
Scenarios 03 and 04 cover the Risk Posture & Proportionality initiative's
register-match (Phase 1) and accepted-risk/escalation (Phase 2) mechanisms.

## File conventions

- `pass-1.<lensid>.response.json` — one synthetic Codex response per lens, matching
  what the real run writes to `state/<scope-hash>/`. Schema-valid against
  `../../reviewer-output.schema.json` (enforced by `tools/check-examples.py`).
- `pass-1.<lensid>.response.json.malformed` — a deliberately invalid response
  representing a failed lens. The suffix keeps it out of JSON validation; the
  invalidity is the point.
- `input.diff` — the diff under review, when the scenario doesn't reuse one from
  `../selection/`.
- `expected-merge.md` — inputs, expected aggregate verdict with reasoning, expected
  merged list with attribution, the expected pass-log block, the expected
  checkpoint, and the wrong-result table.

Responses are pretty-printed for reviewability. The real runtime writes
single-line JSON; the difference is formatting only.

## Adding a scenario

Pick **one** rule you want protected and build the smallest lens combination that
would break if it were misread. Scenario 02 is the model: it exists because
"raises to at least REVISE" has a plausible wrong reading that silently discards a
BLOCK, and no amount of prose in `SKILL.md` prevents someone implementing the
plausible one. A scenario that merely exercises the happy path protects nothing.
