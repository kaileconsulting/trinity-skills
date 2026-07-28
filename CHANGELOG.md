# Changelog

## 2.1.1 — 2026-07-28 — bound the content-regex match span

Fixes [#5](https://github.com/kaileconsulting/trinity-skills/issues/5), found while
dogfooding `iterate-review` on this repo.

### Fixed

- **A content regex could bridge an entire minified file.** Lens `content_regexes` are
  matched against changed content lines — but minified or single-line JSON makes a whole
  file *one* line, so a pattern like
  `(SELECT|UPDATE|…)\s+.*\b(FROM|TABLE)\b` spanned **959 characters** of unrelated
  prose and selected the `security` lens for a fixture containing no SQL.
  A regex is now evaluated against at most **400 characters** of a changed line, chunked
  with a **200-character overlap** so any genuine match up to 200 chars is still found
  in full. Bound and overlap are parsed from `lenses/README.md` like the other rule
  data, and an overlap ≥ span is a hard error rather than a non-terminating loop.

### Why this was worth fixing before a measurement period

Over-inclusion is the deliberate selection bias, so a spurious lens costs one Codex
call rather than correctness. But real repos contain minified JSON, and the next few
weeks are for measuring **whether the added lenses earn their keep**. A `security` lens
that fires on bundled artifacts and returns empty APPROVEs would make itself look
low-value — contaminating exactly the signal being collected.

### Added

- `selection/14-minified-json-span.diff` — a true regression fixture: it selects
  `security` spuriously *without* the bound and `senior-dev` alone with it. 13 → 14
  routing fixtures.
- 9 checker self-tests (44 → 53) covering chunking, the bound stopping a bridge, a
  genuine match surviving chunking at four offsets including chunk boundaries, and
  overlap ≥ span raising.

### Not changed

The same run also selected `qa` because `\bresponse\b` matched the word "response" in
prose mentioning a filename. That is **pattern breadth in the qa lens, not a mechanism
bug** — narrowing it would change routing behaviour and is a judgment call about the
lens rather than a fix. Left alone deliberately; issue #5 was corrected to say so.

## 2.1.0 — 2026-07-28 — classified open questions

A reviewer raising a question now says **who can settle it**, and that label decides
whether an unattended loop stops. Found by dogfooding: during the first multi-lens
`iterate-plan` run, neither lens could resolve a question that needed an external
lookup — the lenses run sandboxed with no network — while two other questions were
genuinely the author's call. The loop guardrail treated all three identically.

### Changed — **breaking** (reviewer output schema)

- **`new_questions` is now an array of objects**, not strings:
  `{question, settled_by, why}`. `settled_by` ∈
  `resolvable_in_fold | needs_lookup | needs_human`. Both skills.
  - Taken as a break rather than a `oneOf string|object` on purpose: an optional
    label is one that quietly stops being filled in.
  - `why` is **required** — a one-line justification, so the label can be audited
    instead of trusted. A bare enum is easy to rubber-stamp.
  - The contract states that **`needs_human` is the correct choice when unsure.**
    An unnecessary escalation costs one question; mislabeling the author's decision
    as machine-resolvable invites a fabricated answer.
- **The loop-mode human-judgment guardrail now halts only on `needs_human`.**
  `resolvable_in_fold` and `needs_lookup` are resolved by Opus and the loop
  continues; a *failed* lookup reclassifies to `needs_human` and then halts.
  Previously the guardrail read "a question Opus can't answer from the plan + repo
  context," which stopped unattended loops for questions a single file read would
  have answered.
- Both fold paths route by class, dedupe questions across lenses, take the **most
  escalating** label on a class conflict, and **sanity-check the label rather than
  trusting it** — a `resolvable_in_fold` that plainly needs the author's preference
  is treated as `needs_human`.
- Pass-log templates record each question's class, resolution, and any override.

### Migration

Seven tracked fixtures reshaped; question text preserved **verbatim**, container
only. Two notes:

- `iterate-plan/examples/pass-4-response.json` is the repo's only *real* Codex
  capture and is now lightly reshaped rather than byte-exact. The frozen copy at
  `v1/iterate-plan-v1/examples/pass-4-response.json` keeps the original shape.
- `v1/` is untouched — it carries its own schema copy and `tools/` does not scan it.

Runtime state files under `*/state/` are gitignored and were not migrated; they are
historical artifacts, and nothing reads them back against the schema.

### Added

- 4 parity rules (32 → 36) covering class routing, most-escalating conflict
  resolution, lookup-failure reclassification, and label auditing. The existing
  `guard-human-judgment` rule was tightened to require naming *which* class halts.
- 8 checker self-tests (36 → 44) asserting both schemas reject unclassified
  `new_questions`, reject an unknown `settled_by`, and require `why`.
- Merge goldens now demonstrate all three classes, including the case that
  **changed behavior**: in `iterate-review/examples/merge/01`, the "is the router
  behind auth middleware" question is `resolvable_in_fold` and no longer halts the
  loop, while the product-intent question still does. Scenario 02's single question
  is `needs_human`, so its halt is unchanged — both cases are pinned so the label
  isn't mistaken for a way to suppress halts.

### Known gaps

- **A lens can mislabel.** The mitigations are the unsure-default, the required
  `why`, and Opus's override — none of which is a guarantee. A `needs_human`
  question mislabeled `resolvable_in_fold` and not caught on review would get a
  fabricated answer. This is plan risk R2 surfacing in a new place.
- The value concentrates in loop mode. Attended, Opus already made this distinction
  by hand; the label makes it explicit and machine-actionable.
- **Routing behaviour is not mechanically tested — only schema shape is.** The 8 new
  self-tests assert the schemas reject unclassified questions, unknown classes, and a
  missing `why`. Nothing asserts that `needs_human` halts the loop and the other two
  continue, because there is no executable fold path to call: routing is prose Opus
  follows at runtime. The goldens state the expected continue-vs-halt outcome per
  class, which is the same coverage model merge correctness uses. Raised as a MEDIUM
  in review and recorded rather than resolved.

## 2.0.0 — 2026-07-28 — Axis 2: persona lenses

Each review pass now runs **several reviewer personas concurrently** and merges their
findings into one list. Same reviewer model, more question categories — this is a
*breadth* change, not a reliability one (model diversity is a separate, later axis).

Plan: [`docs/archive/trinity-axis-2-persona-lenses-2026-07-27.md`](docs/archive/trinity-axis-2-persona-lenses-2026-07-27.md).
Review trail: `docs/archive/code-review-phase{0,1,4}-*.md`.

### Added

- **Persona lenses.** `iterate-plan` runs `architect` + `product-manager` every pass.
  `iterate-review` runs `senior-dev` always, plus `security` and `qa` when the diff's
  shape selects them. Lenses are data-shaped records in `<skill>/lenses/<id>.md`.
- **Deterministic lens selection** — a rules table over changed paths and changed diff
  lines, explicitly *not* an LLM router. `senior-dev` is a floor that always runs, and
  borderline matches include the lens: a wasted Codex call is cheaper than a missed
  category.
- **Fan-out + merge.** N concurrent `codex exec` calls per pass; Opus merges by
  semantic judgment (same location **and** same asserted defect), aggregates verdicts
  **worst-of**, and records every finding's originating lens.
- **`FAILED` lens handling.** A lens that fails is retried once, then recorded as
  `FAILED` — orchestration metadata, not a verdict. It forces at-least-REVISE,
  preserves a `BLOCK` from any completed lens, and **blocks Converge** with a retry
  option, so the loop never converges having silently skipped a selected lens.
- **Loop mode** — `--loop` / `--until-approve` and an `(L)oop from here` checkpoint
  option. Automates `Continue` only, **never `Converge`**, and halts on five
  guardrails: APPROVE reached, max-pass cap (default 6, `--max-passes`, fresh per
  activation), BLOCK, non-convergence (merged HIGH+MEDIUM count not strictly
  decreasing over two transitions), or a fold needing human judgment.
- **Matched context per lens.** `iterate-plan` slices the plan H2 sections each lens
  declares in `requires_sections`; a lens whose section is missing runs anyway and is
  required to flag the gap rather than invent content.
- **Dev checks in `tools/`** — `check-parity.py` (32 shared-machinery rules present in
  both skills), `check-examples.py` (schema validity + fixture-name-claim checks),
  `test-checkers.py` (36 tests that the checkers fail when they should),
  `check-all.sh`. Requires `jsonschema`; see `requirements-dev.txt`.
- **A runnable reference implementation of lens selection** —
  `iterate-review/examples/selection/check-selection.py` plus 13 golden diff fixtures.
  The selection rules claim any two implementations agree on a diff; until this
  existed there was one implementation, and it was a language model reading prose.
  It parses its rule data from the lens frontmatter and `lenses/README.md` rather than
  restating it, so only the evaluation algorithm is duplicated. Test-only — never
  invoked during a real run.
- **Merge goldens** for both skills, covering co-report dedupe, two distinct concerns
  at one location, worst-of with an approving lens, `FAILED` preserving `BLOCK`,
  degraded context, and conflicting `open_question_answers`.
- **`v1/`** — the pre-lens skills, frozen and installable side-by-side via
  `./install.sh --with-v1`. Also tagged `v1.0`.

### Changed

- `reviewer-prompt.md` in both skills is now a **shared contract** that defers only
  ROLE and FOCUS to a lens fragment. Every lens runs under identical restrictions and
  returns the same schema.
- Merge rules gained two cases found while writing the goldens: two lenses answering
  the same `question_id` must be recorded **with the disagreement surfaced**, not
  silently reconciled (`iterate-plan`); and corrections must be deduped, since they
  apply *mechanically* and a duplicate can double-apply an edit (both skills).
- `install.sh` takes `--with-v1` and `--help`, and installs by repo-relative path so a
  skill's directory name need not match its location.
- Reviewer output schemas are **unchanged** — the split altered prompt *assembly*, not
  the contract.

### Fixed

- `iterate-review/examples/pass-malformed.response.json` had been **fake coverage
  since the initial release**. A `$comment` key made it schema-invalid
  (`additionalProperties: false`), so it would have been rejected by schema validation
  a step *before* reaching the patch-marker scan it existed to exercise. `$comment`
  removed from both pre-existing fixtures, and the file renamed to
  `pass-1-patch-marker-violation.response.json` — the old name implied malformed JSON,
  which it never was.
- `check-selection.py` returned wrong answers *silently* in three cases, all found by
  its own code review: renames across the `source_exts` boundary (removed lines
  attributed to the new path), git C-quoted paths, and tab-separated timestamps in
  plain unified diff headers. Each yielded zero changed source lines and quietly
  failed to select `qa`.

### Known gaps

- The plan's "single-lens path is a behavioral non-regression" criterion is
  **explicitly unmet**. It asserts *same findings* versus pre-Axis-2, which no fixture
  establishes and a nondeterministic reviewer arguably cannot.
- `check-parity.py` verifies a rule is *stated* in both skills, not that it is stated
  *correctly*. A rule wrong in both passes.
- Merge correctness is not mechanically tested anywhere. Semantic dedupe is Opus's
  judgment by design, so it ships goldens to compare against, not assertions.
- Matched context on diffs is prompt framing plus already-available inputs, not real
  extraction (no computed trust boundaries).

## 1.0.0 — 2026-05-19 — initial release

`create-plan`, `iterate-plan`, `iterate-review`. One reviewer persona per pass: a
single `codex exec` in a `-s read-only -a never` sandbox with `--output-schema`
enforcement, Opus as sole editor, patch-marker rejection, HISTORICAL audit trail, and
a human checkpoint after every pass.

Tagged `v1.0`. Frozen copies live in [`v1/`](v1/README.md) from 2.0.0 onward.
