# Code Review — branch-kyle-trinity-v2-4

## Pass 1 — 2026-08-21 13:45 [HISTORICAL]

**Scope:** branch · **Diff size:** 1525 lines · **Scope class:** production · **Verdict:** REVISE (worst-of; senior-dev: REVISE, security: APPROVE, qa: REVISE) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, security, qa

### Findings

1. **Freeze streak counting was ambiguous between "counted passes" and "pairwise comparisons"** — HIGH · lens: senior-dev: `iterate-plan/SKILL.md`'s counting-semantics text said a pass counts "only when... equivalent to the prior counted pass," without stating that the first answered pass in a streak trivially becomes counted-pass #1. Read the other way (N consecutive *matches*, i.e. N+1 answered passes), the worked example's "frozen at pass 6 after passes 4/5/6" would require a 4th pass to actually reach N=3.
   → Editor: incorporated — added an explicit baseline clause to the counting-semantics bullet stating the first answered pass after any reset trivially becomes counted-pass #1, walked the pass-4/5/6 arithmetic out concretely, and built `tools/freeze_tracker.py` (a pure reference implementation of the algorithm) plus `tools/check-question-freeze.py` (11 fixture cases, including this exact sequence) as the normative tie-breaker if prose and implementation ever seem to disagree. [introduced_by_pass: null]
2. **Reduced pass budget does not mean three total passes** — MEDIUM · lens: senior-dev: the pre-existing max-pass-cap semantics ("the activating pass doesn't count") mean a budget of 3 auto-continued passes allows 3 passes *beyond* the activating one (e.g. passes 2, 3, 4 from a pass-1 activation) — but the new prose illustrated the exhaustion-checkpoint guard with "a pass-2 fold on a 3-pass budget," which doesn't match that accounting and implies the budget caps at pass 3.
   → Editor: incorporated — rewrote the Max-pass cap guardrail bullet to state the activation-exemption accounting explicitly with the concrete pass numbers (2, 3, 4 from a pass-1 activation), replaced the wrong "pass-2 fold" illustration with "the *last* auto-continued pass before the cap fires," and added the complementary sentence for the common case (a fold on the second-to-last auto-continued pass is already covered — one more pass remains to verify it). [introduced_by_pass: null]
3. **New analytics checker assumes `jq` is installed without a dependency guard** — MEDIUM · lens: senior-dev: `tools/check-all.sh` unconditionally runs `tools/check-provenance-recipe.py`, which shells out to `jq` directly — if `jq` is absent, the checker crashes with an unhandled `FileNotFoundError` traceback instead of a clear, actionable error.
   → Editor: incorporated — added an explicit `shutil.which("jq")` guard at the top of `check-provenance-recipe.py`'s `main()` (clean error + exit 2, not a traceback) and a defense-in-depth check inside `run_recipe()` for anyone calling it as a library function directly; documented `jq` as a prerequisite in `check-all.sh`'s header comment and in the checker's own module docstring. [introduced_by_pass: null]
4. **New loop-control behavior (scope classification, question freezing) is covered only by prose examples** — HIGH · lens: qa: the diff introduces two user-observable control-flow changes with no executable behavioral coverage — a wording or implementation drift could silently misclassify a diff, ignore a `FAILED`-lens pass's correct non-effect on the freeze streak, or leave a stale frozen annotation, and nothing would fail. These paths affect review depth and finding suppression, which `PF-shipbar` (this plan's stated ship bar) identifies as a ship-blocking trust boundary.
   → Editor: incorporated — built `tools/scope_classifier.py` + `tools/check-scope-classification.py` (12 fixture cases: the three SKILL.md worked examples plus case-insensitivity, bare filename conventions, empty input, and a real path from this diff) and `tools/freeze_tracker.py` + `tools/check-question-freeze.py` (11 fixture cases: the 3-pass freeze, `FAILED`-pass skip in three positions, differing-answer reset, alternating-never-freezes, and the reopen/unfreeze state-reset). Both wired into `check-all.sh`. Left uncovered by design: the "`--max-passes` always overrides either default" behavior — there's no classification or counting computation to verify there, only argument-parsing precedence already stated as a Hard rule; a dedicated fixture would test the harness's own flag-precedence handling, not anything this plan's design introduces. [introduced_by_pass: null]

### Code corrections applied

- `iterate-plan/SKILL.md:221` — the invariant-walk item's bold span closed before its parenthetical did (`**Invariant walk (`iterate-plan`-only** — ...)`), a malformed nesting order. → Reordered to `**Invariant walk** (`iterate-plan`-only — ...)`.

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: APPROVE · qa: REVISE

### Fold-provenance pilot note

All 4 findings trace to the original Phase 0 diff, not to a prior fold within this review (`introduced_by_pass: null` throughout — this is pass 1, no prior pass exists to have caused anything). Consistent with §5's data-collection-only scope: this note records the judgment, nothing consults it for control flow.

### Diff snapshot reference

Diff captured at 2026-08-21 13:45; head SHA `798a23355e751f9266d81e90fd5fcf7e7134a864`.

## Pass 2 — 2026-08-21 13:52 [HISTORICAL]

**Scope:** branch · **Diff size:** 1965 lines · **Scope class:** production · **Verdict:** REVISE (worst-of; senior-dev: REVISE, security: APPROVE, qa: REVISE) · **Posture:** absent (no `docs/risk-posture.md` in this repo; no governing plan named for this review invocation) · **Lenses:** senior-dev, security, qa

### Findings

1. **Freeze reference implementation collapses per-lens answers into one merged token** — HIGH · lens: senior-dev: `iterate-plan/SKILL.md`'s counting-semantics text said a pass counts only when "every lens's answer is equivalent to the prior counted pass," which reads as requiring per-lens tracking — but `tools/freeze_tracker.py` (pass 1's fold) models one merged token per pass, and the checker can't exercise a case where one lens's phrasing changes while the aggregate resolution stays the same.
   → Editor: incorporated (via alternative) — not by rebuilding the reference tool to fake per-lens granularity, which would encode a design the system doesn't actually have: step 7's existing cross-lane merge rule already reconciles lenses into one answer (or an escalated disagreement) *before* freeze-counting ever sees a pass. Rewrote the counting-semantics bullet to state the comparison unit explicitly — the merged, per-pass answer produced by that existing merge rule, not each lens's individual phrasing — so the prose now matches what `freeze_tracker.py` already correctly modeled (its own docstring already described the token as "the editor's semantic-equivalence judgment of this pass's merged answer"; the ambiguity was in `iterate-plan/SKILL.md`'s prose, not the tool). [introduced_by_pass: 1 — the ambiguity exists because pass 1's fold introduced the counting-semantics bullet and the reference tool without walking the "every lens" phrasing through what the tool actually models]
2. **Freeze reopening and annotation removal remain untested** — HIGH · lens: qa: `check-question-freeze.py` exercises the counting state machine but never verifies that reopening actually removes the plan file's inline `— FROZEN...` annotation, or that a reopened question is presented to lenses again — the user-observable suppression/reopen behavior itself had no coverage, and `iterate-plan/SKILL.md` never even specified what happens to the annotation on reopen.
   → Editor: incorporated, per the finding's own suggested fallback ("narrow the claim... provide another verifiable safeguard") — this is an editor plan-file-mutation action (find a question's line, remove an annotation), not deterministic computation, and this skill has no automated-mutation tests for any of its other fold-time writes either (HISTORICAL blocks, dispositions, plan_corrections) — freeze annotations aren't a principled exception. Two fixes: (1) `iterate-plan/SKILL.md`'s Reopening paragraph now explicitly specifies the previously-unspecified behavior — reopening removes the inline annotation, returning the question to its plain form, with the freeze/reopen *events* staying on the record in their passes' HISTORICAL blocks regardless; (2) the worked-example callout and the Pointers entry for `freeze_tracker.py`/`check-question-freeze.py` now state precisely what they cover (the counting state machine) and don't, narrowing the earlier claim rather than leaving it to imply full behavioral coverage. [introduced_by_pass: 1 — the untested annotation-removal path, and the prose gap about what removal even means, both trace to pass 1's fold]

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: APPROVE · qa: REVISE

### Fold-provenance pilot note

Both findings this pass trace to pass 1's fold — `introduced_by_pass: 1` for both; **this pass is fully fold-induced**. Consecutive fully-fold-induced passes: 1 (pilot surfaces to Kyle at 2, per this plan's own hand-piloted rule). Worth noting: both findings identify real gaps (a genuine prose/tool mismatch, and a genuinely untested behavior with a previously-unspecified design point) rather than vocabulary hygiene — consistent with the retro's caveat that fold-induced findings are sometimes load-bearing, not automatically noise.

### Diff snapshot reference

Diff captured at 2026-08-21 13:52; head SHA `86cd896eedfa2c82de155943146e600013053d1a`.
