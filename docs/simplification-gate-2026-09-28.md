# Simplification Gate — Plan

## TL;DR

When a trinity loop keeps finding fault with the *same component* pass after pass, each fold patching one more edge case, the loop is telling us the design is wrong, not the wording. Today nothing in either loop skill notices this: the HIGH+MEDIUM stall counter keeps moving because every fold produces a *new* distinct finding, and every escape so far has come from Kyle, outside the loop, saying "stop refining and simplify." This plan makes that instruction structural.

Both `iterate-plan` and `iterate-review` gain a **component tag** on every finding (Phase 0, the data half) and a **simplification decision card** that fires when one component draws HIGH/MEDIUM findings on three consecutive passes (Phase 1, the gate). The card recommends removing, narrowing or replacing the component, states what guarantee is lost and which remaining layer covers it, and lists "fold it one more time" as an alternative, never the recommendation. The gate only ever presents a card: it never auto-stops a loop and never auto-simplifies anything. This closes issue #6, whose data-gated revisit condition is now met.

Expected outcome: the 8-, 11-, 12- and 16-pass loops recorded in ResearchLogix_v2 this month become 4- to 6-pass loops with a design decision in the middle, and the fold-caused share of findings (currently 37%) falls because fewer folds are spent patching a mechanism that should have been deleted.

## Why / Context

**The failure mode, in the record.** Six ResearchLogix_v2 loops from September 2026 show the same shape:

| Loop | Passes | Clustered component | Passes it drew findings on | How it ended |
|---|---|---|---|---|
| CSRF plan review (`iterate-plan`) | 12 | SQL-parsing classifier for the GET write lock | 4, 5, 6, 8, 9, 10 | Kyle's standing instruction at pass 10: "if the architect does not approve, decide what to simplify" → classifier deleted (Q7), converged pass 12 |
| impersonation-c1b (`iterate-review`) | 11 | reload-loop guard, then its replacement recovery mechanism | 3, 4, 5, 6, 7 then 8, 9, 10 | pass-7 card chose a redesign whose disposition reads "there is no guard"; the replacement then drew three consecutive HIGHs |
| edit-only-delegate-proxy-grants | 16 | toggle ownership; tenant picker | 7–10; 12–15 | ground through on folds |
| credential-tokens-phase-1 | 8 | the vacuity species in proof cells | recurring 3× | ground through on folds |
| CSRF code review | 4 | sign-in bootstrap race | 1, 2, 3 | **rule applied**: mount-time fetch removed at pass 3, converged pass 4 |
| login-catch-throwable | 5 | ValidationException carve-out | 3, 4 | **rule applied**: carve-out removed, converged pass 5 |

The last two ran under the prose rule ResearchLogix adopted on 2026-09-25 (`docs/hardening-playbook.md` §7, "When one component keeps drawing findings, simplify it instead of passing again"). It worked both times. This plan ports that rule into the skills themselves, where it applies to every repo and does not depend on a builder remembering a playbook paragraph.

**Why the existing guardrails miss it.** The non-convergence guardrail compares the merged HIGH+MEDIUM *count* across passes. In every loop above the count kept changing because each fold produced a new, distinct, real finding on the same mechanism, so the counter saw progress where a human saw churn. Issue #6 records that this guardrail "never once correctly identified a stall," while "was this finding created by the previous fold?" was hand-recorded as the stop signal in every long pass log.

**Why now.** Issue #6 was punted from Trinity v2.4 on 2026-08-21, gated on "several builds' worth" of `introduced_by_pass` data so the stop condition could be designed against aggregated evidence rather than hand-mined prose. As of 2026-09-28 ResearchLogix_v2 holds 71 instrumented reviews, 408 annotated findings (153 fold-caused, 37%), and 71 state files with per-pass `fold_caused_count`. The gate is met, and the prose rule has two successful firings to design from.

## Who / Use cases

- **Kyle as loop operator.** At the third consecutive pass on one component, he receives one card with a concrete simplification, the guarantee it costs, and the layer that still covers it, instead of discovering the churn himself at pass 10 and improvising a standing instruction. Success: the decision arrives at pass 3–4 with the evidence already assembled.
- **The editor session (Claude) folding findings.** It gets a rule for *when to stop folding and escalate*, matching the existing design-shaped-fold escalation: pause at that finding, present the card, wait. Success: no fourth patch is ever written onto a mechanism that has drawn three passes of findings without a human choosing that.
- **Builder agents in downstream repos (ResearchLogix_v2's Jervis, doc-bot).** They inherit the gate through the skill rather than through a repo playbook. Success: the playbook paragraph can be reduced to a pointer.
- **Future-Kyle reading a pass log.** Component tags make a log greppable for "which mechanism ate this review," the question every retrospective so far has answered by hand.

## Risk posture

### Full variant (initiatives)

#### PF-audience — Audience & reach

Kyle, as the single operator, plus every Claude/Codex session running the trinity loops across his repos (ResearchLogix_v2 is the heaviest consumer: 71 instrumented reviews since 2026-09-02). The repo is public, but external readers are passive consumers — nothing in these skills executes for them. One outside contributor (Matt Stein, read-only) has landed a PR.

#### PF-blast — Blast radius & recoverability

A defective skill change degrades the review process itself, and the worst failure mode is *silent* — a gate that fires too early stops a review immediately before a load-bearing finding (issue #6's stated regression risk), and a gate that never fires looks exactly like today. The skill files revert trivially via git; the real cost is un-reviewed defects reaching downstream builds, or a real mechanism removed on a false streak, before anyone notices. The existing `introduced_by_pass` / `fold_caused_count` instrumentation is the detection mechanism for this class.

#### PF-shipbar — Ship bar

Any change that could cause a loop to terminate early, suppress a finding, or remove/narrow a mechanism **without a human decision point** blocks ship — the convergence gate and the decision-card contract are the trust boundary, and full rigor applies there regardless of posture. The gate must only ever *present a card*; it never auto-stops and never auto-simplifies. Streak-threshold tuning, component-label wording, card copy, and instrumentation can ship with logged accepted risks.


<!-- ─────────────────────────────────────────────────────────────
REGISTER SHAPE REFERENCE (not part of this plan — informational).
The accepted-risks register lives at `docs/risk-posture.md` in this
repo, created or appended to by create-plan when an author dictates
an accepted risk at scaffold time (author action is its own
confirmation — no separate human-confirm step, unlike an editor's
`accepted-risk` fold proposal during automated review in iterate-plan
or iterate-review, which does require one). Entries are narrow and
named, never blanket suppressions, and
use allocation-free date-slug ids so concurrent branches can't
collide on a counter:

  ## Accepted risks

  - **RR-2026-08-06-seq-poison** — client-supplied seq can poison one
    draft for ≤24h; recoverable via discard; accepted 2026-08-06.

Duplicate ids in the file are a malformed source; ids are never
reused or renamed once referenced.
───────────────────────────────────────────────────────────────── -->

## Goals (MVP)

- Every finding in both skills' HISTORICAL blocks carries a `[component: <label>]` tag beside `[introduced_by_pass: N]`, assigned by the editor at fold time under written labeling rules.
- Both skills' per-pass state summaries record the components seen this pass and each component's current consecutive-pass streak; `tools/cluster_tracker.py` pins the counting semantics executably, fixture-tested by `tools/check-cluster-streak.py`, the same pattern as `freeze_tracker.py`.
- Both skills present a **simplification card** at fold time when a component's HIGH/MEDIUM streak reaches 3, before folding that pass's finding on it. Recommendation: remove, narrow or replace. Alternatives include "fold once more" and, in `iterate-plan`, "split the plan." Never an auto-stop.
- The existing non-convergence and max-pass-cap cards gain a cluster check: HIGH/MEDIUM findings grouped by component, streaks shown, so the cap becomes the trigger for the check rather than the only signal.
- The card shows fold-provenance as corroboration ("N of this streak's findings are fold-caused"), consuming `introduced_by_pass` for the first time, which lifts the "no guardrail may consult it" reservation in both SKILL.md files.
- Parity between the two skills is pinned by new `tools/check-parity.py` rules.
- Issue #6 is closed by this plan, with its constraints carried over: always a card, options include delete-the-mechanism and split-the-plan, never auto-stop.

## Non-goals (MVP)

- **No auto-stop and no auto-simplify.** The gate presents; the human decides. This is the ship bar, not a tuning choice.
- **No change to convergence math.** Worst-of verdicts, the HIGH guardrail, the HIGH+MEDIUM counter and the Converge predicates are untouched; the cluster check is *added to* the existing cards, not substituted for them.
- **No pure fold-provenance trigger.** Issue #6's original framing (halt when consecutive passes produce only fold-caused findings) is not built; provenance is shown on the card as evidence, not used as a trigger. Rationale: fold-caused findings are sometimes load-bearing (the #6 regression risk), whereas "same component, three passes" is what actually fired and what humans hand-recorded.
- **No retro-tagging of existing pass logs.** Tags are forward-only.
- **No runner changes.** The runners compose and invoke; tagging and streak counting are editor fold-time judgments pinned by a reference module, exactly as freeze tracking is.
- **No changes to `create-plan`.**

## Approach

The design is a direct port of ResearchLogix's clustering rule into the two skills' existing machinery, using three things the skills already have: the per-finding provenance tag (v2.4 §5) as the model for a per-finding component tag, the freeze tracker (v2.4 §4) as the model for a streak tracker, and the decision-card contract (v2.3/v2.4) as the delivery vehicle. Nothing new is invented at the trust boundary; a sixth card type joins the five that exist.

### §1 Component tags (both skills, Phase 0)

Each finding's `→ Editor:` line gains `[component: <label>]` after `[introduced_by_pass: N]`. The label is a short stable slug for the *mechanism the finding targets*, chosen by the editor at fold time, when the causal chain is freshest, the same judgment moment provenance already uses.

Labeling rules, written into both SKILL.md fold steps:
- **Same mechanism, same label**, regardless of how the finding is worded or which lens raised it. The CSRF classifier drew six findings with six different titles; all six are `get-lock-sql-classifier`.
- **A replacement mechanism gets a new label.** When impersonation-c1b's reload guard was redesigned away at pass 7, the recovery mechanism that replaced it is a new component with a fresh streak. This is what makes the rule fire again correctly on passes 8–10.
- **Narrowing is not replacement.** A mechanism that was reduced but kept retains its label.
- **When uncertain, use the file or function name** the finding cites. Under-clustering is the conservative error: a missed streak costs one more pass, a false streak costs a spurious card.
- Corrections (`code_corrections` / plan corrections) are not tagged; only merged findings count.

### §2 Streak tracker (both skills, Phase 0)

`tools/cluster_tracker.py` is a reference implementation in the style of `freeze_tracker.py`: not invoked by any runner, pinning the counting semantics so prose ambiguity can't reopen them. A pass is represented as `("failed",)` or `("findings", {label: worst_severity})`. Semantics:
- The streak for a label counts **consecutive completed passes** on which that label appears on at least one HIGH or MEDIUM merged finding. LOW findings never count.
- A pass on which the label appears only on LOW findings, or not at all, **resets** the streak to 0.
- A FAILED-lens pass is **skipped**: it neither counts nor resets (the same rule the freeze tracker uses, for the same reason: a lens that didn't run says nothing about the component).
- The gate fires when the streak reaches `CLUSTER_N = 3`, on the third pass, before that pass's finding on the label is folded.
- After a **simplify** outcome the label is retired; a replacement gets a new label and a fresh streak (§1).
- After a **fold once more** outcome the streak is *not* reset; it keeps counting, and the card is re-presented on every further pass on that label.

`tools/check-cluster-streak.py` fixture-pins the boundary cases: first pass counts as 1; LOW-only pass resets; FAILED pass skips; two labels in one pass track independently; retire-and-replace starts a fresh streak; continue-anyway keeps counting.

Both skills' state summaries (`summary_schema` 1 → 2) add per pass: `components: {label: {"severity": ..., "fold_caused": bool}}` and `streaks: {label: n}`. `tools/provenance-recipe.jq` gains a `cluster_hits` query (labels that reached 3 across the accumulated state files, and what was chosen) so the measurement in §5 is a `jq` run, not a re-read.

### §3 The simplification card (both skills, Phase 1)

A sixth named human-judgment moment, under the existing shared card contract. It fires **at fold time**, at the finding that brings a label's streak to 3, exactly like the design-shaped-fold escalation: the editor pauses at that finding, does not fold it, writes the card to the pass log with `chosen: (pending)`, and presents it.

Card content, all fields required:
- The three (or more) findings in the streak, each with pass number, lens, severity and fold-provenance, so the human sees the pattern rather than trusting the count.
- **Recommendation: simplify** — remove, narrow or replace the component, with a concrete sketch. Required sub-fields: *the guarantee lost* and *which remaining layer covers it* (or "none," stated plainly). A card without both is malformed and is not presented.
- **Alternatives** (up to three, per the cardinality rule): *fold once more*; *replace with a named cheaper mechanism* when one exists; in `iterate-review` *accept the risk* when the posture permits, in `iterate-plan` *split the plan* so the component moves to its own plan with its own review. "Fold once more" is always listed and never the recommendation.
- **discuss**, never counted, never omitted.

Outcome mapping: *simplify* → the fold removes/narrows/replaces; the finding is dispositioned `incorporated (by simplification)`, the label retires, and the next pass reviews the simplified head. *Replace* → `incorporated (via alternative)`, new label. *Fold once more* → ordinary fold, streak continues, card returns next pass on that label. *Accept the risk* → the existing `accepted-risk` lifecycle, `AR-<n>`, unchanged. *Split the plan* (`iterate-plan` only) → the component's decisions and questions move to a new plan stub; this plan's text references it; loop resumes on what remains. *discuss* → paused.

The card is written and resolved in two phases like every other card (pending write before presentation, resolution write on answer), so an interrupted session re-presents it on resume.

### §4 Cluster check on the existing cap and stall cards (both skills, Phase 1)

When the max-pass cap or the non-convergence guardrail fires, the card gains a **cluster section**: HIGH/MEDIUM findings from the last three passes grouped by component with each label's streak, and an explicit line either "no component has a streak ≥ 2" or "`<label>` at 2 — one more pass on it triggers the simplification card." This is the ResearchLogix rule's second half ("at the six-pass cap, run the same cluster check before offering another pass"), and it turns the cap into a trigger for the check rather than a bare budget number.

### §5 Measurement contract

Success is judged on future loops in ResearchLogix_v2 (the cohort with instrumentation), not on this repo's own review of this plan. Measures, all computable by `tools/provenance-recipe.jq` from state files:
- **Pass count** of reviews where the card fired, against the pre-rule long-loop baseline (8, 11, 12, 16).
- **Card outcome mix**: simplify / replace / fold-once-more / accept / split. A rule whose cards are always answered "fold once more" is a false-positive generator and gets its threshold raised.
- **False-positive signal**: cards where "fold once more" was chosen *and* the next pass had no finding on that label. If this exceeds one in three cards over the first ten firings, `CLUSTER_N` moves to 4 — a one-line change, recorded here as the rollback condition, not a re-litigation.
- **Fold-caused share** of findings across the cohort, currently 37%, expected to fall.

This is a learning goal, never a ship gate.

### Repo layout

New: `tools/cluster_tracker.py`, `tools/check-cluster-streak.py` (wired into `tools/check-all.sh`). Modified: `iterate-review/SKILL.md` (steps 12, 14, 16), `iterate-plan/SKILL.md` (steps 8, 10, and the state-file section), both `state/example*.json`, `tools/provenance-recipe.jq`, `tools/check-provenance-recipe.py`, `tools/check-parity.py` (new rules), `README.md`, `CHANGELOG.md`.

## Phasing

### Phase 0 — Component tags + streak tracker (the data half) (~4h)
**Deliverables:**
- `[component: <label>]` tag and labeling rules (§1) in both SKILL.md fold steps, beside the provenance tag; HISTORICAL block template updated in both.
- `tools/cluster_tracker.py` + `tools/check-cluster-streak.py` (§2), wired into `check-all.sh`.
- State summary `summary_schema` 2 with `components` and `streaks` per pass, in both skills; both example state files updated; readers tolerate schema-1 files (missing fields read as empty).
- `tools/provenance-recipe.jq` `cluster_hits` query + its checker fixture.
- Parity rules: tag placement, labeling rules, LOW-excluded, FAILED-skips.

**Acceptance:**
- `tools/check-all.sh` green, including the new checker with every §2 boundary case pinned.
- A worked example in each SKILL.md (the impersonation-c1b sequence: guard passes 3–7, redesign, recovery passes 8–10) reproduces the tracker's output.
- The "no guardrail may consult `introduced_by_pass`" sentence is *still present* at the end of Phase 0: this phase collects, it does not gate.

**Iterate-review:** YES (rationale: touches the fold path in both skills and adds a fixture-pinned tracker tool; wrong tagging rules silently under- or over-count streaks)
**Status:** not started

### Phase 1 — Simplification decision card + checkpoint wiring (~5h)
**Deliverables:**
- The simplification card (§3) as the sixth named human-judgment moment in both skills: trigger, required fields, alternatives, outcome mapping, two-phase persistence, resume behavior.
- New disposition wording `incorporated (by simplification)` recognized in both skills' accounting tables (it is an `incorporated` for every ledger).
- Cluster section on the cap and stall cards (§4), both skills.
- The `introduced_by_pass` reservation sentence in both SKILL.md files replaced with: consumed as card evidence only, never as a trigger.
- Parity rules: card fields, "fold once more never the recommendation," never auto-stop, split-the-plan is `iterate-plan`-only (a per-skill rule).

**Acceptance:**
- `tools/check-all.sh` green; parity 2/2 shared files, all rules.
- Both example pass logs / merge fixtures include one simplification card in pending and resolved form.
- A dry read-through of the CSRF code review's passes 1–3 against the new SKILL.md text produces the card at pass 3 with the same recommendation Kyle actually chose.

**Iterate-review:** YES (rationale: this is the trust boundary — the card is the only new human decision point, and both skills' Converge/checkpoint logic changes; parity-pinned across skills)
**Status:** not started

### Phase 2 — Closeout — issue #6, CHANGELOG, README, doc sweep (~1h)
**Deliverables:**
- `CHANGELOG.md` 2.5.0 entry; README's card list and stop-condition prose updated; the pre-merge doc sweep across README, both SKILL.md files, `tools/README.md`, and memory.
- Issue #6 closed with a comment linking the archived plan and stating what was and was not built (no pure provenance trigger).
- ResearchLogix_v2 follow-up noted (not done here): reduce the playbook's clustering paragraph to a pointer once the skill ships there.

**Acceptance:**
- Closeout checklist below fully checked; plan archived.

**Iterate-review:** NO (rationale: docs-only; no code surface to review)
**Status:** not started


## Acceptance criteria

- [ ] Both skills tag findings with `[component: <label>]` under identical labeling rules, parity-pinned.
- [ ] `tools/cluster_tracker.py` + `tools/check-cluster-streak.py` exist, pass, and are wired into `check-all.sh`.
- [ ] State summaries at `summary_schema` 2 carry `components` and `streaks`; schema-1 files still read.
- [ ] The simplification card fires at streak 3, before the fold, with all required fields, in both skills; "fold once more" is always an alternative and never the recommendation.
- [ ] No path exists by which the gate stops a loop or removes a mechanism without a card being answered by a human.
- [ ] Cap and stall cards show the cluster section.
- [ ] `provenance-recipe.jq` answers the §5 measures from accumulated state files.
- [ ] Issue #6 closed; CHANGELOG 2.5.0; README current.

## Risks

### R1 — Label drift: the same mechanism gets different labels across passes, so the streak never forms
**Mitigation:** the labeling rules in §1, a worked example in each SKILL.md, and the cluster section on the cap card (§4), which shows labels side by side so a human can spot two names for one thing. Under-clustering costs one extra pass, which is today's behavior, not a regression.

### R2 — The card fires immediately before a load-bearing finding (issue #6's regression risk)
**Mitigation:** the gate presents a card and never stops anything; "fold once more" is always available; findings on the component are never suppressed or downgraded. The worst case is one card the human dismisses.

### R3 — A simplification silently drops a guarantee
**Mitigation:** the card's *guarantee lost* and *covering layer* fields are required, a card missing either is malformed and not presented, and the next pass reviews the simplified head with all lenses. This is the ship bar's trust boundary; no accepted-risk shortcut applies to it.

### R4 — Parity drift between the two skills
**Mitigation:** every rule in §1–§4 that is shared gets a `check-parity.py` rule; the one deliberate asymmetry (split-the-plan) is a per-skill rule so the checker verifies the *sibling lacks it*.

### R5 — Spurious cards on reviews that legitimately touch one component many times (a focused fix branch)
**Mitigation:** only HIGH/MEDIUM count, and the §5 false-positive signal has a recorded rollback (`CLUSTER_N` 3 → 4). A focused branch whose one component keeps drawing HIGH/MEDIUM findings for three passes is, on the evidence, exactly the case the rule exists for.

### R6 — State schema bump breaks the provenance recipe or older readers
**Mitigation:** additive fields only; `summary_schema` bumped; recipe and checker updated in the same phase; schema-1 files read with empty defaults.

## Rollback plan

Every change is prose plus stdlib tooling; `git revert` of the Phase 0 or Phase 1 merge restores the prior behavior with no data migration. Schema-2 state files remain readable by schema-1 prose (extra fields are ignored). The tuning rollback (`CLUSTER_N` 3 → 4) is a one-line change recorded in §5.

## Sequencing decision

Now, because: the data gate on issue #6 is met; the prose rule is live in ResearchLogix_v2 with two successful firings, so the skills currently lag the practice; and every week of unported rule is another builder relying on a playbook paragraph. Nothing else is in flight in this repo (PR #9 merged 2026-09-28). Axis 1 stays parked.

## Open questions

- **Q1.** Fire *at* the third pass, before folding that finding (as the CSRF code review did), or *after* the third fold, before a fourth? Recommendation: at the third, before folding; the third fold is the one the evidence says gets wasted.
- **Q2.** Should a FAILED-lens pass skip (neither count nor reset) as the freeze tracker does? Recommendation: yes, same reasoning; a lens that didn't run says nothing about the component.
- **Q3.** Does a streak carry across chunk boundaries within one pass log (delegate-grants reviewed chunks B and C in one log)? Recommendation: yes, the log is the unit; the editor retires a label when its component leaves the diff, and the tracker's reset-on-absence handles the rest.
- **Q4.** In `iterate-plan`, what is a "component"? Recommendation: a plan mechanism as the plan names it (a D-numbered decision, an invariant, a named lock or classifier), which is how the CSRF plan's Q7 already described the cluster.
- **Q5.** Should the card also fire on a streak of *two* when both findings are fold-caused? Recommendation: no for MVP; show provenance as evidence, keep one trigger, revisit with §5 data.

## Out of scope

- A pure fold-provenance trigger (issue #6's original framing): shown as evidence, not built as a trigger; see Non-goals.
- Runner-side enforcement of tagging: the runners never read dispositions, and this plan keeps that contract.
- Any change to lens selection, lens prompts, or the reviewer output schema: the reviewer does not know about components; tagging is the editor's.
- Backfilling tags into existing ResearchLogix_v2 or doc-bot pass logs.
- Editing ResearchLogix_v2's hardening playbook: noted as a follow-up in Phase 2, done in that repo.

## Closeout

- [ ] Append entry to your project's milestones / changelog index (if you
  keep one): one paragraph covering what shipped, the ship commit, key
  delta, and a link back to the archived plan path.
- [ ] Update memory and/or project notes: mark plan completed, link to
  ship commits, update any related context files this plan touched.
- [ ] Update any backlog / priority queue: remove if it was queued, or
  mark closed inline.
- [ ] Move plan to archive: `git mv docs/<plan>.md docs/archive/<plan>.md`.
- [ ] Final commit with a "shipped" message referencing this plan.

## References

- Issue #6 — https://github.com/kaileconsulting/trinity-skills/issues/6 (fold-provenance stop-condition machinery, punted from v2.4; revisit condition and constraints).
- `docs/archive/trinity-v2-4-2026-08-21.md` — v2.4 plan: §4 open-question freeze (tracker pattern), §5 fold-provenance instrumentation (tag pattern), Out of scope entry deferring #6.
- `CHANGELOG.md` 2.4.0 — the retro numbers (29% fold-caused; ≥6 fold-caused findings → 10.8 passes vs 3.3).
- ResearchLogix_v2 `docs/hardening-playbook.md` §7 — the clustering rule as adopted 2026-09-25 (the reference prose).
- ResearchLogix_v2 evidence loops: `docs/auth-csrf-hardening-2026-09-24.md` (plan review, Q7, pass table), `docs/reviews/code-review-branch-fix-auth-csrf-hardening-2026-09-24.md` (pass-3 card), `docs/reviews/code-review-branch-fix-login-catch-throwable-2026-09-25.md` (pass-4 disposition), `docs/reviews/code-review-branch-fix-impersonation-c1b-active-filters-nav-gate-2026-09-15.md`, `docs/archive/code-review-branch-feat-edit-only-delegate-proxy-grants.md`, `docs/archive/code-review-credential-tokens-phase-1.md`.
- `tools/freeze_tracker.py`, `tools/check-question-freeze.py` — the reference-module pattern this plan copies.
- `iterate-review/SKILL.md` step 12 (fold, cards, `introduced_by_pass`), step 14 (checkpoint, loop-mode stop conditions), step 16 (state file); `iterate-plan/SKILL.md` steps 8 and 10.
- Memory: `trinity-expansion.md` (2026-09-28 update), `plan-authoring-workflow.md`.

<!--
=========================================================================
TOOLING-RESERVED SECTIONS BELOW THIS LINE.
Do NOT author content here at plan-creation time. iterate-plan and
iterate-review append/maintain these sections automatically.

The stubs below show the expected format. Leave them in place;
the tooling will populate them.
=========================================================================
-->

## Review checkpoints

<!-- TOOLING-MAINTAINED by iterate-review for multi-phase plans.
Updated automatically on each iterate-review pass. Single-page view of
where each phase stands in the review lifecycle.

| Phase | Iterate-review | Status | Last pass | Pass log |
|-------|----------------|--------|-----------|----------|
| Phase 0 | NO  | n/a | n/a | n/a |
| Phase 1 | YES | not started | — | — |
| Phase 2 | CONDITIONAL | not started | — | — |
-->

## Pre-flight review pass (the editor, YYYY-MM-DD) [HISTORICAL]

<!-- OPTIONAL self-review by the editor before execution. Useful as a final
"smell test" pass after iterate-plan converges but before any code
lands. Captures any nits that don't warrant another Codex pass but
are worth noting on the record. Delete this section if you skip the
self-review.

### Context
What state the plan was in when this pass ran.

### Findings
- ...

### What didn't change
- ...

### Verdict
APPROVE / NEEDS REVISION
-->

## Codex review pass N — answers (YYYY-MM-DD) [HISTORICAL]

<!-- TOOLING-MAINTAINED by iterate-plan. Each pass appends a new
"## Codex review pass N — answers (DATE) [HISTORICAL]" section.
Do NOT author this section manually; iterate-plan handles it.

The format below is what iterate-plan produces — kept here as
reference so the template makes the convention visible.

### Verdict
APPROVE / REVISE / BLOCK

### Findings
- **HIGH** — Title — Description — Suggested action
- **MEDIUM** — ...
- **LOW** — ...

### Plan corrections applied
- Location — Issue — Fix

### Open-question answers
- **Q1** — answer

### New questions Codex raised
- ...

### Convergence reasoning (only on APPROVE passes)
Why this pass converged.
-->
