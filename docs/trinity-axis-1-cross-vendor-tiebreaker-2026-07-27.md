# Trinity Axis 1 — Cross-Vendor Tiebreaker — Plan

> # ⏸ PARKED — 2026-07-28
>
> **Deliberately stopped, not abandoned, and not ready to execute.** Design is in good
> shape after two `iterate-plan` passes (REVISE, 8 findings → REVISE, 4 findings with
> `product-manager` at APPROVE; merged HIGH+MEDIUM 8 → 3). Q1–Q8 resolved. **Q9 open.**
>
> ### Why parked
>
> Pass 2 raised **R6**: measured across this repo's 22 folded findings, the `disputed`
> disposition this entire axis triggers on has fired **zero** times. The tiebreaker has
> nothing observed to arbitrate, and Phase 0's model benchmark needs a dispute corpus
> that does not exist. Building ~2.5 days of machinery for an unobserved event is the
> wrong order of operations.
>
> Note the causal story, because it is easy to get wrong: this is **not** because Axis 2
> is good. Disputes come from the reviewer being *wrong* — usually because what makes
> the code correct isn't visible in what it was shown. Better lenses don't reduce that.
> The real reasons are that we have only ever reviewed prose the author wrote (little
> hidden context to misread), Opus both selects the disposition and writes the log (a
> bias toward `incorporated` would be invisible), and this repo has no third-party
> constraints or legacy invariants — precisely the conditions that produce genuine
> disagreement. The use case is **untested, not absent.**
>
> ### What unparks it
>
> Run the **existing** Axis 2 harness on real code — ideally a diff touching history the
> author didn't write, or where a caller-side guarantee matters — and count how often a
> HIGH finding reads as *wrong*. That single run yields three things: the frequency
> evidence for whether Axis 1 has a job, the dispute corpus Phase 0 needs, and the
> lens-ROI measurement that has been outstanding since Axis 2 shipped.
>
> - **Disputes occur with any regularity** → unpark, answer Q9 from the corpus, start Phase 0.
> - **Findings keep proving correct** → close this out. Record the measurement and the
>   decision; the design work is not wasted, it's a documented "not needed, and here's
>   how we know."
>
> ### Read before resuming
>
> Both HISTORICAL pass blocks at the bottom — they carry the reasoning behind the
> disposition matrix, the payload budget, and the loop-guardrail interaction, none of
> which is obvious from the current prose. Axis 2 shipped 2026-07-28 and the fan-out +
> merge scaffold this plan slots onto now exists.

## TL;DR

Axis 1 adds cross-vendor **depth** to the trinity: a **disagreement-triggered Gemini tiebreaker**. When Opus and Codex split on whether a finding is real — i.e., Codex files a **HIGH** finding that Opus dispositions as **`disputed`** rather than incorporating — Gemini is invoked as a decorrelated third vote that **informs the human checkpoint but never outvotes it**. Gemini is the right third model precisely because it's a different vendor / training regime, so its blind spots don't correlate with Claude's (a third Claude would share Claude's).

**v1 trigger scope is `disputed` HIGH only** — not MEDIUM, and not other non-incorporated dispositions like `skipped`. Confirmed by Kyle (Q1); every other section of this plan assumes it. MEDIUM stays revisitable once the HISTORICAL vote record (Q3) yields calibration data.

It is deliberately **not an always-on third reviewer**: firing only on disagreement spends the extra model where it has signal, sidesteps three-way reconciliation every pass, and keeps the human as final arbiter. It reuses Axis 2's fan-out/merge scaffold (Gemini slots in as a conditional extra reviewer on the same between-pass machinery). Groundwork — paid-tier Gemini access + a validated headless call recipe — is already done (see the `gemini-access` memory).

## Why / Context

Axis 2 (personas) buys **breadth** — more issue *categories* asked about — but every lens shares one model's blind spots on *detection reliability within* a category. Decorrelating detection reliability is a different mechanism: **model diversity across vendors**. That's Axis 1.

The naive version — a third reviewer on every pass — triples cost and forces a three-way reconciliation each round. The disagreement-triggered design avoids both: Gemini is spent only where Opus and Codex already disagree, which is rare and high-signal. This is the "depth" half of the two-axis expansion brief (`/home/kyle/trinity-review-expansion-brief.md`); Axis 2 (breadth) is the other half and shipped first.

## Who / Use cases

- **Plan author (`iterate-plan`): a lens files a HIGH design finding Opus believes is wrong** — Codex misread the plan's intent, or a constraint lives outside the sliced sections. Instead of Opus unilaterally disputing, Gemini breaks the tie so the human sees a decorrelated third opinion at the checkpoint. Success: the human reads three views on a contested design claim and resolves it in one checkpoint rather than re-litigating it over two more passes.
- **Code author (`iterate-review`): a lens files a HIGH code finding Opus believes is wrong** — most often because the constraint that makes the code correct isn't visible in the diff (a caller-side guarantee, an invariant enforced elsewhere, a deliberate trade-off). Gemini reads the finding, the diff slice, and Opus's dispute reasoning, and says whether the defect holds. Success: a security-lens HIGH that Opus was about to wave off gets a second opinion *before* the human decides, instead of after the code ships.
- **Reduces both error directions:** false positives (Codex wrong → Gemini backs Opus's dispute) *and* false negatives (Opus about to dismiss a real issue → Gemini sides with Codex, flagging it for the human).

**Scope note on that last bullet:** error-direction reduction is the *intended benefit to calibrate over time*, not an MVP acceptance promise. The MVP bar is the observable workflow — deterministic trigger, one checkpoint, no auto-resolution, bounded payloads, caching, caps, durable vote recording, live validation in both skills. Whether false positives and negatives actually fall is measurable only once the HISTORICAL vote record (Q3) accumulates agreement rates, which is why that record is an acceptance criterion rather than a nice-to-have.

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

**Vote identity (idempotency).** A vote is keyed on `(skill, pass_number, lens_id, finding_index, sha256(finding_payload + dispute_reasoning))`, where **`finding_payload` is the finding's four schema fields concatenated** (title, severity, description, suggested_action) — not the description alone, so a severity or suggested-action edit correctly invalidates the cache. The result is cached in the pass's state directory under that key. Checkpoint rendering, a retry, or a re-render reads the cached vote rather than re-invoking Gemini. Including the content hash means an *edited* dispute reasoning is a new vote, not a stale cache hit.

**Counting unit.** The unit is **per disputed finding**, not per pass. Three disputed HIGHs in one pass request three votes. A **per-pass cap (default 3, configurable)** bounds cost; when the cap is hit, remaining disputes are surfaced as `vote_not_requested (per-pass cap reached)` — an explicit, visible state, never a silent omission. The cap suppresses *requests*, never findings: every disputed HIGH still reaches the human whether or not it got a vote.

### The slice builder — an explicit boundary

The "minimal slice" is a named component with a defined contract, not an implicit behaviour, because both vote quality **and** the data-governance guarantee depend on it.

- **Input:** the finding (with its lens id and cited location), the artefact under review, and Opus's dispute reasoning.
- **Output:** a payload conforming to the budget in *Data governance* below.
- **Selection:** for `iterate-plan`, the H2 section(s) the finding cites — reusing the same `extract_section` slicing Axis 2 already uses for matched context. For `iterate-review`, the cited diff hunk(s) plus a bounded number of context lines.
- **Fallback when the finding cannot be tied to a narrow location:** include a bounded broader section **and mark the payload `low_context: true`**, which propagates to the vote's confidence and the checkpoint display. It must **never** silently widen to the whole plan or diff.

**When the located slice exceeds the 200-line budget** — a cited H2 longer than the cap, or several cited locations that together exceed it — the builder must not choose between violating the budget and truncating arbitrarily. The rule:

1. **Budget is split evenly across cited locations**, floor 20 lines each. Three cited locations get ~66 lines apiece.
2. **Within a location, keep the lines nearest the finding's cited anchor** (the line or subsection it names), expanding symmetrically outward until that location's share is spent. If no anchor is resolvable, keep the leading lines.
3. **Any truncation sets `low_context: true`.** Truncation is a context loss and must be visible in the vote's confidence and at the checkpoint — never silent.
4. **Never raise the 200-line cap to fit content.** The cap is the governance boundary; content yields to it, not the reverse. Raising it is the deliberate re-sign-off described below, not an automatic accommodation.

Stated because the slice builder is simultaneously the data-minimization enforcement point and the vote's input boundary: an unspecified cap policy would have let an implementation satisfy one by quietly breaking the other.

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

### Wrapper budget (latency)

**30s timeout, one retry, then `unavailable`.** Worst case ~60s added to a pass; typical 5–15s.

The deciding constraint is that the vote is requested *before* the checkpoint renders, so a human is waiting on it — that argues for tight rather than patient. Axis 2's lens fan-out already costs ~42–51s of measured wall clock per pass, and the tiebreaker stacks on top of that. One retry catches a transient 503; a second wouldn't help against quota, which is the other realistic failure. An `unavailable` vote is a fully-handled state that costs a third opinion, not correctness — so failing fast is cheap, and waiting is what actually degrades the experience.

### Surfacing (informs, never decides)

The tiebreaker vote is presented at the existing human checkpoint next to Opus's disposition and Codex's finding — three views for the human to arbitrate. No verdict is auto-changed. The "skill never decides convergence / human always confirms" invariant is untouched.

**Confidence renders inline, and the low end carries an explicit caveat.** A vote with `confidence: low` *or* `low_context: true` is rendered with a "thin context — weigh accordingly" note; normal-confidence votes are not.

```
TIEBREAKER (gemini-3.6-flash)          TIEBREAKER (gemini-3.6-flash)
  agrees with finding: NO                agrees with finding: NO
  confidence: high                       confidence: low  ⚠ thin context — weigh accordingly
  "The caller validates q before         "Cannot see the caller; the claim may hold upstream."
   this path is reachable."
```

Two failure modes are being balanced. Hiding confidence is worse than showing it, because a hedged vote presented flat reads as confident — and over-reading a hedge is how R1 (drift from "informs" to "decides") actually happens in practice. But caveating *every* vote produces banner blindness, and a warning nobody reads is worse than no warning. So the caveat is reserved for where it carries information.

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

### Bootstrapping the dispute corpus (and a premise check)

Phase 0 is required to choose its model default from a benchmark over real disputed-HIGH findings. **That corpus does not exist yet**, and measuring the repository says something uncomfortable about the trigger itself.

Across every archived and current pass log in this repo — **22 folded findings** — the disposition counts are:

| Disposition | Count |
|---|---|
| `incorporated` | 22 |
| `skipped` | 0 |
| `disputed` (clean) | **0** |
| "disputed in part" (prose, not a clean disposition) | 2 |

**The trigger this entire axis is built on has never once fired in the recorded history.** Two partial disputes exist, both authored during the 2026-07-28 sessions, and both were *partial* — incorporated in substance while disputing a specific claim.

Read this carefully rather than as a verdict on the design:

- **The sample is small and unrepresentative.** 22 folds, all on a prose/skills repo reviewed by its own author. Axis 1's stronger use case is `iterate-review` on real code, where the reviewer *lacks* the context that makes the code correct — exactly the condition that produces genuine disputes and which this repo barely exercises.
- **There is a disposition-selection bias.** Opus chooses the disposition *and* wrote these logs. A bias toward `incorporated` (or toward recording disagreement as "disputed in part" rather than `disputed`) would produce this data without any real absence of disagreement.
- **But the frequency assumption is unvalidated either way.** The plan asserts disputes are "rare and high-signal." Rare is confirmed; *high-signal* and *non-zero* are not. If the true rate is near zero, Axis 1 is machinery for an event that does not occur, and the per-pass cap of 3 is defending against a load that never arrives.

**Consequence for sequencing.** Phase 0 must not begin until a dispute corpus exists. The corpus should come from **running the existing Axis 2 harness on real code — a project where the reviewer genuinely lacks context** — and recording the dispositions. That run is worth doing on its own merits (it is the outstanding lens-ROI measurement), and it produces exactly the data Phase 0 needs plus the frequency evidence that tells you whether to build Axis 1 at all.

Minimum corpus size and the fallback if disputes stay sparse are Kyle's call — see Q9.

## Phasing

### Phase 0 — Gemini tiebreaker vote wrapper + slice builder (~1 day)
**Deliverables:**
- The vote output schema (`agrees_with_finding` / `confidence` / `reasoning`) plus the orchestration states `unavailable` and `vote_not_requested`.
- A tiebreaker prompt (refute-framed) + the headless invocation wrapper with a **30s timeout, one retry, then `unavailable`** (Q7 resolved), and graceful `unavailable` fallback.
- The **slice builder** to the contract in Approach: located slice, ≤ 200-line budget, `low_context` fallback, and the prohibited-field list enforced in the payload construction rather than by convention.
- `TIEBREAKER_MODEL` as configuration, with the shipped default **recorded in the skill**.

**Acceptance:**
- Given a finding + slice + dispute reasoning, returns a schema-valid vote; on Gemini failure, returns `unavailable` — and the *caller* still renders its checkpoint (this phase cannot itself skip a checkpoint).
- A constructed payload contains only the six permitted fields and no prohibited field, verifiable by reading it.
- A finding whose location cannot be narrowed produces a bounded slice with `low_context: true`, never a whole-artefact payload.
- **Model default is chosen from a recorded benchmark** of `gemini-2.5-pro` vs `gemini-3.6-flash` over the same dispute set, not asserted. The rejected candidate and the reason are written down.
- **The benchmark corpus is identified before Phase 0 starts** — see *Bootstrapping the dispute corpus*. Phase 0 cannot satisfy its own acceptance without one, and the corpus does not currently exist.

**Iterate-review:** YES (rationale: external-vendor integration + a new prompt/schema contract + the data-governance boundary — all load-bearing)
**Status:** not started

### Phase 1 — Disagreement trigger + checkpoint surfacing (~1 day)
**Deliverables:**
- Deterministic trigger on a **`disputed` HIGH** finding — per the disposition table in Approach, explicitly **not** `skipped` and not other un-incorporated states — in both skills' fold path.
- Vote identity + caching keyed on `(skill, pass, lens_id, finding_index, sha256(finding_payload + dispute_reasoning))` — `finding_payload` per Approach — so a re-render or retry reuses the cached vote.
- Per-pass cap (default 3, configurable) with `vote_not_requested (per-pass cap reached)` surfaced explicitly.
- Surface the vote at the **existing** human checkpoint alongside Codex's finding and Opus's disposition, with confidence inline and the "thin context" caveat on `low`/`low_context`.
- **Write the vote into the pass's HISTORICAL block** (vote, confidence, brief reasoning, model, `unavailable`/`vote_not_requested` state, and a slice *reference* — never the slice contents). This is a distinct write path from the pass-state cache: the cache serves re-renders within a pass, the HISTORICAL record serves calibration across passes. Owning it here, because acceptance requires it and no other phase touches the log.

**Acceptance:**
- A `disputed` HIGH triggers exactly one vote **per disputed finding**; `skipped` HIGHs and `disputed` MEDIUMs trigger none.
- Re-rendering a checkpoint or retrying a pass reuses the cached vote rather than re-invoking Gemini; an edited dispute reasoning correctly produces a *new* vote.
- Multiple disputed HIGHs beyond the cap surface `vote_not_requested` visibly; **no finding is dropped** because its vote wasn't requested.
- The pass still presents exactly one checkpoint, and a `disputed` HIGH halts loop mode **regardless of vote outcome** — including `unavailable`.
- The HISTORICAL block carries the vote metadata **and no slice contents**, verifiable by reading the log.
- Confidence renders inline; `confidence: low` **or** `low_context: true` renders the "thin context" caveat, and a normal-confidence vote does not (Q8 resolved).

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
- [ ] The checkpoint shows the vote's confidence inline, and renders the "thin context" caveat exactly when `confidence: low` or `low_context: true` — not on every vote.
- [ ] The wrapper bounds itself at 30s per attempt with one retry, so the tiebreaker adds at most ~60s to a pass before degrading to `unavailable`.
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

### R6 — The trigger may never fire (premise risk)

Axis 1 assumes Opus⇄Codex disputes are "rare and high-signal." Measured over this repo's entire recorded history — 22 folded findings — clean `disputed` dispositions number **zero**, with 2 partial disputes. *Rare* is confirmed; *non-zero* is not. If the true rate is near zero, this axis is ~2.5 days of machinery guarding an event that does not occur, and the per-pass cap of 3 defends against a load that never arrives.

**Mitigation:** treat the frequency as unvalidated and **measure before building**. The corpus-bootstrap run (see Approach → Bootstrapping) produces the evidence as a by-product of a measurement worth doing anyway. Two confounders keep this from being a verdict: the sample is 22 folds on a prose repo reviewed by its own author — not the code-review case Axis 1 is strongest for — and Opus both selects the disposition and writes the log, so a bias toward `incorporated` (or toward recording disagreement as "disputed in part") would produce this data without any real absence of disagreement. Both are reasons to measure properly, not reasons to discount the signal.

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

**Raised by pass 2:**

- **Q9.** **What minimum dispute corpus is acceptable for Phase 0's model benchmark, and what is the fallback if real disputed HIGHs stay sparse?** *(Kyle's call — `needs_human`, label upheld on audit: no repository fact settles a calibration threshold.)*
  The lookup half **is** answerable and has been done: across 22 folded findings in every archived and current pass log, there are **zero clean `disputed` dispositions** and 2 partial ones. So the corpus is currently *empty*, not merely unspecified. Options, in the order I'd consider them:
  1. **Gate Phase 0 on a real-code run** — take the outstanding lens-ROI measurement on a project where the reviewer lacks context, record dispositions, and use whatever disputes it produces. Also yields the frequency evidence for whether to build Axis 1 at all. *Recommended.*
  2. **Synthesise a corpus** — hand-author N plausible disputed HIGHs. Cheap and immediate, but benchmarks the models on invented disagreements, which is exactly the "theater" failure Axis 2's R2 warns about.
  3. **Defer the model choice** — ship Phase 0 with `gemini-2.5-pro` (stable, Pro-tier) as an unbenchmarked default and revisit once real disputes accumulate. Honest, but drops a Phase 0 acceptance criterion.
  Raised by `architect`.

**Raised by pass 1:**

- **Q6.** (resolved on fold — where the vote is persisted so checkpoint rendering, retries, and historical logging read one vote rather than re-invoking. Answered by the vote-identity/cache design in Approach → Exactly-once votes. Raised by `architect`.)
- **Q7.** (resolved by Kyle 2026-07-28 — **30s timeout, one retry, then `unavailable`**; worst case ~60s added to a pass, typical 5–15s. The deciding consideration: the vote is requested *before* the checkpoint renders, so the human is waiting on it — that argues for tight rather than patient. One retry catches a transient 503; a second wouldn't help against quota. See Approach → Wrapper budget. Raised by `architect`.)
- **Q8.** (resolved by Kyle 2026-07-28 — **show confidence inline, caveat the low end.** `low` confidence *or* `low_context: true` renders with an explicit "thin context — weigh accordingly" note; normal-confidence votes do not. Reasoning: hiding confidence is worse than showing it, because a hedged vote presented flat reads as confident — but caveating *every* vote produces banner blindness, so the caveat is reserved for where it carries information. See Approach → Surfacing. Raised by `product-manager`.)

## Out of scope

- Always-on / every-pass third reviewer — trigger-only by design.
- Gemini as an editor — read-only vote only.
- Vendors beyond Gemini.
- Auto-resolution of disputes.

## Closeout

**Not applicable yet — this plan is parked, not shipped.** Left unchecked deliberately so
nobody mistakes a parked plan for a completed one. It stays in `docs/` rather than
`docs/archive/`: the archive is for shipped work, and moving it there would imply it
was executed.

- [ ] Append entry to `CHANGELOG.md`: what shipped, ship commit, key delta, link to the archived plan.
- [ ] Update memory: mark Axis 1 completed, link ship commits, update `trinity-expansion` + `gemini-access`.
- [ ] Update any backlog / priority queue.
- [ ] Move plan to archive: `git mv docs/<plan>.md docs/archive/<plan>.md`.
- [ ] Final commit referencing this plan.

**If Axis 1 is instead closed out as "not needed"** (see the parked banner — the measurement
comes back showing findings keep proving correct), the closeout is different and shorter:
record the measurement and the decision in `CHANGELOG.md`, note it in the
`trinity-expansion` memory, and archive the plan as a documented non-build. A design that
was correctly *not* built is a result worth keeping, not a failure to tidy away.

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

### Merge notes (pass 1)

Two same-location pairs were deliberately **not** merged (findings 4/5 on the slice, 6/7 on vote counting) — same subject, different asserted defects, and in both cases differing severities. One correction pair *was* merged (both lenses filed the TL;DR contradiction), exercising the `plan_corrections` dedupe rule added in Axis 2 Phase 4 — on its first live run, and correctly: corrections apply mechanically, so the duplicate would have double-applied.

## Codex review pass 2 — answers (2026-07-28) [HISTORICAL]

Second multi-lens pass, run after Q7/Q8 were resolved by Kyle and folded.
`architect` + `product-manager` concurrent (35s wall clock); 4 findings filed →
**4 merged** (nothing overlapped); 1 correction; 1 new question.

**First pass to run under the 2.1 reviewer contract**, so `new_questions` arrived
classified.

### Verdict
**REVISE** (worst-of: architect REVISE / product-manager **APPROVE**; no FAILED lenses)

The product-manager lane is now satisfied — its only finding is a LOW scope nit. All
remaining substance is architectural.

### Findings

1. **Oversized cited sections had no deterministic cap rule** — HIGH · lens: architect: the slice contract said "the cited H2 section(s)" and, separately, "≤ 200 lines" — but never what happens when a cited H2 exceeds the cap. An implementation had to either break the governance budget or truncate arbitrarily, and the slice builder is simultaneously the data-minimization enforcement point *and* the vote's input boundary, so an unspecified policy let one be satisfied by quietly breaking the other.
   → Opus: **incorporated** — added a four-part rule: budget split evenly across cited locations (floor 20 lines each); within a location keep lines nearest the finding's cited anchor, expanding outward; **any truncation sets `low_context: true`**; and the 200-line cap is never raised to fit content.
2. **HISTORICAL vote persistence had no owning phase** — MEDIUM · lens: architect: acceptance required the vote recorded durably with vote/confidence/reasoning/model/state/slice-reference, but Approach only defined the pass-state cache and checkpoint display, and no phase assigned the log write. Checkpoint rendering could read a cached vote while the durable calibration record — the whole point of Q3 — never got written.
   → Opus: **incorporated** — Phase 1 now owns the HISTORICAL write explicitly, distinguished from the cache (cache serves re-renders within a pass; the log serves calibration across passes), with an acceptance criterion that the log carries vote metadata **and no slice contents**.
3. **Phase 0's benchmark corpus was never identified** — MEDIUM · lens: architect: Phase 0 acceptance requires choosing the model default from a benchmark "over the same real disputes," but the plan never said where those come from, how many suffice, or what happens if history holds too few — a sequencing risk, since Phase 0 cannot satisfy its own acceptance without a corpus that may not exist.
   → Opus: **incorporated, and it turned out worse than described.** Measured the repository: across 22 folded findings in every archived and current pass log, clean `disputed` dispositions number **zero** (2 partial). The corpus is *empty*, not merely unspecified. Added Approach → *Bootstrapping the dispute corpus*, gated Phase 0 on a real-code run, and raised **R6** — the trigger this axis is built on has never fired in recorded history.
4. **Outcome claims broader than MVP verification** — LOW · lens: product-manager: "reduces both error directions" reads as an MVP promise, but acceptance verifies the *mechanism* (trigger, checkpoint, payload bounds, caching, caps) and not the error-rate effect.
   → Opus: **incorporated** (LOW, but a one-line clarification) — added a scope note that error-direction reduction is the intended benefit to calibrate over time, measurable only once the Q3 vote record accumulates agreement rates, which is why that record is an acceptance criterion.

### Plan corrections applied

- **Approach → Exactly-once votes vs Phase 1 deliverables**: the hash input was named `sha256(finding_text + ...)` in one place and `sha256(finding + ...)` in the other → canonicalised to `finding_payload`, defined as the finding's four schema fields concatenated, so a severity or suggested-action edit correctly invalidates the cache.

### Open-question answers

None requested — Q1–Q8 were all resolved before this pass, so no lens had an open question to answer.

### New questions Codex raised

- **What minimum dispute corpus is acceptable for Phase 0's benchmark, and what is the fallback if real disputed HIGHs stay sparse?** — **`needs_human`** (lens: architect): *"a calibration and risk-tolerance decision; the plan can define a threshold, but there is no uniquely correct number derivable from the repository."*
  → Opus: **label audited and upheld** — correctly `needs_human`; no repo fact settles a calibration threshold. But the question had a `resolvable_in_fold` half, and per the 2.1 routing rules I resolved that before escalating: measuring the repo showed the corpus is currently **empty** (0 clean disputes in 22 folds). **Carried to Open questions as Q9** with three concrete options and a recommendation, so Kyle decides against data rather than in the abstract.

### Lens run summary

- architect: REVISE · product-manager: **APPROVE**

### Merge notes (pass 2)

Nothing merged — all four findings were lane-unique and non-overlapping, so 4 filed → 4 merged. No co-reports this pass, in contrast to pass 1 where both lenses independently hit the TL;DR trigger contradiction.

The question-classification routing added in 2.1 did real work on its first live run: the lens's `needs_human` label was right, but treating it as *purely* `needs_human` would have escalated an abstract question. Splitting off the answerable half turned "how big should the corpus be?" into "the corpus is empty — here are three ways forward," which is a materially better thing to put in front of a human.

### Convergence status

Verdicts: REVISE (1H 2M) → REVISE (1H 2M 1L). Merged HIGH+MEDIUM count **8 → 3**, strictly decreasing. Not converged: one HIGH and two MEDIUMs were folded this pass, and **Q9 is open and blocking** — Phase 0 cannot start without a corpus decision. A pass 3 would be reviewing the cap rule, the HISTORICAL ownership, and the bootstrap section, none of which existed when pass 2 ran.
