# Trinity Axis 1 — Cross-Vendor Tiebreaker — Plan

> **STATUS: IN REVIEW (pass 1 folded 2026-07-28).** Scaffolded + first-draft authored by Opus from the expansion brief + the `gemini-access` memory. Sequenced **after Axis 2** (shipped 2026-07-28). One `iterate-plan` pass folded — verdict REVISE, 8 merged findings. **Do not execute until it converges.**

## TL;DR

Axis 1 adds cross-vendor **depth** to the trinity: a **disagreement-triggered Gemini tiebreaker**. When Opus and Codex split on whether a finding is real — i.e., Codex files a **HIGH** finding that Opus dispositions as **`disputed`** rather than incorporating — Gemini is invoked as a decorrelated third vote that **informs the human checkpoint but never outvotes it**. Gemini is the right third model precisely because it's a different vendor / training regime, so its blind spots don't correlate with Claude's (a third Claude would share Claude's).

**v1 trigger scope is `disputed` HIGH only** — not MEDIUM, and not other non-incorporated dispositions like `skipped`. That is the decision, not a placeholder; Q1 asks you to confirm or change it, and every other section of this plan assumes it.

It is deliberately **not an always-on third reviewer**: firing only on disagreement spends the extra model where it has signal, sidesteps three-way reconciliation every pass, and keeps the human as final arbiter. It reuses Axis 2's fan-out/merge scaffold (Gemini slots in as a conditional extra reviewer on the same between-pass machinery). Groundwork — paid-tier Gemini access + a validated headless call recipe — is already done (see the `gemini-access` memory).

## Why / Context

Axis 2 (personas) buys **breadth** — more issue *categories* asked about — but every lens shares one model's blind spots on *detection reliability within* a category. Decorrelating detection reliability is a different mechanism: **model diversity across vendors**. That's Axis 1.

The naive version — a third reviewer on every pass — triples cost and forces a three-way reconciliation each round. The disagreement-triggered design avoids both: Gemini is spent only where Opus and Codex already disagree, which is rare and high-signal. This is the "depth" half of the two-axis expansion brief (`/home/kyle/trinity-review-expansion-brief.md`); Axis 2 (breadth) is the other half and shipped first.

## Who / Use cases

- **Plan author (`iterate-plan`): a lens files a HIGH design finding Opus believes is wrong** — Codex misread the plan's intent, or a constraint lives outside the sliced sections. Instead of Opus unilaterally disputing, Gemini breaks the tie so the human sees a decorrelated third opinion at the checkpoint. Success: the human reads three views on a contested design claim and resolves it in one checkpoint rather than re-litigating it over two more passes.
- **Code author (`iterate-review`): a lens files a HIGH code finding Opus believes is wrong** — most often because the constraint that makes the code correct isn't visible in the diff (a caller-side guarantee, an invariant enforced elsewhere, a deliberate trade-off). Gemini reads the finding, the diff slice, and Opus's dispute reasoning, and says whether the defect holds. Success: a security-lens HIGH that Opus was about to wave off gets a second opinion *before* the human decides, instead of after the code ships.
- **Reduces both error directions:** false positives (Codex wrong → Gemini backs Opus's dispute) *and* false negatives (Opus about to dismiss a real issue → Gemini sides with Codex, flagging it for the human).

Both skills are in MVP scope, so both user moments above are v1 requirements — not one path with the other inferred from it.

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

The fold taxonomy Axis 2 shipped has exactly three dispositions: **`incorporated`**, **`skipped`**, **`disputed`**. The trigger is **`disputed` on a HIGH finding, and nothing else.** Precisely:

| Disposition | Severity | Triggers a vote? | Why |
|---|---|---|---|
| `disputed` | HIGH | **yes** | genuine Opus⇄Codex disagreement about whether a defect is real — the only case a third opinion informs |
| `disputed` | MEDIUM / LOW | no (v1) | see Q1; keeps the trigger rare |
| `skipped` | any | **no** | "acknowledged, not acting" is a *priority* call, not a disagreement about the facts. Gemini has no vote on priority. |
| `incorporated` | any | no | no disagreement exists |
| lens `FAILED` | — | no | no finding to arbitrate; Axis 2 already blocks Converge |

"Un-incorporated HIGH" is **not** the trigger — that set includes `skipped`, and voting on deliberately deferred findings would spend the tiebreaker where there is no factual dispute. This distinction is load-bearing: it is the difference between a rare, high-signal trigger and one that fires on routine scope decisions.

### Interaction with the existing loop-mode guardrail

Axis 2's guardrail already halts loop mode on an un-incorporated HIGH. Axis 1 does **not** relax it. The sequence is:

1. Opus dispositions a HIGH as `disputed`.
2. **Before** the checkpoint renders, the tiebreaker vote is requested.
3. The vote (or `unavailable`) becomes display data on that same checkpoint.
4. The checkpoint halts loop mode exactly as it does today, and the human decides.

**"Gemini failure does not block the pass" means the checkpoint still renders — it does not mean the pass proceeds past it.** A `disputed` HIGH halts loop mode whether the vote succeeded, failed, or was never attempted. No Gemini outcome can make a disputed HIGH auto-continue. Stating this explicitly because the shorter phrasing reads as though an unavailable vote lets the loop carry on, which would silently delete the guardrail Axis 2 built.

### Exactly-once votes, and the per-pass cap

Two separate questions, both previously conflated under "exactly one vote":

**Vote identity (idempotency).** A vote is keyed on `(skill, pass_number, lens_id, finding_index, sha256(finding_text + dispute_reasoning))`. The result is cached in the pass's state directory under that key. Checkpoint rendering, a retry, or a re-render reads the cached vote rather than re-invoking Gemini. Including the content hash means an *edited* dispute reasoning is a new vote, not a stale cache hit.

**Counting unit.** The unit is **per disputed finding**, not per pass. Three disputed HIGHs in one pass request three votes. A **per-pass cap (default 3, configurable)** bounds cost; when the cap is hit, remaining disputes are surfaced as `vote_not_requested (per-pass cap reached)` — an explicit, visible state, never a silent omission. The cap suppresses *requests*, never findings: every disputed HIGH still reaches the human whether or not it got a vote.

### The slice builder — an explicit boundary

The "minimal slice" is a named component with a defined contract, not an implicit behaviour, because both vote quality **and** the data-governance guarantee depend on it.

- **Input:** the finding (with its lens id and cited location), the artefact under review, and Opus's dispute reasoning.
- **Output:** a payload conforming to the budget in *Data governance* below.
- **Selection:** for `iterate-plan`, the H2 section(s) the finding cites — reusing the same `extract_section` slicing Axis 2 already uses for matched context. For `iterate-review`, the cited diff hunk(s) plus a bounded number of context lines.
- **Fallback when the finding cannot be tied to a narrow location:** include a bounded broader section **and mark the payload `low_context: true`**, which propagates to the vote's confidence and the checkpoint display. It must **never** silently widen to the whole plan or diff.

### The Gemini vote
Invoke Gemini via the validated headless recipe (`gemini-access` memory):
```
env -u GOOGLE_API_KEY GEMINI_API_KEY="$(from keyfile)" \
  gemini -m "$TIEBREAKER_MODEL" --skip-trust --approval-mode plan -o json -p '<vote prompt>'
```
Read-only is automatic (the API has no filesystem access). Input to the vote: the slice-builder payload (disputed finding + located slice + Opus's dispute reasoning + lens id). Output: a small schema — `{ agrees_with_finding: bool, confidence: low|med|high, reasoning: string }`, plus the orchestration states `unavailable` and `vote_not_requested`. The vote is refute-framed like Codex ("try to determine whether the finding is real"), and lens id is included as *context for the reviewer*, never as a weighting input (see Q5).

**Model choice is configuration, not a hard-coded constant** (`TIEBREAKER_MODEL`, with the chosen default recorded in the skill). Phase 0 must record the default it ships with, so a later capability/cost change is a config edit rather than a change to fold logic.

Grounding the default — models actually available to the project key (enumerated 2026-07-28):

| Candidate | State | Note |
|---|---|---|
| `gemini-2.5-pro` | **stable** | the only *stable Pro*; a generation behind |
| `gemini-3-pro-preview`, `gemini-3.1-pro-preview` | preview | **every 3.x Pro tier is preview** |
| `gemini-3.6-flash`, `gemini-3.5-flash` | **stable** | much newer generation than 2.5-pro |
| `gemini-pro-latest` | floating alias | resolves to a different model over time — rejected: a tiebreaker whose model silently changes is not reproducible for calibration |

Q2 as originally posed (`gemini-2.5-pro` vs `gemini-3-pro-preview`, "cost vs capability") was a **false dichotomy**: the real trade is *stability vs generation*, and there is no stable 3.x Pro to pick. Both review lenses independently advised against depending on a preview model, which given the table leaves two credible defaults — `gemini-2.5-pro` (stable, Pro-tier, older) or `gemini-3.6-flash` (stable, newer generation, cheaper). Phase 0 should benchmark both on **the same recorded set of real disputes** and record which was chosen and why. The task is a narrow single-claim adjudication, which is exactly the shape where a newer flash tier may match or beat an older pro — but that is a hypothesis to test in Phase 0, not to assume here.

### Surfacing (informs, never decides)
The tiebreaker vote is presented at the existing human checkpoint next to Opus's disposition and Codex's finding — three views for the human to arbitrate. No verdict is auto-changed. The "skill never decides convergence / human always confirms" invariant is untouched.

### Reuse of the Axis 2 scaffold
Gemini is a **conditional extra reviewer** slotted into the same between-pass machinery Axis 2 built. It does not participate in the per-pass lens fan-out (that's Codex lenses); it runs only on a triggered dispute.

### Data governance

Paid-tier Gemini (no training on submitted content) is the floor (see `gemini-access`). For CancerLogix-sensitive code this still warrants a conscious data-handling sign-off; Vertex AI is the escalation path if stricter controls (residency, VPC-SC, CMEK) are required.

"Minimal slice" is not independently checkable, so the payload has a **verifiable budget**. The vote payload contains **exactly** these fields and nothing else:

| Field | Bound |
|---|---|
| `finding` | title, severity, description, suggested_action — verbatim from the reviewer response |
| `lens_id` | the string only |
| `dispute_reasoning` | Opus's text, verbatim |
| `slice` | **≤ 200 lines total.** `iterate-plan`: the cited H2 section(s). `iterate-review`: the cited hunk(s) + ≤ 20 context lines each. |
| `artefact_kind` | `"plan"` or `"diff"` |
| `low_context` | bool — true when the slice hit the fallback path |

**Explicitly prohibited without separate sign-off:** the full plan, the full diff, any file not cited by the finding, repository metadata, and the pass log / HISTORICAL trail. Sending the whole artefact "for better context" is the failure mode this budget exists to prevent.

The 200-line ceiling is a starting figure to be validated in Phase 0 against real disputes — if votes are systematically low-confidence at 200 lines, the honest response is to raise the bound deliberately and re-sign-off, not to widen silently.

This budget is what makes the data-minimization acceptance criterion checkable: a reviewer can read a payload and say whether it conforms.

## Phasing

### Phase 0 — Gemini tiebreaker vote wrapper + slice builder (~1 day)
**Deliverables:**
- The vote output schema (`agrees_with_finding` / `confidence` / `reasoning`) plus the orchestration states `unavailable` and `vote_not_requested`.
- A tiebreaker prompt (refute-framed) + the headless invocation wrapper, with a **stated timeout and retry budget** (see Q7) and graceful `unavailable` fallback.
- The **slice builder** to the contract in Approach: located slice, ≤ 200-line budget, `low_context` fallback, and the prohibited-field list enforced in the payload construction rather than by convention.
- `TIEBREAKER_MODEL` as configuration, with the shipped default **recorded in the skill**.

**Acceptance:**
- Given a finding + slice + dispute reasoning, returns a schema-valid vote; on Gemini failure, returns `unavailable` — and the *caller* still renders its checkpoint (this phase cannot itself skip a checkpoint).
- A constructed payload contains only the six permitted fields and no prohibited field, verifiable by reading it.
- A finding whose location cannot be narrowed produces a bounded slice with `low_context: true`, never a whole-artefact payload.
- **Model default is chosen from a recorded benchmark** of `gemini-2.5-pro` vs `gemini-3.6-flash` over the same real disputes, not asserted. The rejected candidate and the reason are written down.

**Iterate-review:** YES (rationale: external-vendor integration + a new prompt/schema contract + the data-governance boundary — all load-bearing)
**Status:** not started

### Phase 1 — Disagreement trigger + checkpoint surfacing (~1 day)
**Deliverables:**
- Deterministic trigger on a **`disputed` HIGH** finding — per the disposition table in Approach, explicitly **not** `skipped` and not other un-incorporated states — in both skills' fold path.
- Vote identity + caching keyed on `(skill, pass, lens_id, finding_index, sha256(finding + dispute_reasoning))`, so a re-render or retry reuses the cached vote.
- Per-pass cap (default 3, configurable) with `vote_not_requested (per-pass cap reached)` surfaced explicitly.
- Surface the vote at the **existing** human checkpoint alongside Codex's finding and Opus's disposition.

**Acceptance:**
- A `disputed` HIGH triggers exactly one vote **per disputed finding**; `skipped` HIGHs and `disputed` MEDIUMs trigger none.
- Re-rendering a checkpoint or retrying a pass reuses the cached vote rather than re-invoking Gemini; an edited dispute reasoning correctly produces a *new* vote.
- Multiple disputed HIGHs beyond the cap surface `vote_not_requested` visibly; **no finding is dropped** because its vote wasn't requested.
- The pass still presents exactly one checkpoint, and a `disputed` HIGH halts loop mode **regardless of vote outcome** — including `unavailable`.

**Iterate-review:** YES (rationale: touches the fold/checkpoint machinery + the human-arbitration invariant + the Axis 2 loop guardrail)
**Status:** not started

### Phase 2 — Fixtures + live validation (~0.5 day)
**Deliverables:**
- Trigger-routing fixtures across the full disposition matrix: `disputed` HIGH → vote; `skipped` HIGH → **no** vote; `disputed` MEDIUM → no vote; `incorporated` → no vote; `FAILED` lens → no vote.
- Fixtures for surface-not-decide, for `unavailable` still halting loop mode, for cap behaviour, and for cache reuse vs. cache-miss on edited reasoning.
- A payload-conformance fixture asserting the six-field budget and the ≤ 200-line bound.
- A live end-to-end test in **both** skills: a real disputed finding → Gemini vote → checkpoint.

**Acceptance:**
- Every row of the disposition matrix routes correctly.
- No code path changes a verdict or a disposition based on the vote — asserted, not asserted-in-prose.
- Live test produces a coherent third opinion in both `iterate-plan` and `iterate-review`.

**Iterate-review:** YES (rationale: the E2E-analog; validates the trigger matrix + the no-auto-decide invariant)
**Status:** not started

## Acceptance criteria

- [ ] A **`disputed`** HIGH finding (in either skill) triggers exactly one schema-valid Gemini vote **per disputed finding**. `skipped` HIGHs, `disputed` MEDIUM/LOWs, `incorporated` findings, and `FAILED` lenses trigger none.
- [ ] The vote is surfaced at the human checkpoint and **never** auto-resolves the dispute, changes a verdict, or alters a disposition.
- [ ] Gemini unavailability degrades to `unavailable`; **the checkpoint still renders, and a `disputed` HIGH still halts loop mode.** "Doesn't block the pass" means the checkpoint is reached, never that it is skipped.
- [ ] The vote payload contains **exactly** the six permitted fields, with the slice **≤ 200 lines**, and no prohibited field (full plan, full diff, uncited files, repo metadata, pass log). Verifiable by reading a payload.
- [ ] A finding whose location cannot be narrowed yields a bounded slice with `low_context: true` — never a whole-artefact payload.
- [ ] Vote identity is stable: a re-render or retry reuses the cached vote; edited dispute reasoning produces a new one.
- [ ] The per-pass cap (default 3) surfaces `vote_not_requested` explicitly and **never drops a finding**.
- [ ] Reuses the Axis 2 between-pass scaffold; **exactly one** human checkpoint per pass, unchanged.
- [ ] The tiebreaker vote is recorded durably in the HISTORICAL block (vote, confidence, brief reasoning, model, `unavailable`/`vote_not_requested` state, slice reference) so agreement rates can be calibrated later.
- [ ] `TIEBREAKER_MODEL` is configuration; the shipped default is a **stable** model and the benchmark behind the choice is recorded.
- [ ] Both `iterate-plan` and `iterate-review` are validated live — neither is inferred from the other.

## Risks

### R1 — Tiebreaker drifts from "informs" to "decides"
Convenience pressure to auto-resolve disputes on Gemini's vote would break the human-arbitration invariant.
**Mitigation:** structurally surface-only; the vote is display data at the existing checkpoint; no code path changes a verdict based on it.

### R2 — Sensitive code leaves the infrastructure
The disputed finding + slice is sent to a third-party API.
**Mitigation:** paid tier (no training); minimal-slice only; conscious data-handling sign-off; Vertex escalation path for stricter compliance.

### R3 — Cost / latency on frequent disagreements
**Mitigation:** trigger only on `disputed` HIGH (rare by construction — `skipped` is excluded precisely because it is *not* rare); one vote per disputed finding; a **per-pass cap of 3 (configurable)**, implemented in Phase 1 and asserted by a Phase 2 fixture. The cap is in delivery scope, not just stated here — a mitigation no phase implements is not a mitigation.

### R4 — Gemini unavailability (503 / quota)
**Mitigation:** paid-tier reliability; on failure, surface `unavailable` and fall back to the human decision. **This never shortens the loop:** the checkpoint still renders and a `disputed` HIGH still halts loop mode. The failure mode being guarded against is not "the pass stalls" but "an unavailable vote is treated as an absent dispute."

### R5 — Slice widening under pressure
A low-confidence vote creates pressure to send more context, and "just include the whole file" is one edit away.
**Mitigation:** the payload budget is an enumerated field list with a line bound, not a guideline; the `low_context` flag makes thin context *visible* rather than something to fix by widening; raising the bound requires a deliberate re-sign-off. Phase 0 validates the 200-line figure against real disputes instead of assuming it.

## Sequencing decision

After Axis 2 (built + live-validated 2026-07-27). Axis 1 depends on the Axis 2 fan-out/merge scaffold and slots onto it as a conditional extra reviewer. Building it second was the deliberate call in the brief (breadth first — no new vendor; depth second).

## Open questions

<!-- Q1–Q5 resolved by iterate-plan pass 1 (both lenses agreed on all five — no
     escalation needed). Resolutions folded into Approach / Acceptance criteria.
     Q6–Q8 raised by pass 1; Q7 and Q8 need Kyle's call. -->

- **Q1.** (resolved — **HIGH `disputed` only for v1.** Both lenses independently agreed: it matches the existing loop-mode halt semantics, keeps the conditional reviewer rare, and makes the acceptance path crisp. MEDIUM is revisitable once calibration data exists — which Q3's HISTORICAL record makes possible. See Approach → Trigger.)
- **Q2.** (resolved — **configuration, defaulting to a stable model, benchmarked in Phase 0.** The question's premise was a false dichotomy: enumerating the models actually available to the project key showed **every 3.x Pro tier is preview**, so the real trade is stability vs generation, not cost vs capability. Both lenses advised against depending on a preview model, leaving `gemini-2.5-pro` (stable Pro, older) vs `gemini-3.6-flash` (stable, newer generation, cheaper) — decided by recorded benchmark, not assertion. `gemini-pro-latest` rejected: a floating alias makes calibration irreproducible. See Approach → The Gemini vote.)
- **Q3.** (resolved — **yes, record it.** Both lenses agreed, for the same reason from different angles: architect wants durable attribution to audit duplicate suppression and reconstruct why a checkpoint showed a given opinion; PM wants calibration and reviewer continuity. Record vote, confidence, brief reasoning, model, `unavailable`/`vote_not_requested` state, and a slice *reference* rather than the slice itself where minimization requires. See Acceptance criteria.)
- **Q4.** (resolved — **an enumerated six-field payload with a ≤ 200-line slice bound**, not a judgment call about "minimal." Both lenses converged on minimal-plus-slice and on the same failure handling: when context is insufficient, surface low confidence rather than silently widening. See Approach → Data governance.)
- **Q5.** (resolved — **no behaviour change for lens-attributed findings in v1.** Both lenses agreed, and both gave the same reason: weighting a security-lens HIGH differently would smuggle decision-making into a component defined as informational. Lens id travels in the payload as *context for the reviewer* and in the display, never as a weight. See Approach → Trigger.)

**Raised by pass 1:**

- **Q6.** (resolved on fold — where the vote is persisted so checkpoint rendering, retries, and historical logging read one vote rather than re-invoking. Answered by the vote-identity/cache design in Approach → Exactly-once votes. Raised by `architect`.)
- **Q7.** **What timeout and retry budget should the Gemini wrapper get, and does it fit the pass-latency expectation?** *(Kyle's call — no basis in the plan or repo to set it.)* Context: neither existing skill imposes a timeout on `codex exec` today, and Axis 2's lens fan-out already added ~50s of wall clock per pass. Proposal to accept or change: **one attempt, 30s timeout, one retry, then `unavailable`** — bounding the tiebreaker's worst case at ~60s on top of a pass. Raised by `architect`.
- **Q8.** **Should the checkpoint display Gemini's confidence as a separate visible field, and does low confidence need explicit framing so it isn't over-read?** *(Kyle's call — a presentation decision.)* Proposal: show confidence inline, and render `low` confidence or `low_context: true` with an explicit caveat ("thin context — weigh accordingly") so a hedged vote isn't read as a verdict. Raised by `product-manager`.

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

<!-- TOOLING-MAINTAINED by iterate-plan. Each pass appends a new
"## Codex review pass N — answers (DATE) [HISTORICAL]" section. -->

## Codex review pass 1 — answers (2026-07-28) [HISTORICAL]

First multi-lens pass. `architect` + `product-manager` fanned out concurrently
(51s wall clock); 9 findings filed → **8 merged**; 5 corrections → **4 merged**.

### Verdict
**REVISE** (worst-of: architect REVISE / product-manager REVISE; no FAILED lenses)

### Findings

1. **Trigger scope drifts between TL;DR (HIGH/MEDIUM) and the rest of the plan (HIGH-only)** — HIGH · lens: **architect, product-manager** (co-reported): the TL;DR licensed a MEDIUM trigger that Goals, Non-goals, Approach, Phasing, Acceptance and Q1 all exclude. Architect framed it as structural drift changing frequency and cost/latency behaviour; PM framed it as a scope contradiction an implementer could ship *from the TL;DR* despite the non-goals. Both routes independently justify the fix.
   → Opus: incorporated — TL;DR now states HIGH `disputed` only, and adds that this is the decision rather than a placeholder, with Q1 as confirm-or-change.
2. **`disputed` vs "un-incorporated" is not the same trigger** — HIGH · lens: architect: Approach said `disputed`, Phase 1 said "un-incorporated HIGH". The Axis 2 taxonomy is `incorporated|skipped|disputed`, so "un-incorporated" silently includes `skipped` — voting on deliberately deferred findings, where no factual dispute exists.
   → Opus: incorporated — added an explicit disposition matrix; `skipped` excluded with the reasoning that it is a *priority* call Gemini has no vote on. This is the difference between a rare trigger and one that fires on routine scope decisions.
3. **Gemini-failure fallback conflicted with the existing HIGH halt semantics** — HIGH · lens: architect: "degrades without blocking the pass" reads as permission to continue past the checkpoint, which would delete Axis 2's un-incorporated-HIGH loop guardrail.
   → Opus: incorporated — new *Interaction with the existing loop-mode guardrail* section spelling out the 4-step sequence, and stating that "doesn't block the pass" means the checkpoint still **renders**, never that it is skipped. A `disputed` HIGH halts loop mode regardless of vote outcome.
4. **Data-minimization criterion was not verifiable** — HIGH · lens: product-manager: "only the disputed finding + a minimal slice" has no observable boundary, so no reviewer could tell whether a full section, file, or plan violated it.
   → Opus: incorporated — replaced with an enumerated six-field payload, a ≤ 200-line slice bound, and an explicit prohibited-field list. Also added R5 for the widening pressure a low-confidence vote creates.
5. **Slice-builder ownership was architecturally undefined** — MEDIUM · lens: architect: no component owned slice selection, determinism was unstated, and missing context had no representation — yet both vote quality and the governance guarantee depend on it.
   → Opus: incorporated — slice builder is now a named boundary with inputs, outputs, per-skill selection (reusing Axis 2's `extract_section` for plans), and a `low_context: true` fallback that must never widen to the whole artefact.
   *(Kept separate from finding 4 despite the shared subject: architect asks "who owns the mechanism", PM asks "what makes the criterion checkable". Different defects, one shared fix — and their severities differ, so merging would have forced discarding a severity judgment.)*
6. **Exactly-once needs an idempotency boundary** — MEDIUM · lens: architect: "exactly one vote" had no identity key or persistence boundary, so retries or a re-rendered checkpoint could duplicate votes.
   → Opus: incorporated — vote keyed on `(skill, pass, lens_id, finding_index, sha256(finding + dispute_reasoning))`, cached in the pass state dir. Content hash means edited reasoning is correctly a *new* vote.
7. **Exactly-one vote: per-finding or per-pass, and what does the cap do?** — MEDIUM · lens: product-manager: acceptance said "exactly one vote", R3 said "one per finding; a per-pass cap" — unclear whether a cap could suppress votes and still satisfy acceptance.
   → Opus: incorporated — unit is **per disputed finding**; cap is 3/pass, configurable; over-cap disputes surface `vote_not_requested` explicitly and **no finding is dropped**.
   *(Kept separate from finding 6 — same location, different defects. Defining an identity key doesn't settle the counting unit, and vice versa.)*
8. **Use cases omitted `iterate-review` despite it being in MVP scope** — MEDIUM · lens: product-manager: Goals and Acceptance required both skills, but Who / Use cases described only plan review, so the code-review user moment was never specified.
   → Opus: incorporated — added the `iterate-review` use case (the constraint that makes code correct often isn't in the diff), and stated both are v1 requirements rather than one inferred from the other.

### Plan corrections applied

- **TL;DR para 1** *(co-reported — deduped)*: HIGH/MEDIUM contradiction → aligned to HIGH `disputed` only.
- **Phase 1 deliverables**: "un-incorporated HIGH" → the exact disposition name, with the matrix distinguishing it from `skipped`.
- **Risks R3 mitigation**: cited a per-pass cap no phase implemented → cap moved into Phase 1 deliverables and Phase 2 fixtures.
- **Open questions Q1 vs Non-goals**: Q1 read as undecided while Non-goals already excluded MEDIUM → HIGH-only is now stated as the current v1 decision, with Q1 as confirm-or-change.

### Open-question answers

Both lenses answered all five. **They agreed on every one** — no disagreement to escalate, so each is recorded as one merged answer with both attributions. Full resolutions are inline in *Open questions*.

1. **Q1** — HIGH `disputed` only for v1 (both lenses).
2. **Q2** — Configuration, stable default, benchmarked in Phase 0 (both). **Opus addition:** the question's premise was a false dichotomy. Enumerating the models actually available to the project key showed **every 3.x Pro tier is preview** and there is no stable 3.x Pro — so the trade is stability vs generation, and the credible pair is `gemini-2.5-pro` vs `gemini-3.6-flash`. Neither lens could see this; neither had the model list.
3. **Q3** — Yes, record the vote (both, for different reasons: audit/duplicate-suppression vs calibration/continuity — both folded).
4. **Q4** — Minimal finding + slice, with low confidence rather than silent widening (both). Opus turned the shared intent into the enumerated payload budget.
5. **Q5** — No behaviour change for lens-attributed findings; lens id is reviewer context, never a weight (both, same reasoning).

### New questions Codex raised

- **Q6** (architect) — where the vote is persisted so rendering/retries/logging read one vote → **resolved on fold** by the vote-identity/cache design.
- **Q7** (architect) — timeout/retry budget → **open, needs Kyle.** Proposal recorded: 30s, one retry, then `unavailable`.
- **Q8** (product-manager) — confidence display + low-confidence framing → **open, needs Kyle.** Proposal recorded.

### Lens run summary

- architect: REVISE · product-manager: REVISE

### Merge notes

Two same-location pairs were deliberately **not** merged (findings 4/5 on the slice, 6/7 on vote counting) — same subject, different asserted defects, and in both cases differing severities. One correction pair *was* merged (both lenses filed the TL;DR contradiction), exercising the `plan_corrections` dedupe rule added in Axis 2 Phase 4 — on its first live run, and correctly: corrections apply mechanically, so the duplicate would have double-applied.
