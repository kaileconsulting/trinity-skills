# Code Review — branch-kyle-risk-posture-phase-0

## Pass 1 — 2026-08-13 12:19 [HISTORICAL]

**Scope:** branch · **Diff size:** 380 lines · **Verdict:** REVISE (worst-of; single lens) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev

### Findings

1. **Newly seeded register is immediately malformed to iterate-review** — HIGH · lens: senior-dev: `create-plan/SKILL.md` Step 3 has the skill create `docs/risk-posture.md` with only an `## Accepted risks` H2 and the new entry when the file doesn't exist — no `PF-` fields at all. `iterate-review/SKILL.md` Step 9, as originally written, would then treat a repo posture file missing any `PF-` field as malformed and halt before fan-out, so the create-plan-documented seeding path produced a file the consuming workflow immediately rejected.
   → Editor: incorporated — redefined "malformed" in Step 9 to distinguish a genuinely broken attempt (some but not all three `PF-` fields present, or duplicate `RR-` ids) from a file that never attempted posture fields at all (register-only, exactly what create-plan's seeding produces). The latter is now explicitly documented as a normal, valid state: it resolves as "no `PF-` fields from the repo file" while the register is still read from it as usual.
2. **Digest excludes wrapped bound and recovery text** — HIGH · lens: senior-dev: Step 11 defined the register-match digest as the sha1 of the single physical `- **RR-<id>** — ...` line, but `create-plan/template.md`'s own canonical register example wraps one entry across two physical lines (bound/recovery/date continue on an indented second line). Under the original recipe, editing only the wrapped continuation text — i.e. the actual bound or recovery path — would not change the digest, so an invalidated entry could keep passing as a valid `register-match` on later passes or resume. This defeats the invalidation invariant the digest exists to provide.
   → Editor: incorporated — redefined the digest extraction in Step 11 to cover the entry's complete logical bullet (every physical line from the `- **RR-<id>** — ` marker up to the next `- **RR-` bullet or section end), each line trailing-whitespace-stripped and joined with `\n`, before hashing. A single-line entry is unaffected (it's the degenerate one-line case of the same rule).

### Code corrections applied

- `iterate-review/reviewer-prompt.md:ON RISK POSTURE` — "v1 has no automatic discovery" was imprecise: the repo's `docs/risk-posture.md` *is* read automatically; only automatic *plan* discovery is deferred to v2. Reworded to state both facts so a lens doesn't misread posture-block absence as meaning "nothing has been set up" when actually "no plan was named" is the more common absence case.
- `iterate-review/SKILL.md:Pointers` — the create-plan pointer claimed create-plan scaffolds `docs/risk-posture.md`'s "posture fields and register entries"; create-plan's Step 3 only ever seeds the register. Corrected to say register entries only, with a note on where posture fields actually come from.

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 12:19; head SHA `43ef07758ff5cc3feaec8e3a66aea0b9a4d98f05`.

## Pass 2 — 2026-08-13 12:21 [HISTORICAL]

**Scope:** branch · **Diff size:** 380 lines · **Verdict:** REVISE (worst-of; single lens) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev

### Findings

1. **Register-only files are validated but never exposed to reviewers** — HIGH · lens: senior-dev: a direct consequence of the Pass 1 fold — Step 9 said the register always comes from `docs/risk-posture.md` independent of field precedence, but the block-composition trigger was still gated on "if a source resolved" for *fields*. So a register-only file (Pass 1's newly-legitimized state) resolved zero fields, the whole `RISK POSTURE` block was skipped, and the register's entries never reached the lenses at all — silently defeating `register_ref` tagging for exactly the state Pass 1 just declared valid.
   → Editor: incorporated — decoupled the block's trigger from the field/register distinction: it now composes whenever `PF-` fields resolved OR the register has ≥1 entry (or both), omitting only the parts that didn't resolve (no `PF-` lines when fields are none; no register sub-block when the register is absent/empty — not written as "none recorded," so an empty register and no-file-at-all compose identically). Only skips entirely when *both* are empty. Added a fifth **Posture:** log value, `register-only (no PF- fields; N entries)`, so this state is distinguishable from `absent` in the pass log.

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 12:21; head SHA `43ef07758ff5cc3feaec8e3a66aea0b9a4d98f05`.

## Pass 3 — 2026-08-13 12:23 [HISTORICAL]

**Scope:** branch · **Diff size:** 380 lines · **Verdict:** REVISE (worst-of; single lens) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev

### Findings

1. **Collected posture answers are never written into the generated plan** — HIGH · lens: senior-dev: `create-plan/SKILL.md` Step 3 collects all three posture answers during the same scaffolding conversation, but Step 6's generation transforms only pruned the unused variant and explicitly retained the `...` stubs — no instruction replaced them with what was just collected. Following the workflow literally produced a plan without the promised posture content, and Step 7 then sent the author back to fill in a section that should already have been done.
   → Editor: incorporated — Step 6's Risk-posture prune transform now explicitly populates the surviving variant (full or lightweight) from Step 3's answers instead of leaving placeholders, with a note distinguishing this from TL;DR/Why/Approach (which are never collected at scaffold time and are correctly left for the author). Step 7's guidance updated to say Risk posture is already filled in, rather than listing it among sections still needing content.
2. **Register matching does not enforce PF-shipbar trust-boundary exclusions** — HIGH · lens: senior-dev: `create-plan/template.md` names trust-boundary code as exempt from `accepted-risk` entirely (the anti-criteria), but `iterate-review/SKILL.md` Step 11's `register_ref` validation checked only behavior/bound/recovery — never whether the finding concerns a `PF-shipbar`-named boundary. A register-match is functionally a pre-confirmed accepted-risk (no fresh human sign-off), so a matching entry could silently disposition an auth/approve/payments-path defect as `register-match`, contrary to the posture's own stated exemption.
   → Editor: incorporated — Step 11 now checks the trust-boundary exclusion as a second gate after the behavior/bound/recovery check: if `PF-shipbar` is available for this pass and the finding concerns the boundary it names, the match is invalid regardless of fit, and the finding dispositions normally instead. No `PF-shipbar` available (e.g. the register-only case) means nothing to exclude against — doesn't block matching.

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 12:23; head SHA `43ef07758ff5cc3feaec8e3a66aea0b9a4d98f05`.

## Pass 4 — 2026-08-13 12:24 [HISTORICAL]

**Scope:** branch · **Diff size:** 380 lines · **Verdict:** REVISE (worst-of; single lens) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev

### Findings

1. **Review input omits the incorporated code changes from prior passes** — HIGH · lens: senior-dev: the DIFF supplied to this pass was still the original pre-fold diff (branch vs `main` at commit `43ef077`), while PRIOR PASSES claimed Passes 1–3's incorporations. The editor's own folds were sitting uncommitted in the working tree, so `--scope=branch`'s `git diff <merge-base>...HEAD` never picked them up — an execution mistake, not a defect in the reviewed prose itself. Correctly flagged: reviewing a stale diff risks re-filing already-resolved findings or approving unreviewed behavior.
   → Editor: incorporated — committed Passes 1–3's folds (`f941cf7`) so the diff recaptured for Pass 5 onward reflects HEAD, matching the established operational practice (recapture the diff each pass so reviewers see folds — see the runner-scripts project's own hard-won lessons on this exact point).

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 12:24; head SHA `f941cf77dd62647ba44cffbb4f29676a96f0f2a7`.

## Pass 5 — 2026-08-13 12:30 [HISTORICAL]

**Scope:** branch · **Diff size:** 558 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, security, qa

### Findings

1. **Reviewer contract still describes required register_ref as optional** — HIGH · lens: senior-dev: `reviewer-prompt.md` still said "`register_ref` — optional," left over from before the Pass-4-adjacent schema fixup made it a required-but-nullable field. A lens following the stale prose could omit the field entirely, reproducing the exact structured-output rejection this fixup exists to prevent.
   → Editor: incorporated — reworded to "required field, but set it to `null` in the common case," matching the schema.
2. **Accepted-risk seeding does not handle an existing file without the register section** — HIGH · lens: senior-dev: `create-plan/SKILL.md` Step 3's seeding steps handled "file doesn't exist" and "file exists with the H2 already" but not "file exists with only `PF-` fields, no `## Accepted risks` H2 yet" (a valid state per Pass 1's own fold).
   → Editor: incorporated — added the missing case: add the H2 to the existing file, then the entry under it.
3. **Branch-controlled register entries are treated as pre-authorized risk acceptance** — HIGH · lens: security: register-match validation checked behavior and (as of Pass 3) trust-boundary exclusion, but never that the entry *predates* the diff being reviewed. A contributor could add or edit an `RR-` entry in the same branch as a real defect and have it wave through as `register-match` with no fresh human confirmation — the entry's "standing confirmation" claim only holds if it isn't self-supplied by the same change it excuses.
   → Editor: incorporated — restructured register_ref validation into three explicit, ordered gates: **(1) provenance** — the entry's exact text (by the digest recipe) must already exist at the diff's base revision (`merge-base HEAD main` / `HEAD` / the PR's base ref, per scope); **(2) behavior** — the existing bound/recovery match check; **(3) trust-boundary** — Pass 3's `PF-shipbar` exclusion. All three must pass; any failure means untagged, disposition normally.
4. **New posture workflows have no regression coverage** — MEDIUM · lens: qa: register-only composition, malformed-field rejection, wrapped-entry digest invalidation, precedence, and trust-boundary exclusion were all newly documented behavior with no fixture — exactly the gap that let two of this pass's own bugs (the digest and the malformed-source redefinition) ship undetected in Pass 1's original draft.
   → Editor: incorporated — added `examples/merge/03-register-match-gates/` (real, computed sha1 digests, not hand-waved): pins the three-gate order evaluated **per-finding** (two findings sharing one `register_ref` get different dispositions when only one touches trust-boundary code), and a wrong-result table reproducing this review's own three real bugs (first-line-only digest silently misses a wrapped amendment; skipped trust-boundary gate; skipped provenance gate) with the actual digest values that would result from each. Scoped to the highest-value combination rather than exhaustive coverage of every listed case — flagged as a scope choice, not an oversight, should broader coverage be wanted later.

### Code corrections applied

- `iterate-review/SKILL.md:Step 12 pass-log header template` (co-reported: senior-dev, qa) — the documented `Posture:` value alternatives omitted `register-only (no PF- fields; N entries)`, though Step 9 requires it. Added to the Step 12 template.

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 12:30; head SHA `f941cf77dd62647ba44cffbb4f29676a96f0f2a7`.

## Pass 6 — 2026-08-13 12:48 [HISTORICAL]

**Scope:** branch · **Diff size:** 700 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, security, qa

### Findings

1. **Prior register matches bypass provenance and trust-boundary revalidation** — HIGH · lens: senior-dev: the invalidation-recheck instruction only recomputed the digest before trusting a carried `register-match`, but the other two gates have inputs that can also change between passes — a mid-review posture change could add the finding's location to `PF-shipbar`, or a rebase could make the entry absent at a newly-resolved base revision — and neither would be caught by a digest-only recheck.
   → Editor: incorporated — broadened the recheck to re-run all three gates (digest, base-revision provenance, trust-boundary) against the *current* pass's context before trusting a carried match, not just the digest.
2. **SHA-1 is used for a security-sensitive acceptance-integrity check** — MEDIUM · lens: security: the register-match digest is an adversarial integrity boundary (it's what the provenance gate relies on to detect a self-serving edit), and SHA-1's broken collision resistance is inappropriate for that role even though exploitation would require an attacker who also controls the entry's original wording.
   → Editor: incorporated — digest recipe switched to sha256. Recomputed all three fixture digest values in `examples/merge/03-register-match-gates/` (real values, not placeholders). Left the unrelated, non-adversarial state-file `scope-hash` (Setup step 6, pre-existing, sha1-of-tag-and-path for namespacing only) untouched — noted explicitly in SKILL.md why that one stays sha1.
3. **Posture composition and seeding paths remain uncovered** — MEDIUM · lens: qa: scenario 03 covers register-match validation but not register-only composition, malformed-source rejection, plan-over-repo precedence, or create-plan's existing-file-without-H2 seeding path.
   → Editor: **skipped**, deliberately, with reasoning for the record: scenario 03 already targets the single highest-risk, adversarial-integrity-relevant path (register-match validation) and caught three real bugs doing it. The remaining named paths are prose-procedural branches with no adversarial dimension — closer in kind to the existing composition/selection prose this repo already exercises through real usage and `iterate-plan` smoke tests, not through exhaustive merge fixtures. Building a fixture for every named branch of a tool that reviews itself is exactly the "meta-tooling past diminishing returns" pattern already on record for this project (memory: `trinity-expansion`, "Honest assessment on record"). This is a proportionality call in the same spirit as the initiative under review — flagged prominently for Kyle rather than either silently dropped or reflexively built.

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-13 12:48; head SHA `e61f345752d291796d732e8ec985483ffced7ce5`.

## Pass 7 — 2026-08-13 12:54 [HISTORICAL]

**Scope:** branch · **Diff size:** 700 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, security, qa

### Findings

1. **Carried-match revalidation omits the behavior gate it claims to rerun** — HIGH · lens: senior-dev: my own pass-6 fold said "re-run all three gates" but only actually prescribed digest/provenance-recheck plus trust-boundary reapplication — the behavior gate was silently dropped from the recheck, and "digest" was imprecisely presented as if it were a fourth, separate gate rather than the mechanism the provenance gate uses.
   → Editor: incorporated — rewrote the recheck as three explicit sub-bullets (provenance/digest, behavior, trust-boundary), each re-evaluated on its own terms; digest is now described as provenance's mechanism, not a standalone gate.
2. **Branch-controlled PF-shipbar changes can bypass the trust-boundary gate** — HIGH · lens: security: the trust-boundary gate (pass 3) checked only the *current* pass's resolved `PF-shipbar`. A contributor could leave a register entry untouched (passing the provenance gate) while narrowing `PF-shipbar` in the same diff to drop the affected path from the named trust boundaries — the same self-serving-edit shape the provenance gate defends against, but aimed at the exclusion rule instead of the acceptance.
   → Editor: incorporated — gate 3 now checks **both** the current pass's `PF-shipbar` and its content at the diff's base revision; either naming the code as a trust boundary fails the gate. This lets a legitimate expansion apply immediately while preventing a same-diff narrowing from retroactively legalizing the defect it exempts. Added a fourth wrong-result row to `examples/merge/03-register-match-gates/` covering this exact exploit.

### Code corrections applied

- `iterate-review/SKILL.md:Step 12 dispositions paragraph` (lens: senior-dev) — the invalidation summary named only "digest mismatch or the entry was removed," contradicting Step 11's broader current-context gates. Reworded to cover all three gates generically.

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: APPROVE

### Diff snapshot reference

Diff captured at 2026-08-13 12:54; head SHA `753e72ca57977f3b46d10f6fee13658af96259c1`.

**Max-pass guardrail fired after pass 7** (6 auto-continued passes, still REVISE). Kyle's checkpoint decision: continue with a fresh budget — every fold to this point was a real, non-manufactured finding and the HIGH+MEDIUM count was trending down (4→3→2), not stalling.

## Pass 8 — 2026-08-13 12:58 [HISTORICAL]

**Scope:** branch · **Diff size:** 706 lines · **Verdict:** APPROVE (worst-of; all three lenses clean) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, security, qa

### Findings

- (none — first fully clean pass; all three lenses APPROVE)

### Code corrections applied

- `iterate-review/SKILL.md:Step 12 pass-log header template` (lens: senior-dev) — the `both-present` Posture value was spelled `repo shadowed` in the Step 12 template, while Step 9 defines the canonical wording as `repo fields shadowed`. Unified on Step 9's wording.

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: APPROVE · security: APPROVE · qa: APPROVE

### Diff snapshot reference

Diff captured at 2026-08-13 12:58; head SHA `2acd3063d77a8fe0bf8096cae2761271c31e6443`.
