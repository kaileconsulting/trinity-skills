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
