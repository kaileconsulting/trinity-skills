# iterate-review lenses

Persona lenses for diff-time review (Axis 2). Each lens is a **data-shaped record**: YAML frontmatter (identity + deterministic selection + matched-context spec) followed by a **persona-prompt fragment** that layers onto the shared reviewer contract in `../reviewer-prompt.md`.

The shared contract (HARD RESTRICTIONS, output schema, scope guidance, convergence guidance) stays common. A lens fragment replaces the **ROLE**, supplies a **FOCUS** list, and may add a short **lens-specific guidance** note after FOCUS (lane boundaries / output reminders). At fan-out time the skill concatenates: shared contract → lens ROLE → lens FOCUS (+ guidance) → `=== INTENT/DIFF/PRIOR PASSES ===` (with the lens's matched-context framing prepended).

## Lens record format

```yaml
---
id: <slug>                       # unique lens id, also its attribution tag
skill: iterate-review            # owning skill
role: <one-line role title>
selection:
  always: true|false             # true = runs on every pass (the floor lens)
  match: any                     # ANY path_glob OR content_regex match selects the lens
  path_globs: [ ... ]            # globs over changed file paths (see Matching semantics)
  content_regexes: [ ... ]       # regexes over added/removed diff lines
  non_trivial_without_tests: true|false   # optional (qa): select on an untested non-trivial change
matched_context: <framing prepended for this lens; v1 = framing, not extraction>
---
<persona-prompt fragment: ROLE + FOCUS>
```

## Selection rules (deterministic — no LLM router)

`senior-dev` is the **floor**: always runs. `security` and `qa` are selected by heuristics over the diff (changed paths + added/removed content). **Any** heuristic match selects the lens.

| Lens | Runs when |
|---|---|
| `senior-dev` | **always** |
| `security` | diff touches auth/authz, crypto, secrets/credentials, network I/O, migrations/schema, input parsing/deserialization, or permissions (see `security.md` heuristics) |
| `qa` | user-facing surface changes (`path_globs` / `content_regexes`), OR a non-trivial source change with no test change (`non_trivial_without_tests`) |

## Matching semantics (deterministic — how `selection` is evaluated)

A lens with `always: true` (senior-dev) is always selected. For the others, evaluate `selection` over the diff deterministically:

- **`path_globs`** — matched against each changed file's repo-relative path, **case-insensitive**; `**` matches any number of path segments. Matches if ANY changed path matches ANY glob.
- **`content_regexes`** — PCRE, **case-insensitive**, matched against the **added (`+`) and removed (`-`) content lines** of the unified diff only (not context lines, not the `@@`/`+++`/`---` headers). Matches if ANY regex matches ANY changed line.
  - *Match-span bound:* a content regex is evaluated against at most **400 characters** of a changed line at a time. Lines longer than that are chunked with a **200-character overlap**, so any genuine match up to 200 characters is still found in full while a pattern cannot bridge arbitrarily distant text. This exists because **minified or single-line JSON makes an entire file one "changed line"** — without the bound, a pattern like `(SELECT|UPDATE|…)\s+.*\b(FROM|TABLE)\b` can span hundreds of characters of unrelated content and match a file containing no SQL at all. Observed spanning 959 characters before the bound was added.
- **`match: any`** — the lens is selected if ANY `path_glob` OR ANY `content_regex` matches (plus, for qa, the rule below).
- **`non_trivial_without_tests`** (qa only) — selected when the diff contains a **non-trivial source change** with **no accompanying test change**:
  - *source file* = a changed file whose extension is in `source_exts` **and** whose path does not match `test_globs`. Files outside `source_exts` (docs, config, data — `.md`, `.json`, `.yaml`, lockfiles, etc.) never count toward non-trivial.
  - *non-trivial source change* = **≥ 8 changed non-blank content lines across source files**, where a *changed line* is any added (`+`) or removed (`-`) line in the unified diff — a modified line counts as both its `-` and its `+` (i.e. 2), and a deletion-only change counts its `-` lines. This is a deliberately mechanical count — it does **not** parse comments or detect symbol definitions per-language, so it is language-agnostic and two implementations compute the same result.
  - *no accompanying test change* = the diff changes no file matching `test_globs`.
  - `source_exts`: `.py .js .jsx .ts .tsx .go .rb .java .rs .c .cc .cpp .h .hpp .cs .php .swift .kt .scala .sh`
  - `test_globs`: `**/*test*`, `**/*spec*`, `**/tests/**`, `**/__tests__/**`, `**/*_test.go`
  - *Glob/extension semantics:* `test_globs` use the same repo-relative, **case-insensitive** `**` glob semantics as `path_globs`; `source_exts` extension comparison is also **case-insensitive** (so `src/Foo.TEST.TS` matches `test_globs`, and `.TS` matches `source_exts`).
  - *Consequence (intended):* a large mechanical change (e.g. a wide rename) that crosses the 8-line threshold with no test change **will** select `qa` — that is the over-inclusion bias, and qa will APPROVE quickly if it's a genuine no-op. Changes below the threshold do not select qa on this rule.

Two implementations applying these rules to the same diff MUST select the same lens set — that is the determinism guarantee. The pattern lists in each lens file are the **v1 baseline, not a closed set**; they are extensible.

### Ambiguity biases toward inclusion (load-bearing)

When a heuristic is borderline — *is this "network"? is this "user-facing"? is this change "non-trivial"?* — **run the lens.** A false include costs one wasted Codex call; a false exclude costs the category-specific miss the lens exists to catch (plan R5). Do not tune heuristics narrow enough to pass only the worked examples below.

### Worked examples (incl. borderline)

| Diff | senior-dev | security | qa | Why |
|---|---|---|---|---|
| Rename a local variable within one function (≤ 8 changed lines) | ✅ | — | — | below the non-trivial threshold; no category surface |
| Add an HTTP endpoint with no auth check | ✅ | ✅ | ✅ | auth + network (security), user-facing (qa) |
| Add a `parse_csv()` with no tests | ✅ | ✅ | ✅ | input parsing (security, borderline→include), new code w/o tests (qa) |
| Bump a dependency version in a lockfile | ✅ | ✅ | — | dependency change can carry a vuln → security (borderline→include) |
| Reword a user-facing error string | ✅ | — | ✅ | user-visible behavior change |
| Add an internal pure helper + its unit test | ✅ | — | — | not user-facing, tests present, no security surface |
| Change a regex used on request input | ✅ | ✅ | ✅ | input parsing + potential ReDoS (security), behavior change (qa) |

## Merge & attribution

The editor merges all selected lenses' findings (semantic dedupe; co-reported findings retain **all** contributing lens ids), aggregates verdict worst-of, and records each finding's originating lens id in the pass log — the attribution that powers the ROI metric. A selected lens that fails after one retry is recorded as `FAILED` (orchestration metadata, not a verdict), aggregates the pass to REVISE, and blocks Converge with an (R)etry option.
