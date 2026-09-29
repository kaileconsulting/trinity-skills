# Code Review — branch-kyle-simplification-gate

## Pass 1 — 2026-09-29 12:10 [HISTORICAL]

**Scope:** branch · **Diff size:** 2460 lines · **Scope class:** production · **Verdict:** REVISE (worst-of: senior-dev REVISE, security APPROVE, qa REVISE; no FAILED lens) · **Posture:** used docs/simplification-gate-2026-09-28.md · **Lenses:** senior-dev, security, qa

### Findings

1. **Tracker cannot replay lifecycle changes made without a simplification card** — HIGH · lens: senior-dev (HIGH), qa (MEDIUM; merged, same defect): `tools/cluster_tracker.py` rejects narrow / replace / accept-risk unless the label fired a card that pass, while both SKILL.md fold steps state those lifecycles independently of any card, so a Phase-0 history (replacement before the threshold, a change on a FAILED pass) raises instead of replaying; `iterate-plan/state/example.json` pass 2 (accepted-risk) keeps `freeze-counter` at 2, contradicting the prose's accept-risk reset.
   → Editor: incorporated — outcomes split into two kinds. *Mechanism events* (`retire`, `replace`) are facts about the code or plan, replayable on any pass, card or not, FAILED passes included. *Card answers* (`remove`, `narrow`, `accept-risk`, `fold-once-more`, `split-plan`) still require a card fired that pass. The streak resets on narrow/accept-risk are card-answer-only, and both SKILL.md lifecycle bullets now say so explicitly: an ordinary narrowing fold or an editor's own `accepted-risk` *proposal* resets nothing, since a reset without a human decision would let the editor defer the card (the PF-shipbar trust boundary). That makes `iterate-plan/state/example.json` pass 2 (freeze-counter held at 2 across an AR proposal) correct as written, so no state-file change. Fixtures added: pre-threshold replacement without a card, replacement on a FAILED pass, ordinary folds reset nothing, accept-risk without a card is rejected. Parity rule `component-lifecycles` tightened to pin the card-only resets. Claims-vs-behavior sweep: tracker docstring, both SKILL.md bullets and the plan's §1/§2 (already card-scoped) now agree. Not a design-shaped fold: no new mechanism, a correction inside the reference module and its prose. [introduced_by_pass: null] [component: cluster-tracker-lifecycle-events]

### Code corrections applied

- `tools/check-provenance-recipe.py` success line — reports seven recipe invocations but `main()` runs six → success line now reports 6/6

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: APPROVE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-09-29 12:05; head SHA `6e76679`.
