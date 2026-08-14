# Code Review — phase-2

## Pass 1 — 2026-08-13 19:14 [HISTORICAL]

**Scope:** custom range `1661dfe..eb30c6a` (Phase 2's commits only — Phase 0+1 already converged separately, `docs/reviews/code-review-branch-kyle-risk-posture-phase-0.md`) · **Diff size:** 435 lines / 5 files · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, qa

### Findings

1. **Decision-card option contract exceeds the structured-question mechanism** — HIGH · lens: senior-dev: the card format specified 1 recommendation + 2–3 alternatives + a separately-listed `discuss` option — for accepted-risk confirmation's 4 resuming transitions (confirm-this-review, confirm+register, reject, defer) plus a listed discuss, that's 5 explicit options, but the interactive structured-question mechanism caps at 4 per question. No cardinality rule reconciled the two.
   → Editor: incorporated — clarified that `discuss` is never a listed option; it's the harness's built-in free-form response, so it never competes for a slot. Cardinality is now explicit: recommendation + alternatives together must never exceed 4 (so at most 3 alternatives with a recommendation, already the stated range) — a card design that would need more must use a narrower alternative set or a follow-up card, never assume the harness copes. Accepted-risk confirmation's 4 resuming transitions now fit exactly.
2. **Multi-field dependency digests lack a deterministic canonicalization contract** — HIGH · lens: qa: the posture-dependency descriptor can name multiple posture fields, but the digest recipe only specified single-entry content extraction (generalized from step 11's register-match recipe) — no ordering, field-boundary, or id-inclusion rule for combining more than one field, so two sessions could reconstruct different digests for the same logical descriptor.
   → Editor: incorporated — explicit multi-field canonicalization added: per-field content extraction unchanged (reuses step 11's recipe); ids sorted lexicographically; each field built as `<id>:\n<content>`; blocks joined with `\n---\n`; sha256 of the result. A single-field descriptor is the degenerate case of the same procedure, not a separate rule. Extended the fixture with a real multi-field example (AR-4, descriptor `["PF-blast","PF-audience"]`, real computed digests before and after amendment) since the qa lens correctly noted the existing fixture only exercised single-field descriptors.
3. **Example claims rejection behavior its adopted mechanism did not establish** — MEDIUM · lens: senior-dev: the fixture's finding-4 "adopt the mechanism" fold only added a version counter for *detecting* the autosave race, but the later pass-2 dispute reasoning claimed the caller could now *reject* a version-mismatched write outright — a capability never actually folded, an unstated additional fold smuggled into the narrative.
   → Editor: incorporated — finding 4's adopted mechanism is now scoped explicitly to include both detection and rejection-on-mismatch as one fold, so the pass-2 dispute rests on a capability the fixture actually established.
4. **Lifecycle and resume behavior is specified only by a read-only narrative fixture** — MEDIUM · lens: qa: the change introduces observable state transitions, checkpoint repetition, immediate design-card pauses, write-failure handling, and cross-session reconstruction with no executable test verifying any of it.
   → Editor: **disputed.** This asks to convert a read-only merge/accounting fixture into executable test infrastructure — a different kind of artifact than what this directory is for. `examples/merge/README.md` states the design reason explicitly: merge (and, by the same argument, accounted disposition state) is the editor's *semantic judgment*, not mechanically computable from the JSON alone — scripting it either badly reimplements judgment or degrades to a naive check the plan already rejected. Register-match (Phase 1) got the identical read-not-run treatment without this objection; nothing about accepted-risk's bookkeeping is categorically different. Building a markdown-pass-log state-machine validator is a real, separate engineering effort — proportionate to build if and when this repo's own "meta-tooling past diminishing returns" pattern (on record from an earlier honest assessment) is judged worth reversing, not as a rider on this phase.
5. **The fixture does not actually exercise interruption-crossing reconstruction** — MEDIUM · lens: qa: the fixture asserted a fresh session would reproduce AR-2/AR-3's outcomes but never simulated an interruption, a serialized pass-log read, or an independently-observed post-resume result — the claim could pass by inspection even if resume behavior secretly depended on session-local state.
   → Editor: incorporated, and this one is fair unlike finding 4 — the read-not-run convention covers *judgment*, not *rigor of the demonstration itself*. Rewrote the reconstructability section to walk through a concrete session boundary: pass log contents durably recorded at end-of-session-A, a fresh session-B declared to have zero memory beyond those two durable inputs (pass log + posture source), and the same recompute-and-compare carried out explicitly against session-B's inputs, reaching the identical three outcomes (AR-2 invalidated, AR-3 stands, AR-4 invalidated) as the same-session version — demonstrated, not just asserted.

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Decision cards

- (none this pass — all findings resolved via ordinary fold/dispute; no design-shaped-fold, accepted-risk confirmation, needs_human question, non-convergence stall, or malformed-posture-source moment arose reviewing this diff)

### Lens run summary

- senior-dev: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 19:14; range `1661dfe..eb30c6a`; folds applied to the working tree, not yet committed.

## Pass 2 — 2026-08-13 19:21 [HISTORICAL]

**Scope:** custom range `1661dfe..HEAD` (pass-1 folds committed at `654eaf8`) · **Diff size:** 592 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, qa

### Findings

1. **Separator normalization is asserted but not specified** — HIGH · lens: senior-dev, qa (co-reported; qa rated HIGH, senior-dev MEDIUM — merged at the more severe rating): the multi-field digest recipe joined blocks with a literal `\n---\n` separator and claimed it was "normalized away if it appears in content," but never defined what that normalization actually does — two implementations (or a resumed session vs. the original) could handle separator-bearing field content differently and reach different digests for the same descriptor.
   → Editor: incorporated — replaced separator-joining entirely with length-prefixed (netstring-style) framing: each field's id and content are UTF-8-encoded with an explicit byte-length prefix, so no separator is ever scanned for and no content can ever be misread as one. Collision-safety no longer depends on an escaping rule that didn't exist — it's structural.
2. **Single-field fixture digests contradict the new canonical digest procedure** — HIGH · lens: senior-dev: the spec described one unified procedure (always id-prefixed) covering both single- and multi-field descriptors, but the fixture's single-field digests (AR-1/2/3) were computed as bare content, matching register-match's existing recipe, not the new prefixed one.
   → Editor: incorporated — resolved by correcting the spec rather than the fixture (the fixture's original values were the right call): a single-field descriptor now explicitly uses the plain single-entry recipe (identical to register-match, nothing to combine), and only two-or-more-field descriptors use the length-prefixed combination procedure. No fixture values needed to change; AR-4 (the multi-field case, added in pass 1) got its digests recomputed under the corrected length-prefixed procedure.
3. **Accepted-risk fixture omits the legal defer transition** — MEDIUM · lens: senior-dev, qa (co-reported): AR-1's confirmation card listed only 3 of the 4 legal resuming transitions (confirm-this-review, confirm+register, reject) — nothing prohibits `defer` for this finding, so context-sensitive omission didn't license leaving it out.
   → Editor: incorporated — added `defer` as AR-1's fourth explicit alternative (recommendation + 3 alternatives = 4, exactly the cardinality cap from pass 1's fold); updated the other two decision cards in the same fixture (findings 3 and 4) to use the same "discuss is the harness's free-form response, not a listed option" framing for consistency, since pass 1's own cardinality fix hadn't been retrofitted onto them.

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Decision cards

- (none this pass)

### Lens run summary

- senior-dev: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 19:21; range `1661dfe..HEAD`; folds applied to the working tree, not yet committed.

## Pass 3 — 2026-08-13 19:35 [HISTORICAL]

**Scope:** custom range `1661dfe..HEAD` (pass-2 folds committed at `d6a7906`) · **Diff size:** 605 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, qa

### Findings

1. **Decision-card examples violate the shared minimum-alternatives contract** — HIGH · lens: senior-dev, qa (co-reported; senior-dev HIGH, qa MEDIUM — merged at the more severe rating): the general contract stated "2–3 genuine alternatives" as if it were a hard minimum, but the fixture's finding-3 and finding-4 cards each legitimately have only 1 alternative after context-sensitive omission removes the others (no cheaper alternative for finding 4; accept-the-risk excluded for finding 3's trust-boundary code) — the spec never said what the floor actually is when omission bites.
   → Editor: incorporated — "2–3" is now explicit as a *target*, with a stated floor of 1 (a card needs at least one genuine alternative to be a decision at all) and an explicit escape valve: if omission would leave *zero* alternatives, that means there's only one legal continuation — proceed with it directly rather than presenting a degenerate card.
2. **Fixture processes a second finding after an immediate-halt escalation** — HIGH · lens: qa: the fixture folds finding 4 within the same "Pass 1" narrative as finding 3, even though finding 3's card is described as "halts immediately" — under the stated contract, that reads as forbidding any further folding within the same pass, which the fixture's own structure then violates.
   → Editor: incorporated, and this was a real ambiguity in the spec, not just the fixture — clarified the halt's actual granularity: a design-shaped-fold escalation pauses **the fold of that one finding** to get a live decision; it does not freeze the rest of that pass's already-Codex-returned findings. This is a different, finer granularity than step 14's between-pass loop-mode guardrails, which the original wording didn't distinguish. Added an explicit framing note to the fixture's Pass-1 section stating this is deliberate, not an oversight.
3. **Reopened AR-1 is given an inaccurate disputed disposition** — MEDIUM · lens: senior-dev: the fixture's pass-2 resolution disposed AR-1's reopened finding as `disputed`, but the finding was never wrong (a real race existed) — it was resolved as a side effect of finding 4's mechanism, which is `incorporated`, not `disputed` (which specifically means "the finding misread intent or an unseen constraint").
   → Editor: incorporated — changed the fixture's disposition to `incorporated (superseded by finding 4's mechanism)`, and added a rule to SKILL.md's accepted-risk lifecycle: pick the terminal disposition for what actually happened, not for narrative convenience — a defect closed as a side effect of an unrelated fold is `incorporated` with a qualifying parenthetical (the same shape `incorporated (via alternative)` already uses), never `disputed`.

### Code corrections applied

- `iterate-review/examples/merge/04-accepted-risk-lifecycle/expected-merge.md:Lens run summary` (lens: senior-dev) — said "three accepted-risk proposals" and omitted AR-3 (confirmed and still valid) from the breakdown entirely, though the scenario defines four (AR-1 through AR-4). Corrected to name all four and their individual outcomes.

### New questions Codex raised

- (none)

### Decision cards

- (none this pass)

### Lens run summary

- senior-dev: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 19:35; range `1661dfe..HEAD`; folds applied to the working tree, not yet committed.

## Pass 4 — 2026-08-13 21:25 [HISTORICAL]

**Scope:** custom range `1661dfe..HEAD` (pass-3 folds committed at `142d716`) · **Diff size:** 628 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, qa

### Findings

1. **Zero-alternative escape valve can silently adopt an unapproved mechanism** — HIGH · lens: senior-dev, qa (co-reported): pass 3's fix for the alternatives floor said that when omission leaves zero alternatives, the editor should "proceed with the only legal continuation directly" — but for a design-shaped-fold escalation, that continuation is very often *adopting the mechanism*, meaning the fix I made to close one gap opened exactly the hole the whole escalation rule exists to prevent: a mechanism built without ever asking.
   → Editor: incorporated, and this one mattered — reworked the rule entirely: the recommendation and `discuss` are never counted among "alternatives" and are never omittable, so the true floor is *zero listed alternatives*, not "skip the card." A card with zero alternatives is still a real two-way choice (adopt the recommendation, or discuss) and is **always presented, never auto-proceeded past** — no exception for design-escalation, no exception anywhere. Removed the "proceed directly" language entirely rather than trying to patch it.
2. **Pre-presentation persistence format requires a choice that does not exist yet** — HIGH · lens: qa: the rule said cards are logged before presentation using a template that requires a `chosen:` field — but there's no chosen option yet at that point, an unresolved contradiction in the format itself.
   → Editor: incorporated — defined the persistence as two phases: a pending write before presentation (`chosen: (pending)`, the resume signal for an interrupted session) and a resolution write after, updating the same entry in place with the real outcome. Updated the pass-log template and added a concrete demonstration to the fixture (AR-1's card, both phases shown explicitly).
3. **Summary invariant still presents 2–3 alternatives as unconditional** — MEDIUM · lens: qa (co-reported as a code_correction by senior-dev at the same location): two earlier summary lines (the initial card-shape statement, and the Hard-rules bullet) still said "2–3 alternatives" without qualification, contradicting the detailed cardinality rule fixed at pass 3.
   → Editor: incorporated — both summary lines reworded to say "up to 3" and point to the floor rule, rather than repeating a now-inaccurate hard range.

### Code corrections applied

- (already covered by finding 3's fold — no separate corrections this pass)

### New questions Codex raised

- (none)

### Decision cards

- (none this pass)

### Lens run summary

- senior-dev: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 21:25; range `1661dfe..HEAD`; folds applied to the working tree, not yet committed.
