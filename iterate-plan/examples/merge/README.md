# Multi-lens merge fixtures

Worked examples for the merge half of the per-pass loop (`../../SKILL.md`
steps 7–10). Read, not run — merge is Opus's semantic judgment by design; see
`../../../iterate-review/examples/merge/README.md` for the reasoning, which
applies identically here.

## Scenarios

| Scenario | Verdicts in | Aggregate | Pins |
|---|---|---|---|
| [`01-co-report-and-degraded-context`](01-co-report-and-degraded-context/) | REVISE, REVISE | REVISE | Co-report collapses while keeping **both** lenses' evidence; two findings on the same goal with different defects stay separate; degraded context is *flagged, not filled in* (R2); two lenses answering one `question_id` in opposition is escalated, not reconciled |

## What differs from the iterate-review side

Three things, all consequences of reviewing a plan rather than a diff:

1. **Selection is unconditional.** Both lenses run on every pass, so there is no
   routing to pin — `iterate-plan` has no equivalent of `../../../iterate-review/examples/selection/`.
2. **Degraded context is a real path.** A lens whose `requires_sections` are absent
   runs anyway and must flag the gap. That behaviour is the whole reason plan risk
   R2 has a mitigation, and scenario 01 pins it.
3. **`open_question_answers` can collide.** Two lenses can answer the same
   `question_id`, and can disagree. `iterate-review`'s schema has no answer field,
   so this is `iterate-plan`-only.

## Machinery changed by building these

Scenario 01 was written first and exposed two gaps in step 7, both fixed during
Phase 4:

- Merge rules covered `findings` only — nothing said two lenses answering the same
  `question_id` must be recorded with the disagreement surfaced rather than
  silently reconciled.
- Nothing said `plan_corrections` need deduping. Since corrections are applied
  **mechanically**, a duplicate could double-apply the same edit. The parallel rule
  for `code_corrections` was added to `iterate-review` at the same time to keep the
  shared machinery in semantic parity.

Worth recording because it is the argument for fixtures existing at all: both gaps
had been through plan review and two code reviews without being noticed. Writing
down what the *correct* output is forced the question of what the rules actually
said.

## File conventions

Same as the `iterate-review` side: `pass-1.<lensid>.response.json` per lens,
schema-valid against `../../reviewer-output.schema.json` and checked by
`tools/check-examples.py`; `expected-merge.md` holding inputs, aggregation
reasoning, the merged list with attribution, the expected HISTORICAL block, the
expected checkpoint, and a wrong-result table.
