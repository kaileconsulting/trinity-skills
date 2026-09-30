# Review-Diff Exclusions — Plan

## TL;DR

`iterate-review` sends every lens the whole diff, "unchanged" (step 9). On a long branch, that diff routinely carries content the reviewer doesn't need: the review's **own pass log**, which already arrives a second time as `=== PRIOR PASSES ===`; **lockfiles and generated files**, which a line-by-line reviewer can't meaningfully read; and a **converged governing plan** the review treats as its spec. Each lens re-sends that input across several file-reading turns, so it is the main cost against the reviewer's usage limit. On 2026-09-29 a three-lens pass on a ~3,300-line branch cost 25–50% of a ChatGPT Plus 5-hour window, and two parallel projects exhausted a fresh window in about 40 minutes.

This plan makes two exclusions first-class, with the runner applying both and disclosing both mechanically: (Phase 0) the runner always drops the pass log's own file from the composed diff, which removes nothing from review; (Phase 1) the editor may name further paths to exclude, by class, and the runner refuses any exclusion that would take reviewable production code out of review without the disclosure and summary its class requires. Closes [issue #10](https://github.com/kaileconsulting/trinity-skills/issues/10).

Expected outcome: 20–35% less input per lens on plan-driven branches (estimate, see §Why), with every exclusion visible in the pass header and the pass summary.

## Why / Context

**The measurement (2026-09-29, from `~/.codex/sessions` token events).** Per-lens input on the simplification-gate review: 330–510k tokens per call (the composed input is ~80k; the rest is Codex re-sending context across its file reads, mostly cached but still counted). A three-lens pass cost 25–50% of a 5-hour window; a two-lens `iterate-plan` pass cost 10–13%. Reasoning effort (`high`) is under 1% of tokens, so lowering effort doesn't save quota; input volume does.

**What was in that diff.** Of the branch diff at pass 4: pass log 130 lines, plan + handoff 524, fixtures/examples 1,036, SKILL.md 802, tools 791. The pass log and the plan (654 lines, ~20% of the diff) were redundant or settled. *Assumption to challenge:* the savings estimate scales that ~20% by the diff's share of per-lens input (large, but below 100%, since prior passes and file reads also count), giving the 20–35% range above. It is an estimate; the pass summaries' recorded line counts (§1) are the check.

**Practice is already ahead of the skill.** ResearchLogix_v2 reviews excluded content by hand and recorded it in the pass header: "docs/ excluded" (8 passes across two testing-suite branches), "plan doc, builder brief and this log excluded" (CSRF hardening), and "lockfiles excluded, summarised" (a dependabot cleanup, with the lockfile audit written into the intent: every npm `resolved` checked against the registry, every composer `dist.url` against GitHub). Every one of those broke step 9's "unchanged" rule, and nothing written said what is safe to drop. The dependabot case matters most: a lockfile is **production** under this skill's own path heuristic, and the review still wanted it out of the line-by-line diff. A rule of "never exclude production paths" would have forbidden the most careful exclusion in the record.

**Why this is a trust boundary.** Excluding code from the reviewed diff is a way of suppressing findings. Today it happens silently, by hand. The point of making it first-class is less the savings than making every exclusion mechanical, bounded and visible.

## Who / Use cases

- **Kyle, running reviews across several repos on one shared quota.** Fewer passes lost to the limit mid-loop; the pass header says exactly what the reviewer didn't see.
- **The editor session running a long, plan-driven branch review.** It stops hand-editing the diff file; the runner does it and records it.
- **Downstream builders (ResearchLogix_v2, query-iq).** They get the savings through the skill rather than a playbook convention, and a lockfile-heavy review has a defined, disclosed path.
- **A later reader of a pass log.** "What didn't the reviewer see, and why?" is answered by the pass header and `pass-N.summary.json`, not by reconstructing it from commit history.

## Risk posture

### Full variant (initiatives)

#### PF-audience — Audience & reach

Kyle as the single operator, plus every Claude/Codex session running trinity reviews across his repos (ResearchLogix_v2, query-iq, doc-bot). The installed skills are symlinks to this repo's checked-out branch, so a change reaches every project at once. The repo is public; external readers are passive consumers.

#### PF-blast — Blast radius & recoverability

A defect either wastes quota (harmless: today's behavior) or silently drops reviewable code from review (the dangerous case). Both revert with git, but in the dangerous case unreviewed defects may already have shipped downstream before anyone notices.

#### PF-shipbar — Ship bar

Any path by which a production file leaves the reviewed diff without being disclosed in the pass header blocks ship, as does any change to input composition not pinned by the golden fixtures (composition is byte-deterministic by contract). This is the trust boundary: excluding code from review is a way of suppressing findings, and full rigor applies to it regardless of posture. Estimates of the token savings, and the wording of disclosures, can ship with logged accepted risks.

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

- The runner drops the review's own pass log from the composed diff on every pass, with no flag, and records it in the pass summary.
- The editor can exclude further paths by passing them to the runner **with a class**; the runner applies the class's rule, refuses what the rule forbids, and records every exclusion in the pass summary.
- Every exclusion appears in the pass header's `Scope:` line, copied from the summary.
- Composition stays byte-deterministic; goldens pin the excluded forms.
- `tools/scope_classifier.py` and the runner's refusal logic apply the same heuristic, pinned so they cannot drift.

## Non-goals (MVP)

- **No automatic exclusion beyond the pass log.** Every other exclusion is the editor's named, classed decision.
- **No lens trimming.** Lens choice goes both ways in practice (qa was *forced on* for a whole ResearchLogix review); `--lenses` stays the manual override.
- **No reading the reviewer's usage-limit state.** It lives in Codex's private session-log format, which could change with any release.
- **No `iterate-plan` change.** Its input is the plan itself; nothing to exclude (see Out of scope for its growing-history cost).

## Approach

### §1 Pass-log self-exclusion (runner, Phase 0)

`run-pass` / `run-lens` already resolve the pass-log path (`resolve_log_path()`). Before composing, the runner parses the diff into per-file sections (`diff --git a/<p> b/<p>` boundaries) and drops any section whose old or new path, resolved against the repo root, equals the pass log. It changes nothing else: prior passes still arrive via `=== PRIOR PASSES ===`, so nothing leaves review. The summary gains `excluded: [{"path", "class": "pass-log", "lines"}]`. A diff that is *only* the pass log after exclusion is treated like an empty diff (the review has nothing to review), not composed as an empty `=== DIFF ===`.

### §2 Classed editor exclusions (runner-applied, Phase 1)

The editor passes `--exclude <class>:<path-or-glob>` (repeatable) to `run-pass` / `run-lens`. **Load-bearing decision to challenge:** exclusions are applied by the runner, not by the editor editing the diff file. That makes disclosure mechanical (the summary records what was actually removed, with line counts) and lets the refusal be enforced in code rather than prose. Classes:

| Class | May exclude | Requires | Refused when |
|---|---|---|---|
| `governing-plan` | the plan named in the intent as the review's spec | the intent names it | the path is production under the heuristic |
| `docs` | documentation paths | nothing further | the path is production under the heuristic |
| `generated` | lockfiles and generated files | an `=== EXCLUDED SUMMARY ===` block in the intent describing what the editor audited (the ResearchLogix dependabot precedent) | the summary block is absent or names no audited property |

The refusal is fail-closed: an unknown class, a glob matching nothing, or a `governing-plan`/`docs` path the heuristic calls production exits non-zero before fan-out, like any other runner contract violation. The heuristic is step 3's production/non-production rule; because the runner can't import `tools/` in a copied install, it carries its own copy in `bin/`, and a checker asserts it agrees with `tools/scope_classifier.py` on every fixture (the same dev-side-pin pattern as the cluster threshold in 2.5.0).

### §3 Disclosure

Step 12's header template gains the exclusions in `Scope:`, e.g. `branch (excluded: pass-log 130 lines; governing-plan docs/x.md 498 lines)`, copied from the summary's `excluded` array, never written from memory. Step 9's "unchanged" rule is rewritten to "unchanged except for runner-applied exclusions, each recorded in the summary and the pass header."

### Repo layout

Modified: `iterate-review/bin/review_runner.py` (diff sectioning + exclusion + summary field), `iterate-review/bin/run-pass`, `iterate-review/bin/run-lens` (flags), `iterate-review/SKILL.md` (steps 9, 10, 12, Hard rules), `tools/check-runners.py`, composition goldens under `iterate-review/examples/composition/`. New: a `bin/` copy of the path heuristic and a checker pinning it to `tools/scope_classifier.py`. `iterate-plan` untouched.

## Phasing

### Phase 0 — Runner self-exclusion of the pass log (~2h)
**Deliverables:**
- Diff sectioning + pass-log exclusion in `review_runner.py` (§1), applied by both `run-pass` and `run-lens`.
- `excluded` array in `pass-N.summary.json` and in `run-lens` output.
- Composition golden: a diff containing the pass log composes byte-identically to the same diff without it. A pass-log-only diff exits as "nothing to review".
- SKILL.md step 9's "unchanged" rule rewritten (§3); step 12's `Scope:` header shows the exclusion.

**Acceptance:**
- `tools/check-all.sh` green, including new `check-runners.py` cases: log section dropped (added, modified, renamed-into and renamed-out-of the log path), unrelated sections untouched, summary records path and line count.
- Replaying the simplification-gate branch's pass-4 diff through the new runner drops exactly the 130-line log section.

**Iterate-review:** YES (rationale: changes the runner's input composition, whose byte-determinism is golden-pinned; a bug here drops or duplicates reviewed content)
**Status:** not started

### Phase 1 — Editor-side excludable classes, disclosed (~4h)
**Deliverables:**
- `--exclude <class>:<path-or-glob>` on both runners, the three classes and their rules (§2), fail-closed refusal.
- The `bin/` copy of the path heuristic and a checker pinning it to `tools/scope_classifier.py`.
- `=== EXCLUDED SUMMARY ===` intent block convention for `generated`, documented in step 9.
- SKILL.md: when to use each class, the Scope-line disclosure, a Hard rules entry ("no path leaves the reviewed diff except through the runner, and every exclusion is disclosed").

**Acceptance:**
- `tools/check-all.sh` green, including refusal cases: a production path under `docs`/`governing-plan`; `generated` without a summary block; an unknown class; a glob matching nothing.
- A parity or checker assertion that the SKILL.md heuristic prose, the `bin/` copy and `tools/scope_classifier.py` agree on the classifier fixtures.
- A worked example in `examples/merge/` (a lockfile-bearing diff, with summary and disclosure), built from the ResearchLogix dependabot review.

**Iterate-review:** YES (rationale: the trust-boundary half: rules that let the editor take files out of review; wrong rules silently suppress findings)
**Status:** not started

### Phase 2 — Closeout — CHANGELOG, README, close #10 (~1h)
**Deliverables:**
- CHANGELOG entry, README (review cost + the exclusion classes), `tools/README.md`, pre-merge doc sweep.
- Issue #10 closed with a comment linking the archived plan.

**Acceptance:**
- Closeout checklist fully checked; plan archived.

**Iterate-review:** NO (rationale: docs-only; no code surface to review)
**Status:** not started

## Acceptance criteria

- [ ] The runner drops the review's own pass log from every composed diff and records it in the summary; nothing else changes (golden-pinned).
- [ ] Classed `--exclude` works for `governing-plan`, `docs` and `generated`, and fails closed on every refusal case.
- [ ] No path can leave the reviewed diff except through the runner, and every exclusion appears in both `pass-N.summary.json` and the pass header's `Scope:` line.
- [ ] The runner's heuristic copy and `tools/scope_classifier.py` are pinned to agree.
- [ ] Issue #10 closed; CHANGELOG and README current.

## Risks

### R1 — An exclusion hides a real defect
**Mitigation:** production paths can leave only as `generated`, and only with an audit summary in the intent; every exclusion is disclosed with its line count; the refusal is in code. The residual risk is an editor mislabeling a hand-written production file as `generated`. Its disclosure makes that visible to the human, but it is not prevented. *To challenge:* should `generated` also require a path pattern list (lockfile names, a `generated/` segment) rather than any path?

### R2 — The heuristic copy drifts from `tools/scope_classifier.py`
**Mitigation:** a checker asserts agreement on every classifier fixture, the same pattern 2.5.0 uses for the cluster threshold.

### R3 — Composition determinism breaks
**Mitigation:** the sectioning is a pure function of the diff text and the resolved log path; goldens pin with/without cases; renames covered.

### R4 — Savings smaller than estimated
**Mitigation:** none needed for safety. The pass summary's line counts give the actual removed volume per pass; if it's small on real branches, Phase 1 can be reconsidered before building.

## Rollback plan

`git revert` of either phase restores step 9's "unchanged" behavior; no state migration (the summary's `excluded` field is additive and ignored by older readers).

## Sequencing decision

After the simplification-gate PR merges (done: PR #11, merged 2026-09-30; this branch is rebased onto it): it touches the same SKILL.md step 9 and step 12 header and the runner's summary, so building in parallel means a rebase over freshly reviewed text. Drafted during that PR's review, while it was blocked on the reviewer's usage limit. Until this ships, reviews apply the exclusions by hand and record them in the `Scope:` line (never a production path without a summary).

## Open questions

- **Q1.** Where are exclusions applied: by the runner from `--exclude` flags (recommended: mechanical disclosure, refusal in code), or by the editor editing the diff file, as ResearchLogix did (no runner change for Phase 1, but disclosure and refusal stay prose)?
- **Q2.** May a lockfile (production under the path heuristic) be excluded at all? Recommendation: yes, only as `generated` with an audit summary in the intent, per the dependabot precedent. Alternative: never; lockfile reviews stay full-size.
- **Q3.** Should Phase 0's self-exclusion also apply when the pass log is only in the working tree (`--scope=working`), not committed? Recommendation: yes; the rule is "the log's path", not "the log's commit".
- **Q4.** Does `iterate-review --scope=branch` need a `--base <rev>` so a later phase can be reviewed without re-sending earlier, already-converged phases? This is the largest remaining lever (the simplification-gate review re-sent all of Phase 0 during Phase 1), but it changes what a "branch review" means. Recommendation: out of scope here; raise as its own issue if Phase 0–1 savings prove insufficient.

## Out of scope

- Automatic lens trimming: lens choice goes both ways in practice; `--lenses` is the override.
- Reading Codex's usage-limit state: private, version-coupled format.
- `iterate-plan`'s growing input: its HISTORICAL blocks live in the plan and grow each pass (the simplification-gate plan review went from ~95k to ~270k input tokens per call over 5 passes), but a two-lens plan pass costs about a quarter of a large code-review pass, and the simplification gate should shorten long plan loops anyway. Revisit only if plan loops start hitting the limit.
- A per-phase `--base` for branch reviews: see Q4.

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
- [ ] Close issue #10 with a comment linking the archived plan and stating what was and was not built.
- [ ] ResearchLogix_v2 (in that repo): replace hand exclusions in review practice with the classed flags.

## References

- Issue #10: https://github.com/kaileconsulting/trinity-skills/issues/10
- `iterate-review/SKILL.md` step 3 (the production/non-production heuristic), step 9 ("unchanged" diff), step 10 (summary contract), step 12 (pass header).
- `iterate-review/bin/review_runner.py`: `compose_input()`, `resolve_log_path()`, `read_prior_passes()`.
- `tools/scope_classifier.py`, `tools/check-scope-classification.py`: the heuristic and its fixtures.
- `docs/archive/simplification-gate-2026-09-28.md` (2.5.0): the literal-in-SKILL.md / dev-side-pin pattern reused for the heuristic copy; its review log (`docs/archive/code-review-branch-kyle-simplification-gate.md`) is where the cost was measured.
- ResearchLogix_v2 review logs with hand exclusions: the testing-suite batch 2 and 3 branches ("docs/ excluded"), `code-review-branch-fix-auth-csrf-hardening-2026-09-24.md`, `code-review-branch-chore-dependabot-cleanup-2026-09-10.md` (lockfiles, with the audit summary).
- Memory: `codex-quota.md` (the measurements), `trinity-expansion.md`.

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
