# Code Review — Phase 4 fixtures + tooling (Axis 2)

Reviewed via direct single-Codex passes (shared contract + `senior-dev` framing)
rather than dogfooding the multi-lens `iterate-review` on the fixtures that assert
its own merge/verdict machinery — non-circular by design, same treatment as
Phase 1.

## Pass 1 — 2026-07-28 [HISTORICAL]

**Scope:** `HEAD~1..HEAD` (commit `8a16982`, 40 files) — selection fixtures +
`check-selection.py`, merge goldens for both skills, two shared-machinery deltas,
the pre-existing-fixture audit, and `tools/` · **Verdict:** REVISE

### Findings

1. **Changed-line counting attached to the wrong file for renames** — HIGH:
   `check-selection.py` set the current path from the `diff --git` line's *new*
   path and recorded every subsequent `+` and `-` line under it. A source file
   renamed out of `source_exts` (e.g. `lib/calc.py` → `notes/calc.txt`) therefore
   counted **zero** changed source lines, so `qa` could fail to select where the
   prose rule selects it.
   → Opus: **incorporated** — verified first: a purpose-built rename fixture
   reported `source lines: 0` against 8 removed source lines. `parse_diff` now
   returns added-by-new-path and removed-by-old-path separately, and
   `nontrivial_source_line_count` classifies each side by its own path. Added
   fixture `11-source-to-nonsource-rename.diff` (golden `qa,senior-dev`; returned
   `senior-dev` only before the fix) plus three self-tests.
   → **Partially disputed on scope:** the finding also claimed deleted source
   files were miscounted. They were not — git writes `diff --git a/x b/x` for a
   deletion, so the new path *is* the source path. Verified empirically (8 source
   lines, `qa` selected) both before and after the fix. A regression test now pins
   the deletion case so it stays correct.
   → Also fixed while in the same function: a removed line reading `--- foo` was
   parseable as a file header. `in_hunk` tracking now prevents it. Not raised by
   Codex; found while reworking the parser.

2. **README threshold parsed by unanchored regex** — MEDIUM: the non-trivial line
   threshold was extracted with a repo-wide search for any `≥ N changed non-blank`
   phrase, so future prose mentioning a different count could silently become the
   threshold — undermining the stated "README is the source of truth" discipline
   in the hardest-to-notice way.
   → Opus: **incorporated** — anchored to the bullet that defines the rule
   (`non-trivial source change` … `≥ N changed non-blank`), with a failure message
   saying the threshold is read from that bullet specifically. Self-test uses a
   decoy `>= 99 changed non-blank` phrase placed *earlier* in the file and asserts
   the parsed threshold is still 8.

3. **Parity pattern for corrections-dedupe was structurally loose** — MEDIUM: the
   rule matched `dedupe (plan|code)_corrections` anywhere in either file, so it did
   not require each skill to state the rule for **its own** correction field, and
   did not require the rule's substance. A cross-reference to the sibling skill
   could satisfy it without the per-pass loop instructing anything.
   → Opus: **incorporated** — `RULES` entries now accept per-skill patterns
   (`{skill: [patterns]}`) as well as a shared list. The corrections rule requires,
   per skill, its own field name **plus** `corrections are applied mechanically`
   **plus** `collapse by location + intended fix`. A per-skill rule that forgets a
   skill is now an exit-2 config error rather than a silent pass. Three self-tests,
   including one proving a crossed pattern is *not* satisfied by the sibling's text.

### Code corrections applied

- `merge/01-dedupe-and-worst-of/pass-1.qa.response.json` — the fixture returns
  APPROVE while filing a MEDIUM, and the golden presented that as unremarkable.
  → Kept APPROVE (it is the only case in the fixture set where worst-of has to
  discriminate; changing it to REVISE would remove the thing the scenario pins) and
  added an explicit callout in `expected-merge.md` labelling it a deliberately
  atypical fixture, not a model for reviewer behaviour.

### New questions Codex raised

- (none)

### Diff snapshot reference

Commit `8a16982` on branch `axis-2-persona-lenses` (base `main` @ `30e2a0b`).
Suite state after folding: 11/11 routing fixtures, 11/11 example fixtures,
32/32 parity rules, 25/25 checker self-tests.

## Pass 2 — 2026-07-28 [HISTORICAL]

**Scope:** working tree — pass 1's fold on top of `8a16982` · **Verdict:** REVISE

Both findings share one failure mode, and it is the one that matters most for this
tool: the checker returned a **wrong answer silently** — zero changed source lines,
`qa` quietly not selected. For something whose only value is being a trustworthy
second opinion, silently wrong is worse than crashing.

### Findings

1. **Quoted paths dropped by the header parser** — HIGH: `---`/`+++` handling
   stripped only a literal `a/` / `b/`, so git's C-quoted form
   (`--- "a/lib/my calc.py"`, used whenever a path contains a space, quote,
   backslash or non-printable byte) produced a path *including the quotes and
   prefix*. That path matched no `source_exts` entry and no `path_glob`, and it also
   polluted `changed_paths` with a non-canonical value. The `diff --git` regex
   required a bare `a/` too, so it failed on the same input rather than
   compensating.
   → Opus: **incorporated** — verified first: the quoted rename reported
   `source lines: 0` and `changed paths: "a/lib/my calc.py", "b/notes/my calc.txt"`.
   Added `_unquote_c` (C-style escapes plus octal UTF-8, byte-buffered so multi-byte
   sequences decode correctly), `_normalise_header_path`, and a quote-aware
   `_parse_diff_git`. Fixture `12-quoted-path-rename.diff`; 5 self-tests.

2. **Tab-separated timestamps became part of the path** — MEDIUM: a plain
   (non-git) unified diff writes `--- lib/foo.py<TAB>2026-07-28 …`. The timestamp
   stayed in the path, so `splitext` saw a nonsense extension and the file stopped
   counting as source. Pass 2's intent had explicitly asked about no-`diff --git`
   diffs, so this was the answer to a question I posed.
   → Opus: **incorporated** — the header payload is split at the first tab before
   unquoting (safe ordering: a quoted path's closing quote precedes any timestamp,
   and a tab *inside* a quoted path is escaped as `\t`, never raw). Fixture
   `13-plain-unified-with-timestamps.diff`; 2 self-tests.

### Code corrections applied

- (none — Codex returned no `code_corrections`)

### New questions Codex raised

- *"Should selection fixtures intentionally support git-quoted paths and
  timestamp-bearing non-git unified diffs, or is the accepted diff format narrower
  than the README/tooling currently implies?"*
  → **Answered:** it was narrower, silently — which was the defect. Resolved by
  supporting all three forms **and** writing the contract down: the selection README
  now has an "Accepted diff formats" section listing git, git-C-quoted, and plain
  unified, each backed by a fixture or self-test, plus the residual limitation
  (in-hunk `--- ` disambiguation is a heuristic, not a full diff grammar).

### Diff snapshot reference

Working tree on `axis-2-persona-lenses`. Suite state after folding: 13/13 routing
fixtures, 11/11 example fixtures, 32/32 parity rules, 34/34 checker self-tests.
Merged HIGH+MEDIUM count 3 → 2, so the convergence trend is decreasing.

## Pass 3 — 2026-07-28 [HISTORICAL]

**Scope:** working tree — pass 2's fold · **Verdict:** REVISE

### Findings

1. **Side-prefix stripping applied to plain unified diffs too** — MEDIUM:
   `_normalise_header_path` stripped a leading `a/` / `b/` unconditionally. Correct
   for git headers, wrong for the plain unified format the README had just promised
   to support: a real path under a top-level directory named `a` (`a/lib/foo.py`)
   was silently normalised to `lib/foo.py`, which can add or drop `path_glob`
   matches and leaves `changed_paths` wrong.
   → Opus: **incorporated.** `--- a/lib/foo.py` is *genuinely* ambiguous — the
   header alone cannot distinguish a git side prefix from a real directory — so it
   is resolved from format context instead: `parse_diff` computes `git_format` from
   the presence of a `diff --git` line anywhere in the input and strips the prefix
   only in git format. Two self-tests pin both directions (plain preserves
   `a/lib/foo.py`; git still yields `lib/foo.py`). The README now states the rule
   and its consequence: `git diff --no-prefix` is not supported, being git format
   without the prefixes the format implies.

   Codex offered narrowing the README as the cheaper alternative. Rejected: it
   would leave a silently-wrong case *inside* the stated contract, which is the
   failure mode all three passes have been about.

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Diff snapshot reference

Working tree on `axis-2-persona-lenses`. Suite state after folding: 13/13 routing
fixtures, 11/11 example fixtures, 32/32 parity rules, **36/36** checker self-tests.
Merged HIGH+MEDIUM count 3 → 2 → 1: strictly decreasing across both transitions,
so the non-convergence guardrail is not implicated.

## Pass 4 — 2026-07-28 [HISTORICAL] (confirming)

**Scope:** working tree — pass 3's fold · **Verdict:** APPROVE

### Findings

1. **Git-format detection is per input, not per file section** — LOW: `git_format`
   is derived from whether any line starts with `diff --git `, so a single file
   concatenating a git diff *and* a plain diff would be treated as git format
   throughout, stripping a real `a/` component from the plain section's headers.
   Codex's own action was *"no code change required for this pass"* — curated
   single-format fixtures are the supported workflow, and the README scopes accepted
   formats rather than promising mixed bundles.
   → Opus: **incorporated as documentation, not code** — added to the README's
   residual-limitations list alongside the in-hunk `--- ` heuristic, with the
   remedy noted (compute format per section) should mixed bundles ever be supported.

   The pass also **confirmed** the reasoning behind the pass-3 fold that this pass
   was asked to attack: a *content* line reading `diff --git …` cannot trigger a
   false positive, because hunk content always carries a `+`, `-` or space prefix and
   so never matches at position 0.

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Convergence reasoning

Verdicts: REVISE (1H 2M) → REVISE (1H 1M) → REVISE (1M) → **APPROVE (1L)**. Merged
HIGH+MEDIUM count 3 → 2 → 1 → 0, strictly decreasing at every transition. Pass 4
raised only a LOW whose recommended action was explicitly no code change, and it
independently confirmed the mechanism behind the previous fold rather than reopening
it. No lens `FAILED`; no open questions outstanding. **Converged.**

Suite state at convergence: 13/13 routing fixtures, 11/11 example fixtures, 32/32
parity rules, 36/36 checker self-tests — `tools/check-all.sh` green.

### Reviewer-diversity note

All four passes used the same reviewer model with `senior-dev` framing, chosen for
non-circularity: dogfooding the multi-lens `iterate-review` on the fixtures that
assert its own merge and verdict machinery would let a defect in that machinery mask
itself. The cost is that this review had no `security` or `qa` lens on it. Given the
diff is dev-time tooling with no runtime path, no network, and no untrusted input,
that is an acceptable trade — but it is a real gap, not an oversight.
