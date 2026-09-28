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
- Both skills' per-pass state summaries record the components seen this pass, each component's committed streak, explicit retirements, and every simplification card presented with its outcome; `tools/cluster_tracker.py` pins the counting semantics executably, fixture-tested by `tools/check-cluster-streak.py`, the same pattern as `freeze_tracker.py`.
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
- **A label names a mechanism, never a document location.** In `iterate-review` the mechanism is a guard, a lock, a recovery path, a classifier; in `iterate-plan` it is the mechanism or invariant a decision describes (a D-number or section may *cite* it, but numbering and headings change while the mechanism stays the same, so they never *define* identity), and unrelated mechanisms that happen to sit under one broad decision get separate labels.
- **Three simplification outcomes, three label lifecycles** (the tracker in §2 pins each): *remove* → the label **retires**; *replace* → the old label retires and the replacement gets a **new label with a fresh streak**; *narrow* → the mechanism was kept, so the label is **retained** and its streak **resets to 0** (a human decision was made and applied; continued findings on the narrowed mechanism start a fresh three-pass count, and the card returns if they reach it).
- **Retirement is explicit and persisted; absence is only a reset.** When a component leaves the review's scope (a chunk boundary drops it, a fold deletes it), the editor writes `retired: <label> (<why>)` in that pass's HISTORICAL block; a resumed session reconstructs identity from that record. A pass on which a label merely draws no HIGH/MEDIUM finding resets its streak and nothing more.
- **When uncertain, use the file or function name** the finding cites. Under-clustering is the conservative error, but its cost is not bounded to one pass: persistent label drift can delay the card indefinitely. The existing cap and stall cards remain the backstop, and their new cluster section (§4) lists labels side by side so drift is visible to the human there.
- Corrections (`code_corrections` / plan corrections) are not tagged; only merged findings count.

### §2 Streak tracker (both skills, Phase 0)

`tools/cluster_tracker.py` is a reference implementation in the style of `freeze_tracker.py`: not invoked by any runner, pinning the counting semantics so prose ambiguity can't reopen them. A pass is represented as `("failed",)` or `("findings", {label: worst_severity})`. Semantics:
- The streak for a label counts **consecutive completed passes** on which that label appears on at least one HIGH or MEDIUM merged finding. **One pass is one observation**, however many findings on the label it carries. LOW findings never count.
- A pass on which the label appears only on LOW findings, or not at all, **resets** the streak to 0.
- A pass with a FAILED lens after retry is **skipped** for streak purposes: it neither counts nor resets (the freeze tracker's rule, for the same reason: a lens that didn't run says nothing about the component). Findings the completed lenses did return are still dispositioned normally; only the streak accounting skips. Three qualifying passes may therefore span more than three attempted passes.
- **The committed record is the pass log** (the HISTORICAL blocks; in `iterate-plan` the plan file itself), never the state file, which both skills derive only at exit. The **candidate streak** at fold time = the streak committed by prior completed passes + 1 if this pass's *merged* findings carry the label at HIGH/MEDIUM. The gate fires when the candidate streak reaches `CLUSTER_N`, before the first fold on that label this pass (§3 defines the transition order).
- Outcomes, per §1: *remove* → retired; *replace* → retired + new label at streak 0; *narrow* → retained, streak reset to 0; *fold once more* → the streak is **not** reset, it keeps counting, and the card returns on every further pass on that label; *accept the risk* → the label is **retained** and its streak resets to 0 (a human decision applied), because the `AR-<n>` lifecycle is finding-specific and owns only that finding: a later HIGH/MEDIUM merged finding on the label, whether outside the accepted behavior or the same finding re-reported after a rejected or posture-invalidated `AR-<n>` restores it to the open ledgers, is an ordinary observation on the pass that reports it. **Checkpoint lifecycle events are never observations**: a rejection or invalidation changes the finding's ledger state exactly as today and nothing else; a reopened finding folded on a later pass without a reviewer re-reporting it is likewise not an observation, since it was already counted on the pass that reported it. There is exactly one observation source, merged HIGH/MEDIUM findings at fold time, and exactly one transition path (§3); the cost is that a rejected AR on an otherwise quiet pass can delay the card by at most one pass, which is accepted for the sake of a single counting rule; *split the plan* → the label **retires** here (explicit, persisted), since the mechanism has left this plan's scope and the new plan tracks it from 0.
- **The threshold is stated as a literal number in each skill's own SKILL.md** (fold step, checkpoint lookahead, card evidence length), because each skill directory is independently installable by copy (README's supported install; `check-plan-runners.py` tests skill-only copies) and a copied install has no `tools/`. `tools/cluster_tracker.py`'s `CLUSTER_N` is the **development-side pin, not a runtime source**: `tools/check-cluster-streak.py` asserts that every threshold literal in both SKILL.md files equals the constant and that the two files agree with each other, so a tuning change that misses a copy fails the suite instead of shipping two thresholds. Tuning is therefore a three-place edit (constant + both files) that the checker keeps consistent; the recipe takes the number as `--arg n`.

`tools/check-cluster-streak.py` fixture-pins the boundary cases: first pass counts as 1; LOW-only pass resets; FAILED pass skips; two labels in one pass track independently; several findings on one label in one pass count once; remove retires; replace starts a fresh label at 0; narrow retains the label at 0 and re-fires after N further passes; fold-once-more keeps counting and re-fires next pass; accept-risk retains the label at 0 and a later merged finding counts; a checkpoint AR rejection on a quiet pass is *not* an observation and the next re-report is; split-plan retires; explicit retirement vs absence; the impersonation-c1b sequence end to end.

**State summary `summary_schema` 1 → 2, both skills, additive.** Per pass: `observation: true|false` (true when every selected lens completed, false when any lens was FAILED after retry, derived from the block's Lens run summary line; this is what lets the recipe tell a skipped pass from a quiet one, which the aggregate verdict alone cannot), `components: {label: {"worst_severity": ..., "findings": n, "fold_caused": n}}` (counts, not booleans: a label with mixed provenance reports how many of its findings were fold-caused), `streaks: {label: n}` (as committed at the end of the pass), `retired: [labels]`, and `cards: [{"type": "simplification", "component", "streak_at_fire", "findings_in_streak", "fold_caused_in_streak", "chosen": "remove|narrow|replace|fold-once-more|accept-risk|split-plan|pending|aborted", "reason": "premature|deliberate|null"}]` (the three `simplify (...)` resolutions map to their operation so replay can tell them apart), one row per card presented that pass. Rows are derived from the HISTORICAL blocks by the same deterministic procedure v2.4 uses for the existing rows; a schema-1 file, or a Phase-0-only run with no cards, reads as `cards: []`. `tools/provenance-recipe.jq` gains `cluster_hits` (every card row across the accumulated state files, with its outcome and the `components` entry for that label from the **next row with `observation: true`**; a schema-1 row has no flag and is reported as `next: unknown` rather than guessed) so every §5 measure is a `jq` run over `cards` rows, not a re-read of prose. Fixtures: a Phase-0-only file, a mixed schema-1/schema-2 set, a pass with a pending card, a pass with two cards.

### §3 The simplification card (both skills, Phase 1)

A sixth named human-judgment moment, under the existing shared card contract. It fires **at fold time**, at the finding that brings a label's streak to 3, exactly like the design-shaped-fold escalation: the editor pauses at that finding, does not fold it, writes the card to the pass log with `chosen: (pending)`, and presents it.

Card content, all fields required:
- The three (or more) findings in the streak, each with pass number, lens, severity and fold-provenance, so the human sees the pattern rather than trusting the count.
- **Recommendation: simplify** — remove, narrow or replace the component, with a concrete sketch. **Every simplification operation the card offers, recommended or alternative, carries its own three sub-fields**: *the guarantee lost*, *which remaining layer covers it* (or "none," stated plainly), and a **per-finding accounting**: one line per finding in the streak stating whether *that operation* resolves it and how, or does not. Sharing a mechanism does not mean one change closes every defect (narrowing a classifier's inputs can fix one bypass and leave another inside the retained inputs), and removal and narrowing resolve different subsets, so the accounting is per operation and the chosen operation's accounting is the one that licenses dispositions. *Fold once more*, *accept the risk* and *split the plan* carry no accounting; they change nothing about the mechanism. A card whose offered simplification options are missing any sub-field is malformed and is not presented.
- **Alternatives** (up to three, per the cardinality rule). Two options are **mandatory on every card**: *remove the mechanism* (issue #6's carried constraint; it is the recommendation or else the first alternative) and *fold once more* (always listed, never the recommendation). The remaining slot or slots, in priority order when the cap of four total options bites: the skill's escape hatch, *split the plan* in `iterate-plan` or *accept the risk* in `iterate-review` when the posture permits; then the other simplify operation (*narrow* or *replace with a named cheaper mechanism*) when it exists. A card that recommends narrowing therefore reads: recommendation narrow; alternatives remove, fold once more, and one of split/accept or replace. Context-sensitive omission may drop optional options only, never the two mandatory ones.
- **discuss**, never counted, never omitted.

Outcome mapping: *simplify* → one fold applies exactly one of the three operations §1 defines, and the card's resolution records which: `chosen: simplify (remove)`, `simplify (narrow)` or `simplify (replace)`. The label lifecycle is the one §1/§2 give that operation (remove → retired; narrow → retained, streak 0; replace → retired, replacement labeled fresh at 0), never a fourth rule of §3's own; the resolved findings are dispositioned `incorporated (by simplification)` per the per-finding accounting below, and the next pass reviews the simplified head. *Fold once more* → ordinary fold, streak continues, card returns next pass on that label; the human's reason (`premature` / `deliberate`) is recorded. *Accept the risk* → the existing `accepted-risk` lifecycle, `AR-<n>`, unchanged, and **the component stays tracked** (§2). *Split the plan* (`iterate-plan` only) → the component's decisions and questions move to a new plan stub; this plan's text references it; the label retires here because the mechanism has left this plan's scope; loop resumes on what remains. *discuss* → paused.

**Transition order, so counting and presentation happen exactly once.** (1) Merge produces the pass's findings. (2) The editor classifies every finding's component label and computes each label's candidate streak from the committed record plus this pass, *before any fold*. (3) For each label whose candidate streak reaches N, the editor writes the card to this pass's `### Decision cards` with `chosen: (pending)`, the component label, the streak, and the findings it comprises; **the tagged findings' `→ Editor:` slots stay empty** (the tag lives in the card entry, not the disposition line), so the existing resume rule — an empty slot is unfinished work — remains true and a persisted classification never reads as a completed disposition. (4) The card is presented; folding of *other* labels' findings may proceed meanwhile, matching how the design-shaped-fold escalation pauses at one finding rather than the whole pass. (5) On the answer, the card is resolved in place naming the chosen operation, and the same-label findings are dispositioned **according to that operation's per-finding accounting as persisted in the pending card, never the recommendation's by default and never as a batch** (a resumed session reads the chosen operation from the resolution and applies the matching accounting): a finding the simplification resolves becomes `incorporated (by simplification)` (one implementation fold covers all of those; no per-finding patches follow); a finding it does *not* resolve keeps its ordinary path, an ordinary fold, `disputed` with reasoning, or an `accepted-risk` proposal under that lifecycle's own rules and trust-boundary exclusions, and is never marked incorporated by association. This is R2's "findings are never suppressed" made operational. For *fold once more*, every finding takes its ordinary path. (6) The pass's HISTORICAL block, once sealed, is what the next pass's candidate streak reads. A card is identified by `(pass, component)`; a resumed session that finds a `(pending)` card re-presents that one card and does not recount, and a resumed session that finds a resolved card with un-dispositioned same-label findings completes step (5) without re-presenting. The *fold once more* alternative records a one-word reason the human picks at the card, `premature` (the card wasn't warranted) or `deliberate` (warranted, but one more targeted fold is the right call), which §5 consumes.

The card is written and resolved in two phases like every other card (pending write before presentation, resolution write on answer), so an interrupted session re-presents it on resume.

### §4 Cluster check on the existing cap and stall cards (both skills, Phase 1)

When the max-pass cap or the non-convergence guardrail fires, the card gains a **cluster section**: HIGH/MEDIUM findings from the last three passes grouped by component with each label's streak, and one explicit line per state: "no component has a streak ≥ N−1"; "`<label>` at N−1 — one more pass on it triggers the simplification card"; or, for a label already at or past N, "`<label>` at <n> — simplification card presented at pass <p>, chosen: <outcome>" (a *fold once more* label keeps climbing past N, and this line is how the cap card shows that a decision was already taken and what it was). This is the ResearchLogix rule's second half ("at the six-pass cap, run the same cluster check before offering another pass"), and it turns the cap into a trigger for the check rather than a bare budget number.

### §5 Measurement contract

Success is judged on future loops in ResearchLogix_v2 (the cohort with instrumentation), not on this repo's own review of this plan. Measures, all computable by `tools/provenance-recipe.jq` from state files:
- **Pass count** of reviews where the card fired, against the pre-rule long-loop baseline (8, 11, 12, 16).
- **Card outcome mix**: remove / narrow / replace / fold-once-more / accept / split. Descriptive only: it shows what operators actually choose. The threshold-change decision belongs solely to the false-positive rule below; a run of *deliberate* fold-once-more answers is a legitimate pattern, not a trigger.
- **False-positive signal**: cards where *fold once more* was chosen with reason `premature` (§3), the human's own verdict at the card that the escalation wasn't warranted. "The next pass was quiet on that label" is deliberately *not* the signal: that is also what a good fold looks like, so it cannot distinguish a needless card from a useful one. Denominator: cards with a resolved outcome; `pending` and `aborted` rows are excluded. If `premature` exceeds one in three over the first ten resolved cards, `CLUSTER_N` moves to 4, recorded here as the rollback condition. That is a coordinated change (constant, both SKILL.md files, fixtures, recipe argument) that `check-cluster-streak.py`'s threshold-consistency assertion keeps honest, not a re-litigation of the design.
- **Fold-caused share** of findings across the cohort, currently 37%, expected to fall.

This is a learning goal, never a ship gate.

### Repo layout

New: `tools/cluster_tracker.py`, `tools/check-cluster-streak.py` (wired into `tools/check-all.sh`). Modified: `iterate-review/SKILL.md` (steps 12, 14, 16), `iterate-plan/SKILL.md` (steps 8, 10, and the state-file section), both `state/example*.json`, `tools/provenance-recipe.jq`, `tools/check-provenance-recipe.py`, `tools/check-parity.py` (new rules), `README.md`, `CHANGELOG.md`.

## Phasing

### Phase 0 — Component tags + streak tracker (the data half) (~4h)
**Deliverables:**
- `[component: <label>]` tag and labeling rules (§1) in both SKILL.md fold steps, beside the provenance tag; HISTORICAL block template updated in both.
- `tools/cluster_tracker.py` + `tools/check-cluster-streak.py` (§2), wired into `check-all.sh`.
- State summary `summary_schema` 2 with `components` (counts), `streaks`, `retired` and `cards` per pass, in both skills; both example state files updated; readers tolerate schema-1 files (missing fields read as empty, `cards` as `[]`); derivation procedure documented beside v2.4's.
- `tools/provenance-recipe.jq` `cluster_hits` query taking the threshold as `--arg n`, + checker fixtures: Phase-0-only, mixed schema, pending card, two cards in one pass.
- `check-cluster-streak.py` asserts every literal threshold in both SKILL.md files equals `cluster_tracker.CLUSTER_N`.
- Parity rules: tag placement, labeling rules, three-outcome label lifecycle, explicit-retirement-vs-reset, one-observation-per-pass, LOW-excluded, FAILED-skips, threshold-literal-present-and-equal.

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
- **Every copy** of the `introduced_by_pass` reservation in both SKILL.md files rewritten in one fold: the per-finding prose in the fold step, the state-summary paragraph (which currently forbids consulting *any* field defined there, and would otherwise contradict the new `cards`/`components` consumers), and the Hard rules entry. The replacement text draws the line explicitly: **component-based triggering is permitted and is the only trigger; provenance fields are consumed as card evidence and §5 measurement only, never as a trigger.** `check-parity.py` pins the new sentence in both files and `tools/test-checkers.py` gains a negative case that the old "none may consult" wording is absent.
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
- [ ] State summaries at `summary_schema` 2 carry `components` (counts), `streaks`, `retired` and `cards`; schema-1 files still read; every §5 measure is demonstrated from state-file fixtures including a multi-finding label and a pending card.
- [ ] Both installed skills state the threshold as a literal in their own SKILL.md; `check-cluster-streak.py` fails when either literal disagrees with the development constant or with the other file.
- [ ] The simplification card fires at streak 3, before the fold, with all required fields, in both skills; "fold once more" is always an alternative and never the recommendation.
- [ ] No path exists by which the gate stops a loop or removes a mechanism without a card being answered by a human.
- [ ] Cap and stall cards show the cluster section.
- [ ] `provenance-recipe.jq` answers the §5 measures from accumulated state files.
- [ ] Issue #6 closed; CHANGELOG 2.5.0; README current.

## Risks

### R1 — Label drift: the same mechanism gets different labels across passes, so the streak never forms
**Mitigation:** the labeling rules in §1, a worked example in each SKILL.md, and the cluster section on the cap card (§4), which shows labels side by side so a human can spot two names for one thing. Stated honestly: persistent drift can delay the card indefinitely, not by one pass, and the cap card is an opportunity for human detection rather than a guaranteed recovery. That is today's behavior, not a regression, and every existing guardrail stays in force.

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

Every change is prose plus stdlib tooling; `git revert` of the Phase 0 or Phase 1 merge restores the prior skill behavior with no data migration, and schema-2 state files remain readable by schema-1 prose (extra fields are ignored). **Analytics compatibility is a separate decision from skill rollback**: today's `tools/provenance-recipe.jq` selects `summary_schema == 1` only, so Phase 0 also teaches it to read both schemas. If a rollback reverts that reader change too, every schema-2 run silently drops out of the recipe's tallies; the rollback instruction is therefore to keep the schema-tolerant reader even when reverting the skill prose, and to say so in the revert commit. The tuning rollback (`CLUSTER_N` 3 → 4) is the coordinated change §5 describes, kept consistent by the checker's threshold assertion.

## Sequencing decision

Now, because: the data gate on issue #6 is met; the prose rule is live in ResearchLogix_v2 with two successful firings, so the skills currently lag the practice; and every week of unported rule is another builder relying on a playbook paragraph. Nothing else is in flight in this repo (PR #9 merged 2026-09-28). Axis 1 stays parked.

## Open questions

- **Q1.** Fire *at* the third pass, before folding that finding (as the CSRF code review did), or *after* the third fold, before a fourth? Recommendation: at the third, before folding; the third fold is the one the evidence says gets wasted. *Pass 1: both lenses agree — fire before the first qualifying fold on that label, computed as a candidate streak (committed record + this pass); the finding stays pending until the card is answered. Folded into §2/§3; Kyle to confirm at Converge. Pass 2: both lenses answered equivalently (freeze streak 2). Pass 3: same resolution, but the architect attached a new condition (checkpoint-event protection, its F2); conservatively not equivalent, streak resets to 1. That condition is now moot: pass 3's fold removed checkpoint events from observation counting entirely. Pass 4: both lenses equivalent, the architect withdrawing the condition explicitly (streak 2).*
- **Q2.** Should a FAILED-lens pass skip (neither count nor reset) as the freeze tracker does? Recommendation: yes, same reasoning; a lens that didn't run says nothing about the component. *Pass 1: both lenses agree — skip streak accounting for the whole pass, still disposition the findings the completed lenses returned; N qualifying passes may span more than N attempts. Folded into §2. Pass 2: both lenses answered equivalently (freeze streak 2). Pass 3: equivalent again.* — FROZEN at pass 3 (answered identically ×3; reopens on any edit touching this question or new evidence)
- **Q3.** Does a streak carry across chunk boundaries within one pass log (delegate-grants reviewed chunks B and C in one log)? Recommendation: yes, the log is the unit; the editor retires a label when its component leaves the diff, and the tracker's reset-on-absence handles the rest. *Pass 1: both lenses agree, with a sharpening — mechanism continuity, not the shared log, is what carries a streak; explicit retirement (persisted) is distinct from a quiet pass (reset). Folded into §1; a cross-chunk case is in the tracker fixtures. Pass 2: both lenses answered equivalently (freeze streak 2). Pass 3: equivalent again.* — FROZEN at pass 3 (answered identically ×3; reopens on any edit touching this question or new evidence)
- **Q4.** In `iterate-plan`, what is a "component"? Recommendation: a plan mechanism as the plan names it (a D-numbered decision, an invariant, a named lock or classifier), which is how the CSRF plan's Q7 already described the cluster. *Pass 1: both lenses agree with one correction — the mechanism or invariant is the identity; a D-number or section may cite it but never defines it, and unrelated mechanisms under one decision get separate labels. Folded into §1. Pass 2: both lenses answered equivalently (freeze streak 2). Pass 3: equivalent again.* — FROZEN at pass 3 (answered identically ×3; reopens on any edit touching this question or new evidence)
- **Q5.** Should the card also fire on a streak of *two* when both findings are fold-caused? Recommendation: no for MVP; show provenance as evidence, keep one trigger, revisit with §5 data. *Pass 1: both lenses agree — one trigger until the single-trigger behavior is measured. Pass 2: both lenses answered equivalently (freeze streak 2). Pass 3: equivalent again.* — FROZEN at pass 3 (answered identically ×3; reopens on any edit touching this question or new evidence)

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

## Codex review pass 1 — answers (2026-09-28) [HISTORICAL]

### Verdict
REVISE (worst-of: architect REVISE, product-manager REVISE; no FAILED lens). Merged HIGH+MEDIUM count: 5.

### Findings
1. **Narrowing both retains and retires the component label** — HIGH · lens: architect, product-manager (co-reported, same defect): §1 said narrowing keeps the label while §2/§3 retired the label after every simplify outcome, so a narrowed mechanism that keeps drawing findings had two incompatible tracking paths.
   → Editor: incorporated — §1 now defines three outcomes with three lifecycles (remove → retire; replace → retire + new label at 0; narrow → retain, streak reset to 0) and §2's tracker fixtures pin "narrow, then keeps drawing findings, re-fires after N". Not plan-shaping: a rule clarification inside the approved mechanism. [introduced_by_pass: null]
2. **Pre-fold counting lacks a durable, idempotent transition** — HIGH · lens: architect: §2 counted completed passes while §3 fired mid-fold; no distinction between a candidate streak and committed history; multiple same-label findings and resume could double-count or double-present; tagging a finding before its card is answered could collide with the existing empty-slot resume rule; state files can't serve as the live record since both skills derive them at exit.
   → Editor: incorporated — §2 names the pass log as the committed record and defines the candidate streak; §3 gains a six-step transition order: classify before fold, card keyed by (pass, component) with tags in the card entry and `→ Editor:` slots left empty, one-move disposition of all same-label findings on answer, resume rules for pending and resolved-but-incomplete cards. [introduced_by_pass: null]
3. **State summaries cannot support the promised §5 measurements** — HIGH · lens: product-manager (HIGH), architect (MEDIUM; merged, same gap): schema 2 recorded a worst severity, one boolean and a streak, with no card records, no outcome, no next-pass association, and no aggregation rule for mixed provenance on one label.
   → Editor: incorporated — schema 2 now carries `components` as counts, `retired`, and a `cards` array (type, component, streak at fire, findings and fold-caused counts in the streak, chosen outcome incl. pending/aborted, reason); `cluster_hits` joins each card to the next completed pass's entry; fixtures added for Phase-0-only, mixed schema, pending card, two cards. Goals bullet 2 and Phase 0 deliverables updated to match. Judged a mapping correction of an approved goal, not plan-shaping. [introduced_by_pass: null]
4. **The one-line threshold rollback has no runtime source of truth** — MEDIUM · lens: architect: the tracker is not invoked by runners, so changing its constant would leave SKILL.md prose, card evidence length, the checkpoint lookahead and the recipe firing at three.
   → Editor: incorporated — §2 makes `cluster_tracker.CLUSTER_N` the single source, all prose says "N" and cites it, the recipe takes `--arg n`, and `check-cluster-streak.py` asserts every literal threshold in both SKILL.md files equals the constant; §5 and Rollback now call tuning a coordinated change the checker keeps honest. [introduced_by_pass: null]
5. **The false-positive rule also counts successful ordinary fixes** — MEDIUM · lens: product-manager: "fold once more, then a quiet next pass" is also what a useful fold looks like; pending and FAILED next passes were untreated.
   → Editor: incorporated — the signal is now the human's own reason recorded at the card (`premature` vs `deliberate` on the fold-once-more alternative, §3); denominator is resolved cards only; the next-pass-quiet heuristic is explicitly rejected in §5. [introduced_by_pass: null]

### Plan corrections applied
- §4 cluster section: the status line now has three cases, including a label already at or past N with its card outcome shown (both lenses filed this).
- §1 uncertainty rule + R1: under-clustering's cost stated honestly as an indefinitely delayed card with the cap card as an opportunity for detection, not a one-pass bound (both lenses filed this).
- Phase 1 deliverables: the provenance-reservation replacement now covers every copy in both SKILL.md files (fold-step prose, state-summary paragraph, Hard rules) and states the permitted/forbidden line explicitly; parity rule + negative checker case added (architect).

### Open-question answers
1. Q1 — both lenses: fire before the first qualifying fold on the label; candidate streak = committed + this pass. Agree with the recommendation; folded.
2. Q2 — both lenses: skip the whole pass for streak accounting on a FAILED lens; still disposition returned findings. Agree; folded.
3. Q3 — both lenses: carry across chunks on mechanism continuity, not log sharing; persist explicit retirement, distinct from a reset. Agree with a sharpening; folded.
4. Q4 — both lenses: identity is the mechanism/invariant, not the D-number or section. Agree with a correction; folded.
5. Q5 — both lenses: no second trigger for MVP. Agree.

### New questions Codex raised
- (none)

### Lens run summary
- architect: REVISE · product-manager: REVISE

## Codex review pass 2 — answers (2026-09-28) [HISTORICAL]

### Verdict
REVISE (worst-of: architect REVISE, product-manager REVISE; no FAILED lens). Merged HIGH+MEDIUM count: 3 (down from 5 — strictly decreasing).

### Findings
1. **Narrowing still has contradictory label lifecycles** — HIGH · lens: architect, product-manager (co-reported, same defect): pass 1 fixed §1/§2 but §3's outcome mapping still said "the label retires" after any simplify, which would deny a narrowed mechanism its promised fresh streak.
   → Editor: incorporated — §3's mapping now defers to §1/§2's three lifecycles and records which operation was applied (`simplify (remove|narrow|replace)`); the schema's `chosen` enum maps the three operations distinctly so replay can tell them apart. The defect pre-existed pass 1 (the original §3 text) and pass 1's claims-vs-behavior sweep missed it; recorded as pre-existing with that note. [introduced_by_pass: null]
2. **Batch incorporation assumes simplification resolves every finding** — HIGH · lens: architect: pass 1's transition step (5) marked every same-label finding incorporated after a simplify outcome, contradicting R2 and the existing rule that `incorporated` means actually resolved.
   → Editor: incorporated — the card gains a required per-finding accounting line; step (5) dispositions each finding by that accounting, never as a batch; unresolved findings keep their ordinary path including accepted-risk's own exclusions. [introduced_by_pass: 1]
3. **Risk acceptance retires more than the accepted-risk lifecycle owns** — MEDIUM · lens: architect: pass 1's §2 bullet retired the whole label on *accept the risk*, though `AR-<n>` is finding-specific and can be rejected or invalidated, leaving a retained mechanism untracked.
   → Editor: incorporated — accept-the-risk now retains the label at streak 0; out-of-scope findings and rejected/invalidated ARs count as observations; only split-the-plan retires (explicit, persisted). Fixtures extended for both transitions. [introduced_by_pass: 1]

### Plan corrections applied
- §5 card outcome mix: made descriptive; the threshold decision belongs only to the `premature` rule, so a run of deliberate continuations no longer reads as a false-positive signal (product-manager).

### Open-question answers
1. Q1 — both lenses: before the first qualifying fold on the third counted pass; the candidate/committed distinction supports it. Equivalent to pass 1 (streak 2).
2. Q2 — both lenses: skip the FAILED pass for observations, still disposition findings; architect adds that lifecycle changes made in that pass (a removal) still persist. Equivalent to pass 1 (streak 2); the addition is already what §1's persisted-retirement rule says.
3. Q3 — both lenses: carry on mechanism continuity; retirement vs reset are different events. Equivalent (streak 2).
4. Q4 — both lenses: mechanism/invariant is identity; numbers and sections locate, never define. Equivalent (streak 2).
5. Q5 — both lenses: one trigger for MVP. Equivalent (streak 2).

### New questions Codex raised
- (none)

### Lens run summary
- architect: REVISE · product-manager: REVISE

## Codex review pass 3 — answers (2026-09-28) [HISTORICAL]

### Verdict
REVISE (worst-of: architect REVISE, product-manager REVISE; no FAILED lens). Merged HIGH+MEDIUM count: 3 (from 3 — one non-decreasing transition; the stall guardrail needs two consecutive, so it has not fired).

### Findings
1. **The threshold source is absent from supported copied installs** — HIGH · lens: architect: pass 1's fold made `tools/cluster_tracker.py` the single source of N, but each skill directory is independently installable by copy and a copied install has no `tools/`.
   → Editor: incorporated — inverted: the literal number lives in each SKILL.md (the deployed source); the constant is the development-side pin, and `check-cluster-streak.py` asserts both files' literals equal it and each other. §2, Phase 0 deliverables and §5 updated to say "three-place edit kept consistent by the checker." [introduced_by_pass: 1]
2. **Checkpoint risk events bypass the pre-fold streak transition** — HIGH · lens: architect: pass 2's fold made an AR rejection or invalidation an observation, but §3's transition computes candidates from merged findings only, so a label at 2 on a quiet pass with a rejected AR had no path to a card.
   → Editor: incorporated (via alternative — simplified rather than extended): checkpoint events are never observations; merged HIGH/MEDIUM findings at fold time are the one source and §3 the one path; a rejected or invalidated AR changes ledger state exactly as today, and the finding's next re-report is the observation. Cost stated: at most one pass of delay on a quiet pass. Fixture updated to pin the negative case. [introduced_by_pass: 2]
3. **The card does not guarantee the required removal option** — HIGH · lens: product-manager: §3 allowed a narrow/replace recommendation whose alternatives never included removal, contradicting the carried issue #6 constraint.
   → Editor: incorporated — *remove* and *fold once more* are mandatory on every card (remove as recommendation or first alternative); a priority order governs the remaining slots under the four-option cap; context-sensitive omission can drop optional options only. [introduced_by_pass: null]

### Plan corrections applied
- Rollback plan: skill rollback and analytics-reader compatibility separated; the schema-tolerant `provenance-recipe.jq` reader is kept even when reverting skill prose, else schema-2 runs silently vanish from tallies (architect).

### Open-question answers
1. Q1 — both lenses: before the first affected fold on the third qualifying pass; the architect added "the checkpoint lifecycle-event path needs equivalent protection." Treated as not equivalent (new condition); streak 1. The condition is moot after finding 2's fold.
2. Q2 — both lenses: skip the FAILED pass for observations, disposition findings, persist lifecycle changes. Equivalent ×3 → **FROZEN at pass 3**.
3. Q3 — both lenses: carry on mechanism continuity; retirement ends identity, absence resets. Equivalent ×3 → **FROZEN at pass 3**.
4. Q4 — both lenses: mechanism/invariant is identity. Equivalent ×3 → **FROZEN at pass 3**.
5. Q5 — both lenses: one trigger for MVP. Equivalent ×3 → **FROZEN at pass 3**.

### New questions Codex raised
- (none)

### Lens run summary
- architect: REVISE · product-manager: REVISE

## Codex review pass 4 — answers (2026-09-28) [HISTORICAL]

### Verdict
REVISE (worst-of: architect REVISE, product-manager APPROVE; no FAILED lens). Merged HIGH+MEDIUM count: 2 (from 3 — strictly decreasing; the stall window is cleared).

### Findings
1. **Disposition accounting covers only the recommended simplification** — HIGH · lens: architect: pass 2 attached the guarantee/covering-layer/per-finding accounting to the recommendation only, so choosing an alternative operation would disposition findings against the wrong accounting.
   → Editor: incorporated — every offered simplification operation carries its own three sub-fields; the resolution names the chosen operation and step (5) applies that operation's persisted accounting, including on resume. [introduced_by_pass: 2]
2. **State rows cannot identify the next qualifying completed pass** — MEDIUM · lens: architect: `cluster_hits` joined to "the next completed pass" but rows carried no lens-status distinction, so a FAILED-lens pass and a quiet pass were indistinguishable.
   → Editor: incorporated — schema 2 rows gain `observation: true|false` derived from the Lens run summary; the join targets the next row with `observation: true`; schema-1 rows report `next: unknown`. [introduced_by_pass: 1]

### Plan corrections applied
- Acceptance criteria and Phase 0 parity rule still carried the pass-1 "one runtime source" contract; reworded to the pass-3 contract (literal in each installed skill, checker-enforced consistency) (product-manager).

### Open-question answers
1. Q1 — both lenses: before the first affected fold on the third qualifying pass; the architect explicitly withdraws the checkpoint-path condition. Equivalent to pass 3's resolution; streak 2. (Q2–Q5 frozen; neither lens re-answered them, as `reviewer-prompt.md` instructs.)

### New questions Codex raised
- (none)

### Lens run summary
- architect: REVISE · product-manager: APPROVE

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
