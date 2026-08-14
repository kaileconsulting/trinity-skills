# Risk Posture & Proportionality — Plan

## TL;DR

The trinity review loop finds real bugs but has no vocabulary for "real, but not worth it for this product." Evidence from doc-bot's write-path week: review costs 2–3× build time, phases took 5–10 passes to converge, and findings were folded 57 times vs disputed 7 — every dispute being "the reviewer couldn't see a constraint," never a proportionality call. Worst case: a narrow page-unload race in Phase 0 was fixed by introducing a server-enforced seq mechanism whose own bugs then consumed passes 5–9.

This plan gives the loop that vocabulary at three points: **create-plan** captures a risk posture at planning time (who the audience is, what the blast radius of a defect is, how "perfect" the thing must be to ship); **iterate-review** feeds that posture to the Codex lenses via the intent context so severity judgments aren't made blind; and the **editor** gains an `accepted-risk` disposition plus explicit license — and criteria — to push back on disproportionate findings and to escalate design-shaped folds to the human instead of building them mid-loop.

Expected outcome: typical phases converge in 3–5 passes instead of 10, with trust-boundary phases keeping full rigor, and every accepted risk recorded with a rationale and confirmed by the human at Converge.

## Why / Context

During doc-bot's editor write-path build (2026-08-06 → 2026-08-12), iterate-review's pass counts and wall-clock costs were measured directly from the pass logs and git timestamps:

| Phase | Build time | Review time | Passes |
|---|---|---|---|
| Phase 0 (autosave) | ~40 min | ~2.5 hrs | 10 |
| Phase 1 (publish) | ~35 min | ~2.5 hrs | 5 |
| Phase 2 (images) | ~40 min | ~6 hrs | 10 |
| Phase 3 (approve) | ~2 hrs | open | 7+, not converged |

Two structural causes, both visible in the logs:

1. **No proportionality lever.** Dispositions are `incorporated | skipped | disputed`, and loop mode halts if a HIGH isn't incorporated — so the path of least resistance is always to fix. Findings like "max-bigint seq poisons a draft on a Tailscale-internal tool, recoverable via discard" get built rather than accepted. 57 folds vs 7 disputes across the write-path logs.
2. **Design decisions smuggled into folds.** Phase 0 pass 4 fixed a page-unload race by introducing a schema migration + clock-skew-bounded sequence tokens; passes 5, 6, 7, 8, and 9 then fixed bugs in that mechanism. Escalated to the human at pass 4, the answer might have been "drop the keepalive" — one line instead of six passes. The same shape recurs in doc-bot Phase 3 (pass 2 finding 1 and pass 6 finding 1 are both bugs in earlier passes' folds).

A third irritant: because each review starts a fresh log, the lenses re-derive posture-blind severities every review — doc-bot's "drafts have no auth" HIGH was disputed and settled in write-path Phase 0 pass 1, then re-filed verbatim in Phase 3 pass 1 (finding 8).

The counterweight, and why this plan is tuning rather than teardown: the loop's findings are real. Phase 0 passes 1–3 caught user-visible data loss; Phase 3 pass 1 caught "approve merges content the reviewer never previewed," co-reported by all three lenses. The goal is to keep that while stopping the tail-chasing.

## Who / Use cases

- **Kyle (plan author + review checkpoint human)** — states the product's risk posture once at planning time instead of re-litigating it verbally every review; triages batched accepted-risk calls at checkpoints instead of watching the loop build fixes he'd have declined.
- **The editor (Claude, folding findings)** — has explicit criteria for when to push back (`accepted-risk`, dispute-on-proportionality) and a hard rule for when to stop and ask (fold requires new mechanism/schema/invariant).
- **The reviewer (Codex lenses)** — sees the documented trust posture and audience in the intent context, so severity is assessed against the actual product instead of an imagined internet-facing one.
- **Future repos/plans** — any project using the trinity gets posture capture for free at create-plan time; standalone reviews (no plan) fall back to a per-repo posture file.

## Goals (MVP)

- create-plan captures a risk posture section in every new plan (audience, blast radius, recoverability, ship bar, trust boundaries); plans carry no register — the repo-level accepted-risks register lives solely in `docs/risk-posture.md`.
- iterate-review includes the applicable posture in the intent context the lenses receive, every pass.
- The editor has an `accepted-risk` disposition: recorded rationale, satisfies the loop's guardrails, batched for human confirmation at the next checkpoint; Converge is blocked until confirmed.
- The editor's fold step carries explicit pushback guidance, including the design-shaped-fold escalation rule.
- Everything escalated to the human arrives as a decision card — recommendation, 2–3 alternatives with trade-offs, and a standing "discuss" option — so a checkpoint is a choice, not a research task.
- One live doc-bot review validates the changes and measures the pass-count delta.

## Non-goals (MVP)

- No plan-bound iterate-review (`--plan` / `--phase`) — that's the existing v2 deferral, unchanged.
- No changes to lens selection (`selection_engine.py`) — which lenses run is orthogonal to what they're told.
- No auto-tuning of `--max-passes` or convergence math beyond how accepted-risk findings are counted.
- No retro-editing of existing pass logs or re-review of shipped doc-bot phases.

## Approach

### Proposed design

**1. Posture capture (create-plan).** Add a `## Risk posture` section to `create-plan/template.md` — **REQUIRED for every plan type**, so the "every new plan carries posture" promise holds without exception. Initiatives get the full section; fix-type plans get a mandatory lightweight variant: one short paragraph answering the same three questions. No plan of either type carries its own register — the register's single home (below) makes it apply to every review automatically. create-plan asks the author three questions:

- **Audience & reach** — who uses this, roughly how many, behind what perimeter?
- **Blast radius & recoverability** — what does a defect cost, and is the damage reversible (e.g., "a lost draft is retypeable" vs "a wrong merge ships to customers")?
- **Ship bar** — what class of defect blocks ship vs gets logged as accepted? Name the trust boundaries where full rigor applies regardless (e.g., doc-bot's approve/merge path).

The **accepted-risks register has exactly one home per repo: `docs/risk-posture.md`** — plan posture sections carry only the three posture fields, never their own register. One home means inheritance is automatic (every review reads the same canonical register regardless of which source supplies the posture fields) and entry digests have a single provenance. Entries are narrow and named ("client-supplied seq can poison one draft for ≤24h; recoverable via discard; accepted 2026-08-06"), never blanket suppressions.

**Register entries are published only by human authority — never by an editor fold.** A review-scoped `AR-<n>` proposal lives solely in the pass log until confirmed (AR ids stay sequential — they're scoped to one review's pass log, where no concurrent allocation exists), and confirmation chooses its scope: *confirm for this review only* (recorded in pass log + state file; the register is untouched) or *confirm and add to the register* (the editor appends the `RR-` entry to the repo file *as part of the confirm transition*, scaffolding the file if absent, and records the new id in the pass log; a failed write surfaces at the checkpoint and the confirmation does not complete). Rejection or posture-dependency invalidation of a proposal never touches the repo file. At scaffold time, create-plan may seed entries the author dictates — author action is its own confirmation.

**Register ids are allocation-free date-slugs** (`RR-2026-08-06-seq-poison`), not sequential numbers — concurrent branches and reviews cannot collide on a next-number counter, merges are ordinary git conflicts on one file, and persisted references never renumber. Duplicate ids in the file are a malformed source (the halt card); ids are never reused or renamed once referenced.

**Every posture element carries a stable field id, written by the template:** `PF-audience`, `PF-blast`, `PF-shipbar` for the three answers (the lightweight fix variant labels the same three inline), and `RR-<id>` for register entries in `docs/risk-posture.md`. These ids are the structural anchors everything downstream points at — register refs, accepted-risk dependency descriptors — so no consumer ever has to identify posture content by prose. Template changes are additive H2s, but Phase 0 verifies iterate-plan's reviewer expectations (Q-numbering, HISTORICAL formats) are untouched.

**2. Posture → lenses (iterate-review).** The editor already composes the intent file per pass (SKILL.md step 9, "best-effort intent context"). Extend the composition rule: include a `=== RISK POSTURE ===` block whose **posture fields** are sourced by this priority order, each outcome logged distinctly in the pass log header (never collapsed to a bare "none") — while the **register** is *always* read from its single home, `docs/risk-posture.md`, independent of field precedence (shadowing applies to fields only):

- (a) the governing plan's `## Risk posture` section, **when the invocation names the plan** (e.g., `/iterate-review --scope=branch` with "posture from docs/foo-plan.md"). v1 has no plan binding, so there is no automatic discovery — the human names the plan or it isn't used. Automatic discovery arrives with v2's `--plan` flag (existing deferral, unchanged).
- (b) the repo's `docs/risk-posture.md`.
- (c) none. Distinguish in the log: *absent* (no source found), *malformed* (source found but unparseable), and *both-present* (plan section wins; repo file noted as shadowed).

**Malformed sources have deterministic control flow, not just a log line:** a malformed source at the selected precedence level halts the pass *before fan-out* and presents a decision card **under the same contract as every other human escalation** (recommendation with a one-line why, alternatives, standing *discuss* option; persisted to the pass log before presentation, re-presented on resume): fix the source now / fall back to the next source in precedence / proceed with no posture / abort / discuss — with the choice recorded in the pass log. This is a fifth named human-judgment moment, covered by the same acceptance as the other four. There is no silent fallback at any level: a human who named a plan gets to decide whether reviewing under the repo file (or under nothing) is acceptable, rather than the review quietly proceeding under a posture they didn't choose.

**Register references are machine-readable.** Register entries carry stable ids (`RR-<id>`) in the posture source. `reviewer-output.schema.json` gains an optional per-finding `register_ref` field (the enforced schema is the protocol boundary — no prose-tag conventions). The **editor validates** every `register_ref` against the actual register at fold time: validity requires the current finding to fall within the entry's recorded behavior, bound, and recovery path — not merely to name it; an unknown or malformed ref is treated as untagged and noted in the pass log. **The register-match disposition has the same durability as the AR lifecycle:** a valid match is recorded in the pass log as `register-match (RR-<n>, entry-digest <hash>)`, where the digest is a canonical-content hash of the entry's behavior/bound/recovery text *as validated* — that snapshot identity is what makes amendment detectable from durable state alone. The register entry's owner and date serve as its standing confirmation — no fresh human confirmation per review, which is the register's entire purpose — and it counts as resolved *while the entry stands unchanged*: before a match's resolved credit carries into any later pass or a resume, the editor recomputes the current entry's digest, and a mismatch or missing entry invalidates the match, re-entering the finding as `reopened`. The state is fully reconstructable from the pass log plus the posture source; nothing lives only in session memory. Lenses are instructed to (i) set `register_ref` on findings that are independently actionable but match a register entry's declared bound, and (ii) not file findings that merely restate a documented posture decision (perimeter, trust boundary) without new evidence — but a finding presenting evidence that a register entry's bound or recovery path is *false* is a fresh finding, never a match.

`reviewer-prompt.md` gains a short instruction on how to use the block (see Q2 for the severity-semantics decision). Composition goldens in `examples/composition/` are regenerated for the prompt change — the new goldens become the baseline. The no-posture invariant is therefore: **zero posture-specific bytes in the intent file** (no `=== RISK POSTURE ===` block), and composition byte-identical to the *new* goldens; byte-identity with today's goldens is impossible once the shared prompt changes and is not claimed.

**3. Proportionality in the fold (iterate-review).** SKILL.md changes:

- **New disposition `accepted-risk`** — "real finding, disproportionate to this product's posture; not fixing." Requires a written rationale referencing the posture. Satisfies the HIGH-must-be-incorporated loop guardrail (per Q1's resolution); all accepted-risk items are listed prominently at the next human checkpoint, and **Converge is blocked until the human confirms each one** — confirmation recorded in the pass log and the final state file, so acceptance has an owner and a date.
- **Accepted-risk identity and lifecycle.** Each proposal gets a stable id (`AR-<n>`, scoped to the review) minted when the editor writes the disposition into the pass log — the pass log is the durable record; matching is by id, never by prose. Lifecycle: `proposed` (editor) → `confirmed` or `rejected` (human only). Rejection moves the item to **`reopened`** — an explicitly unresolved state that blocks Converge exactly as `proposed` does, and that immediately restores the finding to the open ledgers per the accounting table below (it re-enters the non-convergence count and no longer satisfies the HIGH guardrail) the moment the rejection is recorded. A reopened finding must receive a subsequent disposition on a later pass — incorporated or disputed (both terminal), or a fresh accepted-risk proposal under a new id, which is itself resolved only through the proposed → confirmed lifecycle. A *materially changed* finding (different location, behavior, or bound) is a new proposal with a new id — prior confirmation never carries over. **Confirmations carry a machine-reconstructable posture dependency:** the confirmation persists a dependency descriptor — the list of posture *field ids* its rationale relies on (`PF-shipbar`, `RR-2026-08-06-seq-poison`, …) — together with a canonical-content digest of those fields as confirmed (the same snapshot mechanism as register matches). On any later pass or resume, the descriptor re-selects the same fields from the current posture source and the digest is recomputed: a mismatch, or a descriptor that no longer resolves (field removed or ambiguous), invalidates the confirmation and returns the item to `proposed` for fresh confirmation — invalidation is the safe direction. Posture edits outside the descriptor's fields never invalidate. Because descriptor and digest live in the pass log and fields are selected by id, the comparison is identical in-session and after interruption — no prose interpretation, no session memory. Confirmations otherwise persist across checkpoints within the review; the **Converge predicate is: zero items in `proposed` or `reopened` state**, and confirmed ids are written to the final state file. On resume after interruption, pending proposals are re-read from the pass log and re-presented — nothing lives only in session memory.
- **Design-shaped-fold escalation** — a hard rule in the fold step: if incorporating a finding requires a new mechanism, the fold does not proceed; loop mode halts with the finding framed as a design decision for the human, with a cheaper alternative sketched when one exists. **"New mechanism" has an operational boundary**, with signals and examples in SKILL.md: schema change or migration; new persisted or protocol field; new invariant that must hold beyond the current request (state outliving the call); new background/timed process; new external dependency. Non-mechanisms (fold normally): guard clauses, error-handling and message fixes, test additions, bounded refactors within existing types. The halt's **outcome mapping is deterministic** — each card option names its continuation: *adopt the mechanism* → fold proceeds this pass (plan/posture updated if the mechanism changes either); *cheaper alternative* → the alternative is folded and recorded as `incorporated (via alternative)`, re-reviewed next pass; *accept the risk* → routes to the `accepted-risk` lifecycle above; *discuss* → loop stays paused, no fold occurs. **Card construction is context-sensitive:** an option whose transition is prohibited for this finding is never displayed — in particular, *accept the risk* is excluded for trust-boundary code named in the ship bar (the pushback anti-criteria), so a trust-boundary escalation offers adopt / cheaper alternative / discuss only. Every displayed option is a legal continuation. The card is appended to the pass log *before* it is presented, so an interrupted session re-presents pending cards from the log on resume.
- **Per-card outcome mappings — every card type, not just design escalations.** Each of the five judgment moments has a defined option set and deterministic transitions (context-sensitive omission applies to all of them alike):
  - *Accepted-risk confirmation*: **confirm — this review only** → `confirmed`, recorded in pass log + state file, register untouched; **confirm + add to register** → `confirmed` and the `RR-` entry published to `docs/risk-posture.md` as part of the transition (write failure surfaces here; the confirmation does not complete); **reject** → `reopened` (resolved credit reversed immediately); **defer** → the item *stays `proposed`* under the same `AR-<n>` — no new state; per the accounting table it keeps blocking Converge while staying out of the open-finding count, and the card is re-presented at every subsequent checkpoint; **discuss** → paused conversation.
  - *Design-shaped-fold escalation*: adopt / cheaper alternative / accept-the-risk (where legal) / discuss, as specified above.
  - *`needs_human` question*: **adopt the recommendation** or **pick an alternative** → the answer is recorded in the pass log and the plan's Open questions, loop resumes; **defer** → the question stays open and Converge-blocking, re-presented next checkpoint; **discuss** → paused conversation.
  - *Non-convergence stall*: **continue anyway** → loop resumes with a fresh two-transition comparison window; **switch to manual** → loop mode ends, per-pass checkpoints resume; **abort** → review ends per the abort path; **discuss** → paused conversation.
  - *Malformed posture source*: fix now / fall back / proceed with none / abort / discuss, as specified in §2.
- **Pushback guidance** — the fold step explicitly states the editor is expected to spend `disputed` and `accepted-risk` when warranted, with criteria (finding contradicts the posture; fix cost exceeds the defect's bounded blast radius; finding re-litigates a register entry) and anti-criteria (never on trust-boundary code named in the ship bar; never to avoid a small honest fix).
- **Accounting is defined per ledger, per state — one table, three consumers.** The loop has three distinct accounting contexts that earlier drafts conflated under "resolved credit": the per-pass HIGH guardrail (*may the loop continue?*), the HIGH+MEDIUM non-convergence counter (*is the review stalling?*), and the Converge predicate (*may the review end?*). Each lifecycle state has explicit standing in each:

  | State | HIGH guardrail | Non-convergence count | Converge |
  |---|---|---|---|
  | `proposed` (incl. deferred) | satisfied — loop may continue | excluded (dispositioned, not open) | **blocks** |
  | `confirmed` | satisfied | excluded | clear |
  | `reopened` | **not satisfied** — fresh disposition required | **re-included** | **blocks** |
  | register-match, digest valid | satisfied | excluded | clear |
  | register-match, digest broken/missing | treated as `reopened` | treated as `reopened` | **blocks** |

  This table is normative: the lifecycle prose, card outcome mappings, Q1 rationale, and Phase 2 fixtures all defer to it. Accepting a risk therefore can't read as a stall (proposed/confirmed items leave the non-convergence count) while still being impossible to converge past unconfirmed.
- **Decision cards at every human-judgment moment** — whenever the loop hands back to the human with items needing judgment (batched accepted-risk confirmations, design-shaped-fold escalations, `needs_human` questions, non-convergence stalls, malformed-posture-source resolution), each item is presented in a fixed shape: **(1) the editor's recommendation with a one-line why, (2) two or three genuine alternatives with their trade-offs, (3) an always-present "discuss" option** for talking it through before deciding. Options are decisions, not descriptions — selecting any option other than *discuss* resumes the loop deterministically per its card type's outcome mapping, with no follow-up prose needed. *Discuss* is deliberately non-resuming: it transitions into a paused conversation with the human, and when the discussion concludes the card is re-presented with the agreed direction as the new recommendation — so "pick-one-resumes" governs every option except the one whose purpose is to pause. In interactive sessions the editor presents these via the harness's structured-question mechanism (AskUserQuestion: recommendation listed first and marked, free-form "Other" built in); in the pass log the same card is recorded as text so the decision and its alternatives are on the record.

### Repo layout

```
create-plan/template.md          # + ## Risk posture section (REQUIRED for all plans; full for initiatives, lightweight for fixes)
create-plan/SKILL.md             # + posture questions step (between plan-type and phases)
iterate-review/SKILL.md          # + intent-file posture rule; accepted-risk disposition;
                                 #   escalation rule; pushback guidance; guardrail updates
iterate-review/reviewer-prompt.md# + RISK POSTURE block usage instruction
iterate-review/examples/         # regenerated composition goldens
docs/risk-posture.md (per-repo, downstream) # fallback posture for standalone reviews — documented, not shipped here
```

## Phasing

### Phase 0 — Posture capture in create-plan (~2h)
**Deliverables:**
- `## Risk posture` section added to `create-plan/template.md` with inline authoring guidance and stable field ids (`PF-audience`, `PF-blast`, `PF-shipbar`) in both the full and lightweight variants; the register shape (`RR-<id>` entries) is defined for `docs/risk-posture.md`, its single home, which create-plan scaffolds or appends to when a plan accepts a risk.
- create-plan SKILL.md gains the three posture questions (audience/reach, blast radius/recoverability, ship bar + trust boundaries) as a step for **both plan types**; fix-type plans get the mandatory one-paragraph lightweight variant (no plan-local register — the repo file is the register's single home).
- Verified: iterate-plan's reviewer expectations (Q-numbering, section names it keys on, HISTORICAL formats) are unaffected by the additive section.

**Acceptance:**
- Scaffolding exercises **both plan types**: a fresh initiative plan produces the full section (all three questions answered under their `PF-` ids); a fresh fix plan produces the mandatory lightweight paragraph covering the same three answers. Neither type can scaffold without the posture step. When a scaffold adds a register entry, it lands in `docs/risk-posture.md` (created if absent), never in the plan.
- iterate-plan smoke test on a sample plan carrying the new section: the pass raises **no posture-specific format findings** (findings about section absence, shape, or unanswered posture questions). Unrelated design findings don't fail the smoke — the criterion is posture-format acceptance, not a clean review.

**Iterate-review:** YES (rationale: template + skill-procedure changes are load-bearing machinery prose; a bad section shape propagates into every future plan)
**Status:** reviewed

### Phase 1 — Posture flows to the lenses (~3h)
**Deliverables:**
- iterate-review SKILL.md step 9: intent-file composition includes the `=== RISK POSTURE ===` block with the named-plan → repo-file → none priority order; the source outcome (used / absent / malformed / both-present-shadowed) is recorded in the pass log header.
- `reviewer-output.schema.json`: optional per-finding `register_ref` field; SKILL.md fold step validates refs against the register (unknown/malformed → untagged, logged).
- `reviewer-prompt.md`: instruction for weighing the posture block, setting `register_ref` on independently-actionable matches, and not re-filing findings that merely restate documented posture decisions without new evidence (severity semantics per Q2).
- Composition goldens regenerated as the new baseline; runner tests green.

**Acceptance:**
- A pass run against a repo with a posture file shows the block in the composed `pass-N.<lensid>.input.txt`; without any posture source, the intent file contains zero posture-specific bytes and composition matches the new goldens byte-for-byte.
- Collision case: an invocation naming a plan in a repo that also has `docs/risk-posture.md` uses the plan's posture fields, and the pass log attributes the source and notes the shadowed fields; **the register still arrives from the repo file** — a named fix plan with no local register sees the repo's `RR-<id>` entries in its lens inputs (fixture). Malformed-source case halts before fan-out and surfaces as a standard decision card (recommendation, alternatives, standing discuss option; persisted before presentation, re-presented on resume) rather than silently degrading to "none."
- Fixture: a finding carrying a valid `register_ref` routes to the register-match path; an unknown ref is treated as untagged and logged. (A finding that merely restates a documented posture decision is not filed at all — distinct from a tagged, independently-actionable match.)
- Fixture: amending or removing a referenced register entry mid-review invalidates the matches against it — the affected findings re-enter as `reopened` and block Converge until re-dispositioned.

**Iterate-review:** YES (rationale: touches the deterministic composition path and its goldens — regression risk is concrete)
**Status:** reviewed

### Phase 2 — accepted-risk disposition + editor pushback (~3h)
**Deliverables:**
- SKILL.md dispositions extended with `accepted-risk` (rationale required, HISTORICAL block format updated, state-file field added for converge-time confirmations).
- Loop-mode guardrails updated per Q1; non-convergence counting treats accepted-risk as resolved.
- Design-shaped-fold escalation rule and pushback criteria/anti-criteria added to the fold step.
- Checkpoint prompt updated: batched accepted-risk items presented for confirmation; Converge blocked until confirmed.
- Decision-card format specified in SKILL.md and applied to all five human-judgment moments (accepted-risk confirmation, design-shaped-fold escalation, `needs_human` questions, non-convergence stalls, malformed-posture-source resolution — the last implemented in Phase 1 under this shared contract): recommendation + why, 2–3 alternatives with trade-offs, always a "discuss" option; card recorded in the pass log, presented interactively via AskUserQuestion.

**Acceptance:**
- A dry-run review (fixture diff) exercises the accounting table state by state: a `proposed` AR lets the loop continue while blocking Converge and staying out of the non-convergence count; Converge refuses while any `AR-<n>` remains `proposed` **or `reopened`**; a rejected proposal enters `reopened`, re-enters the open ledgers (counts again, fails the HIGH guardrail), and requires a fresh disposition on the next pass; a mechanism-requiring finding halts the loop instead of folding.
- Boundary cases exercised, not just the obvious mechanism: at least one fixture finding whose fix is a non-mechanism (e.g., a guard clause or error-message fix) folds normally, and one genuinely ambiguous case resolves per the SKILL.md signals.
- Each dry-run escalation arrives as a decision card (recommendation, alternatives, discuss): every non-discuss option resumes the loop per its card type's outcome mapping with no follow-up prose; *discuss* pauses into conversation and re-presents the card afterward; *defer* leaves the item blocking and re-presented at the next checkpoint; the card and the choice appear in the pass log, and a card written-but-unanswered is re-presented on session resume.
- Posture-dependency fixture, two-sided and interruption-crossing: a confirmed accepted-risk whose descriptor fields are then amended returns to `proposed`; one whose fields are untouched by an unrelated posture edit stays `confirmed`; both outcomes reproduce identically when the descriptor and digest are re-resolved from the pass log + posture source alone after a simulated session interruption; a descriptor that no longer resolves invalidates.

**Iterate-review:** YES (rationale: changes the loop's safety guardrails — the exact machinery that keeps unattended runs honest)
**Status:** in progress (built 2026-08-13, commit `93ee247`; its own dedicated `iterate-review` is **in progress** — 12 passes run so far against scope-tag `phase-2`, range `1661dfe..HEAD`, log at `docs/reviews/code-review-phase-2.md`. Kyle's call was to batch across phases rather than review per-phase; in practice Phase 0+1 converged as one batch and Phase 2 is being reviewed as its own)

### Phase 3 — Live validation on doc-bot (~1 review session)
**Deliverables:**
- A `docs/risk-posture.md` authored for doc-bot — the canonical register home — with posture fields and `RR-<id>` entries for the already-accepted write-path risks (perimeter/auth posture, seq-poisoning bound).
- The next real doc-bot review (Phase 3 wrap-up or the next phase) run with the new machinery, framed as an **indicative case study, not causal proof** — the deterministic behaviors are already proven by Phase 2's fixtures. Recorded dimensions for the baseline comparison: diff size, phase type (trust-boundary vs plumbing/UI), lens set, pass count, disposition mix, and halt quality.
- Pre-defined outcome classes, written before the review runs: **success** = fewer passes than the baseline band for comparable diff size/phase type with no fix-to-fix churn passes on non-trust-boundary code and no disputed trust-boundary bugs; **inconclusive** = scope not comparable on the recorded dimensions (say so, no metric torture); **regression** = pass count up, or pushback misapplied to a real trust-boundary defect.
- Findings about the machinery itself fed back as fixes to Phases 0–2 before closeout.

**Acceptance:**
- The posture block visibly reaches the lens inputs, and *whatever findings actually arise* are handled per design — register matches route correctly **if any occur** (the machinery's determinism is Phase 2's proof, not this review's burden; nothing is preserved or solicited to manufacture a metric).
- The review's outcome is classified against the pre-defined classes, with the recorded dimensions written into the review log; disposition quality (were pushbacks warranted, were folds proportionate) is assessed explicitly alongside pass count.

**Iterate-review:** NO (rationale: validation exercise in a downstream repo; no trinity-skills code ships in this phase)
**Status:** done (scope changed 2026-08-13 — see execution note below)

**Execution note (2026-08-13) — scope changed from live validation to retrospective mining, by Kyle's explicit direction.** The deliverables above assume a *new* doc-bot review run live with the new machinery. That didn't happen: doc-bot's editor write-path (Phases 0–4) had already fully converged on 2026-08-12 and sits in open PR #11 — there was no live review left to attach the new machinery to, and Kyle was explicit he wanted doc-bot **read-only** (mine the existing pass logs for learnings, no new commits, no live `iterate-review` run against doc-bot). What follows is what that read-only mining produced, in place of the originally-scoped live case study.

**Findings that directly validate the initiative's premise:**
- **Kyle independently hand-wrote the exact doctrine `accepted-risk`/pushback formalizes**, at write-path Phase 3 pass 10 (2026-08-12), *before* any of this plan existed: dispute when a scenario needs scale the deployment won't reach and the failure is inconvenience rather than dishonesty; fold without argument anything where the app would lie, anything in the merge path, anything a reviewer meets at real scale. That's `accepted-risk`'s pushback criteria and `PF-shipbar`'s trust-boundary exemption, independently invented in prose a day before Phase 2 shipped the mechanism. Convergent invention is stronger validation than a pass-count win would have been — it means the problem is real, not manufactured to justify the machinery.
- **One dispute recurred three separate times** across write-path Phase 0, Phase 1, and Phase 3 (the "drafts/publish/approve have no app-level auth" finding — same Q3 posture each time, invisible in each phase's diff) purely because no phase review had memory of the prior ones. This is direct, concrete evidence for what the register closes: one `RR-` entry would have let the *lens* recognize the pattern and stop filing it, instead of three separate dispute-and-cite cycles. (Folded into the Axis 1 dispute corpus as a clarifying update to entry 3, plus a genuinely new independent entry 4 — corpus now 4/6.)
- **A live, real operational hazard was caught in passing**: `merged-at-rev-0007` pass 2 (2026-08-13, in doc-bot) recorded "ALL LENSES FAILED" — every Codex call failed identically — traced in that review's own log to trinity-skills commit `43ef077`, the exact schema bug this plan's own Phase 1 shipped and then fixed minutes later in this session. Because `~/.claude/skills/iterate-review` is a live symlink into whichever trinity-skills commit is checked out, doc-bot's concurrent use hit the broken schema mid-fix. Nobody was at fault — the doc-bot review correctly diagnosed it as an external tooling defect and escalated rather than patching doc-bot — but it's a concrete instance of the symlink's known hazard (already on record: "the symlink tracks the checked-out branch") biting *harder* than expected: not just branch-switching, but any in-progress commit on the active branch being live for concurrent users mid-edit.

**Proposed `docs/risk-posture.md` for doc-bot** (reference only — not written to doc-bot; Kyle's call whether/when to apply it):

```
## Risk posture

PF-audience: Internal editorial/support staff, 1-3 person team, Tailscale-perimeter
             only (tailnet ingress verified as a deploy-review checklist item).
             Authentik identity is a planned drop-in seam, not yet built (Q3,
             closed 2026-08-04) — no public or anonymous access.
PF-blast: The plan's operating principle throughout (Q1-Q10 closeout): the
          cheapest correct mechanism for a 1-3 person team, not the most
          general one. Autosave-path corruption is bounded to one draft,
          recoverable via discard. Attribution weaker than ideal (`unknown`
          author) is a permanent accepted limitation until Authentik lands,
          not a probabilistic risk.
PF-shipbar: Blocks ship: the app claiming more than it verified (the "UI
            honesty rule" -- never render unattested authorship as verified,
            never report success when the actual outcome differs). The
            approve/merge path is a trust boundary -- full rigor applies to
            any authorization, atomicity, or merge-precondition defect there
            regardless of posture. Logged-as-accepted: no app-level auth on
            any endpoint (perimeter is Tailscale + eventual Authentik);
            attribution reads `unknown` until Authentik lands; autosave-path
            staleness/corruption bounded and recoverable; review queue
            unpaged at current single-digit-draft scale.

## Accepted risks

- **RR-2026-08-06-seq-poison** -- client-supplied seq can poison one draft
  for <=24h; recoverable via discard; accepted 2026-08-06 (write-path
  Phase 0 pass 5).
- **RR-2026-08-04-no-app-identity** -- no application-level authentication
  or authorization on any editor endpoint (drafts, publish, approve,
  cancel); perimeter is Tailscale-only ingress, Authentik is the planned
  drop-in seam; attribution is an explicit `unknown` sentinel until it
  lands; accepted 2026-08-04 (DevOps, Q3), ratified at code-review
  checkpoints 2026-08-06 (Phase 0), 2026-08-10 (Phase 1), 2026-08-12
  (Phase 3).
- **RR-2026-08-12-queue-unpaged** -- the review queue lists at most 100
  pending changes with no pagination; unreachable at the deployment's
  expected single-digit scale, and the failure mode there is an unlisted
  row, not data loss or a wrong answer; accepted 2026-08-12 (write-path
  Phase 3 pass 10).
```

Not proposed as a register entry: the deferred ruleset-ref-scoping finding (Phase 3 pass 12) — it's a conditional trigger ("fix when the content repo's ruleset exists"), not a settled acceptance, and the concurrent-approve/cancel dispute (`merged-at-rev-0007` pass 6) — that one was refuted as not a real risk at all, not accepted as a bounded one.

**Classification against the pre-defined outcome classes:** none of success/inconclusive/regression cleanly apply — those measure whether a *live* posture-aware review outperforms the baseline, and no live review ran. This is better described as a **premise check**, and it comes back strongly validating: the target problem (real proportionality judgment happening ad hoc, disputes recurring for lack of memory) is confirmed to exist in exactly the shape the plan assumed, independently and before the mechanism shipped. **What remains genuinely untested**: whether `accepted-risk`/register-match *actually reduces* pass count on a live future review — deferred to whenever the proposed posture file is actually applied to doc-bot and a real phase (write-path's own next work, or the new `runtime-pipeline-2026-08-13` plan once it has code) gets reviewed against it.

## Acceptance criteria

- [ ] Fresh plans of **both types** scaffolded by create-plan carry their Risk posture variant — initiative: all three answers under `PF-` ids; fix: the mandatory lightweight paragraph — with any register entries landing in `docs/risk-posture.md`, and an iterate-plan pass raises no posture-specific format findings against either.
- [ ] iterate-review passes include the posture block in the lens inputs when a posture source exists (correct precedence and source attribution when multiple sources exist); with no source, the intent file carries zero posture-specific bytes.
- [ ] `accepted-risk` exists end-to-end with stable ids and the full lifecycle (`proposed` → `confirmed`, or → `rejected` → `reopened`): disposition → batched checkpoint confirmation → recorded in pass log and state file; Converge is impossible while any item is `proposed` or `reopened`.
- [ ] Mechanism-requiring folds halt the loop with a design-decision framing instead of being built silently, per the operational boundary (signals + examples) in SKILL.md.
- [ ] Every named human-judgment moment (accepted-risk confirmation, design-shaped-fold escalation, `needs_human` questions, non-convergence stalls, malformed-posture-source resolution) produces a decision card — recommendation, 2–3 alternatives, standing discuss option — persisted in the pass log, where selecting any non-discuss option alone resumes the loop per that card type's outcome mapping (discuss deliberately pauses into conversation and re-presents).
- [ ] One live doc-bot review runs as the Phase 3 case study, with its outcome classified against the pre-defined success/inconclusive/regression classes and its dimensions recorded.

## Risks

### R1 — Suppression creep: posture becomes a mute button for real findings
The register or a vague ship bar could blanket-silence whole finding classes, and the editor could over-spend `accepted-risk` to converge faster.
**Mitigation:** register entries must name a specific behavior, its bound, and its recovery path — the reviewer prompt instructs lenses to ignore entries that read as categories ("ignore auth findings") rather than behaviors; `accepted-risk` requires a posture-referencing rationale; every acceptance needs explicit human confirmation to converge; trust-boundary code named in the ship bar is exempt from `accepted-risk` entirely (anti-criteria).

### R2 — Severity semantics drift breaks convergence math and cross-review comparability
If lenses start downgrading severities per posture, the HIGH+MEDIUM non-convergence guardrail and historical pass-log comparisons silently change meaning.
**Mitigation:** Q2's recommended resolution keeps lens severity absolute (worst credible outcome) and moves proportionality entirely into disposition; the guardrail change is confined to counting accepted-risk as resolved.

### R3 — Composition-golden and determinism regressions
The intent file and reviewer prompt sit on the byte-deterministic composition path with pinned goldens.
**Mitigation:** posture inclusion is editor-side (intent file content), keeping the runner untouched; the reviewer-prompt change regenerates goldens in the same commit; Phase 1 acceptance includes the no-posture byte-identity check.

### R4 — Pushback overcorrection: the editor starts disputing real, proportionate bugs
Training the editor that pushback is available could swing the 89% fold rate too far the other way.
**Mitigation:** criteria/anti-criteria are explicit and narrow; `accepted-risk` HIGHs always surface to the human, so overuse is visible per-review; Phase 3 explicitly reviews disposition quality, not just pass count.

## Open questions

*(All five recommendations below were endorsed by both lenses at pass 1, with the refinements now folded into the Approach; they remain open pending Kyle's confirmation at the checkpoint.)*

- **Q1.** When the editor marks a HIGH as `accepted-risk` in loop mode, does the loop halt immediately (current HIGH-guardrail behavior) or continue and batch the item for the next checkpoint? **Recommendation: continue and batch.** Halting per-finding recreates the interruption cost this plan exists to remove; the safety property ("no HIGH silently vanishes") is preserved because the proposal is persisted to the pass log immediately under a stable `AR-<n>` id, stays conspicuously pending at every checkpoint, and blocks Converge until confirmed. Immediate halt stays for the design-shaped-fold rule, where continuing would commit to an unapproved design.
- **Q2.** Do lenses adjust severity based on the posture block, or does severity stay absolute with posture informing only disposition? **Recommendation: severity stays absolute.** Severity should answer "what's the worst credible outcome," posture answers "do we care enough to fix it" — collapsing them makes pass logs incomparable across reviews and quietly rewires the non-convergence guardrail (R2). Lenses use posture to (a) set `register_ref` on independently-actionable matches and (b) skip filing findings that merely restate the documented perimeter/trust decisions without new evidence.
- **Q3.** How do accepted risks stop recurring across fresh reviews of the same repo? **Recommendation: the accepted-risks register is the recurrence firewall** — lenses see it every pass and reference entries by stable `RR-<id>` id instead of filing fresh HIGHs. A match never suppresses independent evidence that an entry's declared bound or recovery path is false — that's a new finding, and materially changed behavior requires a new or amended register entry with fresh confirmation. The alternative (carrying prior pass logs across reviews) bloats the prompt and couples unrelated reviews.
- **Q4.** Where does posture live for standalone reviews with no governing plan? **Recommendation: a per-repo `docs/risk-posture.md`** with the same section shape, maintained by the repo owner; a plan section overrides its *posture fields* when the invocation names the plan (v1 has no automatic plan discovery — see Approach §2), while the register always reads from the repo file, its single home. Missing, malformed, and both-present outcomes are logged distinctly. Authoring the file stays a downstream-repo task (doc-bot's is a Phase 3 deliverable).
- **Q5.** Does human confirmation of accepted-risk items happen only at Converge, or at every checkpoint where new ones accumulated? **Recommendation: every checkpoint surfaces them; confirmation is only *required* at Converge.** Confirmations persist across checkpoints; a rejected or deferred item stays visibly unresolved and blocks convergence rather than silently reverting to resolved; a material change to an accepted risk invalidates its prior confirmation.

## Out of scope

- **iterate-plan posture-awareness and decision cards** — the design reviewer could weigh posture too, and its checkpoints could adopt the same card format; plan review hasn't shown the same churn, so revisit after Phase 3 evidence.
- **Automatic posture inference** — the machinery never guesses the audience or ship bar from the code; posture is always human-authored.
- **`--max-passes` default changes** — the cap is a separate lever; this plan aims to make passes converge naturally, not to clip them.
- **Retro-application to doc-bot's shipped phases** — done reviews stay done; only new reviews use the machinery.

## Closeout

- [ ] Append entry to `CHANGELOG.md`: what shipped, ship commit, key delta, link to archived plan.
- [ ] Update memory (`trinity-expansion.md`): posture/proportionality shipped, link ship commits; note the doc-bot validation outcome and pass-count delta.
- [ ] Re-run `install.sh` so `~/.claude/skills/` picks up the changed skills; confirm doc-bot's next review uses them.
- [ ] Move plan to archive: `git mv docs/risk-posture-proportionality-2026-08-12.md docs/archive/`.
- [ ] Final commit with a "shipped" message referencing this plan.

## References

- doc-bot pass logs (evidence base): `~/code/doc-bot/code-review-editor-write-path-phase-0.md` (the seq-mechanism spiral, passes 4–9), `~/code/doc-bot/docs/reviews/code-review-editor-write-path-phase-3.md` (fold-introduced bugs at passes 2 and 6; re-filed auth HIGH at pass 1 finding 8).
- Disposition counts: 57 incorporated / 7 disputed across write-path logs (grep, 2026-08-12).
- `iterate-review/SKILL.md` — steps 9 (intent composition), 11–12 (fold + dispositions), 14 (checkpoint + loop guardrails).
- `iterate-review/reviewer-prompt.md` — lens instruction surface.
- `create-plan/template.md`, `create-plan/SKILL.md` — posture capture surface.
- Memory: `plan-authoring-workflow.md`, `trinity-expansion.md`.

<!--
=========================================================================
TOOLING-RESERVED SECTIONS BELOW THIS LINE.
Do NOT author content here at plan-creation time. iterate-plan and
iterate-review append/maintain these sections automatically.
=========================================================================
-->

## Review checkpoints

<!-- TOOLING-MAINTAINED by iterate-review for multi-phase plans.

| Phase | Iterate-review | Status | Last pass | Pass log |
|-------|----------------|--------|-----------|----------|
| Phase 0 | YES | reviewed | Pass 8, APPROVE×3 (2026-08-13) | `docs/reviews/code-review-branch-kyle-risk-posture-phase-0.md` |
| Phase 1 | YES | reviewed | Pass 8, APPROVE×3 (2026-08-13) | `docs/reviews/code-review-branch-kyle-risk-posture-phase-0.md` |
| Phase 2 | YES | in progress | — | review in progress — 12 passes, `docs/reviews/code-review-phase-2.md` |
| Phase 3 | NO  | n/a | n/a | n/a |
-->

## Pre-flight review pass (the editor, YYYY-MM-DD) [HISTORICAL]

<!-- OPTIONAL self-review by the editor before execution. Delete if skipped. -->

## Codex review pass 1 — answers (2026-08-12) [HISTORICAL]

### Verdict
REVISE (worst-of; both lenses REVISE, no FAILED lenses)

### Findings
1. **Accepted-risk identity and confirmation lifecycle are undefined** — HIGH · lens: architect: matching by prose is unstable; no state transitions from proposal through confirmation, no behavior for changed/re-filed findings, no Converge predicate.
   → Editor: incorporated — Approach §3 now defines stable `AR-<n>` ids minted at disposition time (pass log is the durable record, matching by id), the proposed→confirmed/rejected lifecycle (rejection reopens the finding; material change mints a new proposal), the Converge predicate (zero `proposed` items), and resume-from-log after interruption.
2. **Register-match tagging has no defined protocol boundary** — HIGH · lens: architect: "arrives tagged" had no representation in the enforced reviewer schema, and tagging responsibility alternated between lenses and editor.
   → Editor: incorporated — `reviewer-output.schema.json` gains an optional per-finding `register_ref`; register entries carry stable `RR-<id>` ids; the editor validates refs at fold time (unknown/malformed → untagged, logged). Tag-vs-don't-file distinction specified: independently-actionable matches get `register_ref`; findings merely restating posture decisions aren't filed; evidence a register bound is false is a fresh finding.
3. **Governing-plan discovery is unspecified** — HIGH · lens: architect: v1 has no `--plan` binding, so "the governing plan's section" was an unresolvable primary source.
   → Editor: incorporated — narrowed honestly: plan-section posture applies only when the invocation names the plan; `docs/risk-posture.md` is the only automatic source in v1; automatic discovery ships with v2 plan-binding (existing deferral). Absent/malformed/both-present outcomes logged distinctly.
4. **No-posture byte-identity conflicts with prompt modification** — HIGH · lens: architect: composed inputs can't both contain the new reviewer-prompt instruction and stay byte-identical to today's goldens.
   → Editor: incorporated — invariants separated: no-posture runs contribute zero posture-specific intent bytes and match the *regenerated* goldens; identity with today's goldens is explicitly not claimed.
5. **Design-shaped-fold halt lacks resumable control flow** — MEDIUM · lens: architect: card choices had no deterministic continuations; crash/resume unspecified.
   → Editor: incorporated — outcome mapping added (adopt → fold this pass; alternative → `incorporated (via alternative)`, re-reviewed next pass; accept → AR lifecycle; discuss → paused, no fold); card written to the pass log before presentation, so pending cards re-present on resume.
6. **Validation requires manufacturing an accepted risk** — HIGH · lens: product-manager: Phase 3 acceptance demanded a register match + confirmations from a live review, pressuring metric-driven misclassification.
   → Editor: incorporated — deterministic proofs moved to Phase 2 fixtures as the sole burden of proof; Phase 3 judges correct handling of whatever actually arises, with an explicit "nothing is preserved or solicited to manufacture a metric" clause.
7. **Pass-count outcome is not independently comparable** — MEDIUM · lens: product-manager: "comparable scope" undefined; ≤5-or-explain makes the 3–5-pass claim non-falsifiable.
   → Editor: incorporated — Phase 3 reframed as an indicative case study with recorded comparison dimensions (diff size, phase type, lens set, disposition mix, halt quality) and pre-defined success/inconclusive/regression classes written before the review runs.
8. **Decision-card goal is absent from top-level acceptance** — MEDIUM · lens: product-manager.
   → Editor: incorporated — top-level acceptance criterion added covering all four judgment moments, required card elements, pass-log persistence, and option-selection-resumes-loop.
9. **Posture source precedence is not covered by acceptance** — MEDIUM · lens: product-manager: the collision case (both sources present) was untested.
   → Editor: incorporated — Phase 1 acceptance gains the collision case (plan wins, source attributed, shadowed file noted) and the malformed-source case; top-level criterion updated to require correct precedence and attribution.
10. **Mechanism-requiring escalation boundary is too subjective** — MEDIUM · lens: product-manager: "new mechanism"/"new invariant" had no operational boundary.
    → Editor: incorporated — Approach §3 now lists classification signals (schema/migration, persisted or protocol field, cross-request invariant, background process, external dependency) and non-mechanism counter-examples; Phase 2 acceptance exercises a non-mechanism case and an ambiguous boundary case, not just the obvious one.

### Plan corrections applied
- Phase 1 Acceptance, register-match bullet: distinguished independently-actionable findings (tagged via `register_ref`) from findings that merely restate an accepted posture decision (not filed) — the original wording conflicted with Q2/Q3 (lens: product-manager).

### Open-question answers
1. **Q1** — both lenses endorse continue-and-batch, conditional on immediate persistence under a stable id, conspicuous pending display, and an explicit Converge predicate; immediate halt retained for design-shaped folds (architect: continuing there could commit to an unapproved mechanism). Refinements folded into Q1 and Approach §3.
2. **Q2** — both lenses endorse absolute severity with posture driving disposition only; refinement: a register match must not silently suppress a technically distinct finding — matching needs explicit identity and scope rules (now specified via `RR-<id>`/`register_ref`).
3. **Q3** — both lenses endorse the register as recurrence firewall, conditional on stable ids, bounded scope, and never suppressing evidence that an entry's bound/recovery is false (now specified).
4. **Q4** — both lenses endorse the per-repo fallback; refinement: missing/malformed/multiple sources must be distinguished in logs, not collapsed to "none" (now specified).
5. **Q5** — both lenses endorse surface-every-checkpoint, confirm-at-Converge; refinements: confirmations persist across checkpoints, rejected/deferred items stay visibly blocking, material change invalidates prior confirmation (now folded into Q5 and Approach §3).

### New questions Codex raised
- (none)

### Lens run summary
- architect: REVISE · product-manager: REVISE

## Codex review pass 2 — answers (2026-08-12) [HISTORICAL]

### Verdict
REVISE (worst-of; both lenses REVISE, no FAILED lenses)

### Findings
1. **Rejected accepted risks can satisfy the stated Converge predicate** — HIGH · lens: architect: after proposed → rejected there are zero `proposed` items, so Converge could become eligible while the reopened finding is unresolved; rejection's reversal of "resolved" accounting was unspecified.
   → Editor: incorporated — rejection now moves the item to an explicit `reopened` state that blocks Converge exactly as `proposed` does and immediately reverses the finding's resolved credit in guardrail/non-convergence accounting; Converge predicate is now zero items in `proposed` *or* `reopened`; Phase 2 dry-run acceptance exercises the reopened path.
2. **Fix-plan posture coverage contradicts the every-plan MVP goal** — HIGH · lens: product-manager: Goals promised posture in "every new plan" while Approach §1 made it only RECOMMENDED for fixes.
   → Editor: incorporated — one contract chosen: REQUIRED for every plan type; fixes get a *mandatory* lightweight variant (same three answers in one paragraph, register optional, inheriting the repo register when present). Approach §1, Phase 0 deliverables/acceptance, and the top-level criterion all updated consistently.
3. **Malformed primary-source fallback behavior is ambiguous** — MEDIUM · lens: architect: "surfaced, never silently skipped" didn't say whether composition stops, falls back, or proceeds without posture.
   → Editor: incorporated — deterministic control flow specified: a malformed source at the selected precedence level halts before fan-out with a decision card (fix / fall back to next source / proceed with none / abort), choice logged; no silent fallback at any level.
4. **Register-match resolution path lacks lifecycle semantics** — MEDIUM · lens: architect: the disposition's durability, confirmation basis, and behavior on mid-review register amendment were undefined — weaker than the AR lifecycle.
   → Editor: incorporated — register-match recorded as `register-match (RR-<n>)` in the pass log; validity requires the finding to fall within the entry's recorded behavior/bound/recovery; the entry's owner/date are its standing confirmation; amendment or removal mid-review invalidates matches against it, re-entering those findings as `reopened`; fully reconstructable from pass log + posture source.
5. **Fresh-plan acceptance is underspecified** — MEDIUM · lens: product-manager: "filled-in" and "without format complaints" had no observable definition and didn't distinguish posture-format failures from unrelated findings.
   → Editor: incorporated — Phase 0 and top-level acceptance now name both plan types, the observable content per variant (three answers + register for initiatives; lightweight paragraph for fixes), and the smoke condition (no posture-specific format findings; unrelated findings don't fail the smoke).

### Plan corrections applied
- (none supplied by either lens)

### Open-question answers
1. **Q1** — both lenses re-endorse continue-and-batch; architect's condition (rejection must immediately reverse resolved accounting) folded via finding 1.
2. **Q2** — both lenses re-endorse absolute severity; refinement (posture must not alter severity when new evidence falsifies a bound) already covered by the fresh-finding rule in Approach §2.
3. **Q3** — both lenses re-endorse the register firewall; refinement (match conditional on the finding falling within the recorded behavior/bound/recovery) folded via finding 4.
4. **Q4** — both lenses re-endorse the per-repo fallback; architect's demand for deterministic pause-or-fallback on malformed higher-priority sources folded via finding 3.
5. **Q5** — both lenses re-endorse surface-every-checkpoint / confirm-at-Converge; refinement (rejected/deferred proposals stay explicitly unresolved and convergence-blocking) folded via finding 1.

### New questions Codex raised
- (none)

### Lens run summary
- architect: REVISE · product-manager: REVISE

## Codex review pass 3 — answers (2026-08-12) [HISTORICAL]

### Verdict
REVISE (worst-of; architect REVISE, product-manager APPROVE, no FAILED lenses)

### Findings
1. **Escalation options bypass the trust-boundary prohibition** — HIGH · lens: architect: the design-shaped-fold card offered *accept the risk* even where the pushback anti-criteria forbid it (trust-boundary code named in the ship bar), contradicting "any displayed option resumes the loop."
   → Editor: incorporated — card construction is now context-sensitive: prohibited transitions are never displayed; trust-boundary escalations offer adopt / cheaper alternative / discuss only, so every displayed option stays a legal continuation.
2. **Register invalidation behavior lacks an explicit verification case** — MEDIUM · lens: product-manager: the amend/remove-entry-mid-review promise had no acceptance test.
   → Editor: incorporated — Phase 1 gains a fixture: amending or removing a referenced entry invalidates its matches, re-entering affected findings as `reopened` and blocking Converge until re-dispositioned.

### Plan corrections applied
- Repo layout, `create-plan/template.md` annotation: "REQUIRED for initiatives" → "REQUIRED for all plans; full for initiatives, lightweight for fixes" (filed by architect AND product-manager; deduplicated, applied once).
- Approach §3, accepted-risk lifecycle: "terminal disposition (… or a fresh accepted-risk proposal)" reworded — a fresh proposal is not terminal; it resolves only through proposed → confirmed (architect).
- Top-level acceptance, accepted-risk bullet: lifecycle summary now includes rejected → reopened and the complete zero-`proposed`-or-`reopened` Converge condition (product-manager).

### Open-question answers
1. **Q1–Q5** — third consecutive unanimous endorsement of all five recommendations from both lenses, with no new refinements this pass: continue-and-batch (Q1), absolute severity (Q2), register as recurrence firewall (Q3), per-repo fallback with named-plan precedence and the halt-on-malformed card (Q4), surface-every-checkpoint / confirm-at-Converge (Q5). All prior refinements already folded; answers recorded for the register.

### New questions Codex raised
- (none)

### Lens run summary
- architect: REVISE · product-manager: APPROVE

## Codex review pass 4 — answers (2026-08-12) [HISTORICAL]

### Verdict
REVISE (worst-of; both lenses REVISE, no FAILED lenses)

### Findings
1. **Register amendments are not detectable from the durable state** — HIGH · lens: architect: a match recorded as bare `register-match (RR-<n>)` gives resume/later passes no way to tell an unchanged entry from an amended one, so a stale match could keep counting as resolved — the Phase 1 invalidation fixture promised behavior the persisted state couldn't support.
   → Editor: incorporated — matches now persist a snapshot identity: `register-match (RR-<n>, entry-digest <hash>)`, a canonical-content hash of the entry's behavior/bound/recovery text as validated; resolved credit carries into a later pass or resume only after recomputing the current entry's digest, with mismatch/missing → invalidated → `reopened`.
2. **Malformed-source card violates the universal decision-card contract** — HIGH · lens: product-manager: the pass-2 card omitted the standing "discuss" option and sat outside the named judgment moments, so an inconsistent escalation surface could ship without failing acceptance.
   → Editor: incorporated — malformed-posture-source resolution is now the fifth named human-judgment moment under the shared card contract (recommendation, alternatives, standing discuss; persisted before presentation, re-presented on resume); Approach §3, Phase 2 deliverables, Phase 1 acceptance, and the top-level criterion all updated.

### Plan corrections applied
- (none supplied by either lens)

### Open-question answers
1. **Q1–Q5** — fourth consecutive unanimous endorsement from both lenses, no new refinements; architect's Q5 nuance (confirmations persist only while the finding and governing posture remain materially unchanged) was already folded via the material-change and digest-invalidation rules.

### New questions Codex raised
- (none)

### Lens run summary
- architect: REVISE · product-manager: REVISE

## Codex review pass 5 — answers (2026-08-12) [HISTORICAL]

### Verdict
REVISE (worst-of; both lenses REVISE, no FAILED lenses). **Loop-mode non-convergence guardrail fired after this pass** (HIGH+MEDIUM counts 2 → 2 → 3 across the last two transitions); halted for the human stall decision.

### Findings
1. **Four decision-card types lack deterministic outcome mappings** — HIGH · lens: architect: only design-shaped-fold cards had defined continuations; deferral semantics for accepted-risk were undefined (Q5 said "deferred," the lifecycle had no such notion), so Phase 2's "every option matches the outcome mapping" promised mappings that didn't exist.
   → Editor: incorporated — Approach §3 now maps all five card types (accepted-risk confirmation, design escalation, `needs_human`, non-convergence stall, malformed source) with per-option transitions; *defer* is defined as staying `proposed` under the same `AR-<n>` — no new state, no resolved credit, re-presented each checkpoint; context-sensitive omission applies uniformly.
2. **"Discuss" contradicts the pick-one-resumes acceptance contract** — HIGH · lens: product-manager: Approach §3 paused on discuss while the card contract and two acceptance criteria required any selection to resume — an implementation could only satisfy one.
   → Editor: incorporated — one consistent rule: every non-discuss option resumes deterministically per its mapping; *discuss* is deliberately non-resuming (paused conversation, card re-presented afterward with the agreed direction as the new recommendation). Card contract, Phase 2 acceptance, and the top-level criterion all aligned.
3. **Confirmed accepted risks are not invalidated when governing posture changes** — MEDIUM · lens: architect: a design-card choice can update the posture mid-review, yet a confirmed `AR-<n>` justified by the old posture kept its resolved credit.
   → Editor: incorporated — confirmations now carry a posture dependency: the rationale names the posture content it relies on and stores a canonical digest of exactly those parts (same mechanism as register matches); a change to the named content returns the item to `proposed` for fresh confirmation, unrelated posture edits never invalidate. Phase 2 gains the two-sided fixture.

### Plan corrections applied
- (none supplied by either lens)

### Open-question answers
1. **Q1–Q5** — fifth consecutive unanimous endorsement from both lenses; architect's Q5 deferral nuance (deferral retains an unresolved, convergence-blocking proposal, never resolved credit) folded via finding 1.

### New questions Codex raised
- (none)

### Lens run summary
- architect: REVISE · product-manager: REVISE

## Codex review pass 6 — answers (2026-08-12) [HISTORICAL]

### Verdict
REVISE (worst-of; architect REVISE, product-manager APPROVE — zero findings, its first clean pass; no FAILED lenses)

### Findings
1. **Proposed accepted risks have contradictory resolved-credit semantics** — HIGH · lens: architect: "satisfies the HIGH guardrail," "counts as resolved," "reverses resolved credit," and "no resolved credit (deferred)" could not all hold — three accounting contexts were sharing one undefined word, so different parts of the control flow could give different answers for the same `AR-<n>`.
   → Editor: incorporated — a normative per-state × per-ledger accounting table added to Approach §3 (HIGH guardrail / non-convergence count / Converge, for `proposed`, `confirmed`, `reopened`, and both register-match conditions); lifecycle prose, the defer mapping, rejection wording, and the Phase 2 dry-run fixture all rewritten to defer to the table.

### Plan corrections applied
- (none supplied by either lens)

### Open-question answers
1. **Q1–Q5** — sixth consecutive unanimous endorsement from both lenses; architect's Q1 condition (explicit per-ledger treatment of `proposed`) folded via finding 1.

### New questions Codex raised
- (none)

### Lens run summary
- architect: REVISE · product-manager: APPROVE

## Codex review pass 7 — answers (2026-08-12) [HISTORICAL]

### Verdict
REVISE (worst-of; architect REVISE, product-manager APPROVE — second consecutive clean pass; no FAILED lenses)

### Findings
1. **Posture-dependency digests lack durable, recomputable selectors** — HIGH · lens: architect: register dependencies had stable `RR-<id>` ids to anchor digests, but ship-bar/blast-radius dependencies were identified only by prose — different implementations could canonicalize different spans, miss a relevant amendment, or invalidate on unrelated edits, and post-interruption reconstruction was unverifiable.
   → Editor: incorporated — posture elements now carry stable field ids written by the template (`PF-audience`, `PF-blast`, `PF-shipbar`, alongside `RR-<id>`); confirmations persist a dependency descriptor (list of field ids) + digest of those fields as confirmed; re-resolution is by id on every pass and resume, with unresolvable/ambiguous descriptors invalidating toward `proposed`; the Phase 2 fixture is now two-sided *and* interruption-crossing.

### Plan corrections applied
- (none supplied by either lens)

### Open-question answers
1. **Q1–Q5** — seventh consecutive unanimous endorsement from both lenses; both explicitly note the accounting table and source-handling rules now make the recommended behaviors verifiable. No new refinements.

### New questions Codex raised
- (none)

### Lens run summary
- architect: REVISE · product-manager: APPROVE

## Codex review pass 8 — answers (2026-08-12) [HISTORICAL]

### Verdict
REVISE (worst-of; architect REVISE, product-manager APPROVE — third consecutive clean pass; no FAILED lenses). **Loop-mode non-convergence guardrail fired after this pass** (HIGH+MEDIUM counts 1 → 1 → 1 across the last two transitions); halted for the human stall decision.

### Findings
1. **Fix plans cannot inherit the repo accepted-risks register** — HIGH · lens: architect: the pass-2 "fixes inherit the repo register" promise contradicted single-source precedence — a named fix plan shadowed `docs/risk-posture.md` entirely, so lenses and the fold could never see the repo's `RR-<id>` entries, defeating the recurrence firewall.
   → Editor: incorporated — resolved by giving the register **a single home per repo (`docs/risk-posture.md`)**: plan posture sections carry only the three `PF-` fields, never a register; create-plan/the editor append new accepted risks to the repo file (scaffolded if absent); precedence and shadowing now govern posture fields only, while the register always arrives from its home. This deletes the merge/collision/digest-provenance problem space entirely rather than specifying it. Approach §1/§2, Phase 0 deliverables/acceptance, Phase 1 acceptance (named-fix-plan fixture added), Phase 3 deliverable, Q4, and the top-level criterion all updated.

### Plan corrections applied
- (none supplied by either lens)

### Open-question answers
1. **Q1–Q5** — eighth consecutive unanimous endorsement from both lenses; architect's Q3/Q4 caveats (the fix-plan/register source conflict must be corrected; merge semantics needed if inheritance stands) resolved by the single-home model folded via finding 1.

### New questions Codex raised
- (none)

### Lens run summary
- architect: REVISE · product-manager: APPROVE

## Codex review pass 9 — answers (2026-08-12) [HISTORICAL]

### Verdict
REVISE (worst-of; architect REVISE, product-manager APPROVE — fourth consecutive clean pass; no FAILED lenses). Run as a single manual pass per Kyle's stall decision, with convergence agreed regardless of outcome after folding.

### Findings
1. **Register publication is not synchronized with human confirmation** — HIGH · lens: architect: pass 8's "editor appends at fold time" let an unconfirmed (or later-rejected) `AR-<n>` become a durable `RR-` entry with standing confirmation — editor proposals could turn into repo policy without a human in the loop.
   → Editor: incorporated — publication now happens only inside the human confirm transition, with an explicit scope choice on the confirmation card: *confirm — this review only* (register untouched) vs *confirm + add to register* (entry written as part of the transition; write failure surfaces at the checkpoint and the confirmation does not complete). Rejection/invalidation never touches the repo file; create-plan seeding is author-dictated and thus self-confirming.
2. **Sequential register IDs have no collision-safe allocation mechanism** — HIGH · lens: architect: two branches allocating the same next `RR-<n>` and merging would silently retarget or orphan persisted references (refs, digests, dependency descriptors all key on the id).
   → Editor: incorporated — ids are now allocation-free date-slugs (`RR-2026-08-06-seq-poison`): no counter to race, merges are ordinary git conflicts, references never renumber; duplicate ids in the file are a malformed source (halt card); ids are never reused or renamed once referenced.

### Plan corrections applied
- Goals (MVP), first bullet: plans no longer described as capturing a register — posture-field capture (plan) explicitly separated from register maintenance (`docs/risk-posture.md`) (architect).

### Open-question answers
1. **Q1–Q5** — ninth consecutive unanimous endorsement from both lenses; the product-manager lens explicitly endorses the single-home model as coherent; architect's Q3 condition (the AR→RR publication boundary must exist) folded via finding 1.

### New questions Codex raised
- (none)

### Lens run summary
- architect: REVISE · product-manager: APPROVE
