# Expected merge — co-report, degraded context, and conflicting open-question answers

Golden for the merge half of `../../SKILL.md` steps 7–10. Read, not run — merge is
Opus's semantic judgment by design (see `../../../iterate-review/examples/merge/README.md`
for why these are goldens rather than tests).

**Scenario.** A plan for adding CSV export to a reporting tool. Both lenses always
run on `iterate-plan`, so selection is unconditional. The plan is **missing its
`Acceptance criteria` section**, so the `product-manager` lens runs with degraded
context and is told so explicitly (step 5's `NOTE: required section ... is absent`
line). The plan poses one open question, `Q1`.

## Inputs

| Lens | Verdict | Findings filed | Answers `Q1` |
|---|---|---|---|
| `architect` | REVISE | Phase 2/3 sequencing inversion (HIGH), 10k cap vs. no-limit goal (HIGH), fast-goal unachievable on the request path (HIGH) | yes — **cap at 10k** |
| `product-manager` | REVISE | no Acceptance criteria section (HIGH), 10k cap vs. no-limit goal (HIGH), fast-goal unverifiable (MEDIUM) | yes — **unbounded required** |

Six findings filed, two answers to one question.

## Expected aggregate verdict: REVISE

Worst-of over `{REVISE, REVISE}`. No lens is `FAILED`. Three HIGH findings survive
the merge, so APPROVE is unavailable regardless of aggregation.

## Expected merge: 6 filed → 5 merged

### One pair merges

Both lenses filed "Phase 1's 10k-row cap contradicts the no-row-limit goal" —
same location (Phase 1 deliverable ↔ Goals (MVP)), same asserted defect. Collapse
to one finding retaining **both** lens ids.

Note the descriptions reach the same defect by different routes: `architect` via
Approach's streaming design, `product-manager` via the primary use case's row
count. Same defect, different evidence — **merge them and keep both lines of
evidence**, because each independently justifies the fix. Dropping one leaves the
fold weaker than the review was.

### Two findings on the SAME goal do NOT merge

Both lenses target `Goals (MVP)` bullet 2, "exports are fast":

- `architect`: unachievable — the synchronous request path exceeds the gateway
  timeout at the stated volume. **HIGH.**
- `product-manager`: unverifiable — no threshold, percentile, or observable. **MEDIUM.**

Same location, different defects. Fixing one does not fix the other: adding a p95
threshold makes it verifiable and still unachievable; moving generation off the
request path makes it achievable and still unverifiable. They stay separate.

This is the over-dedupe direction of plan risk **R4**, and it is a realistic trap
because both findings quote the same three words. Collapsing them would bury a
HIGH architecture claim inside a MEDIUM wording nit.

### Expected merged list

| # | Finding | Severity | Lens(es) |
|---|---|---|---|
| 1 | Phase 1's 10k-row cap contradicts the no-row-limit goal | HIGH | `architect`, `product-manager` |
| 2 | Phase 2 depends on the job queue that Phase 3 delivers | HIGH | `architect` |
| 3 | "Exports are fast" is unachievable on the request path Approach specifies | HIGH | `architect` |
| 4 | Plan has no Acceptance criteria section | HIGH | `product-manager` |
| 5 | "Exports are fast" is not verifiable | MEDIUM | `product-manager` |

Plus one `plan_correction` (duplicate Phase 3 heading number, from `architect`)
applied mechanically.

## Degraded context behaved correctly

`product-manager`'s primary finding is the **absence** of `Acceptance criteria`,
and it explicitly declines to infer criteria from the Goals section. That is the
required behaviour from `../../lenses/README.md` ("never skipped, never fed empty
context") and the lens's own degraded-context guidance.

A wrong result here is subtle and worth naming: the lens **inventing** plausible
acceptance criteria and reviewing the plan against its own invention. The review
would read as thorough and the missing section would never be reported — plan
risk **R2** (personas without matched context invent requirements) landing exactly
where the plan predicted.

## Conflicting answers to Q1 — the human decides

`Q1` asked whether the MVP caps at 10k rows or requires unbounded export. Both
lenses answered, **in direct opposition**, and both are correct in their own lane:

- `architect` is right that unbounded export is not sequenceable as the plan is
  phased — it pulls Phase 3's queue into Phase 1.
- `product-manager` is right that a 10k cap ships something that cannot serve the
  primary use case, making the MVP fail its stated purpose.

The conflict is not a defect in either answer. It is the plan's actual, unresolved
tension surfacing — which is what asking two lenses is *for*.

**Expected handling:** record both answers with attribution, state the conflict
explicitly, and escalate. Do not average them, pick the more senior-sounding lens,
or let the last-read answer win. Under `--loop` this halts on the
"fold needs human judgment" guardrail: Opus cannot resolve cap-vs-unbounded from
the plan and repo alone, because it is a product decision the plan exists to make.

> **Machinery gap this fixture found.** Step 7's merge rules covered *findings*
> only and said nothing about two lenses answering the same `question_id`. The
> rule above was added to step 7 during Phase 4 as a direct result of building
> this fixture. `iterate-review` needs no equivalent — its schema has
> `new_questions` but no `open_question_answers`, so the collision cannot arise.

## Expected pass log — one block for two lenses

```markdown
## Codex review pass 1 — answers (2026-07-28) [HISTORICAL]

### Verdict
REVISE   (worst-of architect REVISE / product-manager REVISE; no FAILED lenses)

### Findings
1. **Phase 1's 10k-row cap contradicts the no-row-limit goal** — HIGH · lens: architect, product-manager: Approach specifies streaming so size is time-bounded, Goals commits to "regardless of row count," and the primary use case is ~50k rows — but Phase 1 caps at 10k.
   → Opus: incorporated — see the Q1 resolution below; cap removed from Phase 1 and the phasing resequenced.
2. **Phase 2 depends on the job queue that Phase 3 delivers** — HIGH · lens: architect: Phase 2's background-export deliverable needs the queue Phase 3 stands up.
   → Opus: incorporated — queue moved into Phase 2.
3. **"Exports are fast" is unachievable on the request path Approach specifies** — HIGH · lens: architect: a ~50k-row export exceeds the 30s gateway timeout on the synchronous path.
   → Opus: incorporated — Approach now moves generation off the request path above 5k rows.
4. **Plan has no Acceptance criteria section** — HIGH · lens: product-manager: no goal is paired with a verifiable condition.
   → Opus: incorporated — added Acceptance criteria, one condition per goal.
5. **"Exports are fast" is not verifiable** — MEDIUM · lens: product-manager: no threshold, percentile, or volume stated.
   → Opus: incorporated — restated as p95 under 60s for a 50k-row export.

### Plan corrections applied
- Phasing, Phase 3 heading: duplicate "Phase 2" number → renumbered to Phase 3.

### Open-question answers
1. **Q1 (cap at 10k vs. unbounded) — LENSES DISAGREE, escalated to human.**
   - `architect`: cap at 10k — unbounded pulls Phase 3's queue forward and collapses the phasing.
   - `product-manager`: unbounded — the primary use case is ~50k rows, so a cap fails the plan's stated purpose.
   - Not resolvable from the plan + repo: this is a product decision. Both answers recorded; awaiting Kyle.

### New questions Codex raised
- What is the gateway timeout in the target environment? — resolvable_in_fold (lens: architect): the ingress config is in this repository, outside the sliced sections. Resolved by reading `infra/ingress.yaml`: 30s.
- What is the p95 row count of the monthly finance export in production today? — needs_lookup (lens: architect): the figure is in production data, not on disk. Queried: p95 is 47,000 rows, which puts every real export above the 10k cap.
- Is there a secondary use case the 10k cap would fully serve? — needs_human (lens: product-manager): no artefact names one; whether it exists and is worth targeting is Kyle's product knowledge. Carried to Open questions as Q2.

### Lens run summary
- architect: REVISE · product-manager: REVISE
```

## Expected checkpoint — one prompt, and loop mode halts

```
Pass 1: REVISE across architect, product-manager, 5 findings, 1 correction.
Q1 unresolved — the lenses disagree and it needs your call.
Recommendation: Continue (after resolving Q1). Choose: (C)ontinue / (V)Converge / (A)bort / (L)oop
```

Two Codex calls, one HISTORICAL block, one prompt (plan risk **R1**). Under
`--loop`, this halts on the human-judgment guardrail rather than auto-continuing,
because Q1 is unresolved.

This scenario also exercises all three `settled_by` classes in one pass, which is
why it is the reference example for question routing:

| Source | Class | Handling |
|---|---|---|
| `architect`: gateway timeout | `resolvable_in_fold` | the ingress config is **in the repo** — Opus reads it and answers. **Does not halt.** |
| `architect`: production p95 row count | `needs_lookup` | the figure is **not on disk** — needs a query. Opus performs it and answers. **Does not halt** (a *failed* query would reclassify to `needs_human` and then halt). |
| `product-manager`: secondary use case | `needs_human` | carried to Open questions — **halts the loop** |
| Q1 (cap vs unbounded), answered *in conflict* by both lenses | — | escalated as a disagreement, not a classification — **halts the loop** |

**The first two rows are the boundary that matters**, and the one the pass-1 review of
this change caught me getting wrong: *reading a repo file is `resolvable_in_fold`, not
`needs_lookup`.* `needs_lookup` is for facts that are not on disk at all. Collapsing
the two makes `needs_lookup` a synonym for "the lens couldn't see it," which would put
ordinary file reads one failed-lookup away from a spurious human escalation.

The third row is a different mechanism from the other two and must not be
conflated with them: conflicting `open_question_answers` escalate because the
lenses *disagree*, not because a class says so. A pass can halt for either reason
independently.

## What a wrong merge looks like

| Wrong output | Which failure |
|---|---|
| 6 findings, the 10k cap listed twice | **Under-dedupe** — co-reported defect not collapsed |
| 4 findings, the two "exports are fast" entries merged | **Over-dedupe** — same location keyed instead of same defect; a HIGH buried in a MEDIUM |
| Merged 10k-cap finding keeps only one lens's evidence | **Evidence loss** — both routes to the defect independently justify the fix |
| Merged 10k-cap finding tagged `architect` only | **Attribution loss** — ROI metric under-counts `product-manager` |
| `product-manager` reviews against invented acceptance criteria | **R2 realised** — degraded context filled by fabrication; the missing section goes unreported |
| One Q1 answer recorded, or the two silently reconciled | **Conflict suppressed** — the plan's real unresolved tension hidden from the human who has to decide it |
| Aggregate APPROVE, or two checkpoints | Aggregation inverted / single-checkpoint invariant broken |
