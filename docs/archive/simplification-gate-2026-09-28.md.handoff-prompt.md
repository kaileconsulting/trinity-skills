# Handoff: Simplification Gate — Plan

## Summary
Port ResearchLogix_v2's "clustering rule" into both trinity loop skills: every finding gets a `[component: <label>]` tag beside `[introduced_by_pass]`; a fixture-pinned reference tracker (`tools/cluster_tracker.py`, modeled on `freeze_tracker.py`) counts consecutive HIGH/MEDIUM passes per component; at three, the editor stops before folding and presents a **simplification decision card** (remove / narrow / replace, each with guarantee-lost, covering-layer and per-finding accounting; *remove* and *fold once more* mandatory; never an auto-stop). The cap and stall cards gain a grouped-by-component section. State summaries move to `summary_schema` 2 (additive: `observation`, `components`, `streaks`, `retired`, `cards`). Closes issue #6. Design converged after 5 `iterate-plan` passes (5 → 3 → 3 → 2 → 0 HIGH+MEDIUM; 13 findings, all incorporated; every open question frozen with lens agreement).

## Plan
Full plan at: `/Users/adminformatics-pm/code/trinity-skills/docs/simplification-gate-2026-09-28.md`
Read this first — all of it, including the five HISTORICAL blocks at the bottom, which record *why* several rules ended up the way they did (three of them were rewritten after fold-caused findings).

## Current step
Phase 0 — Component tags + streak tracker (the data half). Branch `kyle/simplification-gate` (already created; plan and review history committed there). Phase 0 is Iterate-review YES: when its commits land, run `/iterate-review --scope=branch --loop` against the branch before moving to Phase 1.

## Shipped commits referenced by the plan
- `191c76d` — docs(simplification-gate): author plan
- `5dde6c9`, `b7d6480`, `d932855`, `153f3f0` — fixup(iterate-plan): folds for passes 1–4
- `86ada2b` — docs(simplification-gate): pass 5 APPROVE x2, loop halts for Converge
- Related, already on main: `26bc198` (PR #9, `prior_passes` in run-pass summaries), `4a443d0` (v2.4: `introduced_by_pass`, freeze tracker, parity checker).

## Remaining risks
- **R1 label drift** is the one the design can't fully engineer away; the labeling rules in Approach §1 and the worked impersonation-c1b example in each SKILL.md are the mitigation. Write the example carefully.
- **Threshold lives as a literal in each SKILL.md** (copied installs have no `tools/`); `check-cluster-streak.py` must assert both literals equal `CLUSTER_N` and each other, or tuning will drift.
- **Observations come from merged findings only.** Do not add a checkpoint-event path; pass 3 deliberately removed it. A rejected accepted-risk on a quiet pass delays the card by at most one pass, and that is accepted.
- **Every copy** of the `introduced_by_pass` "no guardrail may consult" reservation (fold-step prose, state-summary paragraph, Hard rules, in *both* SKILL.md files) is rewritten in Phase 1, not Phase 0. Phase 0 must leave it intact.
- **Parity:** every shared rule in §1–§4 needs a `tools/check-parity.py` rule; split-the-plan is `iterate-plan`-only and needs a per-skill rule so the checker verifies the sibling lacks it.
- Before merging, run the pre-merge doc sweep (README, both SKILL.md, `tools/README.md`, CHANGELOG, memory) — the test suite can't catch stale prose.

## First action
Read the plan, then `tools/freeze_tracker.py` and `tools/check-question-freeze.py` end to end (the pattern Phase 0 copies), then start Phase 0 with `tools/cluster_tracker.py` + `tools/check-cluster-streak.py`, wiring the checker into `tools/check-all.sh`. Confirm `tools/check-all.sh` is green before touching either SKILL.md.
