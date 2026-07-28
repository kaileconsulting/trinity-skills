# Trinity Axis 1 — Cross-Vendor Tiebreaker — Plan

> **STATUS: STUB DRAFT (2026-07-27).** Scaffolded + first-draft authored by Opus from the expansion brief + the `gemini-access` memory, *before* running its own `iterate-plan` cycle. Sequenced **after Axis 2** (which is built + live-validated). Not yet design-reviewed — expect gaps. Do not execute until it converges through `iterate-plan`.

## TL;DR

Axis 1 adds cross-vendor **depth** to the trinity: a **disagreement-triggered Gemini tiebreaker**. When Opus and Codex split on whether a finding is real — i.e., Codex files a HIGH/MEDIUM finding that Opus wants to **dispute** rather than incorporate — Gemini is invoked as a decorrelated third vote that **informs the human checkpoint but never outvotes it**. Gemini is the right third model precisely because it's a different vendor / training regime, so its blind spots don't correlate with Claude's (a third Claude would share Claude's).

It is deliberately **not an always-on third reviewer**: firing only on disagreement spends the extra model where it has signal, sidesteps three-way reconciliation every pass, and keeps the human as final arbiter. It reuses Axis 2's fan-out/merge scaffold (Gemini slots in as a conditional extra reviewer on the same between-pass machinery). Groundwork — paid-tier Gemini access + a validated headless call recipe — is already done (see the `gemini-access` memory).

## Why / Context

Axis 2 (personas) buys **breadth** — more issue *categories* asked about — but every lens shares one model's blind spots on *detection reliability within* a category. Decorrelating detection reliability is a different mechanism: **model diversity across vendors**. That's Axis 1.

The naive version — a third reviewer on every pass — triples cost and forces a three-way reconciliation each round. The disagreement-triggered design avoids both: Gemini is spent only where Opus and Codex already disagree, which is rare and high-signal. This is the "depth" half of the two-axis expansion brief (`/home/kyle/trinity-review-expansion-brief.md`); Axis 2 (breadth) is the other half and shipped first.

## Who / Use cases

- **Reviewer files a HIGH finding Opus believes is wrong** (Codex misread intent or a constraint not visible in the diff/plan). Instead of Opus unilaterally disputing, Gemini breaks the tie so the human sees a decorrelated third opinion at the checkpoint. Success: fewer plausible-but-wrong findings folded, and fewer real findings waved off.
- **Reduces both error directions:** false positives (Codex wrong → Gemini backs Opus's dispute) *and* false negatives (Opus about to dismiss a real issue → Gemini sides with Codex, flagging it for the human).

## Goals (MVP)

- A **schema-enforced Gemini tiebreaker vote** via the validated headless recipe (read-only, JSON output).
- A **deterministic disagreement trigger**: the fold path where Opus would mark a HIGH (v1) finding `disputed`.
- The tiebreaker result **surfaced at the human checkpoint** — informs, never auto-resolves.
- Reuse of the Axis 2 between-pass scaffold; no new checkpoint proliferation.
- Works in both `iterate-plan` and `iterate-review`.

## Non-goals (MVP)

- **Always-on third reviewer** — rejected by design; trigger-only.
- **Gemini editing anything** — it's a read-only API vote; Opus remains sole editor.
- **Auto-resolving disputes on Gemini's vote** — the human always decides; Gemini only informs.
- **Other vendors** beyond Gemini.
- **MEDIUM/LOW disputes** as triggers in v1 (see Q1) — keep the trigger rare.

## Approach

### Trigger — the Opus⇄Codex split
The tie is the fold step where Opus would disposition a **HIGH** finding as `disputed` (not `incorporated`). That disagreement is the tiebreaker trigger. It composes with Axis 2's loop-mode "fold needs human judgment" guardrail — an un-incorporated HIGH already halts loop mode; Axis 1 additionally spawns a Gemini vote before the human sees the checkpoint.

### The Gemini vote
Invoke Gemini via the validated headless recipe (`gemini-access` memory):
```
env -u GOOGLE_API_KEY GEMINI_API_KEY="$(from keyfile)" \
  gemini -m <model> --skip-trust --approval-mode plan -o json -p '<vote prompt>'
```
Read-only is automatic (the API has no filesystem access). Input to the vote: the **disputed finding** + the **relevant plan/diff slice** + **Opus's dispute reasoning**. Output: a small schema — `{ agrees_with_finding: bool, confidence: low|med|high, reasoning: string }`. The vote is refusal-framed like Codex ("try to determine whether the finding is real").

### Surfacing (informs, never decides)
The tiebreaker vote is presented at the existing human checkpoint next to Opus's disposition and Codex's finding — three views for the human to arbitrate. No verdict is auto-changed. The "skill never decides convergence / human always confirms" invariant is untouched.

### Reuse of the Axis 2 scaffold
Gemini is a **conditional extra reviewer** slotted into the same between-pass machinery Axis 2 built. It does not participate in the per-pass lens fan-out (that's Codex lenses); it runs only on a triggered dispute.

### Data governance
Paid-tier Gemini (no training on submitted content) is the floor (see `gemini-access`). Only the disputed finding + a minimal slice leaves the infrastructure — not the whole repo. For CancerLogix-sensitive code this still warrants a conscious data-handling sign-off; Vertex AI is the escalation path if stricter controls (residency, VPC-SC) are required.

## Phasing

### Phase 0 — Gemini tiebreaker vote wrapper (~0.5 day)
**Deliverables:**
- The vote output schema (`agrees_with_finding` / `confidence` / `reasoning`).
- A tiebreaker prompt (refute-framed) + the headless invocation wrapper, with retry + graceful "tiebreaker unavailable" fallback.

**Acceptance:**
- Given a finding + slice + dispute reasoning, returns a schema-valid vote; on Gemini failure, degrades to "unavailable" without blocking the pass.

**Iterate-review:** YES (rationale: external-vendor integration + a new prompt/schema contract — load-bearing)
**Status:** not started

### Phase 1 — Disagreement trigger + checkpoint surfacing (~1 day)
**Deliverables:**
- Deterministic trigger on an un-incorporated HIGH finding, in both skills' fold path.
- Compose the vote input (finding + slice + Opus reasoning); surface the vote at the human checkpoint alongside Codex's finding + Opus's disposition.

**Acceptance:**
- A disputed HIGH spawns exactly one Gemini vote; the vote is displayed, never auto-applied; no extra checkpoints introduced.

**Iterate-review:** YES (rationale: touches the fold/checkpoint machinery + the human-arbitration invariant)
**Status:** not started

### Phase 2 — Fixtures + live validation (~0.5 day)
**Deliverables:**
- Fixtures for the trigger (disputed-HIGH → vote; incorporated-HIGH → no vote) and the surface-not-decide behavior.
- A live end-to-end test: a real disputed finding → Gemini vote → checkpoint.

**Acceptance:**
- Trigger fires only on disputed HIGH; vote informs but never changes a verdict; live test produces a coherent third opinion.

**Iterate-review:** YES (rationale: the E2E-analog; validates the trigger + no-auto-decide invariant)
**Status:** not started

## Acceptance criteria

- [ ] A disputed HIGH finding (in either skill) triggers exactly one schema-valid Gemini vote.
- [ ] The vote is surfaced at the human checkpoint and **never** auto-resolves the dispute or changes a verdict.
- [ ] Gemini unavailability degrades gracefully to "tiebreaker unavailable" without blocking the pass.
- [ ] Only the disputed finding + a minimal slice is sent to Gemini (data-minimization).
- [ ] Reuses the Axis 2 between-pass scaffold; no new human checkpoints per pass.

## Risks

### R1 — Tiebreaker drifts from "informs" to "decides"
Convenience pressure to auto-resolve disputes on Gemini's vote would break the human-arbitration invariant.
**Mitigation:** structurally surface-only; the vote is display data at the existing checkpoint; no code path changes a verdict based on it.

### R2 — Sensitive code leaves the infrastructure
The disputed finding + slice is sent to a third-party API.
**Mitigation:** paid tier (no training); minimal-slice only; conscious data-handling sign-off; Vertex escalation path for stricter compliance.

### R3 — Cost / latency on frequent disagreements
**Mitigation:** trigger only on disputed HIGH (rare by construction); one vote per disputed finding; a per-pass cap.

### R4 — Gemini unavailability (503 / quota)
**Mitigation:** paid-tier reliability; on failure, surface "unavailable" and fall back to the human decision — never block the loop.

## Sequencing decision

After Axis 2 (built + live-validated 2026-07-27). Axis 1 depends on the Axis 2 fan-out/merge scaffold and slots onto it as a conditional extra reviewer. Building it second was the deliberate call in the brief (breadth first — no new vendor; depth second).

## Open questions

- **Q1.** Trigger on HIGH disputes only (v1), or also MEDIUM? HIGH keeps it rare and clearly load-bearing; MEDIUM disputes are more frequent and could add cost/noise.
- **Q2.** Which Gemini model — `gemini-2.5-pro` vs `gemini-3-pro-preview` — trading cost against capability for the vote?
- **Q3.** Record the tiebreaker vote in the HISTORICAL block (attribution-style) for later calibration analysis (how often Gemini sides with Opus vs Codex)?
- **Q4.** Exactly what context is sent — a minimal finding+slice (data-minimization) vs the full plan/diff (more context for a better vote)? Where's the line?
- **Q5.** Does a dispute Opus makes on a **lens-attributed** finding (Axis 2) change anything — e.g., is a security-lens HIGH weighted differently for tiebreaking?

## Out of scope

- Always-on / every-pass third reviewer — trigger-only by design.
- Gemini as an editor — read-only vote only.
- Vendors beyond Gemini.
- Auto-resolution of disputes.

## Closeout

- [ ] Append entry to milestones / changelog index: what shipped, ship commit, key delta, link to archived plan.
- [ ] Update memory: mark Axis 1 completed, link ship commits, update `trinity-expansion` + `gemini-access`.
- [ ] Update any backlog / priority queue.
- [ ] Move plan to archive: `git mv docs/<plan>.md docs/archive/<plan>.md`.
- [ ] Final commit referencing this plan.

## References

- Expansion brief: `/home/kyle/trinity-review-expansion-brief.md`
- Gemini access (key location, validated headless recipe, paid-tier state): memory `gemini-access`
- Axis 2 (the scaffold this reuses): `docs/archive/trinity-axis-2-persona-lenses-2026-07-27.md`
  — **shipped 2026-07-28.** The fan-out + merge stage this plan's conditional
  extra-reviewer step slots onto now exists, along with worst-of aggregation,
  `FAILED`-lens handling, and the single-checkpoint invariant. Read that plan's
  Approach → Merge section before drafting the tiebreaker's verdict handling.
- Overall expansion state: memory `trinity-expansion`

## Review checkpoints

<!-- TOOLING-MAINTAINED by iterate-review for multi-phase plans.

| Phase | Iterate-review | Status | Last pass | Pass log |
|-------|----------------|--------|-----------|----------|
| Phase 0 | YES | not started | — | — |
| Phase 1 | YES | not started | — | — |
| Phase 2 | YES | not started | — | — |
-->

## Pre-flight review pass (Opus, YYYY-MM-DD) [HISTORICAL]

<!-- OPTIONAL self-review by Opus before execution. Delete if skipped. -->

## Codex review pass N — answers (YYYY-MM-DD) [HISTORICAL]

<!-- TOOLING-MAINTAINED by iterate-plan. Each pass appends a new
"## Codex review pass N — answers (DATE) [HISTORICAL]" section. -->
