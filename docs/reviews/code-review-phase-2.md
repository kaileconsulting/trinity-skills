# Code Review — phase-2

## Pass 1 — 2026-08-13 15:01 [HISTORICAL]

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

Diff captured at 2026-08-13 15:01; range `1661dfe..eb30c6a`; folds applied to the working tree, not yet committed.

## Pass 2 — 2026-08-13 15:16 [HISTORICAL]

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

Diff captured at 2026-08-13 15:16; range `1661dfe..HEAD`; folds applied to the working tree, not yet committed.

## Pass 3 — 2026-08-13 15:23 [HISTORICAL]

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

Diff captured at 2026-08-13 15:23; range `1661dfe..HEAD`; folds applied to the working tree, not yet committed.

## Pass 4 — 2026-08-13 15:56 [HISTORICAL]

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

Diff captured at 2026-08-13 15:56; range `1661dfe..HEAD`; folds applied to the working tree, not yet committed.

## Pass 5 — 2026-08-13 20:00 [HISTORICAL]

**Scope:** custom range `1661dfe..HEAD` (pass-4 folds committed at `092de54`; pass log checkpointed at `2919a59`) · **Diff size:** 791 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, security, qa

### Findings

1. **Posture invalidation conflicts with the new-id rule for changed bounds** — HIGH · lens: senior-dev: the accepted-risk lifecycle says a materially changed finding with a "different location, behavior, or bound" always gets a new `AR-` id, while the posture-dependency rule says a digest mismatch returns the item to `proposed` under its existing id. The word *bound* carries a different referent in each, so when the fixture's `PF-blast` is amended from recoverable to not-reliably-recoverable, both rules can claim the event and they disagree about identity — two conforming implementations would produce different AR ledgers, and therefore different answers to the Converge predicate.
   → Editor: incorporated — real collision, not a wording nitpick, precisely because AR identity feeds the accounting table. Disambiguated both sides rather than one: the lifecycle rule now says "bound" there means the *finding's own claimed* bound (what the reviewer alleges the blast radius to be) and never the posture text a rationale rests on, and states the two triggers explicitly — finding changed → **new** id; posture changed → **same** id, back to `proposed`. Added the mirror statement at the posture-dependency rule ("invalidation always preserves the `AR-<n>` id"), so a reader arriving from either direction sees it. Also added a framing note to the fixture at the AR-2 invalidation, since the fixture is where Codex actually hit the ambiguity: neither finding changed, only `PF-blast`'s wording did, so AR-2/AR-4 keep their ids, and minting an AR-5 there would discard the record of a human confirmation that really happened.
2. **Abort-state array has no defined treatment for invalidated confirmations** — MEDIUM · lens: senior-dev: step 16's `confirmed_accepted_risks` says that on Abort it reflects what "was confirmed before the abort" — a historical reading — but never says whether an item confirmed and then invalidated back to `proposed` remains in the array. Historical and current-state readings both fit the prose and produce different state files.
   → Editor: incorporated — chose **current-state** semantics, per Codex's own recommendation and for the reason it gave: the array exists so a resume can act on it. An item lists only if its `confirmed` state still holds at write time; an item invalidated by a posture-digest mismatch or a rejection is absent even though it "was confirmed" at some point. Stated the rationale in the text rather than just the rule (a resume trusting an invalidated confirmation would act on a human decision that no longer applies to the current posture), and kept the pass log as the authority on both pending items and the history the array now deliberately drops.
3. **Mid-fold decision cards lack a defined durable pass-log location** — MEDIUM · lens: qa: pass 4's two-phase card persistence requires a `(pending)` write *before* presentation, but step 12 still described appending the single HISTORICAL block *after* folding — so at the moment the pending write must happen, the block it belongs in does not exist. An interruption exactly at the card is the failure the pending write was built to survive, and the spec left it undefined whether the block had been opened, or how resume avoids appending a second one.
   → Editor: incorporated — a direct consequence of pass 4's own fix, and the fourth consecutive pass to file against the previous pass's fix surface. Defined block creation as incremental: the block opens the moment anything needs durable recording, starting with the `## Pass <N>` header plus the full Scope/Diff-size/Verdict/Posture/Lenses line — every field of which is already known then, since the worst-of verdict is fixed by step 11's merge before the first finding is folded — and its sections fill in as folding proceeds. Made explicit that "append ONE block" constrains the block count, not the number of writes. Added the resume rule: a session finding a `## Pass <N>` block for the pass in progress completes it and never appends a second; the `(pending)` card is the finer-grained signal for *where* folding stopped, the block header the signal for *which* block to write into; a duplicate `## Pass <N>` block is always a bug.

### Code corrections applied

- `iterate-review/examples/merge/04-accepted-risk-lifecycle/expected-merge.md:Pass 2 Branch A` (lens: senior-dev, qa — co-reported, same location) — AR-1's resolution text said finding 4's mechanism was "adopted this same pass," but the scenario adopts it in pass 1 and resolves AR-1 in pass 2. Corrected to "adopted in the prior pass."

### New questions Codex raised

- (none)

### Decision cards

- (none this pass)

### Lens run summary

- senior-dev: REVISE · security: **APPROVE** (zero findings — first clean lens of this review) · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 20:00; range `1661dfe..HEAD`; folds applied to the working tree, not yet committed.

## Pass 6 — 2026-08-13 20:23 [HISTORICAL]

**Scope:** custom range `1661dfe..HEAD` (pass-5 folds committed at `ca39d60`) · **Diff size:** 839 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, security, qa

### Findings

1. **Malformed-posture cards cannot satisfy the uniform persistence contract** — HIGH · lens: senior-dev: pass 5's block-opening fix justified writing the full Scope/Diff-size/Verdict/Posture/Lenses header line up front on the grounds that "every field is already known at that point, since the worst-of verdict is fixed by the merge in step 11." That holds for four of the five card types — but the malformed-posture-source card halts in **step 9, before fan-out**, when no lens has run and no verdict exists. So the one persistence rule I had just declared uniform across all five card types had no valid durable location for one of them, defeating the interruption guarantee exactly where it was claimed.
   → Editor: incorporated — my own pass-5 fold's bug, and a good demonstration that a rule justified by "this is always known" deserves a check of every entry point, not just the one in front of you. Fixed by making the header line obey the same two-phase discipline the card itself uses rather than inventing a second location: the block opens with the fields that *are* known at step 9 (`Scope`, `Diff size`, `Posture`) and `(pending)` for those that aren't (`Verdict`, `Lenses`), each replaced in place once the merge determines it. Template updated to show both fields' `(pending)` form. Explicitly reaffirmed the property Codex was defending — no card type is exempt from persistence-before-presentation, and none needs a location outside the pass block — and stated what an abort at that card leaves behind (a block with `(pending)` header fields, marked incomplete), so the degenerate case is a documented outcome rather than an undefined one.
2. **Rejection cannot invalidate an already-confirmed item under the defined transitions** — MEDIUM · lens: senior-dev: pass 5's step-16 wording cited two ways a confirmation becomes invalid — posture-digest mismatch, or "to `reopened` by a rejection." But the lifecycle defines `rejected`/`reopened` as a transition out of `proposed`, taken *instead of* confirming; confirmed items are never re-presented and have no revocation transition. My example was unreachable, and implied a workflow that doesn't exist.
   → Editor: incorporated **by narrowing, not by building** — deleted the rejection clause and stated the invariant positively: posture invalidation is the *only* path out of `confirmed`. Codex's suggested_action offered "or explicitly define who may revoke a confirmed item, when that card is surfaced, and how the transition is persisted" — that alternative is a new state transition, a new card type, and new persistence for a capability nothing has asked for, to fix a sentence that was simply wrong. Took the cheap correct option and recorded why the expensive one was declined: the one thing that legitimately undoes a confirmation is the posture text it was granted against changing underneath it, which the dependency descriptor already detects.
3. **Resolved-card interruption has no unambiguous resume marker** — MEDIUM · lens: qa: `(pending)` is the resume signal, but it disappears the moment a card is answered. An interruption *after* the answer but *before* the resulting disposition and remaining findings are folded leaves an apparently-settled card in a block that a resuming session cannot distinguish from a complete pass — so remaining findings get silently skipped.
   → Editor: incorporated, and the fix reuses two things that already exist rather than adding a progress ledger. (a) The block's own header tag becomes the completeness marker: `[IN PROGRESS]` from first durable write, flipped to `[HISTORICAL]` as the last write of the pass — the tag covers the whole interruption window, where `(pending)` covers only the sub-window before an answer. The tag is now stated to be the *authoritative* signal, with `(pending)` explicitly finer-grained and subordinate. (b) Recovering *where* folding stopped needs no new bookkeeping at all: the pass's `pass-N.<lens>.response.json` artifacts are already durable and immutable in the state dir, so remaining work is exactly the merged findings/corrections/questions those responses contain that the block doesn't yet record — diff the two. Also pinned the failure mode Codex was worried about: a block left `[IN PROGRESS]` after a pass ends means interrupted, never converged.

### Code corrections applied

- `docs/reviews/code-review-phase-2.md:Pass 4 and Pass 5 headings` (lens: senior-dev) — Pass 4 was stamped 21:25 while the *later* Pass 5 was stamped 20:18, contradicting the documented pass order. Investigated rather than patching the one visible pair: the state dir's `pass-N.summary.json` mtimes are ground truth for when each pass's Codex calls actually ran (15:01, 15:16, 15:23, 15:56, 20:00), and **every** logged timestamp for passes 1–5 was wrong — earlier blocks drifted ~4h ahead, pass 4 ~5.5h, which is what made the inversion visible at pass 5 rather than creating it. Restamped all five blocks and their `Diff captured at` lines to the true run times, and added a template note that the timestamp is the pass's Codex-run time (`pass-N.summary.json` mtime), not the block-write time — the ambiguity that produced the drift.

### New questions Codex raised

- (none)

### Decision cards

- (none this pass)

### Lens run summary

- senior-dev: REVISE · security: **APPROVE** (zero findings — second consecutive clean pass for this lens) · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 20:23; range `1661dfe..HEAD`; folds applied to the working tree, not yet committed.

## Pass 7 — 2026-08-13 20:33 [HISTORICAL]

**Scope:** custom range `1661dfe..HEAD` (pass-6 folds committed at `3d11a01`) · **Diff size:** 885 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, security, qa

### Findings

1. **Intentional abort is indistinguishable from an interrupted pass** — HIGH · lens: senior-dev: pass 6 introduced `[IN PROGRESS]` as the authoritative "folding was interrupted, resume it" signal and separately said an abort at the malformed-posture card leaves the block `[IN PROGRESS]`. Those two statements make a deliberate ending and a crash produce byte-identical durable state, so a later invocation can resume a pass the human deliberately terminated.
   → Editor: incorporated — the completeness tag now has three values instead of two: `[IN PROGRESS]` (resumable), `[HISTORICAL]` (complete), **`[ABORTED]`** (terminal, never resumed, written as the last act of the abort path with a one-line reason beneath the header). A deliberate ending now records a decision rather than looking like a crash. One extra value on an existing field, no new artifact — the alternative shape Codex offered (a separate durable abort marker that resume consults to override the tag) would put the same fact in two places and create a way for them to disagree.
2. **Pre-fan-out block has no valid timestamp source** — HIGH · lens: qa (HIGH), senior-dev (MEDIUM) — co-reported, merged at the more severe rating: pass 6's fix let the malformed-posture card open a block in step 9 *and* defined the block's timestamp as the `pass-N.summary.json` mtime — an artifact that does not exist before fan-out. The `(pending)` allowance covered `Verdict` and `Lenses` only, so a conforming implementation had to either invent a timestamp or skip the block it was required to write.
   → Editor: incorporated — same bug class as pass 6's finding 1 and, notably, in the *fix for* pass 6's finding 1: I extended the pending-field treatment to the fields I was thinking about and not to the one in the header itself. `(pending)` now covers the timestamp on equal footing (`## Pass <N> — (pending) [IN PROGRESS]`), filled in when the summary lands. The abort case is called out separately because it's the one place the summary-mtime rule genuinely cannot apply — an `[ABORTED]` pre-fan-out block is stamped with the abort's wall-clock time and says so inline, since no summary will ever exist for it.
3. **Audit-log lookup does not establish replay-safe approval deduplication** — HIGH · lens: security: the lifecycle fixture's finding-3 card offers "the approve handler already logs a request id; check-and-skip against that existing log" as the chosen cheaper alternative on `editor/approve.ts` — code the fixture's own `PF-shipbar` names as a trust boundary. Read-then-act is not atomic: two concurrent retries can both observe no prior id and both merge, so the fixture records a replay defect as `incorporated (via alternative)` without the alternative ever establishing the property it claims.
   → Editor: incorporated. Worth being explicit about why this wasn't pushed back on, since it's a fixture rather than shipping code and the proportionality criteria could superficially seem to reach it: the pushback **anti-criteria** rule this out twice over — never on code named as a trust boundary in the ship bar, and never to avoid a small honest fix. A fixture that models a hand-wave as an acceptable trust-boundary alternative teaches exactly the wrong lesson, and the fix is one sentence. Changed the alternative to an atomic claim (a uniqueness constraint on the existing audit-log request id, with the insert itself acting as the merge's admission ticket — still no new persisted field, so it remains genuinely cheaper), and used the contrast to state a general rule the fixture previously only implied: on trust-boundary code an alternative must supply the *same* invariant as the mechanism it replaces, only more cheaply; one that merely narrows the race is a weaker fold and must be recorded as one.

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Decision cards

- (none this pass)

### Lens run summary

- senior-dev: REVISE · security: REVISE (first finding from this lens since pass 1 — and a domain-level one about the fixture's content, not the machinery) · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 20:33; range `1661dfe..HEAD`; folds applied to the working tree, not yet committed.

## Pass 8 — 2026-08-13 20:38 [HISTORICAL]

**Scope:** custom range `1661dfe..HEAD` (pass-7 folds committed at `307c511`) · **Diff size:** 933 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, security, qa

*(This block was written `[IN PROGRESS]` while finding 3's decision card was pending at the checkpoint — the exact ordering this pass's own finding 1 established — and sealed to `[HISTORICAL]` when the card was answered. Unplanned dogfood of a rule created in the same pass; it worked.)*

### Findings

1. **Checkpoint cards occur after the pass block is marked complete** — HIGH · lens: senior-dev: passes 6–7 defined `[HISTORICAL]` as "every finding, question, and card outcome recorded," written as the last pass write after folding. But two of the five card types — accepted-risk confirmation and non-convergence stall — are presented at **step 14's checkpoint**, after folding is finished, and the persistence contract requires them written to that same block *before* presentation. So the spec required writing a card into a block it had already declared sealed, and an interruption at a checkpoint card would leave a "complete" block with unresolved work.
   → Editor: incorporated — resolved by moving the seal rather than adding a location: "fully complete" now explicitly means *through the checkpoint*, so the block stays `[IN PROGRESS]` across step 14 and flips to `[HISTORICAL]` only once the checkpoint's cards are answered and recorded. A block is never finalized and then reopened. Also clarified that step 13's "the pass log reflects the latest pass" is about content availability, not finalization — the block is readable as prior-pass context throughout; it simply hasn't been sealed. **This pass's own block is written under the new rule** — see the note above.
2. **The abort tag conflates aborting an incomplete pass with aborting the review** — MEDIUM · lens: senior-dev: pass 7 added `[ABORTED]` for "a pass that deliberately ended without completing," written as the last act of "the abort path" — but step 14 also offers Abort at a checkpoint, where the current pass may be fully complete and correctly `[HISTORICAL]`. The general wording would retag a finished pass as unfinished.
   → Editor: incorporated — scoped the tag explicitly, per Codex's suggested_action, which was right: `[ABORTED]` answers "did *this pass* finish?" and applies only to a pass ended while still open (the pre-fan-out malformed-posture abort being the canonical case). Aborting the review after a complete pass leaves that pass `[HISTORICAL]`, with the review-level outcome recorded by `final_action: aborted` in the step-16 state file. Stated the separation as a rule — one marker per question, never overload one to mean the other.
3. **Atomic claim can permanently suppress an approval that never merged** — HIGH · lens: security, qa (co-reported, independently, same failure) — **NOT YET FOLDED; escalated as a decision card at this checkpoint.** Pass 7's fix made the fixture's cheaper alternative an atomic claim (unique insert on the audit-log request id, insert = admission ticket). That closes the concurrent-duplicate race but creates a new one: the claim is durable *before* the merge outcome is known, so a crash or failure after the insert leaves every retry losing the uniqueness race and skipping a merge that never happened — a dropped approval on the same trust boundary, at-most-once admission mistaken for replay-safe completion. The finding is correct on its own terms.
   → Editor: incorporated, via the card below (Kyle chose the recommendation). Escalated rather than folded directly because the choice was a scope judgment — how much domain fidelity a narrative fixture owes — not a technical one; the finding itself was never in doubt. **Restructured the fixture so the cheaper alternative loses on re-review rather than patching it one layer deeper.** Pass 1 now folds finding 3's alternative *provisionally*, and pass 2 is the re-review the card contract already promised: the `security` lens files this exact claim-before-merge finding, the editor notes that making the claim recoverable (claimed-vs-completed state, stale-claim reconciliation, retry semantics) *is* a dedicated idempotency mechanism arrived at by accretion, and **withdraws the alternative** — recorded as an ordinary `incorporated` on the original finding under the original escalation, no new `AR-` id. Added a short section naming the three things this pins that a plausible-alternative-and-stop version cannot: that `incorporated (via alternative)` is provisional by construction, that "same invariant, only cheaper" is a test an alternative can fail on the *second* look, and that conceding an alternative is a normal outcome rather than an error state. This ends the regress at its source: the fixture no longer asserts the cheap path is sufficient, so there is no next layer to find.

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Decision cards

- **Design-shaped fold — fixture domain fidelity** (finding 3): recommendation — restructure the fixture so the cheaper alternative is folded *provisionally* and its next-pass re-review surfaces this exact claim-before-merge gap, escalating back to the dedicated idempotency mechanism, which makes the fixture teach "cheap alternatives on a trust boundary get re-reviewed and sometimes lose" and stops the regress at its source; alternatives — patch one more layer (couple claim state to merge completion with a recoverable retry path), or record the finding as `disputed` on the grounds that the fixture demonstrates card *mechanics* and its example's domain depth beyond the illustrated point isn't load-bearing; chosen: **restructure so the fixture loses the argument** (Kyle, at the pass-8 checkpoint — "let the fixture lose the argument"; the regress stops at its source rather than at its current depth, and the fixture ends up teaching something true that it previously only promised).

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 20:38; range `1661dfe..HEAD`; all three findings folded; finding 3 resolved via the checkpoint card above.

## Pass 9 — 2026-08-13 20:49 [HISTORICAL]

**Scope:** custom range `1661dfe..HEAD` (pass-8 folds committed at `7b78b41`, `e3ab811`) · **Diff size:** 1021 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, security, qa

### Findings

1. **Failed alternative silently adopts the previously unchosen mechanism** — HIGH · lens: senior-dev, qa (co-reported, independently, same failure): pass 8's new "the alternative loses on re-review" section had the editor withdraw the cheaper alternative and adopt the dedicated idempotency mechanism *"under the same escalation."* But the human's pass-1 card authorized the cheaper alternative — not the mechanism it declined. Adopting a persisted cross-request idempotency mechanism is a mechanism-requiring fold on its own signals, so treating the resolved card as continuing authorization is exactly the silent adoption step 12's hard rule forbids.
   → Editor: incorporated — and this is the finding of the whole review to sit with. **My fold for pass 8's finding 3 reintroduced the precise failure mode this machinery exists to prevent, inside the fixture that demonstrates the machinery** — the same class pass 4 caught in the zero-alternative escape valve. Both lenses found it independently, which is the strongest signal available here that it's real. Fixed by making the failed re-review escalate again: a fresh design-shaped-fold card in pass 2, with `(pending)` → resolved persistence shown, zero listed alternatives (the cheap path just failed; `accept the risk` stays excluded on a `PF-shipbar` trust boundary) — which is a legitimate card shape per the cardinality rule, not a reason to skip presentation. Stated the general rule the fixture now teaches: **a resolved card authorizes the option chosen, never the options declined.** Also extended the section's third lesson to name the hazard in both directions — an editor who won't concede keeps patching a losing alternative; one who concedes too smoothly slides into a mechanism nobody approved.
2. **Fresh pass-2 finding is dispositioned against the wrong ledger item** — HIGH · lens: senior-dev: pass 8's section called the claim-before-merge defect a "fresh HIGH" and then recorded the outcome as an ordinary `incorporated` *on the original finding* — but finding 3 was already terminally dispositioned in pass 1 as `incorporated (via alternative)`, and the newly returned pass-2 finding never got a disposition of its own. Step 12 requires every returned finding to be accounted for; as written, a HIGH could go unrecorded while the pass looked clear.
   → Editor: incorporated — gave the pass-2 defect its own identity (finding 6) and its own disposition, and stated the accounting rule explicitly: the pass log is append-only history, so a later pass records what that pass learned rather than rewriting an earlier entry. Finding 3's pass-1 record stands as written; finding 6's entry names what it supersedes. This also removes the temptation the original phrasing created — folding a new finding into an old entry makes the ledger look tidier and the accounting wrong.

### Code corrections applied

- `iterate-review/examples/merge/README.md:scenario 04 table row` (lens: senior-dev, qa — co-reported) — the row advertised the lifecycle as "terminal re-disposition under a new id," but the fixture resolves reopened AR-1 as `incorporated` under its *existing* id; only a fresh accepted-risk proposal takes a new `AR-` id. Corrected to state both paths separately, since the conflated version described the fixture's own headline case wrongly.

### New questions Codex raised

- (none)

### Decision cards

- (none this pass)

### Lens run summary

- senior-dev: REVISE · security: **APPROVE** · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 20:49; range `1661dfe..HEAD`; folds applied to the working tree, not yet committed.

## Pass 10 — 2026-08-13 20:51 [HISTORICAL]

**Scope:** custom range `1661dfe..HEAD` (pass-9 folds committed at `afe9980`) · **Diff size:** 1063 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, security, qa

### Findings

1. **Once mode leaves the completed pass marked resumable** — HIGH · lens: senior-dev, qa (co-reported): pass 8 moved the `[HISTORICAL]` seal to *after* the step-14 checkpoint, but step 15's `--once` mode skips the checkpoint entirely and exits after step 13. So a normal, fully successful once-mode pass writes `final_action: once-mode-exit` while its block stays `[IN PROGRESS]` — which the resume contract reads as interrupted work and would offer to resume. A second interaction between rules I wrote two passes apart, neither wrong alone.
   → Editor: incorporated — step 15 now seals the block explicitly, and the ordering is stated: seal first, then write the state file, so the two artifacts can never disagree about whether the pass finished. Also recorded *why* sealing early is safe here rather than leaving it as a bare exception: the cards that legitimately hold a block open are checkpoint cards, and once mode has none, so a `(pending)` card at step 15 could only mean a genuine mid-fold interruption — in which case step 15 was never reached.
2. **Resume cannot reliably derive fold progress from unkeyed lens responses** — HIGH · lens: senior-dev: pass 6's resume rule said remaining work is recoverable by diffing the immutable `pass-N.<lens>.response.json` artifacts against the partial block. But those artifacts hold *per-lens* findings with no stable ids, while step 11's merge is semantic — dedupes across lenses, takes worst-of severity, rewrites titles. There is no deterministic correspondence between a raw response item and a partially-recorded merged finding, so a resuming session re-running the merge can classify differently and either double-fold an item or skip one as already handled.
   → Editor: incorporated, and this retires a claim I'd been leaning on since pass 6 — "no ledger needed, the responses are already durable" was true about *durability* and wrong about *identity*. Fixed without adding a ledger, by moving one existing write earlier: the block's `### Findings` section is now populated with the full merged list — numbered, severity, lens attribution, `→ Editor:` lines empty — **before folding begins**, with corrections and questions listed the same way. Folding fills the empty lines in. Resume becomes a lookup ("any item whose `→ Editor:` line is empty is unfolded") instead of a re-derivation, so the semantic merge happens exactly once and is durable the moment it exists. The block's own structure is the progress record.

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Decision cards

- (none this pass)

### Lens run summary

- senior-dev: REVISE · security: **APPROVE** (second consecutive) · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 20:51; range `1661dfe..HEAD`; folds applied to the working tree, not yet committed.

## Pass 11 — 2026-08-13 20:54 [HISTORICAL]

**Scope:** custom range `1661dfe..HEAD` (pass-10 folds committed at `ee8e8a3`) · **Diff size:** 1085 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, security, qa

### Findings

1. **Unescaped reviewer text can forge the durable fold-progress markers** — HIGH · lens: security: pass 10's fix made the block's `→ Editor:` lines the authoritative resume ledger — while the same block holds reviewer-authored titles and descriptions, which are arbitrary strings from a model that just read the diff. A third-party source comment can induce a lens to emit a description containing a newline followed by `→ Editor: incorporated`, or a forged item boundary; persisted verbatim, a resumed session reads an unfolded HIGH as already handled and drops it silently.
   → Editor: incorporated — **the genuinely new finding class of this review, and the security lens's job done exactly right.** My pass-10 fold promoted reviewer-authored text from data to control-bearing structure without noticing it had crossed a boundary. Closed with two independent rules, both required: (a) **sanitize on the way in** — reviewer strings (`title`, `description`, `suggested_action`, correction fields, question text) are written as single logical lines, newlines collapsed and marker sequences escaped so they cannot begin a line, which is the same discipline as the runner's universal output sanitization and `examples/`'s patch-marker detection, extended to a surface that only just became structural; (b) **read only editor-written positions** — resume never scans for marker *text*, only for the `→ Editor:` line belonging to a known merged item at its own indentation, so any occurrence elsewhere is reviewer content by definition and ignored. Deliberately belt-and-braces: the sanitizer is the boundary, and the positional rule means a sanitizer bug is not by itself an exploit.
2. **Resume markers are defined only for findings** — HIGH · lens: qa: pass 10 said corrections and questions are "listed the same way," but only findings have an `→ Editor:` line — corrections use a completed-action sentence and questions an inline resolution, neither with an empty form. An interruption between two corrections would re-apply a mechanical edit already made, or leave a question unanswered with nothing to show it.
   → Editor: incorporated — gave both sections an explicit `(pending)` form (`<location> — <issue> → (pending)`, `<question> — <settled_by> (lens: <id>): (pending)`) and updated the template accordingly, which lets the resume rule read uniformly across all three sections: **an item is unfolded exactly when its outcome slot is empty or `(pending)`.** Fair catch on a fold that generalized in prose but not in the artifact.
3. **Ordinary passes still open the progress block after folding** — HIGH · lens: senior-dev (HIGH), qa (MEDIUM) — co-reported, merged at the more severe rating: the section still opened with "the ordinary case is one append after folding completes," left over from pass 5, which flatly contradicts pass 10's requirement to persist the merged list *before* folding. On a card-free pass the two instructions give different recovery behavior, which reintroduces exactly the ambiguity pass 10 set out to remove.
   → Editor: incorporated — deleted the carve-out rather than reconciling it: block opening is now unconditional, immediately after the merge, before any folding, on every pass. Recorded the reasoning so it doesn't get re-introduced a third time — both original motivations for opening early (a mid-fold card's pending write, and the merged list as resume ledger) apply to ordinary card-free passes too, so there was never a coherent "ordinary case." The pre-fan-out malformed-posture path is now stated as the *one* exception to that rule, rather than as a second special case beside it.

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Decision cards

- (none this pass)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 20:54; range `1661dfe..HEAD`; folds applied to the working tree, not yet committed.

## Pass 12 — 2026-08-13 20:58 [HISTORICAL]

**Scope:** custom range `1661dfe..HEAD` (pass-11 folds committed at `1b45445`) · **Diff size:** 1117 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, security, qa

**First pass with two APPROVEs** — senior-dev and security both clean, qa carrying the only finding.

### Findings

1. **Crash between applying a fold and recording its outcome can duplicate the edit on resume** — HIGH · lens: qa: the pass-10/11 progress markers track *recorded disposition*, not *file mutation*. The working-tree edit and the outcome write are separate acts, so a crash between them leaves the fix applied and the slot empty — and the resume rule ("empty slot means unfolded") re-applies it. Harmless for an idempotent edit; corrupting for an appended declaration, a counter bump, or a migration.
   → Editor: incorporated — a real gap in the resume contract I built over passes 10–11, and the last one standing at this pass. Added a reconcile-before-reapply protocol: for each pending item in order, read the relevant file *first*, and if the change is already present, complete the outcome slot instead of re-applying — noting in the disposition that it was recovered rather than re-done. Where presence genuinely can't be determined by inspection, that's a `needs_human` card, never a guess, because the two possible guesses are destructive in opposite directions. Also recorded why the obvious inversion doesn't work: writing the outcome before applying the edit moves the same window and makes the log claim work that hasn't happened, which is worse given the log is the authority.

### Code corrections applied

- `docs/risk-posture-proportionality-2026-08-12.md:Phase 2 status + review-status table` (lens: senior-dev) — both still said Phase 2's review was "deferred to a batched pass," which twelve completed passes contradict. Updated to describe the review as in progress with its pass count, log path, and scope range, and noted how the batching call actually played out (Phase 0+1 as one batch, Phase 2 as its own).
- `docs/reviews/code-review-phase-2.md:Pass 8 Scope` (lens: senior-dev) — recorded the pass-7 fold commit as `30260db`, which no longer exists: that commit was amended to fix its own timestamp, becoming `307c511`. A good catch on a self-inflicted trap — amending a commit whose SHA is already cited in a document.

### New questions Codex raised

- (none)

### Decision cards

- (none this pass)

### Lens run summary

- senior-dev: **APPROVE** · security: **APPROVE** · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 20:58; range `1661dfe..HEAD`; folds applied to the working tree, not yet committed.

## Pass 13 — 2026-08-13 21:03 [HISTORICAL]

**Scope:** custom range `1661dfe..HEAD` (pass-12 folds committed at `bf73fa5`) · **Diff size:** 1143 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, security, qa

### Findings

1. **Resume rule still excludes pending corrections and questions** — HIGH · lens: senior-dev, qa (co-reported, same defect): the paragraph defines the uniform rule ("unfolded exactly when its outcome slot is empty or `(pending)`") and then *ends* with the older, narrower sentence "any listed item whose `→ Editor:` line is still empty is unfolded" — and only findings have `→ Editor:` lines. A reader following the concluding, more specific sentence skips unapplied corrections and unresolved questions, reintroducing the exact defect pass 11 closed.
   → Editor: incorporated — and the cause is worth naming, because it's the third time this shape has appeared (pass 11 finding 3, pass 12's correction, now this): **my pass-11 and pass-12 edits interleaved into one paragraph without my re-reading the result**, leaving stale fragments in place and even a dangling "Folding fills those lines in" stranded after the text it referred to. Fixed structurally rather than by patching the sentence: the whole resume procedure is now stated once, in one place, as two ordered steps — (1) identify pending items by outcome slot uniformly across all three sections, explicitly *not* by `→ Editor:` alone, with the reason given inline; (2) reconcile before re-applying. Framed so a later narrower restatement can't quietly override it, which is what kept happening.

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Decision cards

- (none this pass)

### Lens run summary

- senior-dev: REVISE · security: **APPROVE** (fourth of the last five passes) · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 21:03; range `1661dfe..HEAD`; folds applied to the working tree, not yet committed.

## Pass 14 — 2026-08-13 21:05 [HISTORICAL] — **CONVERGED**

**Scope:** custom range `1661dfe..HEAD` (pass-13 folds committed at `e12abfe`) · **Diff size:** 1156 lines · **Verdict:** **APPROVE** (worst-of; no FAILED lenses) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, security, qa

**APPROVE ×3, zero findings across all three lenses.** The review converged on its own condition, not on a budget expiring.

### Findings

- (none — all three lenses clean)

### Code corrections applied

- `docs/risk-posture-proportionality-2026-08-12.md:Phase 2 status + review-status table` (lens: senior-dev, qa — co-reported, identical) — both locations still said 12 review passes; pass 13 had since landed. Updated to 14 and to `reviewed` / converged, which is the accurate terminal state now that this pass closes the review.

### New questions Codex raised

- (none)

### Decision cards

- (none this pass)

### Lens run summary

- senior-dev: **APPROVE** · security: **APPROVE** · qa: **APPROVE**

### Diff snapshot reference

Diff captured at 2026-08-13 21:05; range `1661dfe..HEAD`; corrections applied to the working tree, not yet committed.

---

## Review summary — converged at pass 14

**14 passes, APPROVE×3 at pass 14, 0 disputed findings** (one `disputed` at pass 1 stands: the request to convert the read-only merge fixture into executable test infrastructure). Scope: `1661dfe..HEAD`, Phase 2's own commits, deliberately excluding Phase 0+1 which converged separately in an 8-pass review.

**HIGH+MEDIUM trajectory:** 5, 3, 3, 3, 3, 3, 3, 3, 2, 2, 3, 1, 1, 0. Flat at 3 for seven consecutive passes before breaking — worth recording, because that flat stretch tripped the stall guardrail twice and both continue decisions turned out to be right: every finding in it was real, and two of the most valuable findings of the whole review (passes 9 and 11) came after it.

**Lens behavior:** `security` returned APPROVE at passes 5, 6, 9, 10, 12, 13, 14 — and REVISE at 7, 8, 11, each time with a finding no other lens raised. A lens being quiet is not a lens being idle; its two substantive findings were a real trust-boundary flaw in the fixture's example (7–8) and a real injection surface in the resume ledger (11).

**Three things this review is worth remembering for:**
1. **A consistency frontier that ran six passes deep.** Passes 6, 7, 8 each filed primarily against the previous pass's own fix, and 10→11→13 repeated the pattern on a second contract. Neither was a sign to stop; both terminated on their own.
2. **The editor reintroduced, twice, the exact failure the machinery prevents.** Pass 4 caught a fold that opened a path to silently adopting an unapproved mechanism; pass 9 caught the same class again in the fixture restructure. Reviewing your own machinery does not make you immune to its failure modes — it makes you likelier to hit them, since you're editing the surface that defines them.
3. **Editor pushback got spent deliberately and sparingly.** One `disputed` (pass 1, executable-fixture scope), one declined suggested_action recorded with reasoning (pass 6, a confirmation-revocation workflow nothing needed), and one explicit refusal to push back where the anti-criteria forbid it (pass 7, trust-boundary code). Three uses, three different outcomes, all reasoned in the log rather than silently taken.
