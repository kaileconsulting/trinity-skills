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

## Pass 4 — 2026-09-29 10:12 [IN PROGRESS]

**Scope:** branch (Phase 1 focus) · **Diff size:** 3851 lines · **Scope class:** production · **Verdict:** (pending) until the lens retries complete · **Posture:** used docs/simplification-gate-2026-09-28.md · **Lenses:** senior-dev, security, qa

### Findings

- (pending — no lens has returned)

### Lens run summary

- senior-dev: failed (exit 1, empty stderr) · security: failed (exit 1, empty stderr) · qa: failed (exit 1, empty stderr). Direct probe: "You've hit your usage limit … try again at 12:03 PM." Each lens's one `run-lens` retry is **owed, not spent** — deferred until the limit resets, since a retry now would fail identically. Resume: retry the three lenses against this pass's diff (head `79852d8`), then merge into this block.

### Diff snapshot reference

Diff captured at 2026-09-29 10:12; head SHA `79852d8`.
