# Review-Diff Exclusions — Plan

## TL;DR

`iterate-review` sends every lens the whole diff, "unchanged" (step 9). On a long branch, that diff routinely carries content the reviewer doesn't need: the review's **own pass log**, which already arrives a second time as `=== PRIOR PASSES ===`; **lockfiles and generated files**, which a line-by-line reviewer can't meaningfully read; and a **converged governing plan** the review treats as its spec. Each lens re-sends that input across several file-reading turns, so it is the main cost against the reviewer's usage limit. On 2026-09-29 a three-lens pass on a ~3,300-line branch cost 25–50% of a ChatGPT Plus 5-hour window, and two parallel projects exhausted a fresh window in about 40 minutes.

This plan makes two exclusions first-class, with the runner applying both and disclosing both mechanically: (Phase 0) the runner drops the pass log's own sections from the composed diff, content the reviewer already receives as prior passes, while any rename that crosses the log's boundary stays reviewed; (Phase 1) the editor may name further paths to exclude, by class, and the runner refuses any exclusion that would take reviewable production code out of review without the disclosure and summary its class requires. Closes [issue #10](https://github.com/kaileconsulting/trinity-skills/issues/10).

Expected outcome, stated as a hypothesis: roughly 10–20% less input per lens on plan-driven branches (see §Why for the derivation and what would confirm it), with every exclusion visible in the pass header and the pass summary.

## Why / Context

**The measurement (2026-09-29, from `~/.codex/sessions` token events).** Per-lens input on the simplification-gate review: 330–510k tokens per call (the composed input is ~80k; the rest is Codex re-sending context across its file reads, mostly cached but still counted). A three-lens pass cost 25–50% of a 5-hour window; a two-lens `iterate-plan` pass cost 10–13%. Reasoning effort (`high`) is under 1% of tokens, so lowering effort doesn't save quota; input volume does.

**What was in that diff.** Of the branch diff at pass 4: pass log 130 lines, plan + handoff 524, fixtures/examples 1,036, SKILL.md 802, tools 791. The pass log and the plan (654 lines, ~20% of the diff) were redundant or settled. *The estimate, and its limits:* removing ~20% of the diff saves ~20% of the diff's share of per-lens input, and that share is well below 100% (prior passes and Codex's own file reads also count), so the honest range is roughly 10–20% of per-lens input. It is a hypothesis. The pass summary's removed line counts (§1) show how much was excluded, not what it saved; the check on actual savings is the `used_percent` Codex logs per call, compared across passes before and after.

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

- The runner drops the review's own pass log from the composed diff on every pass, with no flag, and records it in the pass summary; a rename or copy crossing the log's boundary is never dropped.
- The editor can exclude further paths by passing them to the runner **with a class**; the runner applies the class's rule, refuses what the rule forbids, and records every exclusion in the pass summary.
- Every exclusion appears in the pass header's `Scope:` line, copied from the summary.
- Composition stays byte-deterministic; goldens pin the excluded forms.
- `tools/scope_classifier.py` and the runner's refusal logic apply the same heuristic, pinned so they cannot drift (as built: after the `docs` class was removed at the Phase 1 review's pass-6 simplification card, the runner's refusals no longer use the heuristic at all; `governing-plan` checks `.md` + git mode 100644 instead, and step 3's prose is pinned to `tools/scope_classifier.py`).

## Non-goals (MVP)

- **No automatic exclusion beyond the pass log.** Every other exclusion is the editor's named, classed decision.
- **No lens trimming.** Lens choice goes both ways in practice (qa was *forced on* for a whole ResearchLogix review); `--lenses` stays the manual override.
- **No reading the reviewer's usage-limit state.** It lives in Codex's private session-log format, which could change with any release.
- **No `iterate-plan` behavior change.** Its input is the plan itself; nothing to exclude (see Out of scope for its growing-history cost). The one shared file it carries, `bin/runner_shared.py`, changes byte-identically in both skills to gain an optional summary argument iterate-plan never passes, so its output is unchanged (decided at the pass-1 card).

## Approach

### §0 What the runner parses (both phases)

Exclusion deletes reviewed content, so the parser has an exact contract rather than a best-effort one:
- **Input:** `git diff` output only: sections that begin at a `diff --git` line. Paths are decoded as git writes them, including C-style quoted paths (`"a/with space"`, octal escapes); the default `a/`/`b/` prefixes are required. A section runs to the next `diff --git` line and is kept or removed as raw bytes, never re-rendered.
- **A section's identity** is its old and new path, taken from the `diff --git` line and confirmed by the `rename from`/`rename to`, `copy from`/`copy to`, `---`/`+++` or `Binary files` lines where present. Sections with no hunks (rename-only, mode-only, binary) are sections like any other.
- **Fail closed.** If any section's identity can't be established (an unparseable header, a custom prefix, a plain unified diff with no `diff --git` lines), the runner applies **no** exclusion: automatic self-exclusion is skipped and reported in the summary's `warnings`, and an explicit `--exclude` request aborts before fan-out.
- **Globs** match the decoded paths present in the diff, both endpoints, deleted paths included, never the working tree.

### §1 Pass-log self-exclusion (runner, Phase 0)

`run-pass` / `run-lens` already resolve the pass-log path (`resolve_log_path()`). Before composing, the runner drops a section **only when every endpoint that exists is the pass log**: the log added, modified or deleted in place (the other endpoint being the log itself or `/dev/null`). A rename or copy whose other endpoint is a different path is **never** auto-excluded: it stays in the reviewed diff, whole, and the summary notes it. Nothing else changes. Within that rule the claim is exact: the removed content is this review's own log, which reaches the reviewer anyway as `=== PRIOR PASSES ===` whenever the log exists at its resolved path. The summary records every removal in `excluded: [{"old_path", "new_path", "class": "pass-log", "lines"}]`. This applies alike to committed and working-tree logs (Q3). Only the default log slot, `docs/reviews/code-review-<scope-tag>.md`, is trusted as the log: a `--log-path` override (which only has to be an in-repo `.md` file, and may name a path the diff deletes) excludes nothing, with a warning (Phase 0 review pass 1, security); so does a default slot reached through a symlink, file or parent directory, since it could point at any in-repo file (pass 2, all lenses). The excluded path is always the literal slot.

### §2 Classed editor exclusions (runner-applied, Phase 1)

The editor passes `--exclude <class>:<path-or-glob>` (repeatable) to `run-pass` / `run-lens`. Exclusions are applied by the runner, not by the editor editing the diff file (Q1, agreed by both lenses at pass 1): disclosure is mechanical (the summary records what was actually removed, with line counts) and the refusal is enforced in code. A section is excluded only if **every existing endpoint** satisfies the class's rule (`/dev/null`, the missing side of an addition or deletion, is not a repository path and is never checked), as in §1; a rename that crosses from an excludable path to a non-excludable one stays reviewed. Classes:

| Class | May exclude | Requires | Refused when |
|---|---|---|---|
| `governing-plan` | the one path named on the intent's `Governing-plan:` line | exactly one line `Governing-plan: <repo-relative path>` in the intent, naming a path present in the diff | the line is missing or duplicated, names a different path, or the path is not documentation (as `docs`) |
| `docs` — **removed** (Phase 1 review, pass-6 simplification card; see As built below) | documentation paths | nothing further | the path is not documentation: a documentation file type (prose or image, nothing executable) under a `docs` segment or a root-level doc file, and nothing test-shaped (as built, passes 4–5: non-production alone would admit tests and fixtures, and a root doc name alone would admit `SECURITY.py`); every class takes **plain paths only** (printable ASCII, no backtick, backslash, double quote or `: `; chosen at the review's pass-5 checkpoint over patching filename tricks one per pass) and refuses audit text that can't be disclosed on one line |
| `generated` | lockfiles and generated files | an `=== EXCLUDED SUMMARY ===` block in the intent with one entry per excluded path, `- <path>: <audited property>`, the property non-empty | any excluded path has no entry, or its entry's property is empty |

The checks are **mechanical presence checks**. The runner verifies that each `generated` path has a non-empty audit entry naming it; whether the audit happened and was adequate is the editor's responsibility, visible to the human because the entries are copied into the pass header. The refusal is fail-closed: an unknown class, a glob matching nothing, or any rule above failing exits non-zero before fan-out, like any other runner contract violation. The heuristic is step 3's production/non-production rule. *As built:* Phase 1 first moved the heuristic's single implementation into `bin/` for the `docs`/`governing-plan` refusals; the review then removed `docs` ("is this documentation?" drew HIGH findings on passes 4–6: tests, `SECURITY.py`, executable `.mdx`, symlinks), `governing-plan` became "a regular, non-executable `.md` blob", and the heuristic moved back to `tools/scope_classifier.py`, with `tools/check-scope-classification.py` now pinning step 3's prose to it both ways. Classed exclusion also takes plain paths and plain-text audits only (pass-5 checkpoint and pass-6 card). Also settled while building: each section is decided by the **first** matching spec in command-line order (so `governing-plan` goes before a broad `docs:docs/**`); `governing-plan` takes the exact path only, no globs; a spec whose only match is the pass log counts as matched; a single-path section failing its class rule refuses, while a rename/copy with only one endpoint in the class is kept with a warning.

### §3 Order of operations

The runner holds two values: the **original diff** and the **reviewed diff** (the original minus exclusions). Lens selection and step 3's production/non-production classification read the **original**, so an excluded lockfile still triggers the `security` lens and an excluded test directory still counts toward `qa`, and exclusions never trim lenses. Only composition reads the reviewed diff. A standalone `run-lens` retry takes the same `--exclude` arguments and resolves the same log path as the pass it retries, so it reproduces the same reviewed diff; the summary records both line counts.

### §4 Disclosure

`publish_summary()` in the shared `bin/runner_shared.py` gains an optional mapping of extra fields, merged into the payload **before** the atomic write, so `excluded` is part of the single commit point, never a later amendment. Step 12's header template gains the exclusions in `Scope:`, e.g. `branch (excluded: pass-log 130 lines; governing-plan docs/x.md 498 lines)`, copied from the summary's `excluded` array, never written from memory. Step 9's "unchanged" rule becomes "unchanged except for runner-applied exclusions, each recorded in the summary and the pass header."

**A diff that exclusions empty entirely is not a pass.** It follows the existing empty-diff contract: the runner exits non-zero before fan-out, publishes no summary and consumes no pass number, and prints the removed paths and line counts on stderr. The editor relays them to the human as "nothing left to review after exclusions", so the disclosure still happens, just without creating a pass.

### Repo layout

Modified: `iterate-review/bin/review_runner.py` (diff sectioning + exclusion), `iterate-review/bin/run-pass`, `iterate-review/bin/run-lens` (flags, the original/reviewed split), `bin/runner_shared.py` in **both** skills, byte-identically (the optional summary argument, §4), `iterate-review/SKILL.md` (steps 9, 10, 12, Hard rules), `tools/check-runners.py` and `tools/check-plan-runners.py` (iterate-plan's summary unchanged), composition goldens under `iterate-review/examples/composition/`. New: a `bin/` copy of the path heuristic and a checker pinning it to `tools/scope_classifier.py`. No `iterate-plan` behavior change.

## Phasing

### Phase 0 — Runner self-exclusion of the pass log (~2h)
**Deliverables:**
- The §0 parser and the §1 pass-log exclusion in `review_runner.py`, applied by both `run-pass` and `run-lens`; the original/reviewed split (§3), with selection and classification on the original.
- `publish_summary()`'s optional extra-fields argument in both skills' `runner_shared.py`, byte-identical (§4); the `excluded` array in `pass-N.summary.json` and in `run-lens` output.
- Composition golden: a diff containing the pass log composes byte-identically to the same diff without it. A pass-log-only diff follows the empty-diff contract (§4).
- SKILL.md step 9's "unchanged" rule rewritten (§4); step 12's `Scope:` header shows the exclusion.

**Acceptance:**
- `tools/check-all.sh` green, including new `check-runners.py` cases: log section dropped when added, modified or deleted in place; **kept** when renamed or copied to or from another path, including with substantive new content; quoted paths and hunk-less (rename-only, mode-only, binary) sections parsed; an unparseable section skips self-exclusion with a warning; selection unchanged by exclusion; working-tree and committed logs alike; summary records both endpoints and line counts.
- `check-parity.py`'s byte-identity check on `runner_shared.py` stays green, and `check-plan-runners.py` shows iterate-plan's summary unchanged.
- Replaying the simplification-gate branch's pass-4 diff through the new runner drops exactly the 130-line log section.

**Iterate-review:** YES (rationale: changes the runner's input composition, whose byte-determinism is golden-pinned; a bug here drops or duplicates reviewed content)
**Status:** reviewed 2026-09-30 — iterate-review converged at pass 3 (APPROVE ×3; HIGH+MEDIUM 4 → 1 → 0, five HIGH findings all incorporated, none fold-caused, no decision card; log `docs/archive/code-review-branch-kyle-review-diff-exclusions.md`). The folds hardened the §0 parser (binary markers confirm identity, binary payloads and no-newline markers validated, nothing before the first section, no create/delete mixed with a move) and narrowed §1 to the lexical default log slot (no override, no symlink). First review on the gpt-5.6-sol pin (2.5.1): ~30% of one 5-hour window, ~5% weekly, for three passes. Built `tools/check-all.sh` green (check-runners 163/163, 37 new: exclusion cases plus the summary-clash guard; check-plan-runners adds an exact-summary-fields case; a mutation pass confirmed the fail-closed, rename-kept, newline-only-split and original/reviewed-split cases each catch their mutant). The strict parser round-trips all 456 non-merge commit diffs in this repo's history byte for byte and refuses the one `diff --cc`. Replay: the simplification-gate branch diff at `8952a56` (the 130-line log) drops exactly one section, the log's 136 lines (130 content + 6 header), and the reviewed diff is byte-identical to `git diff … -- . ':!<log>'`; same at `8bdb0ae` (111-line log, 117-line section). The old pass-4 state was pruned, so the replay is from git history rather than a committed fixture. `lines` in `excluded` is the removed section's length, so `diff_lines.original − reviewed = Σ lines`.

### Phase 1 — Editor-side excludable classes, disclosed (~4h)
**Deliverables:**
- `--exclude <class>:<path-or-glob>` on both runners, the three classes and their rules (§2), fail-closed refusal.
- The `bin/` copy of the path heuristic and a checker pinning it to `tools/scope_classifier.py`.
- `=== EXCLUDED SUMMARY ===` intent block convention for `generated`, documented in step 9.
- SKILL.md: when to use each class, the Scope-line disclosure, a Hard rules entry ("no path leaves the reviewed diff except through the runner, and every exclusion is disclosed").

**Acceptance:**
- `tools/check-all.sh` green, including refusal cases: a production path under `docs`/`governing-plan`; a missing, duplicated or mismatched `Governing-plan:` line; a `generated` path with no audit entry or an empty property; an unknown class; a glob matching nothing; a rename crossing into a non-excludable path (kept, not refused); an unparseable section (aborts). Plus valid cases: several `generated` paths, each with its own entry.
- A parity or checker assertion that the SKILL.md heuristic prose, the `bin/` copy and `tools/scope_classifier.py` agree on the classifier fixtures.
- A worked example in `examples/merge/` (a lockfile-bearing diff, with summary and disclosure), built from the ResearchLogix dependabot review.

**Iterate-review:** YES (rationale: the trust-boundary half: rules that let the editor take files out of review; wrong rules silently suppress findings)
**Status:** reviewed 2026-09-30 — iterate-review converged at pass 8 (APPROVE ×3; passes 4–8, HIGH+MEDIUM 6 → 3 → 6 → 5 → 0; 21 findings, all incorporated, 3 by simplification, 6 fold-caused). Shape changes the review forced, all Kyle's calls: at the pass-5 checkpoint, classed exclusion narrowed to plain paths; at pass 6 two simplification cards fired — the `docs` class was removed and audit text narrowed to plain ASCII shown as code spans; the governing plan must be a regular non-executable `.md` blob. The final LOW (warning order) was folded after the APPROVE without a confirming pass, by Kyle's choice.

### Phase 2 — Closeout — CHANGELOG, README, close #10 (~1h)
**Deliverables:**
- CHANGELOG entry, README (review cost + the exclusion classes), `tools/README.md`, pre-merge doc sweep.
- Issue #10 closed with a comment linking the archived plan.

**Acceptance:**
- Closeout checklist fully checked; plan archived.

**Iterate-review:** NO (rationale: docs-only; no code surface to review)
**Status:** done 2026-09-30, in the same PR as Phases 0–1 (Kyle's call: this repo has no CI gates, so the closeout rides with the change it closes). Drafted while Phase 1's pass 6 waited on the usage window; finalized after Phase 1 converged: CHANGELOG 2.6.0 dated, README "Review cost & diff exclusions" section and dev-check rows, tools/README rows, doc sweep re-run after the `docs` class was removed, plan + handoff + review log archived, issue #10 closes on merge (`Closes #10` in the PR).

## Acceptance criteria

- [x] The runner drops the review's own pass log from every composed diff it can parse and records it in the summary; nothing else changes (golden-pinned). An unparseable diff is left unchanged with a warning (§0).
- [x] Classed `--exclude` works for `governing-plan` and `generated` (the `docs` class was removed at the Phase 1 review's pass-6 simplification card), and fails closed on every refusal case.
- [x] Exclusion never changes lens selection or scope classification (both read the original diff), and never removes a section with an endpoint outside its class.
- [x] No path can leave the reviewed diff except through the runner, and every exclusion is disclosed: in `pass-N.summary.json` and the pass header's `Scope:` line for a pass, or on stderr, relayed by the editor, when exclusions leave nothing to review and no pass is created (§4).
- [x] The runner's heuristic copy and `tools/scope_classifier.py` are pinned to agree. *(Moot as built: after the `docs` class was removed the runner uses no heuristic; SKILL.md step 3's prose is pinned to `tools/scope_classifier.py` both ways instead.)*
- [x] Issue #10 closed (on merge, via `Closes #10`); CHANGELOG and README current.

## Risks

### R1 — An exclusion hides a real defect
**Mitigation:** production paths can leave only as `generated`, and only with an audit summary in the intent; every exclusion is disclosed with its line count; the refusal is in code. The residual risk is an editor mislabeling a hand-written production file as `generated`. Its disclosure makes that visible to the human, but it is not prevented. *To challenge:* should `generated` also require a path pattern list (lockfile names, a `generated/` segment) rather than any path?

### R2 — The heuristic copy drifts from `tools/scope_classifier.py`
**Mitigation:** a checker asserts agreement on every classifier fixture, the same pattern 2.5.0 uses for the cluster threshold. *As built:* moot — once `docs` was removed, the runner no longer uses the heuristic; the remaining copy, SKILL.md step 3's prose, is pinned to `tools/scope_classifier.py` by `check-scope-classification.py`.

### R3 — Composition determinism breaks
**Mitigation:** the sectioning is a pure function of the diff text and the resolved log path; goldens pin with/without cases; renames covered.

### R4 — Savings smaller than estimated
**Mitigation:** none needed for safety. The pass summary's line counts give the actual removed volume per pass; if it's small on real branches, Phase 1 can be reconsidered before building.

## Rollback plan

Phase by phase: reverting **Phase 1** removes `--exclude` and the classes but leaves Phase 0's automatic pass-log exclusion active; reverting **Phase 0** as well restores step 9's fully unchanged diff. The shared `runner_shared.py` change reverts in both skills together, or `check-parity.py` fails. No state migration either way: the summary's `excluded` field is additive and ignored by older readers.

## Sequencing decision

After the simplification-gate PR merges (done: PR #11, merged 2026-09-30; this branch is rebased onto it): it touches the same SKILL.md step 9 and step 12 header and the runner's summary, so building in parallel means a rebase over freshly reviewed text. Drafted during that PR's review, while it was blocked on the reviewer's usage limit. Until this ships, reviews apply the exclusions by hand and record them in the `Scope:` line (never a production path without a summary).

## Open questions

- **Q1.** Where are exclusions applied: by the runner from `--exclude` flags (recommended: mechanical disclosure, refusal in code), or by the editor editing the diff file, as ResearchLogix did (no runner change for Phase 1, but disclosure and refusal stay prose)? *Pass 1: both lenses agree — runner-applied. Folded into §2.*
- **Q2.** May a lockfile (production under the path heuristic) be excluded at all? Recommendation: yes, only as `generated` with an audit summary in the intent, per the dependabot precedent. Alternative: never; lockfile reviews stay full-size. *Pass 1: both lenses agree — yes, via `generated` with audit entries bound to each excluded path; an allowlist can reduce mislabeling but not prove content is generated. Folded into §2.*
- **Q3.** Should Phase 0's self-exclusion also apply when the pass log is only in the working tree (`--scope=working`), not committed? Recommendation: yes; the rule is "the log's path", not "the log's commit". *Pass 1: both lenses agree — yes, same rule for working-tree and committed logs, with the rename safeguard. Folded into §1.*
- **Q4.** Does `iterate-review --scope=branch` need a `--base <rev>` so a later phase can be reviewed without re-sending earlier, already-converged phases? This is the largest remaining lever (the simplification-gate review re-sent all of Phase 0 during Phase 1), but it changes what a "branch review" means. Recommendation: out of scope here; raise as its own issue if Phase 0–1 savings prove insufficient. *Pass 1: both lenses agree — out of scope; the architect adds that a review base would also have to be reconciled with the accepted-risk provenance gate's base.*

## Out of scope

- Automatic lens trimming: lens choice goes both ways in practice; `--lenses` is the override.
- Reading Codex's usage-limit state: private, version-coupled format.
- `iterate-plan`'s growing input: its HISTORICAL blocks live in the plan and grow each pass (the simplification-gate plan review went from ~95k to ~270k input tokens per call over 5 passes), but a two-lens plan pass costs about a quarter of a large code-review pass, and the simplification gate should shorten long plan loops anyway. Revisit only if plan loops start hitting the limit.
- A per-phase `--base` for branch reviews: see Q4.

## Closeout

- [x] Append entry to your project's milestones / changelog index (if you
  keep one): one paragraph covering what shipped, the ship commit, key
  delta, and a link back to the archived plan path. (CHANGELOG 2.6.0; the
  ship commit is the PR's merge.)
- [x] Update memory and/or project notes: mark plan completed, link to
  ship commits, update any related context files this plan touched.
  (trinity-expansion and codex-quota memories; codex-quota's "exclude by
  hand" advice now points at the flags.)
- [x] Update any backlog / priority queue: remove if it was queued, or
  mark closed inline. (Issue #10 is the queue entry; it closes on merge.)
- [x] Move plan to archive: `git mv docs/<plan>.md docs/archive/<plan>.md`. (Handoff prompt and review log moved beside it, per the v2.4 convention.)
- [x] Final commit with a "shipped" message referencing this plan. (The closeout commit on the PR branch; it ships on merge.)
- [x] Close issue #10 with a comment linking the archived plan and stating what was and was not built. (The summary below is the PR description's closing section, and `Closes #10` closes the issue on merge.)
  Closing summary: 2.6.0 builds this in. The runner drops the review's own
  pass log from every composed diff (only the literal default log slot is
  trusted; renames crossing it stay reviewed), and the editor can exclude
  two further kinds of content by class: `--exclude governing-plan:<path>`
  (the one converged plan the intent names; a regular `.md` file) and
  `--exclude generated:<path-or-glob>` (lockfiles and generated files, each
  with a plain-text audit entry in the intent). Every request is refused
  before any Codex call unless its rule holds; only plain paths qualify;
  every exclusion is recorded in `pass-N.summary.json` and shown in the pass
  header's Scope line; lens selection still reads the original diff. Not
  built, as planned: automatic exclusion beyond the pass log, lens trimming,
  reading Codex's usage state, and a per-phase `--base` for branch reviews
  (Q4, still the largest remaining lever). Changed by the review: a `docs`
  class was built and then removed at a simplification card, because "is
  this documentation?" kept admitting code. Learned on the way: the cost
  measured when this issue was opened was mostly the model (Codex 0.157 had
  defaulted to gpt-6-astra, ~9x gpt-5.6-sol's burn), fixed separately in
  2.5.1; this release removes duplicated and settled content on top,
  roughly 10–20% of per-lens input on plan-driven branches. Plan:
  `docs/archive/review-diff-exclusions-2026-09-29.md`; review log:
  `docs/archive/code-review-branch-kyle-review-diff-exclusions.md`.
- [x] ResearchLogix_v2 follow-up noted (tracked in memory; the edit itself happens in that repo): replace hand exclusions in review practice with the classed flags once 2.6.0 is installed there. Note that its "docs/ excluded" practice has no class now: those docs will be reviewed.

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

-->

| Phase | Iterate-review | Status | Last pass | Pass log |
|-------|----------------|--------|-----------|----------|
| Phase 0 | YES | converged (APPROVE ×3) | 3 — 2026-09-30 | `docs/archive/code-review-branch-kyle-review-diff-exclusions.md` |
| Phase 1 | YES | converged (APPROVE ×3) | 8 — 2026-09-30 | `docs/archive/code-review-branch-kyle-review-diff-exclusions.md` |
| Phase 2 | NO | done (in-PR closeout) | — | — |

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

## Codex review pass 1 — answers (2026-09-30) [HISTORICAL]

### Verdict
REVISE (worst-of: architect REVISE, product-manager REVISE; no FAILED lens). Merged HIGH+MEDIUM count: 5.

### Findings
1. **Pass-log renames can take production changes out of review** — HIGH · lens: architect, product-manager (co-reported): §1 drops a whole section when *either* endpoint is the log path, so a log renamed to a production path with new code would vanish without the `generated` audit, and `read_prior_passes()` returns nothing once the old log path is gone; "removes nothing from review" overclaims.
   → Editor: incorporated — §1 now drops a section only when every existing endpoint is the log (added, modified or deleted in place); a rename or copy to or from any other path is never auto-excluded and stays reviewed whole; the claim is narrowed to exactly that case, and the TL;DR and Goals restatements match. §2 applies the same both-endpoints rule to every class. Phase 0 acceptance pins renames with substantive new content. [introduced_by_pass: null] [component: pass-log-self-exclusion]
2. **Summary publication needs a change to the shared runner module** — HIGH · lens: architect: `run-pass` publishes through `runner_shared.publish_summary()`, whose payload is fixed and which `tools/check-parity.py` requires byte-identical across both skills, so the `excluded` field reaches iterate-plan's copy, contradicting the "no iterate-plan change" non-goal; amending a summary after publication would break its atomic-commit contract.
   → Editor: incorporated (via the plan-shaping-fold card below, Kyle: optional field, reword) — §4 adds an optional extra-fields argument to `publish_summary()`, merged before the atomic write so `excluded` is part of the one commit point, changed byte-identically in both skills; the non-goal now reads "no `iterate-plan` behavior change"; Repo layout lists both copies and `check-plan-runners.py`; Phase 0 acceptance adds the byte-identity and unchanged-plan-summary checks. [introduced_by_pass: null] [component: exclusion-disclosure-summary]
3. **The diff section parser has no defined input or failure contract** — MEDIUM · lens: architect: only literal `diff --git a/<p> b/<p>` boundaries are described; quoted paths, rename-only / mode-only / binary sections, custom prefixes and unparseable sections are unspecified, and a best-effort parser is not enough authority to delete sections.
   → Editor: incorporated — new §0 defines the parser: `git diff` sections only, git's C-style path quoting decoded, default prefixes required, raw bytes preserved, identity confirmed from rename/copy/`---`/`+++`/binary lines, hunk-less sections included; any unidentifiable section means no exclusion at all (self-exclusion skipped with a warning, explicit requests abort); globs match decoded diff paths, both endpoints, never the working tree. [introduced_by_pass: null] [component: diff-section-parser]
4. **Exclusion ordering relative to lens selection is unspecified** — MEDIUM · lens: architect: whether selection and scope classification see the original or the filtered diff is undefined (filtering first can drop a security trigger in a lockfile), and retries must reproduce the same exclusions.
   → Editor: incorporated — new §3: the runner holds an original and a reviewed diff; selection and scope classification read the original, composition reads the reviewed; a `run-lens` retry takes the same `--exclude` arguments and log path; the summary records both line counts. [introduced_by_pass: null] [component: exclusion-ordering]
5. **The intent conventions behind the refusals aren't machine-checkable** — MEDIUM · lens: architect (governing-plan identity and audit coverage), product-manager (audit success condition and per-file coverage; merged, same gap): nothing identifies the governing-plan path or binds audit entries to excluded paths, so "names an audited property" could be satisfied by an unrelated sentence.
   → Editor: incorporated — §2 now defines line-exact conventions: exactly one `Governing-plan: <path>` line (missing, duplicated or mismatched refuses), and an `=== EXCLUDED SUMMARY ===` block with one `- <path>: <audited property>` entry per `generated` path (missing or empty refuses); stated as mechanical presence checks, with the audit's truth and adequacy the editor's responsibility, made visible by copying the entries into the pass header. Phase 1 acceptance adds each refusal and a multi-path valid case. [introduced_by_pass: null] [component: intent-structured-conventions]

### Plan corrections applied
- §1, §3, Acceptance (architect): a fully excluded diff was "treated like an empty diff", but empty diffs exit non-zero with no summary, so the disclosure promise had nowhere to live → §4: a fully excluded diff follows the empty-diff contract (non-zero exit, no summary, no pass number) with the removed paths and line counts on stderr for the editor to relay
- Rollback plan (architect): reverting "either phase" does not restore unchanged diffs, since Phase 0's self-exclusion survives a Phase 1 revert → rollback now phase by phase, plus the shared file reverting in both skills together
- TL;DR + Why (product-manager): the 20–35% estimate doesn't follow from ~20% of the diff times a diff share below 100%, and removed lines don't measure token or quota savings → hypothesis of roughly 10–20% of per-lens input, derivation shown, and the check named: Codex's per-call `used_percent`, not the removed line counts

### Open-question answers
1. Q1 — both lenses: runner-applied exclusions (mechanical disclosure, refusal before fan-out). Agree with the recommendation.
2. Q2 — both lenses: yes, lockfiles via `generated`, audit entries bound to the excluded paths; a filename allowlist can reduce mislabeling but can't prove content is generated. Agree.
3. Q3 — both lenses: yes, same eligibility rule for working-tree and committed logs, subject to the rename safeguard. Agree.
4. Q4 — both lenses: keep `--base` out; the architect adds that a review base also has to be reconciled with the accepted-risk provenance gate's base. Agree.

### New questions Codex raised
- (none)

### Decision cards
- **plan-shaping-fold escalation** (finding 2 — the non-goal "No `iterate-plan` change"): recommendation — `runner_shared.publish_summary()` gains an optional `extra` mapping merged into the payload before the atomic write, changed byte-identically in both skills; iterate-plan never passes it, so its output is unchanged; the non-goal is reworded to "no `iterate-plan` *behavior* change"; alternatives — leave the shared module untouched and publish exclusions as a separate `pass-N.exclusions.json` written *before* the summary, keeping the non-goal as written (two files for readers to join); discuss; chosen: optional field, reword (Kyle, 2026-09-30) — one commit point kept, non-goal reworded to "no behavior change".

### Lens run summary
- architect: REVISE · product-manager: REVISE

### Checkpoint
Loop mode (`--loop`). One plan-shaping card, answered; every finding incorporated; five new component labels, each at streak 1. Open questions Q1–Q4 answered in agreement with the recommendations by both lenses (freeze streak 1). → **Continue** to pass 2.

## Codex review pass 2 — answers (2026-09-30) [HISTORICAL]

### Verdict
APPROVE (architect APPROVE, product-manager APPROVE; no FAILED lens). Merged HIGH+MEDIUM count: 0 (from 5).

### Findings
- (none)

### Plan corrections applied
- §2 both-endpoints rule (architect): did not exempt nonexistent endpoints as §1 does, so `/dev/null` on an addition or deletion could block a valid exclusion → now "every existing endpoint", with `/dev/null` named as never checked.
- Acceptance criteria (architect): the "every composed diff" and "every exclusion in the summary" bullets omitted §0's parse-failure and §4's empty-result contracts → both bullets qualified.
- Phase 0 deliverables (architect): step 9's rewrite cited §3 but is specified in §4 → points to §4.

### Open-question answers
1. Q1 — both lenses: runner-applied; the optional summary argument records removals at the existing atomic commit point. Equivalent to pass 1 (freeze streak 2).
2. Q2 — both lenses: yes via `generated`, per-path audit entries; presence enforced, adequacy the editor's. Equivalent (streak 2).
3. Q3 — both lenses: yes, same rule in both scopes, boundary-crossing renames preserved. Equivalent (streak 2).
4. Q4 — both lenses: out of scope; a review base would need coordinated provenance and trust-boundary treatment. Equivalent (streak 2).

### New questions Codex raised
- (none)

### Convergence reasoning
Two passes. HIGH+MEDIUM per pass: 5 → 0. Five merged findings, all incorporated (one via Kyle's plan-shaping card), none fold-caused; six plan corrections, three per pass; 0 disputed, 0 accepted-risk, 0 register-match. Component streaks all at 0 after pass 2; no simplification card fired. Every open question answered in agreement with its recommendation on both passes (freeze streak 2, one short of freezing). No pending cards. The three pass-2 corrections are mechanical and unreviewed. Converge is Kyle's call.

### Lens run summary
- architect: APPROVE · product-manager: APPROVE

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
