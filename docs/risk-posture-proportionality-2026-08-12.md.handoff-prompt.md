# Handoff: Risk Posture & Proportionality — Plan

## Summary
Adds a proportionality layer to the trinity skills so the review loop can say "real, but not worth it for this product": create-plan captures a risk posture (audience, blast radius, ship bar) in every plan via stable `PF-` field ids; iterate-review feeds that posture to the Codex lenses through a `=== RISK POSTURE ===` intent block and an optional `register_ref` reviewer-schema field; the editor gains an `accepted-risk` disposition with a full lifecycle (`proposed` → `confirmed`/`rejected` → `reopened`, normative per-ledger accounting table), a design-shaped-fold escalation rule with an operational "new mechanism" boundary, and decision cards at all five human-judgment moments. The accepted-risks register lives in exactly one place per repo (`docs/risk-posture.md`, allocation-free `RR-<date>-<slug>` ids) and is published to only via human confirmation. Converged after 9 iterate-plan passes (product-manager lens: 4 consecutive clean APPROVEs; all architect findings folded).

## Plan
Full plan at: `/Users/adminformatics-pm/code/trinity-skills/docs/risk-posture-proportionality-2026-08-12.md`
Read this first — the Approach section is normative, including the accounting table and per-card outcome mappings. The nine HISTORICAL blocks at the bottom record why each design decision landed where it did; skim them before deviating from anything that looks arbitrary.

## Current step
Phase 0, first deliverable: add the `## Risk posture` section (with `PF-audience`, `PF-blast`, `PF-shipbar` ids, full + lightweight variants) to `create-plan/template.md`, then the posture-questions step to `create-plan/SKILL.md`.

## Shipped commits referenced by the plan
- (none — implementation not started; the plan file itself is not yet committed)

## Remaining risks
- R1 (suppression creep) and R4 (pushback overcorrection) are behavioral risks that only Phase 3's live doc-bot case study can really test — don't try to close them in Phases 0–2.
- The reviewer-prompt change moves the composition goldens (`examples/composition/`); regenerate them in the same commit and keep `tools/check-parity.py` green — `runner_shared.py` must stay byte-identical to iterate-review's copy.
- Phases 0–2 are all Iterate-review YES: run `/iterate-review --scope=branch` per phase; the per-phase acceptance lists (fixtures, collision cases, interruption-crossing dependency checks) are the review's evidence base.

## First action
Commit the converged plan (`git add docs/risk-posture-proportionality-2026-08-12.md docs/risk-posture-proportionality-2026-08-12.md.handoff-prompt.md && git commit`), create a working branch (e.g. `kyle/risk-posture-phase-0`), then open `create-plan/template.md` and add the `## Risk posture` section per Phase 0's deliverables.
