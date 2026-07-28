# Code Review — working

## Pass 1 — 2026-07-27 17:58 [HISTORICAL]

**Scope:** working · **Diff size:** 227 lines · **Verdict:** REVISE

### Findings

1. **iterate-review lens selection is not deterministic enough to implement or test** — HIGH: `when_diff_touches` were broad natural-language categories (`network`, `input parsing`, `user-facing`, `non-trivial`) with no matching algorithm — two implementations would select different lenses for the same diff, breaking the "deterministic, testable" promise.
   → Opus: incorporated — operationalized selection into `path_globs` + `content_regexes` + `non_trivial_without_tests`, and added a **Matching semantics** spec to `iterate-review/lenses/README.md` (case-insensitivity, added/removed-line matching only, non-trivial threshold = ≥8 non-blank/non-comment lines or a def add/remove, `test_globs`, explicit determinism guarantee). Rewrote `security.md` and `qa.md` frontmatter accordingly.
2. **iterate-plan required-section handling is internally inconsistent** — MEDIUM: `architect.md` had no `requires_sections` despite the README saying it consumes Approach sections; PM's section names differed across three files (`Goals (MVP)` vs `Goals/Non-goals` vs `Who / Use cases + Goals + Acceptance criteria`).
   → Opus: incorporated — added a **canonical section-name table** to `iterate-plan/lenses/README.md`; added `requires_sections: ["Approach","Phasing"]` to `architect.md`; normalized PM `matched_context` to the exact template headings.
3. **README claims fragments only replace ROLE + supply FOCUS, but fragments add behavioral instructions** — LOW: the documented record shape was narrower than the actual files (which carry lane/output guidance).
   → Opus: incorporated — both READMEs now define a fragment as ROLE + FOCUS + optional short **lens-specific guidance**; `security.md`/`qa.md` group that guidance under an explicit heading.

### Code corrections applied

- (none — Codex returned no `code_corrections`)

### New questions Codex raised

- (none)

### Diff snapshot reference

Diff captured 2026-07-27 17:58 UTC on branch `axis-2-persona-lenses` (base `main` @ `30e2a0b`); Phase 0 lens files intent-to-added (`git add -N`) so the working diff includes them. Not yet committed.

## Pass 2 — 2026-07-27 18:05 [HISTORICAL]

**Scope:** working · **Diff size:** 320 lines · **Verdict:** REVISE

### Findings

1. **QA non-trivial selection still leaves implementation-dependent cases** — HIGH: `non_trivial_without_tests` still leaned on underspecified notions (source-vs-test file, comment-line handling, symbol-definition detection) that two implementations could read differently.
   → Opus: incorporated — made the rule purely mechanical: **≥8 added/modified non-blank lines in files matching a defined `source_exts` set (and not `test_globs`)**; dropped comment-parsing and symbol-detection entirely (language-agnostic, reproducible); documented the intended over-inclusion consequence for large mechanical changes.
2. **Worked example contradicts the QA fallback rule for broad refactors** — MEDIUM: "rename across 3 files → senior-dev only" could exceed the ≥8-line threshold and thus select `qa`.
   → Opus: incorporated — narrowed the example to a within-one-function rename (≤8 changed lines), and documented that a large rename intentionally *does* pull in `qa`.

### Code corrections applied

- (none — Codex returned no `code_corrections`)

### New questions Codex raised

- (none)

### Diff snapshot reference

Diff captured 2026-07-27 ~18:05 UTC on branch `axis-2-persona-lenses` (base `main` @ `30e2a0b`); Phase 0 lens files intent-to-added. Not yet committed.

## Pass 3 — 2026-07-27 18:12 [HISTORICAL]

**Scope:** working · **Diff size:** ~330 lines · **Verdict:** REVISE

### Findings

1. **QA non-trivial line-count wording still conflicts on deletions** — HIGH: "≥ 8 added-or-modified non-blank lines" vs "count `+`/`-` content lines only" are not equivalent — a modified line (`-`+`+`) and deletion-only changes counted differently across readings, reintroducing implementation-dependent selection.
   → Opus: incorporated — restated the threshold as **≥ 8 changed non-blank content lines**, where a *changed line* = any `+` or `-` line (modified = 2, deletion-only counts its `-` lines). One unambiguous rule, used consistently with the worked-example wording.

### Code corrections applied

- (none — Codex returned no `code_corrections`)

### New questions Codex raised

- (none)

### Diff snapshot reference

Diff captured 2026-07-27 ~18:12 UTC on branch `axis-2-persona-lenses` (base `main` @ `30e2a0b`); Phase 0 lens files intent-to-added. Not yet committed.

## Pass 4 — 2026-07-27 18:19 [HISTORICAL]

**Scope:** working · **Diff size:** ~335 lines · **Verdict:** REVISE

### Findings

1. **Plan required-section matching still has two possible interpretations** — MEDIUM: the table showed bare `Approach` but the note showed `## Approach` (with marker); frontmatter uses bare names — ambiguous canonical string.
   → Opus: incorporated — declared the canonical form to be the **bare H2 title text with the `## ` marker stripped**, stated once and applied to table, examples, frontmatter, and slicing wording.
2. **QA test/source glob matching inherits unspecified case/glob semantics** — LOW: `test_globs`/`source_exts` didn't state whether they share `path_globs`' case-insensitive `**` semantics.
   → Opus: incorporated — added a *Glob/extension semantics* line: `test_globs` use the same repo-relative case-insensitive `**` semantics; `source_exts` comparison is case-insensitive.

### Code corrections applied

- (none — Codex returned no `code_corrections`)

### New questions Codex raised

- (none)

### Diff snapshot reference

Diff captured 2026-07-27 ~18:19 UTC on branch `axis-2-persona-lenses` (base `main` @ `30e2a0b`); Phase 0 lens files intent-to-added. Not yet committed.

## Pass 5 — 2026-07-27 18:26 [HISTORICAL]

**Scope:** working · **Diff size:** ~340 lines · **Verdict:** REVISE

### Findings

1. **Security input-parsing worked example not selected by declared heuristics** — MEDIUM: the README example `Add a parse_csv() with no tests → security` and the "input parsing" category weren't mechanically implied — `security.md` had no input-parsing heuristic, so `parse_csv` wouldn't match.
   → Opus: incorporated — added an input-parsing `content_regex` to `security.md` (`parse[_a-z]+|parse(|read_csv|csv.reader|xml.|etree|lxml|beautifulsoup|multipart|urlparse|parse_qs|form-data`), making the worked example true. Consistent with "input parsing is a security surface" + the over-inclusion bias.

### Code corrections applied

- (none — Codex returned no `code_corrections`)

### New questions Codex raised

- (none)

### Diff snapshot reference

Diff captured 2026-07-27 ~18:26 UTC on branch `axis-2-persona-lenses` (base `main` @ `30e2a0b`); Phase 0 lens files intent-to-added. Not yet committed.

## Pass 6 — 2026-07-27 18:33 [HISTORICAL]

**Scope:** working · **Diff size:** ~340 lines · **Verdict:** APPROVE

### Findings

- (none — confirming pass; the pass-5 input-parsing fold verified, no new issues)

### Code corrections applied

- (none)

### New questions Codex raised

- (none)

### Convergence

Pass 6 returned APPROVE with zero findings, confirming the pass-5 fold. **iterate-review converged on Phase 0 after 6 passes** (1H2M → 1H1M → 1H → 1M1L → 1M → APPROVE); all HIGH/MEDIUM/LOW findings resolved. The selection contract is now mechanically deterministic (path_globs + content_regexes + a line-count rule with defined source_exts/test_globs), and the iterate-plan section-slicing contract is canonicalized.

### Diff snapshot reference

Diff at 2026-07-27 ~18:33 UTC on branch `axis-2-persona-lenses` (base `main` @ `30e2a0b`).
