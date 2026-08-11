# Trinity Axis 1 — Cross-Vendor Tiebreaker — Plan

> # ⏸ PARKED — 2026-07-28
>
> **Deliberately stopped, not abandoned, and not ready to execute.** Design is in good
> shape after two `iterate-plan` passes (REVISE, 8 findings → REVISE, 4 findings with
> `product-manager` at APPROVE; merged HIGH+MEDIUM 8 → 3). Q1–Q8 resolved. **Q9 open.**
>
> ### Why parked (original 2026-07-28 rationale — see the update below for what changed)
>
> Pass 2 raised **R6**: measured across this repo's 22 folded findings at that time, the
> `disputed` disposition this entire axis triggers on had fired **zero** times. The
> tiebreaker had nothing observed to arbitrate, and Phase 0's model benchmark needed a
> dispute corpus that did not exist. Building ~2.5 days of machinery for an unobserved
> event was the wrong order of operations. *(The corpus situation has since changed —
> the empty-corpus reason is retired; the gate is now the insufficient-corpus threshold, Q9.)*
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
> ### UPDATE 2026-08-11 — the unpark evidence is accumulating
>
> The dispute corpus is **no longer empty: 3 real disputed HIGHs** (was 0 when parked),
> all from real reviews since 2026-08-06 — see *Bootstrapping the dispute corpus* for
> the list. All three match the predicted causal pattern (the reviewer read code with
> constraints not visible in what it was shown), and each needed external evidence to
> arbitrate — an interpreter run, POSIX semantics, plan history — which is precisely
> the tiebreaker's designed job. One was even ad-hoc cross-checked with Gemini at the
> time, a manual preview of this axis.
>
> **Q9 resolved 2026-08-11 (Kyle): the plan stays parked while normal review work
> accumulates the corpus. The unpark trigger is now a number — 6 real disputes —
> at which point Phase 0 starts with a provisional benchmark (re-benchmark
> precommitted at 10).** The design below has been fully fleshed out by review
> passes 3–7 and is execution-ready when the trigger fires; no further design
> work is expected to be needed at unpark time. Corpus at resolution: 3/6.
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

**Scope note on the outcome claims above:** both **error-direction reduction** and **one-checkpoint resolution** ("resolves it in one checkpoint rather than re-litigating over two more passes") are *intended benefits to calibrate over time*, not MVP acceptance promises. The MVP bar is the observable workflow — deterministic trigger, one checkpoint, no auto-resolution, bounded payloads, caching, caps, durable vote recording, live validation in both skills. Both outcomes become measurable from the HISTORICAL record (Q3): agreement rates for error direction, and *dispute recurrence* — the same disputed finding reappearing in a later pass — for one-checkpoint resolution, since every pass's disputes and dispositions are already durably logged. That is one more reason the vote record is an acceptance criterion rather than a nice-to-have.

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

**Vote identity (idempotency).** A vote is keyed on the namespace `(skill, pass_number, lens_id, finding_index)` plus a **content digest computed over a canonical serialization of every inference-relevant input**: a sorted-key UTF-8 JSON object with named fields — the finding's four schema fields (title, severity, description, suggested_action), `dispute_reasoning`, the **built slice content**, `low_context`, the resolved `TIEBREAKER_MODEL`, and a `prompt_version` identifier for the tiebreaker prompt + vote schema. Canonical structured serialization (not bare concatenation) is what makes the key collision-proof and identical across both skills; covering the slice, model, and prompt version means a vote is reused **only** when Gemini would see byte-identical input under the same configuration — an edited dispute reasoning, a re-sliced artefact, or a model/prompt change is correctly a *new* vote, never a stale cache hit. The result is cached in the pass's state directory under that key; checkpoint rendering, a retry, or a re-render reads the cached vote rather than re-invoking Gemini.

**Cache-miss handling is single-writer, not first-past-the-post.** A lookup miss does not license an invocation: the requester must first take a **per-key atomic claim** (an `O_CREAT|O_EXCL` claim file beside the cache entry — the same primitive the runner scripts' scope lock already uses, dead-owner reclaim discipline included); only the claimant invokes Gemini and publishes the result atomically; concurrent observers of a live claim wait for the publication and read it. Without this, two simultaneous checkpoint renders could both miss and both invoke — violating exactly-once and, if the responses differ, making the cached and HISTORICAL records nondeterministic. The concurrent multi-vote fan-out makes this boundary mandatory, not defensive.

**Durable recording rides the existing fold serialization — no second ownership mechanism.** The claim boundary above governs *vendor invocation and cache publication* only. Committing the vote to the checkpoint display and the HISTORICAL block is the **model's fold step**, which Axis 2 already serializes to **exactly one HISTORICAL block and one checkpoint per pass** — the model is the sole log writer, the runner and the cache never touch the log, and concurrent cache *readers* re-render displays but never append records. So exactly-once recording is inherited from the one-fold-per-pass invariant rather than re-implemented; what Phase 2 must assert is that the inheritance holds: one durable vote record per disputed finding per pass, single checkpoint preserved, under concurrent re-renders.

**Counting unit.** The unit is **per disputed finding**, not per pass. Three disputed HIGHs in one pass request three votes. A **per-pass cap (default 3, configurable)** bounds cost; when the cap is hit, remaining disputes are surfaced as `vote_not_requested (per-pass cap reached)` — an explicit, visible state, never a silent omission. The cap suppresses *requests*, never findings: every disputed HIGH still reaches the human whether or not it got a vote.

**Which findings get the capped votes is deterministic:** disputed HIGHs are taken in **merged-findings-list order** (the stable order the HISTORICAL block records), and the first N under the cap receive votes. A retry, re-render, or re-implementation of the same merged list selects the same findings — reproducibility of *which* disputes were voted is part of the exactly-once story, not an implementation accident.

### The slice builder — an explicit boundary

The "minimal slice" is a named component with a defined contract, not an implicit behaviour, because both vote quality **and** the data-governance guarantee depend on it.

- **Input:** the finding (with its lens id and cited location), the artefact under review, and Opus's dispute reasoning.
- **Output:** a payload conforming to the budget in *Data governance* below.
- **Selection:** for `iterate-plan`, the H2 section(s) the finding cites — reusing the same `extract_section` slicing Axis 2 already uses for matched context. For `iterate-review`, the cited diff hunk(s) plus a bounded number of context lines.
- **Fallback when the finding cannot be tied to a narrow location:** include a bounded broader section **and mark the payload `low_context: true`**, which propagates to the vote's confidence and the checkpoint display. It must **never** silently widen to the whole plan or diff.

**When the located slice exceeds the 200-line budget** — a cited H2 longer than the cap, or several cited locations that together exceed it — the builder must not choose between violating the budget and truncating arbitrarily. The rule:

1. **Budget is split evenly across cited locations**, floor 20 lines each. Three cited locations get ~66 lines apiece.
2. **When the floor makes the split impossible** (locations × floor exceeds the ceiling), the budget is partitioned deterministically with **reference lines counted inside the 200-line bound**, computed non-circularly: for a finding citing L locations, let `refs(K)` = one line per unsliced location, capped at 20, plus one summary line ("…and N more locations, not shown") when L − K > 20; **K is the largest value ≤ 10 for which `20·K + refs(K) ≤ 200`** (well-defined: feasibility is monotone in K and K = 8 always fits). The sliced set is the **first K locations in citation order**; the reference block covers the rest; the remaining budget (200 − refs(K)) splits evenly across the K sliced locations, each therefore ≥ the 20-line floor. Total payload lines never exceed 200 by construction; coverage yields, deterministically, and the payload sets `low_context: true`.
3. **Within a location, keep the lines nearest the finding's cited anchor** (the line or subsection it names), expanding symmetrically outward until that location's share is spent. If no anchor is resolvable, keep the leading lines.
4. **Any truncation sets `low_context: true`.** Truncation is a context loss and must be visible in the vote's confidence and at the checkpoint — never silent.
5. **Never raise the 200-line cap to fit content.** The cap is the governance boundary; content yields to it, not the reverse. Raising it is the deliberate re-sign-off described below, not an automatic accommodation.

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

### What the vote adjudicates — the reasoning, not the world

A boundary the motivating corpus makes unavoidable to state: **all three observed real disputes were settled by evidence *outside* any reviewable slice** — an interpreter run, POSIX filesystem semantics, plan history. The payload budget deliberately prohibits shipping the world to Gemini, and the wrapper has no evidence-retrieval mechanism. So the tiebreaker's role is precisely: **adjudication over the supplied evidence** — the finding, the located slice, and Opus's dispute reasoning *including its account of any external evidence* ("verified live: `rmdir` returns `ENOTEMPTY`"). Gemini judges whether the dispute reasoning actually answers the finding — is the cited evidence the right kind, does the argument hold, does the finding survive it — it does **not** independently re-run interpreters, consult specs, or verify the claimed facts.

This is still a real third signal (a wrong dispute usually *argues* wrong, and a decorrelated reader catches that), but it is a different claim than independent verification, and conflating them would overstate the vote at exactly the checkpoint where the human is calibrating trust. Two consequences are binding elsewhere in this plan:

- **The checkpoint display and HISTORICAL record frame the vote as "assessment of the dispute reasoning,"** never as independent confirmation of the underlying facts.
- **The Phase 0 benchmark stratifies its corpus** into slice-resolvable disputes vs externally-evidenced disputes and reports performance separately — a model that looks good only when Opus's account settles the matter has not been shown to adjudicate anything.

A bounded evidence-attachment mechanism (letting Opus include, say, a command transcript as a first-class payload field) is a plausible v2 extension; v1 keeps the six-field budget and states the limitation honestly.

### Wrapper budget (latency)

**Per vote: 30s timeout, one retry, then `unavailable`. Per pass: independent votes fan out concurrently, under one pass-level deadline equal to a single vote budget (~60s).** So the tiebreaker adds at most ~60s of wall clock to a pass regardless of how many disputes fired (up to the cap); typical 5–15s. A vote not complete at the pass deadline degrades to `unavailable` exactly as a timed-out single vote does. Multi-vote orchestration (the fan-out and the deadline) belongs to Phase 1, alongside the trigger; Phase 0 owns only the single-vote wrapper. Votes are independent adjudications of independent findings — the same reason Axis 2 fans lenses out concurrently — and a sequential implementation would silently turn the per-vote budget into a per-pass multiplier (~180s at the cap), which is the contradiction this paragraph exists to rule out.

The deciding constraint is that the votes are requested *before* the checkpoint renders, so a human is waiting on them — that argues for tight rather than patient. Axis 2's lens fan-out already costs ~42–51s of measured wall clock per pass, and the tiebreaker stacks on top of that. One retry catches a transient 503; a second wouldn't help against quota, which is the other realistic failure. An `unavailable` vote is a fully-handled state that costs a third opinion, not correctness — so failing fast is cheap, and waiting is what actually degrades the experience.

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

Phase 0 is required to choose its model default from a benchmark over real disputed-HIGH findings. **That corpus now exists but is small — 3 real disputes as of 2026-08-11, below any plausible benchmark threshold (Q9)** — and the history of measuring it says something important about the trigger itself.

Measured when this plan was parked (2026-07-28), across every archived and current pass log in this repo — **22 folded findings** — the disposition counts were:

| Disposition | Count |
|---|---|
| `incorporated` | 22 |
| `skipped` | 0 |
| `disputed` (clean) | **0** |
| "disputed in part" (prose, not a clean disposition) | 2 |

**At parking time, the trigger this entire axis is built on had never once fired in the recorded history.**

**UPDATE 2026-08-11 — the corpus now holds 3 real disputed HIGHs**, all from reviews of real code (the runner-scripts work and its doc-bot dogfood), all Kyle-ratified at their checkpoints:

1. **2026-08-06, runner-scripts Phase 1 self-review pass 6** (senior-dev): PEP 604 annotations "break the 3.9 floor" — factually wrong; disproven by running the 3.9.6 floor interpreter. (A Gemini second opinion was taken manually at the time and concurred — an ad-hoc preview of exactly what this axis automates.)
2. **2026-08-10, runner-scripts Phase 2 review pass 6** (senior-dev): final-rmdir TOCTOU "can remove a replacement directory" — window real, harm impossible (POSIX `ENOTEMPTY`; verified live). Pass log: `docs/reviews/code-review-commit-13c9e0c.md`.
3. **2026-08-10, doc-bot write-path Phase 1 pass 1** (security): "publish endpoint has no auth" — the plan's accepted posture (Tailscale perimeter, DevOps-closed question), invisible in the diff. Pass log in the doc-bot repo.

All three match the predicted causal pattern — the reviewer read *code with constraints not visible in the diff* — and none arose in the prose-review era. Each was arbitrated with **external evidence** (an interpreter run, POSIX semantics, plan history): the exact job this plan gives the tiebreaker. Observed rate so far: roughly one disputed HIGH per major multi-pass code review. The corpus is still far below any plausible benchmark minimum — which is Q9's threshold question, now answerable against live data rather than in the abstract.

Read this carefully rather than as a verdict on the design:

- **The sample is small and unrepresentative.** 22 folds, all on a prose/skills repo reviewed by its own author. Axis 1's stronger use case is `iterate-review` on real code, where the reviewer *lacks* the context that makes the code correct — exactly the condition that produces genuine disputes and which this repo barely exercises.
- **There is a disposition-selection bias.** Opus chooses the disposition *and* wrote these logs. A bias toward `incorporated` (or toward recording disagreement as "disputed in part" rather than `disputed`) would produce this data without any real absence of disagreement.
- **But the frequency assumption is unvalidated either way.** The plan asserts disputes are "rare and high-signal." Rare is confirmed; *high-signal* and *non-zero* are not. If the true rate is near zero, Axis 1 is machinery for an event that does not occur, and the per-pass cap of 3 is defending against a load that never arrives.

**Consequence for sequencing.** Phase 0 must not begin until a dispute corpus exists. The corpus should come from **running the existing Axis 2 harness on real code — a project where the reviewer genuinely lacks context** — and recording the dispositions. That run is worth doing on its own merits (it is the outstanding lens-ROI measurement), and it produces exactly the data Phase 0 needs plus the frequency evidence that tells you whether to build Axis 1 at all.

Minimum corpus size is settled (Q9, Kyle 2026-08-11): **6 real disputes unlocks Phase 0's provisional benchmark; re-benchmark precommitted at 10; synthetics never scored.** Until the corpus reaches 6, the plan stays parked and normal review work keeps accumulating dispositions.

## Phasing

### Phase 0 — Gemini tiebreaker vote wrapper + slice builder (~1 day)
**Deliverables:**
- The vote output schema (`agrees_with_finding` / `confidence` / `reasoning`) plus the orchestration states `unavailable` and `vote_not_requested`.
- A tiebreaker prompt (refute-framed) + the headless invocation wrapper with a **30s timeout, one retry, then `unavailable`** (Q7 resolved), and graceful `unavailable` fallback.
- The **slice builder** to the contract in Approach: located slice, ≤ 200-line budget (including the >10-locations rule), `low_context` fallback, and the prohibited-field list enforced in the payload construction rather than by convention.
- `TIEBREAKER_MODEL` as configuration, with the shipped default **recorded in the skill**.
- A **written benchmark protocol, predeclared before the runs**: ground truth = the human-ratified disposition outcome of each real dispute (Kyle confirmed every corpus entry at its checkpoint); score = agreement with the ratified outcome, with confidence calibration as the tie dimension; selection rule = higher agreement wins, ties go to the cheaper/newer stable model; corpus **stratified** slice-resolvable vs externally-evidenced (per Approach → What the vote adjudicates) with performance reported per stratum; any coverage gap (e.g. all entries sharing one adjudication direction, as the initial 3 do — all upheld disputes) **disclosed in the recorded result**, and the benchmark labeled *provisional* until both directions and both skills are represented.

**Acceptance:**
- Given a finding + slice + dispute reasoning, returns a schema-valid vote; on Gemini failure, returns `unavailable` — and the *caller* still renders its checkpoint (this phase cannot itself skip a checkpoint).
- A constructed payload contains only the six permitted fields and no prohibited field, verifiable by reading it.
- A finding whose location cannot be narrowed produces a bounded slice with `low_context: true`, never a whole-artefact payload; a finding citing more locations than the floor permits slices the **budget-derived first K locations** (per the non-circular K rule in Approach → The slice builder) and references the rest, within the 200-line total.
- **Model default is chosen from a recorded benchmark** of `gemini-2.5-pro` vs `gemini-3.6-flash` run under the predeclared protocol above — ground truth, scoring, selection/tie rule, strata, and coverage gaps all written down *before* the comparison, so an independent reader can verify the default follows from the recorded runs. The rejected candidate and the reason are written down.
- **The benchmark corpus is identified before Phase 0 starts** — see *Bootstrapping the dispute corpus*. Phase 0 cannot satisfy its own acceptance without one; the gate is **6 real human-adjudicated disputes** (Q9, resolved 2026-08-11 — corpus was 3/6 at resolution).

**Iterate-review:** YES (rationale: external-vendor integration + a new prompt/schema contract + the data-governance boundary — all load-bearing)
**Status:** not started

### Phase 1 — Disagreement trigger + checkpoint surfacing (~1 day)
**Deliverables:**
- Deterministic trigger on a **`disputed` HIGH** finding — per the disposition table in Approach, explicitly **not** `skipped` and not other un-incorporated states — in both skills' fold path.
- Vote identity + caching keyed on the `(skill, pass, lens_id, finding_index)` namespace plus the canonical-serialization content digest per Approach → Exactly-once votes (finding fields, dispute reasoning, slice content, model, prompt version) — so a re-render or retry reuses the cached vote, and any inference-relevant change is a new one. Cache-miss handling through the **per-key atomic claim** (single writer invokes; waiters read the published result; stale claims recovered per the existing dead-owner discipline).
- Per-pass cap (default 3, configurable) with `vote_not_requested (per-pass cap reached)` surfaced explicitly, capped votes selected in deterministic merged-findings-list order.
- **Multi-vote orchestration:** independent votes fan out concurrently under one pass-level deadline (~one vote budget, per Approach → Wrapper budget); a vote missing the deadline degrades to `unavailable`.
- Surface the vote at the **existing** human checkpoint alongside Codex's finding and Opus's disposition, with confidence inline and the "thin context" caveat on `low`/`low_context`.
- **Write the vote into the pass's HISTORICAL block** (vote, confidence, brief reasoning, model, `unavailable`/`vote_not_requested` state, and a slice *reference* — never the slice contents). This is a distinct write path from the pass-state cache: the cache serves re-renders within a pass, the HISTORICAL record serves calibration across passes. Owning it here, because acceptance requires it and no other phase touches the log.

**Acceptance:**
- Each `disputed` HIGH **within the cap** (selected in deterministic merged-list order) triggers exactly one vote; over-cap disputes carry `vote_not_requested`; `skipped` HIGHs and `disputed` MEDIUMs trigger none — one counting rule, identical here and in the top-level criteria.
- Re-rendering a checkpoint or retrying a pass reuses the cached vote rather than re-invoking Gemini; an edited dispute reasoning, a changed slice, or a model/prompt-version change correctly produces a *new* vote.
- Multiple disputed HIGHs beyond the cap surface `vote_not_requested` visibly; **no finding is dropped** because its vote wasn't requested.
- The pass still presents exactly one checkpoint, and a `disputed` HIGH halts loop mode **regardless of vote outcome** — including `unavailable`.
- The HISTORICAL block carries the vote metadata **and no slice contents**, verifiable by reading the log.
- Confidence renders inline; `confidence: low` **or** `low_context: true` renders the "thin context" caveat, and a normal-confidence vote does not (Q8 resolved).

**Iterate-review:** YES (rationale: touches the fold/checkpoint machinery + the human-arbitration invariant + the Axis 2 loop guardrail)
**Status:** not started

### Phase 2 — Fixtures + live validation (~0.5 day)
**Deliverables:**
- Trigger-routing fixtures across the full disposition matrix: `disputed` HIGH → vote; `skipped` HIGH → **no** vote; `disputed` MEDIUM → no vote; `incorporated` → no vote; `FAILED` lens → no vote.
- Fixtures for surface-not-decide, for `unavailable` still halting loop mode, for cap behaviour **including deterministic over-cap selection** (same merged list → same voted findings on re-render), and for cache reuse vs. cache-miss on edited reasoning, changed slice, and changed model/prompt version.
- A payload-conformance fixture asserting the six-field budget and the ≤ 200-line bound, plus the many-locations boundary case (reference lines counted inside the budget, K sliced locations at ≥ the floor, summary line when references overflow, `low_context: true`, total ≤ 200 held by construction).
- A multi-vote latency fixture: N disputes fan out concurrently and the pass-level deadline degrades stragglers to `unavailable` — the tiebreaker's added wall clock is bounded by one vote budget, not N of them.
- A cache-claim concurrency fixture: simultaneous requests for the same vote key produce **one** external invocation and one shared result; a crashed claimant's stale claim is recovered rather than deadlocking waiters; and the durable side holds too — **one HISTORICAL vote record per disputed finding and one checkpoint for the pass**, concurrent re-renders notwithstanding (the fold-serialization inheritance per Approach → Exactly-once votes).
- A live end-to-end test in **both** skills: a real disputed finding → Gemini vote → checkpoint.

**Acceptance:**
- Every row of the disposition matrix routes correctly.
- No code path changes a verdict or a disposition based on the vote — asserted, not asserted-in-prose.
- Live test produces a coherent third opinion in both `iterate-plan` and `iterate-review`.

**Iterate-review:** YES (rationale: the E2E-analog; validates the trigger matrix + the no-auto-decide invariant)
**Status:** not started

## Acceptance criteria

- [ ] Every **`disputed`** HIGH finding (in either skill) is surfaced at the checkpoint, and **each of the deterministically selected findings within the per-pass cap requests exactly one schema-valid Gemini vote**; disputes beyond the cap carry the explicit `vote_not_requested` state — never a duplicate vote, never a silent omission. `skipped` HIGHs, `disputed` MEDIUM/LOWs, `incorporated` findings, and `FAILED` lenses trigger none.
- [ ] The vote is surfaced at the human checkpoint and **never** auto-resolves the dispute, changes a verdict, or alters a disposition.
- [ ] Gemini unavailability degrades to `unavailable`; **the checkpoint still renders, and a `disputed` HIGH still halts loop mode.** "Doesn't block the pass" means the checkpoint is reached, never that it is skipped.
- [ ] The vote payload contains **exactly** the six permitted fields, with the slice **≤ 200 lines**, and no prohibited field (full plan, full diff, uncited files, repo metadata, pass log). Verifiable by reading a payload.
- [ ] A finding whose location cannot be narrowed yields a bounded slice with `low_context: true` — never a whole-artefact payload.
- [ ] Vote identity is stable: a re-render or retry reuses the cached vote; an edited dispute reasoning, changed slice, or model/prompt-version change produces a new one. The identity digest is a canonical structured serialization, identical across both skills.
- [ ] The per-pass cap (default 3) surfaces `vote_not_requested` explicitly and **never drops a finding**.
- [ ] Reuses the Axis 2 between-pass scaffold; **exactly one** human checkpoint per pass, unchanged.
- [ ] The checkpoint shows the vote's confidence inline, and renders the "thin context" caveat exactly when `confidence: low` or `low_context: true` — not on every vote.
- [ ] The wrapper bounds itself at 30s per attempt with one retry, and multiple votes fan out concurrently under a pass-level deadline of one vote budget — so the tiebreaker adds at most ~60s to a pass **regardless of dispute count**, before degrading to `unavailable`.
- [ ] The tiebreaker vote is recorded durably in the HISTORICAL block (vote, confidence, brief reasoning, model, `unavailable`/`vote_not_requested` state, slice reference) so agreement rates can be calibrated later.
- [ ] `TIEBREAKER_MODEL` is configuration; the shipped default is a **stable** model and the benchmark behind the choice is recorded **under a predeclared protocol** (ground truth, scoring, selection/tie rule, strata, disclosed coverage gaps) so the choice is independently verifiable.
- [ ] The checkpoint and HISTORICAL record frame the vote as an **assessment of the dispute reasoning over supplied evidence** — never as independent verification of external facts (see Approach → What the vote adjudicates).
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

### R6 — The trigger may never fire (premise risk) — **materially reduced 2026-08-11**

Axis 1 assumes Opus⇄Codex disputes are "rare and high-signal." Measured at parking time (2026-07-28) over this repo's recorded history — 22 folded findings — clean `disputed` dispositions numbered **zero**, with 2 partial disputes.

**Update 2026-08-11:** the trigger has now fired **3 times on real code reviews** (see Approach → Bootstrapping for the list), at roughly one disputed HIGH per major multi-pass review. All three were Kyle-ratified, all matched the predicted diff-invisible-constraint pattern, and each needed external evidence to arbitrate. *Rare* and *non-zero* are both now confirmed; **high-signal** held in all three observed cases (each dispute was correct). The residual risk is no longer "the event never occurs" but "the corpus accumulates too slowly for Phase 0's benchmark" — which is exactly Q9's fallback question.

**Mitigation:** unchanged in kind — measure before building. Continue accumulating dispositions from real code reviews (each major review has produced ~1); Phase 0 is gated on the corpus reaching **6 real disputes** (Q9, resolved 2026-08-11). The original confounders (author-reviewed prose repo; Opus selecting dispositions and writing the log) are partially retired: the three observed disputes came from code reviews where the reviewer genuinely lacked context, and all three dispositions were confirmed by the human checkpoint.

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

- **Q9.** (resolved by Kyle 2026-08-11 — **option 1: keep accumulating from real reviews; the plan stays parked meanwhile.** Thresholds adopted from the lens consensus (re-affirmed unchanged across passes 3–7 by both lenses): **6 real human-adjudicated disputes unlocks Phase 0 with a *provisional* model benchmark; a re-benchmark at 10 is precommitted here, before any model results exist.** Both adjudication directions and both skills should be represented where feasible; a missing stratum is disclosed in the recorded result, never manufactured. Synthetic disputes may exercise mechanics but never enter the scored corpus. Kyle's stated rationale: the trigger is rare in practice — the skill's defining property — so the right posture is parked-but-ready while normal work grows the corpus (~1 disputed HIGH per major multi-pass review; corpus was 3/6 at resolution time). Raised by `architect` in pass 2; settled against live data rather than in the abstract.)

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

## Codex review pass 3 — answers (2026-08-11) [HISTORICAL]

First pass under the Phase 3 runner machinery (`bin/run-pass`, deterministic
composition, staged `--note` carrying the editor's corpus update) — and the
**iterate-plan dogfood run**: zero Bash permission prompts under the single
allowlist rule. `architect` + `product-manager` concurrent; 7 findings filed →
**7 merged** (no overlaps); 6 corrections filed → **3 merged** (both lenses
independently hit all three staleness contradictions); both lenses answered Q9,
in agreement.

### Verdict
**REVISE** (worst-of: architect REVISE / product-manager REVISE; no FAILED lenses)

### Findings

1. **Slice allocation rule can exceed the governance ceiling** — HIGH · lens: architect: floor-20 × >10 cited locations is mathematically incompatible with the 200-line ceiling; no rule said which constraint yields.
   → Opus: incorporated — new rule 2: >10 locations slices the first 10 in citation order, remaining locations included as one-line references (never content), `low_context: true`; ceiling and floor both hold. Boundary fixture added to Phase 2.
2. **Cache identity omits inputs that can change the vote** — HIGH · lens: architect: the key excluded slice content, artefact revision, model, and prompt version — a re-render after any of those changed could reuse a vote generated from materially different evidence.
   → Opus: incorporated — identity is now namespace + canonical-serialization digest over finding fields, dispute reasoning, slice content, `low_context`, resolved model, and prompt version: reuse iff Gemini would see byte-identical input under the same configuration.
3. **The proposed evidence boundary cannot arbitrate key motivating disputes** — HIGH · lens: architect: all three real disputes were settled by evidence *outside* any permissible slice (interpreter run, POSIX semantics, plan history); the payload prohibits it and the wrapper retrieves nothing, so Gemini cannot independently verify — it can only assess Opus's account.
   → Opus: incorporated — new Approach section *What the vote adjudicates — the reasoning, not the world*: the vote is adjudication over supplied evidence, framed as such at the checkpoint and in HISTORICAL (new acceptance criterion); the Phase 0 benchmark stratifies slice-resolvable vs externally-evidenced disputes; bounded evidence attachment noted as v2. The honest role, not the inflated one.
4. **Model-selection benchmark has no verifiable decision rule** — HIGH · lens: product-manager: acceptance required "chosen from a recorded benchmark" with no ground truth, scoring, or selection rule — and the current 3-dispute corpus is one-sided (all upheld), so a recorded run could satisfy the wording while showing nothing.
   → Opus: incorporated — Phase 0 gains a predeclared written protocol: ground truth = human-ratified outcomes; agreement score with confidence calibration as tie dimension; predeclared selection/tie rule; per-stratum reporting; coverage gaps disclosed and the benchmark labeled provisional until both directions/skills are represented.
5. **Over-cap vote selection is not deterministic** — MEDIUM · lens: architect: with >3 disputed HIGHs, which three got votes depended on traversal order.
   → Opus: incorporated — capped votes go to the first N disputed HIGHs in merged-findings-list order (the order HISTORICAL records); Phase 2 fixture asserts same list → same selection.
6. **Finding payload concatenation is not a canonical encoding** — MEDIUM · lens: architect: bare concatenation of four fields is collision-prone and separator-dependent across two implementations.
   → Opus: incorporated — folded into the same identity rewrite as finding 2: sorted-key UTF-8 JSON with named fields, shared across both skills. (Kept as a distinct finding: 2 is key *coverage*, this is key *encoding* — one shared fix.)
7. **One-checkpoint resolution is promised but not measured** — MEDIUM · lens: product-manager: the use cases' success statement ("resolved in one checkpoint") had no acceptance condition observing it.
   → Opus: incorporated — classified with error-direction reduction as a calibrate-over-time outcome (the existing scope note now covers both), measurable from the HISTORICAL record via dispute recurrence across passes.

### Plan corrections applied

All three co-reported by both lenses — deduped to one application each (the same staleness my pre-pass corpus update left at the edges):

- **Approach → Bootstrapping, opening**: "corpus does not exist yet" → exists but small (3, below Q9 threshold).
- **Phase 0 acceptance, corpus bullet**: "does not currently exist" → 3 disputes, gated on Q9.
- **Parked banner → Why parked**: present-tense empty-corpus rationale → explicitly marked as the original 2026-07-28 rationale; the live gate is the Q9 threshold.

### Open-question answers

1. **Q9** — both lenses answered, independently converging (architect from corpus-diversity grounds, PM from benchmark-integrity grounds): ≥ 6 real disputes for a provisional benchmark, ~10 for a calibrated one; both adjudication directions and both skills represented where feasible, gaps disclosed; synthetics never in the scored corpus; corpus=3 start acceptable only with a predeclared re-benchmark threshold. Recorded in Q9 as the lens consensus; **the threshold number remains Kyle's call — Q9 stays open, needs_human.**

### New questions Codex raised

- (none)

### Lens run summary

- architect: REVISE · product-manager: REVISE

### Merge notes (pass 3)

7 filed → 7 merged (lane-unique; findings 2 and 6 share one fix but assert different defects — coverage vs encoding — and were kept separate, same discipline as pass 1's 4/5 and 6/7). The correction dedupe fired on all three corrections — both lenses independently filed identical staleness fixes, and mechanical double-application was avoided. This pass also exercised the editor-note path: the corpus update was flagged to both lenses via the staged note rather than left for them to diff.

### Convergence status

Verdicts: REVISE (1H 2M 1L) → REVISE (4H 3M). Merged HIGH+MEDIUM count **3 → 7** — an *increase*, expected rather than alarming: 14 days elapsed since pass 2, the corpus premise inverted (0 → 3 real disputes), and this pass reviewed sections (the update blocks, the adjudication boundary) that did not exist at pass 2. One non-decreasing transition is on the stall counter; a second consecutive one would halt the loop. Q9 remains open (needs_human, pre-existing — does not halt the loop; no *new* needs_human question survived this fold).

## Codex review pass 4 — answers (2026-08-11) [HISTORICAL]

`architect` + `product-manager` concurrent via `bin/run-pass`; 2 findings filed →
**2 merged**; 0 corrections; both lenses re-answered Q9, re-affirming the pass-3
consensus. **The product-manager lane reached APPROVE** — both its pass-3
findings (benchmark protocol, outcome-claim scoping) are satisfied by the folds.
Both remaining findings target defects in pass 3's own folds — the consistency
frontier working as observed in prior reviews.

### Verdict
**REVISE** (worst-of: architect REVISE / product-manager **APPROVE**; no FAILED lenses)

### Findings

1. **Over-ten-location rule still exceeds the 200-line payload ceiling** — HIGH · lens: architect: pass 3's rule gave the first 10 locations the full 200 lines *and* put one reference line per remaining location into `slice` (the only field they can live in), so any 11th location overflowed the bound the rule claimed to hold.
   → Opus: incorporated — the budget partition now counts reference lines first (≤ 20 references + a summary line when even those overflow), then splits the remainder across K = min(10, ⌊remaining/20⌋) sliced locations; total ≤ 200 holds by construction. Phase 2's boundary fixture re-specified to assert the accounting.
2. **Per-finding retries can make the pass latency three times the stated bound** — HIGH · lens: architect: three sequential votes at 30s + retry ≈ 180s against the claimed ~60s, and no phase owned multi-vote execution.
   → Opus: incorporated — votes now fan out concurrently under a pass-level deadline of one vote budget (~60s), stragglers degrade to `unavailable`; orchestration explicitly owned by Phase 1; acceptance criterion updated to "at most ~60s regardless of dispute count"; multi-vote latency fixture added to Phase 2.

### Plan corrections applied

- (none filed)

### Open-question answers

1. **Q9** — both lenses re-affirmed the pass-3 consensus unchanged (≥ 6 real for provisional, predeclared re-benchmark at ~10, synthetics never scored, corpus=3 acceptable only as explicitly provisional with the threshold committed before results are examined). **Still Kyle's call; remains open.**

### New questions Codex raised

- (none)

### Lens run summary

- architect: REVISE · product-manager: **APPROVE**

### Convergence status

Verdicts: REVISE (4H 3M) → REVISE (2H). Merged HIGH+MEDIUM count **7 → 2**, strictly decreasing — the stall counter resets. PM lane satisfied; both open items were introduced by pass 3's folds and are now closed. Not converged: two HIGHs folded this pass.

## Codex review pass 5 — answers (2026-08-11) [HISTORICAL]

`architect` + `product-manager` concurrent via `bin/run-pass`; 1 finding filed →
**1 merged**; 0 corrections; both lenses re-affirmed the Q9 consensus a third
time. Product-manager APPROVE for the second consecutive pass.

### Verdict
**REVISE** (worst-of: architect REVISE / product-manager **APPROVE**; no FAILED lenses)

### Findings

1. **Phase 0 still requires ten slices when the budget permits fewer** — HIGH · lens: architect: pass 4's fold fixed the Approach algorithm (budget-derived K) but left Phase 0's acceptance bullet saying "slices the first 10", and described reference allocation in terms of an unsliced set that itself depends on K — circular at the implementation boundary.
   → Opus: incorporated — the slice rule now defines `refs(K)` explicitly and picks **the largest K ≤ 10 with `20·K + refs(K) ≤ 200`** (monotone feasibility, K = 8 always fits — non-circular and total); Phase 0's acceptance bullet re-aligned to the budget-derived K rule.

### Plan corrections applied

- (none filed)

### Open-question answers

1. **Q9** — consensus re-affirmed unchanged by both lenses (third consecutive pass): ≥ 6 real for provisional, precommitted re-benchmark at ~10, synthetics never scored, corpus=3 start only as explicitly provisional. **Remains open — Kyle's call.**

### New questions Codex raised

- (none)

### Lens run summary

- architect: REVISE · product-manager: **APPROVE**

### Convergence status

Verdicts: REVISE (2H) → REVISE (1H). Merged HIGH+MEDIUM count **2 → 1**, strictly decreasing. The finding stream has narrowed to single-defect consistency checks on the previous pass's own fold — the converging tail. Not converged: one HIGH folded this pass.

## Codex review pass 6 — answers (2026-08-11) [HISTORICAL]

`architect` + `product-manager` concurrent via `bin/run-pass`; 1 finding filed →
**1 merged**; 0 corrections. **The lanes swapped: architect APPROVE** (its
frontier is exhausted), product-manager REVISE with an acceptance-consistency
catch. Q9 consensus re-affirmed by both lenses, fourth consecutive pass.

### Verdict
**REVISE** (worst-of: architect **APPROVE** / product-manager REVISE; no FAILED lenses)

### Findings

1. **Exactly-one vote criterion contradicts the per-pass cap** — HIGH · lens: product-manager: the top-level criterion promised "exactly one vote per disputed finding" unconditionally while the cap criterion permits `vote_not_requested` beyond 3; Phase 1 acceptance repeated it. With 4+ disputes in a pass, a verifier cannot satisfy both — re-opening the ambiguity pass 1's finding 7 closed.
   → Opus: incorporated — one counting rule, stated identically in both places: every disputed HIGH is *surfaced*; each of the deterministically selected findings **within the cap** requests exactly one vote; over-cap disputes carry the explicit `vote_not_requested` state — never a duplicate vote, never a silent omission.

### Plan corrections applied

- (none filed)

### Open-question answers

1. **Q9** — consensus re-affirmed unchanged by both lenses (fourth consecutive pass). **Remains open — Kyle's call.**

### New questions Codex raised

- (none)

### Lens run summary

- architect: **APPROVE** · product-manager: REVISE

### Convergence status

Verdicts: REVISE (1H) → REVISE (1H). Merged HIGH+MEDIUM count **1 → 1** — one non-decreasing transition on the stall counter (a second consecutive one halts the loop). Both lanes have now individually reached APPROVE at least once; the remaining churn is single-finding consistency polish. One HIGH folded this pass.

## Codex review pass 7 — answers (2026-08-11) [HISTORICAL]

`architect` + `product-manager` concurrent via `bin/run-pass`; 1 finding filed →
**1 merged**; 0 corrections. Lanes alternated again: product-manager APPROVE
(second consecutive), architect REVISE with a concurrency-correctness catch on
the cache design. Q9 consensus re-affirmed, fifth consecutive pass.

### Verdict
**REVISE** (worst-of: architect REVISE / product-manager **APPROVE**; no FAILED lenses)

### Findings

1. **Cache lookup alone does not guarantee exactly-once invocation** — HIGH · lens: architect: a deterministic key + cached result defines reuse but not *creation ownership* — two concurrent renders/retries can both miss and both invoke Gemini, breaking exactly-once and (on differing responses) making the cached/HISTORICAL record nondeterministic; the new concurrent fan-out raises the stakes.
   → Opus: incorporated — cache-miss handling is now single-writer via a **per-key atomic claim** (`O_CREAT|O_EXCL` claim file, the same primitive and dead-owner reclaim discipline the runner scope lock uses); only the claimant invokes, publishes atomically; waiters read the published vote. Phase 1 owns it; Phase 2 gains a concurrency fixture (simultaneous requests → one invocation, one shared result; stale claims recovered).

### Plan corrections applied

- (none filed)

### Open-question answers

1. **Q9** — consensus re-affirmed unchanged by both lenses (fifth consecutive pass). **Remains open — Kyle's call.**

### New questions Codex raised

- (none)

### Lens run summary

- architect: REVISE · product-manager: **APPROVE**

### Convergence status

Verdicts: REVISE (1H) → REVISE (1H). Merged HIGH+MEDIUM count **1 → 1 → 1** across the last two transitions — **the non-convergence guardrail fires and the loop halts here.** Read honestly, this is a trickle rather than a deadlock: each pass closed its predecessor's single finding and a *different* single-defect polish item surfaced, with the two lanes alternating APPROVE (PM approved passes 4, 5, and 7 — by count; architect approved pass 6). Every finding since pass 3 has targeted a fold from the pass before it, never the original design. The loop's five folded passes this activation: 7 HIGH+MED → 2 → 1 → 1 → 1, all incorporated, none disputed. **Q9 remains the sole open question (needs_human) and blocks Phase 0 regardless of convergence.**

## Codex review pass 8 — answers (2026-08-11) [HISTORICAL]

Manual single-pass continue after the stall-guardrail halt, at Kyle's
checkpoint direction. **Q9 was resolved by Kyle before this pass** (option 1 —
stay parked, accumulate; unpark at 6 real disputes, provisional benchmark;
re-benchmark precommitted at 10; synthetics never scored) and folded into the
banner, Bootstrapping, R6, Phase 0, and Open questions. `architect` +
`product-manager` concurrent via `bin/run-pass`; 1 finding filed → **1 merged**;
0 corrections; no open questions remain, and none were raised.

### Verdict
**REVISE** (worst-of: architect REVISE / product-manager **APPROVE**; no FAILED lenses)

### Findings

1. **Vote claim does not make HISTORICAL publication exactly-once** — HIGH · lens: architect: the single-writer claim covers vendor invocation, but checkpoint/HISTORICAL publication sits outside it, so concurrent renders could append duplicate vote records; the Phase 2 fixture asserted one invocation, not one durable record.
   → Opus: incorporated, with a corrected premise recorded: in this architecture the HISTORICAL writer is the **model's fold step**, already serialized by Axis 2's exactly-one-HISTORICAL-block-per-pass invariant — the runner and cache never write the log, so no second ownership mechanism exists to build. The plan now *states* that inheritance explicitly (the finding's own suggested action anticipated it: "reusing an existing serialized fold/checkpoint transaction if one exists" — it exists), and the Phase 2 concurrency fixture is extended to assert the durable side: one vote record per disputed finding, one checkpoint, under concurrent re-renders. The defect was a real documentation gap; the concurrency scenario it inferred was not reachable.

### Plan corrections applied

- (none filed)

### Open-question answers

- (none open — Q9 resolved by Kyle at the preceding checkpoint; recorded inline in Open questions)

### New questions Codex raised

- (none)

### Lens run summary

- architect: REVISE · product-manager: **APPROVE**

### Convergence status

Verdicts: REVISE (1H) → REVISE (1H). The count is flat but the substance has narrowed to stating an existing invariant the reviewer could not see from the plan alone — the closest this review has come to a dispute-shaped finding, resolved by documentation rather than disagreement. All open questions are now closed. Checkpoint presented to Kyle with the loop's full trail: passes 3–8, 14 findings folded, 0 disputed, PM APPROVE in 4 of the last 5 passes, architect APPROVE at pass 6.
