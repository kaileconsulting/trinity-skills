# Trinity Axis 2 — Persona Lenses — Plan

## TL;DR

Today each trinity review pass is a single `codex exec` invocation with one reviewer persona baked into `reviewer-prompt.md`. A single persona shares one framing's blind spots across every issue category — an "architect" framing underweights product-fit, and a general "staff engineer" framing underweights QA edge-cases and security trust-boundaries. **Axis 2 adds persona/lens breadth:** `iterate-plan` and `iterate-review` will run a *deterministically-selected* set of persona lenses **in parallel**, and Opus will **merge** their findings into one list to fold — one pass, one human checkpoint, broader coverage.

Personas are the *breadth* knob (expand the set of questions asked); they are explicitly **not** a reliability knob (that's Axis 1's cross-vendor tiebreaker, deferred). Selection is a **deterministic rules table keyed on plan/diff shape — never an LLM router** (a misrouting router would skip the lens that catches the bug). Selected lenses run concurrently and merge; each lens is fed its matched context so it isn't theater.

Outcome: more issue-*category* coverage per pass, with the loop's convergence property and single-checkpoint discipline preserved.

This build also folds in an opt-in **loop mode** for both skills (`--loop` flag + an `(L)oop from here` checkpoint option): it auto-continues through REVISE passes and stops at the first APPROVE for the human's Converge call — automating the mechanical between-pass clicks **without ever auto-deciding convergence**. It rides along in Phase 1 because that phase already reworks the per-pass loop.

## Why / Context

The trinity's editor↔reviewer loop currently gets one reviewer viewpoint per pass. That viewpoint is competent but singular: whatever the persona in `reviewer-prompt.md` is framed to look for is what gets scrutinized, and everything outside that framing is underweighted. For plan review that means architecture gets attention but product-fit/acceptance-criteria coverage is incidental; for code review it means correctness gets attention but QA edge-cases and security trust-boundaries depend on the model volunteering them.

Persona diversity is a cheap fix: same reviewer model, fanned out across framings, buys coverage of more issue categories. It is decorrelated on *questions asked*, not on *detection reliability within a question* — a persona swap on one model still shares that model's blind spots. That reliability decorrelation is a different mechanism (cross-vendor, Axis 1) and is deliberately out of scope here.

Source brief: `/home/kyle/trinity-review-expansion-brief.md`. This plan implements **Axis 2** only. Axis 1 (Gemini disagreement-triggered tiebreaker) is sequenced after and its groundwork is already stood up.

## Who / Use cases

- **Plan author** running `iterate-plan`: wants architecture *and* product-fit scrutiny in a single pass, instead of hoping one persona covers both. Success: a REVISE pass surfaces both a structural drift finding and a "this acceptance criterion isn't verifiable" finding in the same round.
- **Code author** running `iterate-review`: wants the lenses matched to what the diff touches — senior-dev always, plus security when the diff touches auth/crypto/migration/input-parsing, plus QA when it changes user-facing behavior or ships without tests. Success: a diff that adds an unauthenticated endpoint gets a security finding it wouldn't have gotten from a generic reviewer.
- **Future (out of scope, [issue #1](https://github.com/kaileconsulting/trinity-skills/issues/1)):** teams add their own lenses via pluggable persona packs.

## Goals (MVP)

- A **deterministic lens-selection rules table** per skill, keyed on plan/diff shape (no LLM router).
- **Parallel lens execution**: Opus spawns one `codex exec` per selected lens concurrently.
- **Opus-side merge**: dedupe overlapping findings into a single list; aggregate verdict as worst-of; one HISTORICAL block; one Continue/Converge/Abort checkpoint per pass.
- Lenses shipped: `iterate-plan` → **architect + product-manager**; `iterate-review` → **senior-dev + QA + security**.
- **Matched context** delivered to each lens (see Approach — v1 scope is honest about framing-vs-extraction).
- **Lens attribution**: every merged finding records which lens raised it, in the HISTORICAL block — makes the loop self-measuring (see Approach → Measurement).
- **Fixtures** that exercise selection, merge/dedupe, and attribution so routing/convergence regressions are caught.
- **Loop mode** (opt-in): a `--loop` flag + `(L)oop from here` checkpoint option that auto-continues REVISE passes and stops at APPROVE for the human's Converge call, bounded by guardrails (see Approach → Loop mode).

## Non-goals (MVP)

- **Pluggable persona-pack loader** — deferred to [issue #1](https://github.com/kaileconsulting/trinity-skills/issues/1). v1 loads lenses from a fixed location, but they are data-shaped so the later loader is a swap, not a rewrite.
- **LLM-based lens routing** — explicitly rejected in the brief; deterministic selection only.
- **Cross-vendor tiebreaker (Axis 1)** — separate mechanism, sequenced next.
- **True per-lens context *extraction* on diffs** — v1 delivers matched context as prompt framing + already-available structured inputs; real extraction (e.g., computing trust boundaries from a diff) is a later enhancement.

## Approach

### Architecture

The per-pass loop grows a **fan-out → merge** stage. Everything else about the loop (Opus-sole-editor, patch-marker rejection, HISTORICAL audit trail, human checkpoint) is unchanged.

```
                         ┌─ lens A (persona + matched context) ─ codex exec ─┐
   select lenses ───────▶├─ lens B ───────────────────────────── codex exec ─┤──▶ Opus merge ─▶ one findings list ─▶ HISTORICAL + ONE checkpoint
   (deterministic table) └─ lens C ───────────────────────────── codex exec ─┘   (dedupe +
                                                                                    worst-of verdict)
```

- **Fan-out** is N concurrent `codex exec` subprocesses (one per selected lens), each `-s read-only -a never --output-schema …` exactly as today — only the persona framing and the matched-context payload differ per lens.
- **Merge** is Opus's job (consistent with Opus-sole-editor): collect the N schema-valid responses, dedupe near-identical findings, aggregate the verdict, fold as today.

### Lens definition shape (data-shaped, fixed location in v1)

Each lens is a small declarative record so the future pack-loader ([issue #1](https://github.com/kaileconsulting/trinity-skills/issues/1)) is a drop-in:

- `id` — e.g. `architect`, `product-manager`, `senior-dev`, `qa`, `security`.
- `persona_prompt` — the framing fragment layered onto the shared reviewer prompt (the shared HARD-RESTRICTIONS/output-contract stays common; only the ROLE/what-to-look-for differs).
- `matched_context` — spec for what context this lens receives (see below).
- `selection_predicate` — the deterministic condition under which this lens runs.

v1 stores **each lens as its own file** — `<skill>/lenses/<id>.md` with a small frontmatter record (decided Q1: per-file is cleaner to read and easier to extend than one combined file, and maps directly onto the future pack-loader); the SKILL.md reads them and applies the selection table.

### Deterministic selection rules

**`iterate-plan`:**
| Lens | Runs when |
|---|---|
| architect | always |
| product-manager | **always** — fed the plan's **Who / Use cases** and **Acceptance criteria** sections as context (guaranteed present by the `create-plan` template). If a non-template plan lacks those sections, PM still runs but is told they're missing and is expected to **flag the gap as a finding** (missing/unverifiable acceptance criteria is itself a PM concern) — never skipped, never fed empty context silently. |

**`iterate-review`** (keyed on diff shape):
| Lens | Runs when |
|---|---|
| senior-dev | always |
| security | diff touches auth / crypto / secrets / network / migration / input-parsing / env / permissions (path + content heuristics) |
| qa | diff changes user-facing behavior OR ships no test files alongside non-trivial code |

Selection *narrows* by change type; execution runs the survivors *in parallel*. Run the 2–3 that plausibly apply rather than picking exactly one. **Concurrency ceiling: 5 lenses max** (decided Q5). Typical selection today is ~3; the 5-cap only becomes live once pluggable packs land ([issue #1](https://github.com/kaileconsulting/trinity-skills/issues/1)) — at which point registering a 6th lens means retiring one.

**Ambiguity biases toward inclusion.** When a predicate is borderline — *is this "network"? is this "user-facing"? is a change "non-trivial"?* — the specialized lens **runs**. The risk model depends on over-inclusion (R5): a false include (a wasted lens) is cheaper than a false exclude (a missed category). Phase 0 must ship borderline worked examples that pin this bias, so implementers can't satisfy the listed examples with predicates narrow enough to miss common cases.

### Matched context (honest v1 scope)

"Persona without matched context is theater" (brief). For `iterate-plan` the context already exists as plan sections (architect → Approach/Architecture; PM → Who/Use-cases + Acceptance criteria), so v1 delivers *real* matched context by slicing those sections. For `iterate-review`, "trust boundaries" and "edge cases" are not cleanly extractable from a raw diff in v1 — so v1 delivers matched context as **prompt framing + the already-available inputs** (diff, intent, prior passes), and real extraction is deferred (Non-goal; decided Q2: framing-only is acceptable for v1). This is called out so the reviewer doesn't mistake framing for extraction.

### Merge, verdict aggregation, and the convergence guard

- **Dedupe:** Opus collapses findings that target the same location and assert the same defect (different lenses often co-report an obvious issue). Distinct concerns at the same location are kept separate. Dedupe is Opus's **semantic judgment, not a mechanical location+title key** (decided Q3: semantic collapse is exactly what the AI layer is good at; a hard key would be both too blunt and too brittle).
- **Verdict aggregation:** overall pass verdict = **worst-of** the selected lenses' verdicts (BLOCK > REVISE > APPROVE). Convergence still requires the single-APPROVE-plus-no-further-changes signal — now meaning *all selected lenses* APPROVE. A lens that only ever emits LOW findings therefore **cannot wedge convergence** — LOW is informational and an APPROVE-with-LOW-nits counts as APPROVE (resolves Q4). Each lens's persona prompt must state explicitly that LOW findings accompany an APPROVE verdict (not a REVISE), so a nit-only lens doesn't inflate the worst-of.
- **One checkpoint:** the fan-out produces exactly one HISTORICAL block and one Continue/Converge/Abort prompt per pass. Fan-out must never multiply human checkpoints — that is the load-bearing convergence property this plan must protect.
- **Lens failure policy:** a *selected* lens that crashes or returns malformed/off-schema output is **retried once**; if it still fails, `FAILED` is recorded as **orchestration metadata on the merge layer — not a reviewer verdict** (reviewers still emit only APPROVE/REVISE/BLOCK; the reviewer-output schema is unchanged). Deterministic aggregate mapping: a pass containing ≥1 failed selected lens emits aggregate verdict **REVISE**, and the `FAILED` metadata **independently blocks Converge** even if every lens that *did* run returned APPROVE — the coverage guarantee means the loop must not silently converge having skipped a selected lens. The failure is surfaced at the checkpoint with an explicit **(R)etry-failed-lens** option alongside Continue/Converge/Abort. Only selected-and-failed lenses block; unselected lenses are irrelevant. (Resolves the HIGH findings of passes 1 & 2 / Q6 / Q8.)

### Measurement — lens attribution

To answer "does Axis 2 actually help, and by how much?" without guessing, the merge step **tags every finding with the lens(es) that raised it**, and the HISTORICAL block records that tag alongside Opus's `incorporated|skipped|disputed` disposition. It's a few words per finding and turns every real review into a data point. Attribution lives in the HISTORICAL fold record (human-readable and greppable); because each lens is a *separate* Codex invocation, Opus knows the originating lens by construction at merge time, so **no per-invocation reviewer-schema field is needed in v1** — a machine-readable attribution field is a possible future measurement-tooling add (resolves Q7).

The ROI metric we care about: **the fraction of *incorporated* findings attributable to a non-default lens** (security / QA / PM — the lenses the pre-Axis-2 baseline would not have run). Over a few weeks of real use this replaces the priors below with an empirical, in-domain, false-positive-adjusted number.

Expected shape of the answer (prior, to be replaced by data): the lift is **categorical and tail-weighted, not a flat percentage** — ~0 on changes whose relevant category the default persona already covered, and occasionally decisive on changes with a blind-spot category the default persona underweights (e.g. an auth-touching diff whose author didn't think about auth). A seeded-bug catch-rate eval would give a cleaner signal and is a possible follow-up, but is out of scope here.

### Loop mode (auto-continue through REVISE)

Both skills gain an opt-in **loop mode** that automates the per-pass `Continue` decision. Selectable two ways: an invocation flag (`--loop`, alias `--until-approve`) that starts in loop mode from pass 1, and an **`(L)oop from here`** option added to every Continue/Converge/Abort checkpoint to switch into it mid-run.

**Principle — automates `Continue`, never `Converge`.** In loop mode the skill runs pass → fold → pass → fold… without prompting between REVISE passes, and **stops at the first APPROVE**, presenting the normal Converge decision to the human. The "skill never decides convergence" hard rule is untouched — loop mode only removes the mechanical between-pass clicks. This is **not** "silent iteration": every pass still appends its HISTORICAL block, and the loop always returns to the human at a decision point with the full trail.

**Guardrails — the loop pauses and hands back to the human when any fire:**
- **APPROVE reached** — stop, present the Converge decision.
- **Max-pass cap** (default **6**, `--max-passes=N`) — counts *auto-continued passes since loop activation*, as a **fresh budget each activation**: `--loop` counts from pass 1; `(L)oop from here` at pass K starts a new N-pass budget (the current pass K does not count), and manual/historical passes never deplete it (resolves Q9). On reaching the cap without APPROVE — stop, surface "hit cap without converging."
- **BLOCK verdict** — stop; a fundamental problem needs the human.
- **Non-convergence (stall)** — let *cₙ* = the count of **merged HIGH+MEDIUM findings** in pass *n* (post-dedupe; LOW findings, `FAILED` metadata, and open questions are **excluded**, so polish churn can't trigger a false stall — resolves Q10). Halt when the count fails to *strictly decrease* across two consecutive transitions (*cₙ ≥ cₙ₋₁* **and** *cₙ₋₁ ≥ cₙ₋₂*). A pass containing a `FAILED` selected lens is skipped in this comparison (its count is incomplete) but still counts toward the max-pass cap.
- **Fold needs human judgment** — halt before the next pass if **(a)** any HIGH finding this pass was *not incorporated* (a skipped/disputed HIGH is always a human call; MEDIUM may still be incorporated or disputed-with-reasoning autonomously), or **(b)** an open question surfaced that Opus cannot answer from the plan + repo context alone (needs product-owner/human input; questions Opus *can* answer from available context are answered and the loop continues).

In loop mode Opus still folds HIGH/MEDIUM findings mechanically as usual; the guardrails catch exactly the cases where autonomous folding would overstep. Loop mode composes with the per-pass fan-out/merge unchanged — it governs the *between-pass* decision, not the *within-pass* lens machinery.

## Phasing

### Phase 0 — Lens definitions + selection-rules design (~0.5 day)
**Deliverables:**
- The data-shaped lens record format (`id` / `persona_prompt` / `matched_context` / `selection_predicate`).
- The five lens definitions (architect, PM, senior-dev, QA, security) as persona-prompt fragments layered on the shared reviewer contract.
- The two deterministic selection rules tables, with concrete path/content heuristics for the `iterate-review` keys.

**Acceptance:**
- Every lens record is complete and cites the matched context it expects.
- Selection tables resolve deterministically for a set of worked examples (a doc-only plan; an auth-touching diff; a UI diff with no tests).
- Ambiguous/borderline inputs bias toward *including* the specialized lens, with concrete worked examples pinning borderline network, input-parsing, user-facing, and test-only/refactor cases.

**Iterate-review:** CONDITIONAL (rationale: mostly design, but lands the load-bearing lens definitions + selection tables later phases depend on — review if it ships those spec files)
**Status:** reviewed (iterate-review converged after 6 passes, 2026-07-27; see `code-review-working.md`)

### Phase 1 — Fan-out + merge scaffold (shared machinery) (~1 day)
**Deliverables:**
- The per-pass loop change common to both skills: spawn N concurrent `codex exec` lens subprocesses, collect schema-valid responses, dedupe, aggregate verdict worst-of, emit one HISTORICAL block + one checkpoint.
- Patch-marker rejection applied per-lens response (unchanged contract, N times).
- Lens attribution: each merged finding tagged with its originating lens id(s), surfaced in the HISTORICAL block alongside the fold disposition.
- Loop mode: `--loop`/`--until-approve` flag + `(L)oop from here` checkpoint option, wired into the shared between-pass control for both skills, with all five guardrails (APPROVE-stop, `--max-passes` cap default 6, BLOCK-stop, non-convergence stop, fold-needs-judgment stop).

**Acceptance:**
- With a single selected lens, the review is a **behavioral non-regression** vs pre-Axis-2 — same reviewer contract, persona, output schema, sandbox, and resulting findings — even though prompt *assembly* may change (the shared-contract + per-lens framing split). The only additive output change is the lens tag in the HISTORICAL block.
- With multiple lenses, exactly one checkpoint and one HISTORICAL block are produced per pass.
- Every merged finding in the HISTORICAL block names the lens that raised it (a co-reported finding names all contributing lenses).
- A lens subprocess failure follows the lens-failure policy (Approach → Merge): retried once, else recorded `FAILED` — which blocks Converge and surfaces an (R)etry option. It does not abort the pass, but it does prevent silent convergence.
- Loop mode auto-continues through consecutive REVISE passes without prompting, stops at the first APPROVE to present the Converge decision (never auto-converges), and each guardrail demonstrably halts the loop with the trail intact: the max-pass cap (fresh per-activation budget), BLOCK, the stall detector (no strict decrease in merged HIGH+MEDIUM count over 2 transitions; LOW/`FAILED`/open-questions excluded), and the human-judgment halt (an un-incorporated HIGH, or an open question Opus can't answer from plan+repo context).

**Iterate-review:** YES (rationale: the per-pass loop change — parallel lens fan-out + dedupe/merge + verdict aggregation; the convergence property is at stake here)
**Status:** not started

### Phase 2 — iterate-plan lenses (architect + PM) (~0.5 day)
**Deliverables:**
- Wire the architect + PM lenses and their matched-context slicing into `iterate-plan`'s per-pass loop.
- Update `iterate-plan/SKILL.md` + `reviewer-prompt.md` structure to the shared-contract + per-lens-framing split.

**Acceptance:**
- A plan pass runs both lenses in parallel and merges to one findings list.
- PM lens receives Who/Use-cases + Acceptance criteria; architect receives Approach/Architecture.
- On a plan missing Who/Use-cases or Acceptance criteria, PM still runs and flags the absence rather than being skipped or fed empty context.

**Iterate-review:** YES (rationale: changes a load-bearing reviewer-prompt/schema = protocol change per repo convention)
**Status:** not started

### Phase 3 — iterate-review lenses (senior-dev + QA + security) (~1 day)
**Deliverables:**
- Wire the three diff-time lenses + the deterministic selection heuristics into `iterate-review`.
- Update `iterate-review/SKILL.md` + `reviewer-prompt.md` to the shared-contract + per-lens-framing split.

**Acceptance:**
- Selection fires correctly on worked-example diffs (auth diff → security runs; UI-no-tests diff → QA runs; trivial refactor → senior-dev only).
- Borderline diffs (ambiguous network/parsing/UI, test-only, pure refactor) resolve per the over-inclusion bias, not narrowed just to pass the listed examples.
- Merged output is a single list with worst-of verdict and one checkpoint.

**Iterate-review:** YES (rationale: protocol change to reviewer-prompt/schema, plus the security/QA deterministic selection keys land here)
**Status:** not started

### Phase 4 — Fixture/validation coverage (~0.5 day)
**Deliverables:**
- Fixtures (synthetic multi-lens Codex responses) exercising: dedupe of co-reported findings, worst-of verdict aggregation, single-checkpoint invariant, selection-table routing, and lens-attribution tagging.
- Audit existing `examples/` fixtures for any invalidated by the shared-contract/per-lens split; update or deprecate.

**Acceptance:**
- Fixtures demonstrate correct merge + selection on the worked examples.
- No existing fixture asserts behavior the new split removed without being updated.

**Iterate-review:** YES (rationale: the E2E-analog here — fixtures exercising selection + merge/dedupe so convergence and lens-routing regressions don't slip)
**Status:** not started

## Acceptance criteria

- [ ] `iterate-plan` runs architect + PM in parallel and folds a single merged findings list per pass.
- [ ] `iterate-review` deterministically selects senior-dev (+ security / QA per diff shape) and folds a single merged list per pass.
- [ ] Exactly one human checkpoint and one HISTORICAL block per pass, regardless of lens count.
- [ ] Single-lens path is a **behavioral non-regression**: same reviewer contract, persona, schema, sandbox, and findings vs pre-Axis-2 (prompt *assembly* may differ due to the shared-contract/per-lens split); the only additive output delta is the lens tag in the HISTORICAL block.
- [ ] A selected lens that fails (after one retry) blocks Converge and offers (R)etry — the loop never silently converges having skipped a selected lens. `FAILED` is orchestration metadata (reviewer schema unchanged); a failed-selected-lens pass aggregates to REVISE.
- [ ] Verdict aggregation is worst-of; convergence requires all selected lenses to APPROVE.
- [ ] Fixtures cover selection routing + merge/dedupe + single-checkpoint invariant + lens attribution.
- [ ] Every folded finding records its originating lens, so incorporated-findings-by-lens can be tallied (the ROI metric).
- [ ] Lens definitions are data-shaped and loaded from a fixed location (pack loader out of scope).
- [ ] Loop mode (`--loop` + `(L)oop` checkpoint option) auto-continues through REVISE passes and stops at the first APPROVE to present Converge — never auto-converges.
- [ ] Loop mode halts and returns control on any guardrail: max-pass cap (default 6), BLOCK, non-convergence (no finding-count decrease over 2 passes), or a fold requiring human judgment.

## Risks

### R1 — Fan-out breaks convergence / multiplies checkpoints
Multiple lenses → more findings → more REVISE verdicts → loop never converges, or the human is prompted per-lens.
**Mitigation:** worst-of verdict + Opus-side dedupe + a hard single-checkpoint-per-pass invariant enforced in Phase 1 and asserted by a Phase 4 fixture.

### R2 — Personas without matched context invent requirements ("theater")
A PM lens fed a raw diff, or a security lens with no trust-boundary context, fabricates findings.
**Mitigation:** matched-context is part of each lens record; `iterate-plan` slices real plan sections; `iterate-review` v1 is explicit that context is framing + available inputs, and defers claims that need real extraction.

### R3 — Latency from N parallel `codex exec` calls
3–5 concurrent Codex invocations per pass raise wall-clock and token cost.
**Mitigation:** selection narrows to the 2–3 lenses that plausibly apply; calls run concurrently not serially; measure in Phase 1.

### R4 — Merge drops distinct findings or keeps duplicates
Over-aggressive dedupe hides a real issue; under-aggressive dedupe spams the fold list.
**Mitigation:** dedupe key = same location AND same asserted defect; distinct concerns at one location are preserved; Phase 4 fixture covers both directions.

### R5 — Selection rules misroute
A diff that needed the security lens doesn't trigger it → the bug the lens existed to catch is missed.
**Mitigation:** conservative predicates (over-include rather than under-include); senior-dev always runs as a floor; worked-example fixtures pin the routing.

### R6 — Loop mode runs away or iterates on a non-converging plan/diff
Auto-continue could spend unbounded Codex calls/tokens, or loop forever on a plan/diff that never converges.
**Mitigation:** hard max-pass cap (default 6, `--max-passes` overridable, fresh budget per loop activation); non-convergence detector (halt if the merged HIGH+MEDIUM finding count doesn't strictly decrease over 2 consecutive transitions; LOW/`FAILED`/open-questions excluded); BLOCK and human-judgment folds (un-incorporated HIGH, or an open question needing human input) also halt. Loop mode **never auto-converges** — it always returns to the human at APPROVE or a guardrail, with the full HISTORICAL trail.

## Rollback plan

All changes are to skill files (`SKILL.md`, `reviewer-prompt.md`, schemas, `lenses/`) in a git repo. Rollback = `git revert` the phase's commits; the single-lens-equivalence acceptance criterion means reverting restores exact prior behavior. No data or external-state migration is involved.

## Sequencing decision

Axis 2 before Axis 1 (per the brief and Kyle's call): personas need no new vendor, deliver everyday value immediately, and build the fan-out+merge scaffold that Axis 1's conditional extra-reviewer step reuses. Axis 1 slots onto the same scaffold afterward.

## Open questions

<!-- Q1–Q5 resolved during Kyle's review; Q6–Q7 raised by Codex pass 1, Q8 by pass 2, Q9–Q10 by pass 4 (loop-mode delta) — all resolved on fold. Resolutions folded into Approach. -->

- **Q1.** (resolved — lens-per-file `<skill>/lenses/<id>.md`; see Approach.)
- **Q2.** (resolved — framing-only matched context for `iterate-review` v1; see Approach.)
- **Q3.** (resolved — semantic dedupe by Opus, not a mechanical key; see Approach.)
- **Q4.** (resolved — worst-of + LOW-is-informational means a LOW-only lens can't wedge convergence; see Approach.)
- **Q5.** (resolved — 5-lens concurrency ceiling, ~3 typical; see Approach.)
- **Q6.** (resolved — selected-lens failure policy: retry once, else `FAILED` blocks Converge + an (R)etry checkpoint option; see Approach → Merge. Raised by Codex pass 1.)
- **Q7.** (resolved — lens attribution lives in the HISTORICAL fold record for v1; no per-invocation schema field needed since each lens is a separate Codex call; machine-readable field is a future option; see Approach → Measurement. Raised by Codex pass 1.)
- **Q8.** (resolved — aggregate verdict for a failed-after-retry selected lens is **REVISE**; `FAILED` is orchestration metadata, reviewer schema untouched; see Approach → Merge. Raised by Codex pass 2.)
- **Q9.** (resolved — loop-mode max-pass cap is a **fresh per-activation budget** counting auto-continued passes; manual/historical passes don't deplete it; see Approach → Loop mode. Raised by Codex pass 4.)
- **Q10.** (resolved — loop-mode non-convergence detector counts **merged HIGH+MEDIUM findings only** (LOW/`FAILED`/open-questions excluded); see Approach → Loop mode. Raised by Codex pass 4.)

## Out of scope

- Pluggable persona-pack loader — [issue #1](https://github.com/kaileconsulting/trinity-skills/issues/1).
- LLM-based lens routing — deterministic selection only, by design.
- Cross-vendor / Gemini tiebreaker — Axis 1, sequenced next.
- Non-Codex reviewers inside Axis 2 — the lenses are all the same reviewer model; model diversity is Axis 1.

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

- Expansion brief: `/home/kyle/trinity-review-expansion-brief.md`
- Deferred extensibility: [issue #1 — pluggable persona-pack loading](https://github.com/kaileconsulting/trinity-skills/issues/1)
- Axis 1 groundwork (Gemini access): memory `gemini-access`
- Current reviewer contracts this plan restructures: `iterate-plan/reviewer-prompt.md`, `iterate-plan/reviewer-output.schema.json`, `iterate-review/reviewer-prompt.md`, `iterate-review/reviewer-output.schema.json`
- **Path convention:** file paths in this plan are **repo-relative** (`<repo-root>/iterate-plan/...`). At runtime the skills live at `~/.claude/skills/<skill>/...` via the `install.sh` symlink, and those installed paths are authoritative when the skills execute — same files, two prefixes.

## Review checkpoints

| Phase | Iterate-review | Status | Last pass | Pass log |
|-------|----------------|--------|-----------|----------|
| Phase 0 | CONDITIONAL | reviewed | 2026-07-27 (6 passes → APPROVE) | `code-review-working.md` |
| Phase 1 | YES | not started | — | — |
| Phase 2 | YES | not started | — | — |
| Phase 3 | YES | not started | — | — |
| Phase 4 | YES | not started | — | — |

## Pre-flight review pass (Opus, YYYY-MM-DD) [HISTORICAL]

<!-- OPTIONAL self-review by Opus before execution. Delete if skipped. -->

## Codex review pass 1 — answers (2026-07-27) [HISTORICAL]

### Verdict
REVISE

### Findings
1. **Lens subprocess failure semantics weaken convergence guarantee** — HIGH: a selected-but-failed lens neither approves nor revises, yet convergence required "all selected lenses APPROVE" — so the plan didn't define whether a pass could converge having skipped a required lens, undermining the coverage guarantee.
   → Opus: incorporated — added an explicit **lens failure policy** (retry once; else `FAILED` outcome that blocks Converge; surfaced with an (R)etry checkpoint option). See Approach → Merge, Phase 1 acceptance, and a new global acceptance criterion.
2. **Single-lens byte-for-byte equivalence conflicts with attribution** — MEDIUM: requiring single-lens output "byte-for-byte equivalent to pre-Axis-2" contradicts adding a lens tag to the HISTORICAL block.
   → Opus: incorporated — retargeted non-regression to **semantic** (identical Codex invocation + findings; the lens tag is an intended additive change). Reworded Phase 1 acceptance + the global acceptance criterion.
3. **Selection predicates need a testable fallback for ambiguous diffs** — MEDIUM: broad categories ("network", "input-parsing", "user-facing", "non-trivial") with no ambiguity rule let implementers write narrow predicates that pass the worked examples but miss common cases.
   → Opus: incorporated — added an **ambiguity-biases-toward-inclusion** rule to the selection section, plus Phase 0 and Phase 3 acceptance requiring borderline worked examples.

### Plan corrections applied
- Approach / iterate-plan selection table (PM row): normalized to the actual template headings (**Who / Use cases**, **Acceptance criteria**) and resolved the "conditional but always" contradiction (unconditional for template-conformant plans; skipped as a fallback if a non-template plan lacks both).
- References: added an explicit **path-convention** note (repo-relative paths vs the installed `~/.claude/skills/...` runtime paths).

### Open-question answers
1. Q1 — Codex concurs: per-lens files are the right v1 shape (reviewable fragments, clean map to a future pack loader). No change.
2. Q2 — framing-only acceptable **if** the plan stays honest that it's weaker than extraction. Plan already is; no change.
3. Q3 — semantic dedupe appropriate; guard: preserve lens attribution for co-reported findings so dedupe doesn't erase measurement data. Already specified (co-reported findings name all contributing lenses); no change.
4. Q4 — resolved provided aggregation uses each lens's actual verdict and LOW can appear under APPROVE; keep this explicit in per-lens prompt guidance. Added that requirement to the verdict-aggregation bullet.
5. Q5 — 5-cap is an execution guard, not a routing target; keep built-in selection at 2–3. Already specified; no change.

### New questions Codex raised
- Retry a failed/malformed lens before Continue/Converge, or auto-mark non-converged? → Resolved as **Q6**: retry once, then `FAILED` blocks Converge with an (R)etry option.
- Attribution only in HISTORICAL, or grow the reviewer schema with a lens field? → Resolved as **Q7**: HISTORICAL-only for v1 (lens known by construction per separate invocation); schema field is a future measurement-tooling option.

## Codex review pass 2 — answers (2026-07-27) [HISTORICAL]

### Verdict
REVISE

### Findings
1. **`FAILED` outcome not mapped onto the verdict contract** — HIGH: the pass-1 failure policy introduced `FAILED`, but the reviewer schema only allows APPROVE/REVISE/BLOCK; the plan didn't say whether `FAILED` is metadata, how it appears in the merged structure, or what aggregate verdict a failed-lens pass emits.
   → Opus: incorporated — defined `FAILED` as **orchestration metadata on the merge layer (not a reviewer verdict; schema unchanged)**; a pass with ≥1 failed selected lens aggregates to **REVISE**, and `FAILED` independently blocks Converge. See Approach → Merge + the failure acceptance criterion.
2. **Non-template PM fallback conflicts with global/Phase 2 acceptance** — MEDIUM: the pass-1 PM "skip if sections missing" fallback contradicted "iterate-plan always runs architect + PM."
   → Opus: incorporated — changed the rule so **PM always runs**; when its context sections are missing it runs with degraded context and is expected to **flag the gap as a finding**, never skipped or fed empty context. Global + Phase 2 acceptance now hold unconditionally (added a Phase 2 acceptance bullet).

### Plan corrections applied
- (none this pass)

### Open-question answers
- (none posed this pass)

### New questions Codex raised
- Aggregate verdict for a failed-after-retry selected lens — REVISE or BLOCK, and how represented without a schema change? → Resolved as **Q8**: aggregate **REVISE**; `FAILED` is orchestration metadata, reviewer schema untouched.

## Codex review pass 3 — answers (2026-07-27) [HISTORICAL]

### Verdict
APPROVE

### Findings
1. **Single-lens invocation equivalence over-specified** — LOW: "identical Codex invocation" is stronger than needed given the shared-contract + per-lens framing restructure; prompt assembly may legitimately change even when behavior is preserved.
   → Opus: incorporated — relaxed Phase 1 + global acceptance to **behavioral non-regression** (same contract / persona / schema / sandbox / findings; prompt assembly may differ).

### Plan corrections applied
- (none this pass)

### Open-question answers
- (none posed this pass)

### New questions Codex raised
- (none)

### Convergence reasoning
Pass 3 returned APPROVE with a single LOW nit, which Opus incorporated (it corrected an internal inconsistency the shared-contract/per-lens split introduced). No HIGH/MEDIUM findings remain, no open questions outstanding, no further changes pending. The pass-1 HIGH (lens-failure policy) and pass-2 HIGH (`FAILED` ↔ schema mapping) are resolved and stable — pass 3 raised no regressions from those folds. Converged.

## Codex review pass 4 — answers (2026-07-27) [HISTORICAL]

_Delta review of the loop-mode addition folded into Phase 1 (plan had already converged at pass 3)._

### Verdict
REVISE

### Findings
1. **Loop-mode cap semantics ambiguous mid-run** — HIGH: `--max-passes` didn't say whether the cap counts absolute passes, auto-continued passes, or total session passes — different behavior for `--loop` vs `(L)oop from here`.
   → Opus: incorporated — defined the cap as a **fresh per-activation budget** counting auto-continued passes (`--loop` from pass 1; `(L)oop` starts a new N-pass budget, current pass excluded; manual/historical passes don't deplete it). Resolves Q9.
2. **Non-convergence detector under-specified** — MEDIUM: didn't define the counted population (per-lens vs merged, LOW included?, FAILED handling) or the exact stall sequence.
   → Opus: incorporated — counts **merged HIGH+MEDIUM findings only** (LOW/`FAILED`/open-questions excluded); halt when the count fails to strictly decrease over 2 transitions; `FAILED`-lens passes skipped in the comparison. Resolves Q10.
3. **Human-judgment fold boundary needs concrete detection** — MEDIUM: "dispute a HIGH" / "open question needing human" left too much to implicit judgment for an auto-loop.
   → Opus: incorporated — halt before the next pass if (a) any HIGH finding was **not incorporated**, or (b) an open question surfaced that Opus **can't answer from plan+repo context**.

### Plan corrections applied
- (none)

### Open-question answers
- (none posed by Opus this pass)

### New questions Codex raised
- Cap shared across manual+auto, or fresh on `(L)oop`? → Resolved **Q9**: fresh per-activation budget.
- Ignore LOW-only findings in non-convergence? → Resolved **Q10**: yes — only HIGH+MEDIUM count.

## Codex review pass 5 — answers (2026-07-27) [HISTORICAL]

_Confirming pass on the loop-mode delta._

### Verdict
APPROVE

### Findings
- (none)

### Plan corrections applied
- (none)

### Open-question answers
- (none)

### New questions Codex raised
- (none)

### Convergence reasoning
Pass 5 returned APPROVE with zero findings, confirming the pass-4 folds. The loop-mode guardrails (fresh per-activation cap, HIGH+MEDIUM stall detector, un-incorporated-HIGH / human-only-open-question escalation) are now mechanically specified and preserve the "never silently iterate" + "skill never decides convergence" invariants. Loop-mode delta converged.

<!-- TOOLING-MAINTAINED by iterate-plan. Each subsequent pass appends a new
"## Codex review pass N — answers (DATE) [HISTORICAL]" section below. -->
