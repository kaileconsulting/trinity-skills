# Code Review — branch-kyle-simplification-gate

## Pass 1 — 2026-09-29 ≈07:04 [HISTORICAL]

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

Diff captured at 2026-09-29 ≈07:03; head SHA `6e76679`. (Timestamps for passes 1–2 corrected from commit times: their summaries were pruned at Converge, and the originally written times were not taken from the summary mtime.)

## Pass 2 — 2026-09-29 ≈07:08 [HISTORICAL]

**Scope:** branch · **Diff size:** 2536 lines · **Scope class:** production · **Verdict:** APPROVE (worst-of: senior-dev APPROVE, security APPROVE, qa APPROVE; no FAILED lens) · **Posture:** used docs/simplification-gate-2026-09-28.md · **Lenses:** senior-dev, security, qa

### Findings

- (none)

### Code corrections applied

- `iterate-review/SKILL.md` schema-2 `components` prose (senior-dev, qa; merged) — calls `worst_severity`, `findings` and `fold_caused` all counts, but `worst_severity` is a HIGH/MEDIUM/LOW label → reworded so only `findings`/`fold_caused` are counts and `worst_severity` is the severity label; the same wording in `iterate-plan/SKILL.md`'s schema-2 bullet fixed identically (sibling copy, same defect)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: APPROVE · security: APPROVE · qa: APPROVE

### Diff snapshot reference

Diff captured at 2026-09-29 ≈07:07; head SHA `65a8367`.

### Checkpoint

APPROVE reached (loop mode stops). No `AR-` items, no `register-match`, no FAILED lens, no pending folds; the one correction is a three-line wording fix, suite green at `9083cdf`. HIGH+MEDIUM trajectory 1 → 0. Component streaks: `cluster-tracker-lifecycle-events` 1 → 0 (no label near the cluster threshold). **Converged by Kyle 2026-09-29** (Phase 0 of `docs/simplification-gate-2026-09-28.md`).

## Pass 3 — 2026-09-29 09:09 [HISTORICAL]

**Scope:** branch (Phase 1 focus; Phase 0 converged at pass 2) · **Diff size:** 3692 lines · **Scope class:** production · **Verdict:** REVISE (worst-of: senior-dev REVISE, security APPROVE, qa REVISE; no FAILED lens) · **Posture:** used docs/simplification-gate-2026-09-28.md · **Lenses:** senior-dev, security, qa

### Findings

1. **Split-the-plan has no disposition that lets the original loop resume** — HIGH · lens: senior-dev (HIGH), qa (MEDIUM; merged, same defect): `iterate-plan/SKILL.md`'s split outcome moves the mechanism to a stub and says findings take their ordinary path there, but defines no disposition in the originating pass — an empty slot trips the resume rule, `skipped` trips the HIGH guardrail, and `incorporated` by association is forbidden; the fixture exercises only remove.
   → Editor: incorporated (via the design-shaped-fold card below, Kyle: scope transfer) — split is now four ordered, durable writes: stub with a verbatim `## Carried findings` section → this plan drops the mechanism, references the stub, gains an Out-of-scope entry → resolution, then each finding `incorporated (moved to <stub path>)` → `retired:`; resume completes from the first missing write without copying twice. The new disposition joins `incorporated (by simplification)` in the accounting sentence (incorporated for every ledger). Fixture 02 gains a split variant (writes, dispositions, both interruption points); parity rule `card-escape-hatch` pins it. [introduced_by_pass: null] [component: split-plan-outcome]
2. **Plan setup does not route an interrupted simplification card to resume** — HIGH · lens: qa: the card promises resume under its `(pass, component)` identity, but iterate-plan Setup step 4 only loads the exit-time state file; interrupted at a pending card, a new invocation starts a fresh pass and fan-out, bypassing the pending card and its unfolded findings.
   → Editor: incorporated (via the design-shaped-fold card below, Kyle: resume check, all cards) — Setup step 4 now checks the plan's last pass block before any fan-out: a pending card, an empty `→ Editor:` slot or a `(pending)` correction/question means that pass is unfinished, and it is resumed under its own number (reconcile before re-applying) instead of starting N+1. Covers all six card types; the "Light-shape; can harden later" note is gone. Per-skill parity rule `resume-unfinished-pass` pins each skill's entry path. Pre-existing gap for the older card types, made load-bearing by this card. [introduced_by_pass: null] [component: plan-resume-entry]
3. **Plan fixture's checkpoint asserts a stall and a live streak its inputs don't support** — MEDIUM · lens: qa (MEDIUM), senior-dev (two corrections, same defect; merged): `02-simplification-card` shows HIGH+MEDIUM 4 → 5 → 5 but carries four pass-6 findings (4 → 5 → 4 would not stall), and reports the retired classifier with a committed streak of 3.
   → Editor: incorporated — the real pass-6 finding 5 (mutation-proof gate, MEDIUM, product-manager) was dropped when condensing; restored in the response and table, so pass 6 carries 5 HIGH/MEDIUM and 4 → 5 → 5 is true. The cluster section lists the classifier as retired and shows 3 only as the card's streak at fire; both SKILL.md cluster sections now say so (retired labels listed as retired; the card line carries `<n>` = streak at fire; the "no live component" line). [introduced_by_pass: null] [component: plan-fixture-02]

### Code corrections applied

- `iterate-plan/SKILL.md` card transition step 1 (all three lenses) — says "step 11's merge", copied from iterate-review; iterate-plan merges in step 7 → now "Step 7's merge"
- `iterate-plan/SKILL.md` card worked-example pointer (qa) — says removal resolves "two of the three" findings; the fixture's accounting resolves three of four → now "three of the streak's four … plus the same card answered split the plan"
- `iterate-plan/SKILL.md` plan-shaping card (qa) — still says it shares its contract with "the other four" card types → "the other five"
- both simplification-card `expected-merge.md` pending examples (qa) — persisted card omits the `discuss` path the textual log must record → a `discuss — always available …` line added to both

### New questions Codex raised

- (none)

### Decision cards

- **design-shaped-fold escalation** (finding 1 — split-the-plan disposition): recommendation — define split as a *scope transfer*: before the resolution write, the stub is created and every same-label finding of this pass is copied verbatim into its `## Carried findings`; each is then dispositioned here `incorporated (moved to <stub>)`, an `incorporated` for every ledger, since the plan edit removing the mechanism's decisions *is* this plan's fold; resume completes any finding whose text is already in the stub; alternatives — drop split-the-plan from the card (contradicts issue #6's carried constraint); require ordinary folds of this pass's same-label findings before the split (split = fold once more + move); discuss (Kyle asked how the ResearchLogix evidence handled it: no loop ever split a plan, but every split-*off* — CSRF code pass 3 "→ own card", impersonation-c1b pass 7 "card C1c", CSRF plan's Eloquent gap in Out of scope — recorded the finding `incorporated` with the remainder named at a durable new home; recommendation re-presented with an Out-of-scope pointer added); chosen: scope transfer (Kyle, 2026-09-29) — stub + `## Carried findings` written before the resolution, Out-of-scope pointer here, findings `incorporated (moved to <stub>)`.
- **design-shaped-fold escalation** (finding 2 — plan-side resume entry): recommendation — Setup step 4 gains a resume check: before any fan-out, read the plan's last HISTORICAL block; a `chosen: (pending)` card or an empty `→ Editor:` / `(pending)` slot means that pass is unfinished, so re-present / complete it under its own pass number instead of starting a new one (covers every card type, which already promise this); alternatives — scope the check to simplification cards only; accept the gap as pre-existing and file it separately (not available: a bypassed pending card suppresses findings without a human decision, the PF-shipbar trust boundary); chosen: resume check, all cards (Kyle, 2026-09-29).

### Lens run summary

- senior-dev: REVISE · security: APPROVE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-09-29 09:08; head SHA `bbcde58`.

### Checkpoint

Both HIGHs incorporated via Kyle's cards; suite green. HIGH+MEDIUM trajectory 1 → 0 → 3 (a new phase's first pass; one non-decreasing transition, the stall needs two). Component streaks: `split-plan-outcome` 1, `plan-resume-entry` 1, `plan-fixture-02` 1 — none at one below the cluster threshold. Loop mode → **Continue** to pass 4 (auto-continued passes used: 1 of 6 in this activation).

## Pass 4 — 2026-09-29 10:12 [HISTORICAL]

**Scope:** branch (Phase 1 focus) · **Diff size:** 3851 lines · **Scope class:** production · **Verdict:** REVISE (worst-of: senior-dev REVISE, security REVISE, qa REVISE — all via retry; no FAILED lens) · **Posture:** used docs/simplification-gate-2026-09-28.md · **Lenses:** senior-dev, security, qa

### Findings

1. **Split mutates both plans before durably recording the human's choice** — HIGH · lens: senior-dev, security, qa (co-reported): the pass-3 scope transfer writes the stub and edits the original plan before the resolution write, so an interruption after write 2 leaves a removed mechanism under a card still reading `(pending)`; resume re-presents it as unanswered, and a different answer leaves a removal nobody authorized — contradicting the shared resolution-on-answer contract.
   → Editor: incorporated — the transfer is now five writes with the **resolution first**, naming the destination (`chosen: split the plan (→ <stub path>)`), then stub + carried findings, plan edit + Out-of-scope entry, dispositions (only once a finding's text is in the stub), `retired:`. A resolved split card is never re-presented; resume continues the recorded transfer from the first missing write, copying nothing twice. Fixture 02's variant now walks all four interruption points in a table. Not design-shaped: a reordering inside the approved transfer that restores the shared contract. [introduced_by_pass: 3 — the pass-3 fold put the resolution third] [component: split-plan-outcome]
2. **Plan resume detection misses unfinished work after the last disposition** — HIGH · lens: senior-dev, qa (co-reported): the pass-3 Setup check recognizes an unfinished pass only by pending cards or slots, so an interruption after every disposition is filled but before the `retired:` line, or before a required stall/cap card is written, leaves no signal; a fresh fan-out then skips the checkpoint, and a later decreasing count can erase the stall.
   → Editor: incorporated (via the design-shaped-fold card below, Kyle: port the block tag) — iterate-plan pass blocks open `[IN PROGRESS]` right after the merge and flip to `[HISTORICAL]` as the pass's last write (after dispositions, `retired:` lines and the checkpoint's answered cards); the pre-fan-out register-card block opens the same way; the block template carries the rule. Setup step 4's predicate is now the tag: an `[IN PROGRESS]` last block is resumed under its own number, including finishing a resolved card's writes and running a checkpoint whose card was never written. Per-skill parity rule `block-tag-completion-marker` pins each skill's wording; `resume-unfinished-pass` tightened. Prose-only: no runner parses plan-block tags. [introduced_by_pass: 3 — the pass-3 fold made slots the only signal] [component: plan-resume-entry]

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Decision cards

- **design-shaped-fold escalation** (finding 2 — a durable pass-completion marker in plan files): recommendation — port `iterate-review`'s block tag: a plan pass block opens `[IN PROGRESS]` right after the merge and flips to `[HISTORICAL]` as its last write, after retirements and the checkpoint's cards; Setup's predicate becomes "the last pass block is `[IN PROGRESS]`" (prose-only — no runner parses plan tags); alternatives — a closing `### Checkpoint` line written last, whose absence means unfinished; keep slot-based detection and add retirement + stall checks to it one by one; chosen: port the block tag (Kyle, 2026-09-29) — `[IN PROGRESS]` from merge to the pass's last write, Setup resumes any `[IN PROGRESS]` block.

### Lens run summary

- senior-dev: failed → **retry REVISE** · security: failed → **retry REVISE** · qa: failed → **retry REVISE**. First attempts hit the Codex usage limit ("try again at 12:03 PM"); each lens's one `run-lens` retry ran after the reset (debug responses `debug/20260929T162050787709Z-82601-f073ec76-senior-dev`, `…787708Z-82603-82ca2fc1-security`, `…787707Z-82605-244ab6ab-qa`).

### Diff snapshot reference

Diff captured at 2026-09-29 10:12; head SHA `79852d8`.

### Checkpoint

Both HIGHs incorporated (one via Kyle's card); suite green. HIGH+MEDIUM trajectory 1 → 0 → 3 → 2 (strictly decreasing from pass 3). Component streaks: `split-plan-outcome` **2**, `plan-resume-entry` **2** — both at one below the cluster threshold, 2: one more HIGH/MEDIUM pass on either triggers the simplification card (this review is now exercising the gate it adds); `plan-fixture-02` 0. Loop mode → **Continue** to pass 5 (auto-continued passes used: 2 of 6).

## Pass 5 — 2026-09-30 06:33 [HISTORICAL]

**Scope:** branch (Phase 1 focus; excluded by hand, pending issue #10: governing plan `docs/simplification-gate-2026-09-28.md` + its `.handoff-prompt.md`, and this pass log — 672 lines, all non-production) · **Diff size:** 3277 lines (3949 before exclusions) · **Scope class:** production · **Verdict:** REVISE (worst-of: senior-dev REVISE, qa REVISE; no FAILED lens) · **Posture:** used docs/simplification-gate-2026-09-28.md · **Lenses:** senior-dev, qa (forced; security deselected for cost — selected only on prose keywords, approved every prior pass with no findings of its own)

### Findings

1. **Plan resume relies on pending items that block creation does not persist** — HIGH · lens: senior-dev (HIGH), qa (MEDIUM; merged, same defect): iterate-plan's block opens with only the merged *findings* pre-populated; corrections and question answers appear only in completed form, yet Setup resumes them by `(pending)` slots — interrupted after the block opens, a resume finishes the findings, runs the checkpoint and seals while silently dropping outstanding corrections or answers. The `[IN PROGRESS]` tag detects the interruption but does not preserve the remaining work list.
   → Editor: incorporated (by simplification) — replace's accounting resolves this finding: iterate-plan no longer resumes an interrupted pass, so nothing has to be persisted as pending for a resume to find. One implementation fold, no per-finding patch: Setup step 4 now retags an `[IN PROGRESS]` last block `[ABORTED]` and reruns; an aborted pass is skipped for streak and stall accounting like a FAILED-lens pass, contributes no state row, and its dispositions, AR proposals and card answers are void; every resume claim in iterate-plan (Setup, the pre-fan-out register card, the shared persistence contract, the fold-step tag rule, the block template, card identity, the split transfer) rewritten to match; the component-streak rules name the aborted skip. Fixture 02's interruption table now shows the rerun at each point; parity rules `interrupted-pass-handling` (deliberately asymmetric with iterate-review, which keeps resume) and `card-identity` replace the resume rules; CHANGELOG records the card. [introduced_by_pass: 4 — the pass-4 tag fold made slot-based resume the recovery path] [component: plan-resume-entry]

### Code corrections applied

- `iterate-review/examples/merge/05-simplification-card/expected-merge.md` transition step 6 (senior-dev, qa; merged) — seals the pass before the accepted-risk checkpoint card it then describes; the block stays `[IN PROGRESS]` through checkpoint cards → step 6 is now "Checkpoint, then seal": the block stays `[IN PROGRESS]` through `AR-1`'s confirmation card and seals after its outcome is recorded

### New questions Codex raised

- (none)

### Decision cards

- **simplification** (`plan-resume-entry`, pass 5, streak 3): streak findings — pass 3 #2 HIGH (qa, introduced_by_pass: null); pass 4 #2 HIGH (senior-dev, qa, introduced_by_pass: 3); pass 5 #1 HIGH (senior-dev, qa, introduced_by_pass: 4); 2 of this streak's 3 findings are fold-caused.
  recommendation — **simplify (replace)**: replace plan-side *resume* with **abandon-and-rerun**. Setup still detects an `[IN PROGRESS]` last block, but instead of completing it, tags it `[ABORTED]` ("interrupted; superseded by pass N+1") and starts pass N+1; an aborted pass is skipped for streak and stall accounting, like a FAILED pass, and its dispositions, `AR-<n>` proposals and card answers are void. Guarantee lost: the interrupted pass's recorded work (a human answer given before the crash is asked again; one extra Codex pass per interruption). Covering layer: the plan is the reviewed artifact, so the fresh pass reviews whatever the interrupted folds left in it; a card that was pending re-fires if the fresh pass re-reports its label (committed streak unchanged, aborted pass skipped). Per-finding: pass 3 #2 — resolves (no fresh pass can bypass a pending card silently: the card is voided with its pass and re-fires from re-reported findings); pass 4 #2 — resolves (the tag still detects; nothing needs completing); pass 5 #1 — resolves (nothing is resumed, so nothing needs persisting).
  alternatives — **simplify (remove)**: drop the plan-side resume promise and the tag, back to pre-Phase-1 Setup. Guarantee lost: interruption recovery. Covering layer: none. Per-finding: pass 3 #2 — does not (a fresh pass can again bypass a pending card); pass 4 #2 — resolves (no completeness claim left); pass 5 #1 — resolves (no claim left). · **fold once more**: port `iterate-review` step 12's rule that corrections and questions are pre-populated `(pending)` when the block opens. · *(accept the risk omitted: a bypassed pending card suppresses findings without a human decision — a PF-shipbar trust boundary)*
  discuss — always available (the harness's free-form response; never counted against the four options).
  chosen: simplify (replace) (Kyle, 2026-09-30) — plan-side resume replaced by abandon-and-rerun; replace's per-finding accounting applies (all three resolve).

retired: plan-resume-entry (replaced by plan-abandon-rerun, simplification card pass 5)

### Lens run summary

- senior-dev: failed → **retry REVISE** · qa: failed → **retry REVISE** · security: failed, retry not run (deselected for cost). First attempts hit the Codex usage limit ("try again at 5:20 PM"); retries ran 2026-09-30 06:33 against the slimmed diff (debug responses `debug/20260930T103338331521Z-18235-8574f134-senior-dev`, `…331520Z-18237-508cf996-qa`). The two slimmed lenses cost 24% of a fresh 5-hour window.

### Diff snapshot reference

Diff captured at 2026-09-30 06:33 (slimmed, at head `8952a56`, the head the pass was opened against).

### Checkpoint

The simplification card fired on this review's own mechanism, `plan-resume-entry`, at streak 3 (passes 3, 4, 5; 2 of 3 fold-caused); Kyle chose **simplify (replace)**, and the resume procedure was removed rather than patched a fourth time. Suite green. HIGH+MEDIUM trajectory 1 → 0 → 3 → 2 → 1 (strictly decreasing). Streaks: `plan-resume-entry` retired (replaced by `plan-abandon-rerun`, fresh at 0); `split-plan-outcome` 0; `plan-fixture-02` 0. Loop mode → **Continue** to pass 6 (auto-continued passes used: 3 of 6), which reviews the simplified head.
