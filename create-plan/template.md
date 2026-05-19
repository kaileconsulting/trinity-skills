# <Initiative Name> — Plan

<!--
=========================================================================
PLAN TEMPLATE — created by the `create-plan` skill, reviewed by
`iterate-plan` (Codex), implementation reviewed per-phase by
`iterate-review` (Codex).

Section legend:
  REQUIRED         — every plan must have this section.
  RECOMMENDED      — include when relevant; remove if it doesn't apply.
  TOOLING-RESERVED — auto-managed by iterate-plan / iterate-review;
                     leave the stub in place and let the tools fill it.

Remove all <!-- comment --> blocks and this header before committing.
=========================================================================
-->

## TL;DR

<!-- REQUIRED. 1-3 short paragraphs. Lead with what we're doing and why,
then the core approach, then the expected outcome. A reader should be
able to stop after this section and have a correct mental model of the
plan. -->

## Why / Context

<!-- REQUIRED. The motivation. What problem are we solving? What evidence
makes this worth doing now? For fixes: cite the bug, the report, the
failing case. For initiatives: cite the strategic driver, the user feedback,
the business need.

Small plans (one-line bug fix, narrow audit): merge with TL;DR or keep
to one paragraph.
Larger initiatives: separate into "## Why" and "## Who / Use cases" H2s. -->

## Who / Use cases

<!-- REQUIRED. Who is this for? Named consumers, stakeholders, or
scenarios that drive the design.

Fix-style example: "Closes <stakeholder> feedback ticket — TRUE-row
gap on PI attribution."

Initiative-style example: list 2-5 named use cases with the user/persona
+ the workflow + the success condition. -->

## Goals (MVP)

<!-- RECOMMENDED for initiatives. Bulleted list of what we ARE delivering
in this scope. Make each goal verifiable. Skip for small fix plans. -->

## Non-goals (MVP)

<!-- RECOMMENDED for initiatives. Bulleted list of what we are NOT
delivering, with one-line rationale each. Prevents scope creep mid-plan.
Skip for small fix plans (use "Out of scope" at the bottom instead). -->

## Current state — evidence from production

<!-- RECOMMENDED for fixes / audits / debugging plans. Concrete production
evidence: SQL output, log excerpts, before/after counts, screenshots.
This is what the reviewer trusts; speculation lives elsewhere. Cite
specific row counts, timestamps, file:line references. -->

## Root cause

<!-- RECOMMENDED for fix-style plans. Where the bug is (file:line),
why it's a bug, and why prior comments / mitigations don't justify it.
Distinguish "we know exactly why" from "we have a strong hypothesis."
If hypothesis: list the disconfirming evidence we'd need to see. -->

## Approach

<!-- REQUIRED. The technical proposal. Sub-sections vary by plan type;
use whichever apply: -->

### Architecture
<!-- RECOMMENDED for builds. Component diagram (ASCII or Mermaid),
data flow, portability principles. -->

### Stack decisions
<!-- RECOMMENDED for builds with non-trivial tech choices. Each decision
gets one short paragraph: choice + rationale + alternatives considered. -->

### Proposed design
<!-- For fix-style plans, the design is usually one section: what's
changing, where, and why this fix is correct. Cite file:line. -->

### Repo layout
<!-- RECOMMENDED for new codebases / new top-level directories. Tree
diagram of new files + brief purpose for each. -->

## Phasing

<!-- REQUIRED for multi-track / multi-day work. Use this section name
("## Phasing") with "### Phase 0/1/2/.../N" sub-sections. Skip this
section entirely for single-track work and use "## Step-by-step plan"
instead.

Each phase has: rough wall-clock estimate, deliverables list, per-phase
acceptance criteria, an explicit Iterate-review marker, and a Status
field (see below).

The Iterate-review marker is load-bearing — it tells the iterate-review
skill which phases to run a Codex code-review pass on. Set deliberately
at planning time, not "we'll figure it out later."

The Status field is auto-maintained by iterate-review (`not started` →
`in progress` → `reviewed` → `shipped`). Author leaves it at `not started`;
iterate-review updates it on each phase APPROVE. Manual override allowed
when iterate-review didn't run (NO-marked phases ship straight to
`shipped` when their commits land).

**iterate-review v1 note (until v2 ships):** v1 is standalone-only and
does NOT auto-update the Status field or the `## Review checkpoints`
table. In v1, the author manually invokes iterate-review against a phase's
shipped diff (e.g., `iterate-review --scope=branch` or
`iterate-review --scope=pr:<n>`) and updates `**Status:**` + the Review
checkpoints table by hand based on the resulting pass log. v2 will
automate this with `--plan=<path> --phase=N` flags. -->

### Phase 0 — Foundations (~estimate)
**Deliverables:**
- ...

**Acceptance:**
- ...

**Iterate-review:** NO (rationale: e.g., "doc/setup-only, no code to review")
**Status:** not started

### Phase 1 — <Name> (~estimate)
**Deliverables:**
- ...

**Acceptance:**
- ...

**Iterate-review:** YES (rationale: e.g., "security model lands here; later phases depend on correctness")
**Status:** not started

### Phase 2 — <Name> (~estimate)
**Deliverables:**
- ...

**Acceptance:**
- ...

**Iterate-review:** CONDITIONAL (rationale: e.g., "review only if migration touches new tables")
**Status:** not started

<!-- Add Phase 3, 4, 5... as needed. -->

## Step-by-step plan

<!-- REQUIRED for single-track / session-scope work (use INSTEAD of
"## Phasing", not in addition). "### Step 1/2/3..." sub-sections with
wall-clock estimates and explicit deliverables. Iterate-review usually
runs once at the end (or not at all) on a small step plan; per-step
markers aren't required.

Each step has a Status field (`not started` → `in progress` → `shipped`).
Author leaves it at `not started`; updated as work progresses. -->

### Step 1 — <Name> (~estimate)
**Status:** not started

- ...

### Step 2 — <Name> (~estimate)
**Status:** not started

- ...

## Acceptance criteria

<!-- REQUIRED. End-of-plan ship-readiness criteria — verifiable conditions
that must be true before we declare the plan done. For multi-phase plans,
this section summarizes ship readiness; per-phase acceptance lives under
each Phase heading above. -->

- [ ] ...
- [ ] ...

## Risks

<!-- REQUIRED. Numbered R1, R2, ... Each risk: what could go wrong,
likelihood/severity, and concrete mitigation. -->

### R1 — <Risk Name>
**Mitigation:** ...

### R2 — <Risk Name>
**Mitigation:** ...

## Rollback plan

<!-- RECOMMENDED for higher-risk changes — anything touching prod data,
auth, schema, or shared infra. Concrete rollback path: what command,
what state we revert to, what side-effects need cleanup. -->

## Sequencing decision

<!-- RECOMMENDED when this plan's order relative to other in-flight
work matters. Why now, why not after X, what blocks what. -->

## Open questions

<!-- REQUIRED. Use Q-numbers (Q1, Q2, Q3, ...). The iterate-plan reviewer
expects this exact shape — its `question_id` field references "Q1", "Q2",
etc. If you have no open questions at plan-creation time, leave the
section with "(none at this time)" — iterate-plan may still raise new
questions which Opus will fold in here as Q-numbered items. -->

- **Q1.** ...
- **Q2.** ...

## Out of scope

<!-- REQUIRED. Explicit non-goals — things a reviewer might reasonably
ask "why aren't we doing X" about. One-line rationale per item. -->

- ...
- ...

## Execution defaults

<!-- RECOMMENDED for one-shot risky operations (migrations, fleet-wide
data changes, etc.). Pre-flight settings that should be locked before
the human runs anything: dry-run-first defaults, batch sizes, timeout
values, abort thresholds. -->

## Closeout

<!-- REQUIRED. Checklist of cleanup actions to run when the plan fully
ships and acceptance criteria are met. Forces clean handoff so a future
session (yours or someone else's) can tell at a glance whether this work
is done. The point isn't bureaucracy — it's that mid-stream timeouts and
context-switch resumes are common, and a half-archived plan is worse
than no archive at all.

Run in order; check items off as completed. The final "move plan to
archive" step is the canonical "this plan is done" signal. -->

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

<!-- REQUIRED. Links to memory files, prior plans, code locations,
external docs, feedback transcripts. -->

- ...

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

## Pre-flight review pass (Opus, YYYY-MM-DD) [HISTORICAL]

<!-- OPTIONAL self-review by Opus before execution. Useful as a final
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
