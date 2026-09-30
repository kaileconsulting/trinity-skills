# Code Review — branch-kyle-review-diff-exclusions

## Pass 1 — 2026-09-30 10:08 [HISTORICAL]

**Scope:** branch (excluded by hand, pre-feature: governing-plan docs/review-diff-exclusions-2026-09-29.md 373 lines; docs docs/review-diff-exclusions-2026-09-29.md.handoff-prompt.md 33 lines) · **Diff size:** 883 lines · **Scope class:** production · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** used docs/review-diff-exclusions-2026-09-29.md · **Lenses:** senior-dev, security, qa

Reviewer model: gpt-5.6-sol (first pass on the 2.5.1 pin). Cost: 5-hour window 85% → 92%, weekly 92% → 93%, ~691k input tokens across the three lenses.

### Findings

1. **Binary markers are not confirmed against the section identity** — HIGH · lens: senior-dev, qa, security: `_parse_section` accepts any final `Binary files …` line without decoding or comparing its paths, so a section headed as the pass log whose marker names a production file is resolved as the log and dropped; plan §0 says binary lines confirm identity.
   → Editor: incorporated — `_binary_marker_confirms()` checks the marker names exactly the resolved endpoints (`a/<old>`/`b/<new>` or `/dev/null`, C-quoting decoded); since a path may contain " and ", every split is tried and exactly one must match, else `DiffParseError`. Fixtures: a marker naming a production file, a mismatched `/dev/null` side (both fail closed), and real git output with "cats and dogs.bin", an added and a deleted binary (all confirmed). [introduced_by_pass: null] [component: diff-section-parser]
2. **Rename/copy combined with new/deleted file mode nulls a non-log endpoint** — HIGH · lens: qa: a malformed section with `rename from lib/production.py`, `rename to <log>` and `new file mode` resolves to `(None, <log>)` and is dropped whole; the inverse with `deleted file mode`.
   → Editor: incorporated — a section carrying `new file mode`/`deleted file mode` together with rename/copy lines, or with differing `diff --git` paths, now raises before any endpoint is nulled. Fixtures for both directions (rename-in + new mode; copy-out + deleted mode) fail closed. [introduced_by_pass: null] [component: diff-section-parser]
3. **A `--log-path` override is an unrestricted exclusion primitive** — HIGH · lens: security: the override only has to resolve inside the repo (and be `.md`), so pointing it at another markdown path excludes that path's section as `pass-log`; a deleted file isn't on disk for the header check at all.
   → Editor: incorporated — `self_exclusion_target()`: only the default slot `docs/reviews/code-review-<scope-tag>.md` is trusted as the log; with any `--log-path` override nothing is self-excluded and the summary warns. Chose the narrow guard over proving log identity from content (a deleted target has no content on disk to check). CLI fixture: an override naming a deleted `docs/SECURITY.md` keeps it in every composed input. SKILL.md step 9 and plan §1 updated. [introduced_by_pass: null] [component: pass-log-identity]
4. **Permissive binary-patch payload and backslash lines** — HIGH · lens: security (HIGH), senior-dev (MEDIUM; merged, same gap): everything after `GIT binary patch` is opaque, and any `\`-prefixed line is accepted inside and after hunks, so reviewable content can hide inside an excludable section instead of tripping the fail-closed path.
   → Editor: incorporated — `_check_binary_patch()` validates the whole payload (1–2 `literal|delta N` blocks, base85 lines whose length character matches their width, blank-line terminators, nothing else); a `\` line is accepted only as the exact `\ No newline at end of file`, directly after a content line, once. Fixtures: content after a binary patch, a wrong-width line, an arbitrary `\` line, a marker at hunk start, repeated markers (all fail closed); a valid two-block patch still parses; all 465 non-merge history diffs still round-trip. [introduced_by_pass: null] [component: diff-section-parser]

### Code corrections applied

- iterate-review/bin/review_runner.py `parse_diff_sections` — the preamble check uses `.strip()`, so whitespace before the first `diff --git` is accepted and then dropped on rejoin → now `starts[0] != 0` refuses any byte before the first section; fixture: a leading blank line fails closed

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Checkpoint

Continue (Kyle, 2026-09-30; he used his full usage reset, so the window is back at 100%). Streaks: diff-section-parser 1, pass-log-identity 1.

### Diff snapshot reference

Diff captured at 2026-09-30 10:01; head SHA `f1e769e0c7fcd8eb29f25448d734770f53a4988b`.

## Pass 2 — 2026-09-30 10:25 [HISTORICAL]

**Scope:** branch (excluded by hand, pre-feature: governing-plan docs/review-diff-exclusions-2026-09-29.md 373 lines; docs docs/review-diff-exclusions-2026-09-29.md.handoff-prompt.md 33 lines; pass-log docs/reviews/code-review-branch-kyle-review-diff-exclusions.md 38 lines) · **Diff size:** 1072 lines · **Scope class:** production · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** used docs/review-diff-exclusions-2026-09-29.md · **Lenses:** senior-dev, security, qa

### Findings

1. **A symlinked default log slot redirects self-exclusion to another file** — HIGH · lens: senior-dev, security, qa (co-reported): run-pass/run-lens resolve the default log path through `realpath()` before `self_exclusion_target()`, which trusts it only because no `--log-path` was given; if `docs/reviews/code-review-<tag>.md` or its parent is an in-repo symlink to a production markdown file, that target's section is excluded as `pass-log` (and a deleted target needs no header at all).
   → Editor: incorporated — `self_exclusion_target()` now binds identity to the **lexical** slot `docs/reviews/code-review-<tag>.md`: the excluded path is always that literal string, and it is used only when the resolved log equals `realpath(repo_root)/<slot>`; any symlink on the way (file or parent) means no self-exclusion, with a warning. The now-unused `log_path_in_diff()` (which derived identity from the resolved target) is removed. CLI fixtures through both run-pass and run-lens: a file symlink, a parent-directory symlink, and a dangling symlink to a file the diff deletes all keep the target in every composed input; a baseline confirms the real slot is still excluded. A mutation restoring the old resolved-target identity fails all three. SKILL.md step 9 and plan §1 updated. [introduced_by_pass: null — realpath-derived identity was in the original Phase 0 commit; pass 1's override guard narrowed the surface but didn't create this] [component: pass-log-identity]

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-09-30 10:18; head SHA `1ddbbfaadc1267f7e61163e3a13c6a0655a8b808`.

### Checkpoint

Continue, one pass (Kyle, 2026-09-30). HIGH+MEDIUM 4 → 1. Streaks: pass-log-identity 2 (one below the cluster threshold), diff-section-parser 0. Cost: 5-hour window 0% → 20%, weekly 0% → 3% (~1.6M input tokens; all three lenses read deeply).

## Pass 3 — 2026-09-30 10:39 [HISTORICAL]

**Scope:** branch (excluded by hand, pre-feature: governing-plan docs/review-diff-exclusions-2026-09-29.md 373 lines; docs docs/review-diff-exclusions-2026-09-29.md.handoff-prompt.md 33 lines; pass-log docs/reviews/code-review-branch-kyle-review-diff-exclusions.md 67 lines) · **Diff size:** 1157 lines · **Scope class:** production · **Verdict:** APPROVE (worst-of; no FAILED lenses) · **Posture:** used docs/review-diff-exclusions-2026-09-29.md · **Lenses:** senior-dev, security, qa

Cost: 5-hour window 22% → 25%, weekly 3% → 4% (~417k input tokens; one lens read deeply).

### Findings

- (none)

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: APPROVE · security: APPROVE · qa: APPROVE

### Diff snapshot reference

Diff captured at 2026-09-30 10:33; head SHA `1c1a6d7e97acb7c6db40496de261fc14d7dad19a`.

### Checkpoint

**Converge** (Kyle, 2026-09-30). Three passes, HIGH+MEDIUM 4 → 1 → 0; five merged findings (all HIGH), all incorporated, none fold-caused, 0 disputed / accepted-risk / register-match; one correction. No decision card fired: pass-log-identity peaked at streak 2, diff-section-parser at 1, both 0 after pass 3. Total reviewer cost on gpt-5.6-sol: ~30% of one 5-hour window, ~5% weekly.

## Pass 4 — 2026-09-30 11:25 [HISTORICAL]

Phase 1 (classed `--exclude`) review, same branch; the diff still carries Phase 0.

**Scope:** branch (excluded by hand, pre-feature: governing-plan docs/review-diff-exclusions-2026-09-29.md 374 lines; docs docs/review-diff-exclusions-2026-09-29.md.handoff-prompt.md 33 lines; pass-log docs/reviews/code-review-branch-kyle-review-diff-exclusions.md 97 lines) · **Diff size:** 2085 lines · **Scope class:** production · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** used docs/review-diff-exclusions-2026-09-29.md · **Lenses:** senior-dev, security, qa

### Findings

1. **The `docs` class accepts every non-production path, including tests** — HIGH · lens: qa: the rule is only `is_non_production()`, so `--exclude docs:tests/**` removes changed tests (QA evidence) and discloses them as `docs`.
   → Editor: incorporated — new `path_classes.is_documentation()`: under a `docs` segment or a root-level doc file, and nothing test-shaped (no test/spec/fixture/golden/example segment, no test-named file); `docs` and `governing-plan` now use it instead of `is_non_production()`. Fixtures: refusals for tests/, spec/, fixtures/, goldens/, examples/, a test-named file, a test under docs/, and a governing plan under examples/; docs/ and root README still accepted. SKILL.md step 9 table and plan §2 table updated. [introduced_by_pass: null] [component: exclusion-class-rules]
2. **Backslash normalization lets a production path read as having a `docs` segment** — HIGH · lens: qa, security (co-reported): `path_classes.py` replaces `\` with `/`, but git paths use `/` only and C-quote a literal backslash, so a root file named `src\docs\billing.py` classifies non-production and a `docs` (or governing-plan) exclusion can remove it.
   → Editor: incorporated — `path_classes._split()` splits on `/` only (git's separator; a C-quoted backslash is a filename character). Fixtures: the classifier case `src\docs\billing.py` → production, a parser case decoding it as one root-level name, and a `docs:src*` refusal of it. [introduced_by_pass: null — the backslash normalization predates this branch (tools/scope_classifier.py, v2.4)] [component: path-heuristic]
3. **Lossy C-path decoding collapses distinct files** — HIGH · lens: security: octal escapes decode with UTF-8 `errors="replace"`, so non-UTF-8 names like `docs/\200.lock` and `docs/\201.lock` both become `docs/�.lock`, share one audit entry, and can't be told apart in disclosure.
   → Editor: incorporated — `_decode_path()` refuses a C-quoted path whose octal bytes aren't valid UTF-8 (the decoded text gains U+FFFD the token didn't have): the section can't be identified exactly, so self-exclusion is skipped with a warning and an explicit `--exclude` aborts. Fixtures for both. [introduced_by_pass: null] [component: diff-section-parser]
4. **A rename/copy exclusion discloses only one of its two endpoints** — HIGH · lens: security, senior-dev (co-reported): the Scope rendering (step 12) and the all-excluded stderr name only `new_path` with one audit property, so a `generated` rename's old path and its audit never reach the human.
   → Editor: incorporated — new `review_runner.disclosure()` renders every `excluded` entry, used by the all-excluded stderr and specified for step 12's Scope suffix: `<class> <path> <N> lines`, `old → new` for a rename/copy, and ` — <old>: <prop> / <new>: <prop>` for a two-endpoint `generated` entry, whose `audit` map is now in old-then-new order. No new summary field. Fixtures: a generated rename's rendering, the all-excluded stderr naming both endpoints, and a single-path rendering. [introduced_by_pass: null] [component: exclusion-disclosure]
5. **One audit entry can satisfy two prefix-related paths** — HIGH · lens: senior-dev: `_audit_entry()` matches `entry.startswith(path + ": ")`, so the entry `a: b: prop` satisfies both `a` and `a: b`.
   → Editor: incorporated — `_audit_entry()` refuses any `generated` path containing `: `, the entry delimiter, instead of guessing which entry binds it. Fixture: `a` and `a: b.lock` under one glob refuse. [introduced_by_pass: null] [component: exclusion-class-rules]
6. **The prose pin doesn't check root doc names in both directions** — MEDIUM · lens: senior-dev: `prose_agreement()` confirms each code name appears but never extracts the prose list, so a prose-only name (e.g. `INSTALL`) passes; its fallback also accepts a name missing its opening backtick.
   → Editor: incorporated — `prose_agreement()` now extracts the backticked root doc names from step 3's list and compares sets both ways (the loose no-opening-backtick fallback is gone); a mutation adding a prose-only `INSTALL` fails it. [introduced_by_pass: null] [component: path-heuristic-prose-pin]

### Code corrections applied

- review_runner.py `self_exclusion_target` warnings (qa, senior-dev; merged) — say "the diff is reviewed unchanged", which classed exclusions can now contradict → both warnings now say the pass log's own sections stay in review

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-09-30 11:14; head SHA `d4e1e820cc118b66e2e5d8715b3ea968061bb01f`.

### Checkpoint

Continue, one pass (Kyle, 2026-09-30). HIGH+MEDIUM 6 (first Phase 1 pass). Streaks: exclusion-class-rules 1, path-heuristic 1, diff-section-parser 1, exclusion-disclosure 1, path-heuristic-prose-pin 1. Cost: ~1.53M input tokens, ~20% of the 5-hour window, ~3% weekly (query-iq was running reviews on the same quota).

## Pass 5 — 2026-09-30 11:48 [HISTORICAL]

**Scope:** branch (excluded by hand, pre-feature: governing-plan docs/review-diff-exclusions-2026-09-29.md 374 lines; docs docs/review-diff-exclusions-2026-09-29.md.handoff-prompt.md 33 lines; pass-log docs/reviews/code-review-branch-kyle-review-diff-exclusions.md 138 lines) · **Diff size:** 2228 lines · **Scope class:** production · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** used docs/review-diff-exclusions-2026-09-29.md · **Lenses:** senior-dev, security, qa

### Findings

1. **Decoded paths can forge the human-facing disclosure** — HIGH · lens: qa, security (co-reported): `disclosure()` and `excluded_stderr()` interpolate C-decoded paths (and audit text) verbatim, so a filename with a newline, carriage return, ANSI escape, bidi control or markdown can erase, reorder or fake parts of the Scope line or stderr, while the JSON summary stays escaped.
   → Editor: incorporated — `_undisplayable()`: every classed exclusion refuses a path or audit property containing a Cc/Cf/Zl/Zp character (controls, bidi/format, line and paragraph separators), and a path containing a backtick; `disclosure()` shows paths in backticks (a code span, so markdown renders literally), rename endpoints as `` `old` → `new` ``. Chose refusal over an escaping scheme: fail-closed, and nothing a human reads needs decoding. Pass-log entries use the lexical slot, whose scope-tag charset is already restricted. Fixtures: newline (with a forged `**Verdict:**`), CR, ANSI escape, bidi override and backtick paths, and a control character in an audit property, all refused; a markdown-laden filename renders in a code span. SKILL.md step 9/12, scenario 06's expected header and plan §2 updated. [introduced_by_pass: null — verbatim interpolation dates from Phase 0's `excluded_stderr`] [component: exclusion-disclosure]
2. **The root-doc rule admits executable files** — HIGH · lens: security: `is_documentation()` matches the basename before the first dot, so `SECURITY.py`, `README.sh`, `NOTICE.js` leave review as `docs` or `governing-plan` without an audit.
   → Editor: incorporated — `is_documentation()` now also requires a documentation file type, `path_classes.DOC_EXTENSIONS` (prose and images; nothing executable, no HTML/SVG), by final extension: under `docs/` always, and for a root doc name unless extensionless. So the same gap closes for `docs/deploy.sh` too. Step 3's budget heuristic (`is_non_production`) is deliberately unchanged, since its "any extension" rule governs pass budgets, not exclusion. Fixtures: `SECURITY.py`, `README.sh`, `NOTICE.js`, `docs/deploy.sh`, `docs/Makefile`, `docs/site.html`, `docs/diagram.svg` refused; `README.en.md`, `LICENSE`, `docs/img/arch.png` accepted. The extension list is pinned to step 9's table, both directions, by check-scope-classification. [introduced_by_pass: 4 — pass 4's `is_documentation()` reused the root-doc rule as-is] [component: path-heuristic]
3. **The non-UTF-8 check is a U+FFFD heuristic, not strict decoding** — HIGH · lens: senior-dev: it rejects a valid C-quoted U+FFFD (`\357\277\275`) and accepts invalid bytes when the token also has a literal U+FFFD, so distinct rename endpoints could still collapse.
   → Editor: incorporated — `selection_engine._unquote_c()` takes an `errors` policy (default "replace", unchanged for selection); `_decode_path()` decodes with "strict" and turns a `UnicodeDecodeError` into `DiffParseError`. Fixtures: a validly quoted U+FFFD decodes exactly; invalid bytes beside a literal U+FFFD fail closed; the pass-4 non-UTF-8 cases still refuse. Selection routing unchanged (14/14). [introduced_by_pass: 4 — pass 4's replacement-character heuristic] [component: diff-section-parser]

### Code corrections applied

- review_runner.py `apply_exclusions` docstring (senior-dev, security, qa; merged) — says docs/governing-plan use `is_non_production` → names `is_documentation` and says tests/fixtures are not eligible
- review_runner.py `_excluded_summary` docstring (senior-dev) — claims a path containing `: ` still binds; `_audit_entry` refuses it → describes raw entries and the delimiter refusal
- review_runner.py pass-log crossing warning (senior-dev) — says the section stays in review, but a classed spec may still exclude it → now says self-exclusion skips it and only an explicit `--exclude` spec could remove it
- tools/check-runners.py (senior-dev, security, qa; merged) — the crossing-rename comment is duplicated → one copy

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-09-30 11:38; head SHA `a2be51146af4efb5529498ec8f3a4872d09a3214`.

### Checkpoint

Continue after a narrowing (Kyle, 2026-09-30): "Narrow to plain paths, pass 6 after 15:18". HIGH+MEDIUM 6 → 3; 2 of 3 fold-caused (pass 4). Streaks: exclusion-disclosure 2, path-heuristic 2, diff-section-parser 2 (each one below the cluster threshold, 2,); exclusion-class-rules 0, path-heuristic-prose-pin 0. Passes 4–5 kept finding filename edge cases (backslash, non-UTF-8, control/bidi, `: `), so before pass 6 the editor proposed, and Kyle chose, narrowing classed `--exclude` to plain paths (printable ASCII, no backtick, backslash, double quote or `: `); anything else is refused and stays in review. Not a simplification card (no label reached 3); recorded here as the checkpoint decision, and pass 6 reviews the narrowed head. Cost: ~1.55M input tokens (one lens 1.46M), ~17% of the 5-hour window, ~2% weekly.

## Pass 6 — 2026-09-30 15:24 [HISTORICAL]

**Scope:** branch (excluded by hand, pre-feature: governing-plan docs/review-diff-exclusions-2026-09-29.md 374 lines; docs docs/review-diff-exclusions-2026-09-29.md.handoff-prompt.md 33 lines; pass-log docs/reviews/code-review-branch-kyle-review-diff-exclusions.md 174 lines) · **Diff size:** 2396 lines · **Scope class:** production · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** used docs/review-diff-exclusions-2026-09-29.md · **Lenses:** senior-dev, security, qa

Label note: passes 4 and 5 tagged the same mechanism — which paths count as documentation for `docs` / `governing-plan` (`is_documentation()`) — as `exclusion-class-rules` (pass 4) and `path-heuristic` (pass 5). That is label drift; this pass counts it honestly as one mechanism, `docs-eligibility`, whose streak is 3 (passes 4, 5, 6).

### Findings

1. **Executable MDX counts as passive documentation** — HIGH · lens: security: `DOC_EXTENSIONS` includes `mdx`, which documentation builds evaluate (imports, JSX), so `--exclude docs:docs/**` can remove production-capable code unaudited.
   → Editor: incorporated (by simplification) — card 1, *simplify (remove)*: the `docs` class is gone (now an unknown class), so no `.mdx` or any other documentation leaves review unaudited; `governing-plan` accepts `.md` only. `DOC_EXTENSIONS`, `is_documentation()` and their prose pin are deleted; the heuristic moved back to `tools/scope_classifier.py`. [introduced_by_pass: 5] [component: docs-eligibility]
2. **Documentation eligibility ignores git object modes** — HIGH · lens: security: a symlink or gitlink named `docs/guide.md`, or a doc file made executable, passes `is_documentation()` (path only) and leaves review.
   → Editor: incorporated (by simplification) — card 1, *simplify (remove)*: `docs` is gone, and `governing-plan` now requires git mode 100644 at every endpoint. The parser records each endpoint's mode (`index`, `new file mode`, `old mode`/`new mode`). Fixtures: an executable-mode plan and a symlinked plan are refused; modes are parsed from all three line kinds. [introduced_by_pass: null] [component: docs-eligibility]
3. **Markdown in an audit property can forge the pass header** — HIGH · lens: security: `_undisplayable()` rejects controls only, so `checked <br> **Verdict:** APPROVE` renders a fake line break and verdict inside the Scope line.
   → Editor: incorporated (by simplification) — card 2, *simplify (narrow)*: audit properties must be plain text (`_PLAIN_TEXT`: printable ASCII, no backtick), replacing `_undisplayable()`, and `disclosure()` shows each one in a code span. Fixtures: backtick, control and non-ASCII audits are refused; `checked <br> **Verdict:** APPROVE` renders literally inside its code span. Scenario 06's audits lost their backticks; its goldens were regenerated deliberately and re-read (the history doc now stays reviewed: 25 of 67 lines). [introduced_by_pass: 4] [component: exclusion-disclosure]
4. **A non-plain unmatched rename endpoint aborts instead of being kept** — MEDIUM · lens: qa, senior-dev (co-reported): the plain-path check runs on every endpoint once any endpoint matches, so `docs/a.md → docs/café.md` under `docs:docs/a.md` aborts rather than staying reviewed with a warning.
   → Editor: incorporated — the plain-path refusal applies to the endpoints the deciding spec *matched*; a non-plain unmatched endpoint makes the section a crossing rename, kept whole, with its paths shown via `repr` in the warning. Fixture: `lib/a.lock → lib/café.py` under `generated:lib/a.lock` is kept with a warning. [introduced_by_pass: null — the narrowing commit ac44dc7, a checkpoint decision, not a pass fold] [component: plain-path-rule]
5. **A scope tag ending in a newline passes validation** — MEDIUM · lens: qa: `SCOPE_TAG_RE` ends in `$`, which matches before a final newline, so `--scope-tag $'x\n'` yields a log path containing a newline (a self-excludable, multi-line-disclosed identity whose prior passes can never be read back).
   → Editor: incorporated — `SCOPE_TAG_RE` ends in `\Z`. Fixture: `validate_scope_tag("x\n")` raises. [introduced_by_pass: null — predates this branch] [component: scope-tag-validation]
6. **Governing-plan paths with `[` are rejected as globs** — MEDIUM · lens: senior-dev: `_GLOB_CHARS` includes `[`, but the runner's glob has no character classes, so `Governing-plan: docs/Plan [draft].md` can't be excluded even though it is plain.
   → Editor: incorporated — `_GLOB_CHARS` is `*` and `?`, the glob syntax the runner actually has. Fixture: `docs/Plan [draft].md` excludes as an exact governing plan. [introduced_by_pass: null] [component: governing-plan-spec]

retired: docs-eligibility (removed at the pass-6 simplification card)

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Decision cards

- **simplification card** (pass 6, component `docs-eligibility`, streak 3): streak findings — P4 HIGH qa "docs admits tests/fixtures" (introduced_by_pass: null); P5 HIGH security "root-doc rule admits SECURITY.py" (introduced_by_pass: 4); P6 HIGH security "MDX counts as documentation" (introduced_by_pass: 5 — DOC_EXTENSIONS was pass 5's fold); P6 HIGH security "git modes ignored" (introduced_by_pass: null). 2 of this streak's 4 findings are fold-caused. Recommendation — **simplify (remove) the `docs` class**: keep `governing-plan` (one exact file the intent names) and `generated` (audited), and narrow `governing-plan` to a regular, non-executable `.md` blob (mode 100644 or new-file 100644), dropping `DOC_EXTENSIONS`, its prose pin and most of `is_documentation()`. *Guarantee lost:* an unaudited way to leave general documentation out of review. *Remaining layer:* the pass log is still dropped automatically and the governing plan still leaves by name, which is most of the measured savings (~550 of the lines excluded by hand per pass here); other docs are reviewed like code. *Accounting:* tests → resolved (class gone); SECURITY.py → resolved; MDX → resolved (docs gone; governing-plan is `.md` only); modes → resolved (governing-plan requires a regular non-executable blob). Alternatives — **simplify (replace)**: `docs` keeps its path rules but, like `generated`, requires an `=== EXCLUDED SUMMARY ===` audit entry per path. *Lost:* the mechanical guarantee; the editor attests instead. *Remaining:* the audit is shown in the pass header. *Accounting:* tests, SECURITY.py, MDX, modes → each resolved only by the editor's attestation, not by code. **simplify (narrow)**: `docs` accepts only regular non-executable `.md`/`.txt`/`.rst` blobs under `docs/` or root doc names. *Lost:* images, PDFs, other prose formats. *Remaining:* everything else stays reviewed. *Accounting:* MDX → resolved; modes → resolved; tests and SECURITY.py → already resolved by passes 4–5. **fold once more** (never recommended): drop `mdx`, add a mode check. accept the risk — omitted (PF-shipbar names exclusion as a trust boundary). chosen: simplify (remove) (Kyle, 2026-09-30 — the `docs` class goes; governing-plan narrows to a regular non-executable `.md` blob; label `docs-eligibility` retires)
- **simplification card** (pass 6, component `exclusion-disclosure`, streak 3): streak findings — P4 HIGH security+senior-dev "rename discloses one endpoint" (null); P5 HIGH qa+security "decoded paths forge the disclosure" (null); P6 HIGH security "markdown in audit text forges the header" (introduced_by_pass: 4 — pass 4's `disclosure()` put audit text in the header verbatim). 1 of 3 fold-caused. Recommendation — **simplify (narrow)**: audit properties become plain like paths (printable ASCII, no backtick) and are rendered as a code span, so nothing in them is ever interpreted as markdown or HTML. *Lost:* backticks and non-ASCII in audit text (the scenario 06 audits lose their backticks). *Remaining:* the summary JSON keeps the audit verbatim; the intent keeps the editor's own wording. *Accounting:* markdown/HTML forgery → resolved; rename endpoints and decoded paths → already resolved (passes 4–5), unaffected. Alternatives — **simplify (remove)**: the header shows `<class> <path> <N> lines` only, with no audit text; audits live in the summary and the intent. *Lost:* the plan's R1 mitigation of seeing each audit claim in the header. *Accounting:* forgery → resolved. **fold once more** (never recommended): escape markdown metacharacters in audit text. accept the risk — omitted (trust boundary). chosen: simplify (narrow) (Kyle, 2026-09-30 — audit properties become plain text shown in a code span; label retained, streak reset to 0)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-09-30 15:20; head SHA `ac44dc7cff710a0c9b12efa64da8115750d0cb5f`.

### Checkpoint

Continue, one pass (Kyle, 2026-09-30). HIGH+MEDIUM 6 (from 3); two simplification cards answered (docs-eligibility: remove → retired; exclusion-disclosure: narrow → streak 0). Streaks after the pass: path-heuristic 0, diff-section-parser 0, exclusion-disclosure 0 (card reset), plain-path-rule 1, scope-tag-validation 1, governing-plan-spec 1. Fold ecc571f net-shrank the diff (+468/−433). ResearchLogix was running reviews on the same quota.

## Pass 7 — 2026-09-30 18:12 [IN PROGRESS]

**Scope:** branch (excluded by hand, pre-feature: governing-plan docs/review-diff-exclusions-2026-09-29.md 390 lines; docs docs/review-diff-exclusions-2026-09-29.md.handoff-prompt.md 33 lines; pass-log docs/reviews/code-review-branch-kyle-review-diff-exclusions.md 222 lines) · **Diff size:** 2443 lines · **Scope class:** production · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Posture:** used docs/review-diff-exclusions-2026-09-29.md · **Lenses:** senior-dev, security, qa

### Findings

1. **Governing-plan mode check validates only the new endpoint on an in-place change** — HIGH · lens: qa, senior-dev (co-reported): `mode_of` is keyed by path, so when old and new paths are equal the new mode overwrites the old; `docs/plan.md` going 100755 or 120000 → 100644 is accepted.
   → Editor: incorporated — `rule_holds()` checks the mode of each side whose path is the plan, so an in-place change needs 100644 on both sides. Fixtures: 100755 → 100644 and 120000 → 100644 refused. [introduced_by_pass: 6 — pass 6's path-keyed `mode_of`] [component: governing-plan-spec]
2. **Contradictory mode headers can forge governing-plan eligibility** — HIGH · lens: security: repeated `new file mode` / `old mode` / `new mode` lines overwrite earlier ones and a conflicting `index` mode is ignored, so symlink/executable modes followed by a forged `100644` pass.
   → Editor: incorporated — every mode source for a side must agree (`mode_agree`, six octal digits), the `index` mode included, and a mode stated for the missing side of an add/delete fails closed. Git never writes such headers (the diff comes from the editor's own `git diff`); this is defense in depth. Fixtures: a forged repeated `old mode`, an `index` mode contradicting `new mode`, and an `old mode` on an added file, all fail closed. [introduced_by_pass: 6 — pass 6's mode parsing] [component: diff-section-parser]
3. **Out-of-range octal escapes alias other paths** — HIGH · lens: security: `_unquote_c()` masks up to three octal digits with `& 0xFF`, so `\544` decodes to `d` like `\144`, and a malformed quoted path can resolve to the governing plan or the pass-log slot.
   → Editor: incorporated — `_decode_path()` accepts only git's canonical C-quoting (`_CANONICAL_C_QUOTED`: the named escapes or exactly three octal digits, `\000`–`\377`) before decoding; anything else fails closed. Selection's decoder is untouched. Fixtures: `\544ocs/…` aliasing the governing plan is refused; `\544`, `\7` and `\4000` are rejected by the parser. [introduced_by_pass: null — the mask predates this branch (selection_engine)] [component: diff-section-parser]
4. **Space-bearing paths are ambiguous in a markdown code span** — HIGH · lens: senior-dev: `_PLAIN_PATH` allows spaces anywhere, and CommonMark strips a paired leading/trailing space inside a code span, so ` plan.lock ` displays as `plan.lock`.
   → Editor: incorporated — `_is_plain()`: `_PLAIN_PATH` plus no empty component and no component starting or ending with a space. Fixtures: leading, trailing and space-padded-component paths refused; interior spaces still accepted. [introduced_by_pass: null — the pass-5 checkpoint narrowing (ac44dc7), a checkpoint decision rather than a pass fold] [component: plain-path-rule]
5. **A failed rule on a two-endpoint `generated` change is downgraded to "crossing"** — MEDIUM · lens: senior-dev: when both endpoints match the glob but one lacks an audit entry, the section is kept with a "crossing out of the class" warning instead of refusing.
   → Editor: incorporated — the keep-with-warning path is now only for a real crossing (an endpoint the spec didn't match, or one that isn't plain); when every endpoint matched and any fails its rule, the request is refused. Fixture: a generated rename with one of two audits missing refuses. [introduced_by_pass: null] [component: exclusion-class-rules]

### Code corrections applied

- iterate-review/SKILL.md step 10 (senior-dev, security, qa; merged) — the summary's `class` values still list `docs` → now `pass-log`, `governing-plan` or `generated`
- tools/check-scope-classification.py (qa) — prose-pin failures are counted as classifier-case failures (e.g. "23/24 passed") → the prose pin is counted as its own check (25/25)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-09-30 18:09; head SHA `dd43336a71bb694b6558255b30cc9b96a66c50ef`.
