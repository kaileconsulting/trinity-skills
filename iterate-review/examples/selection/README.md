# Selection-routing fixtures

Golden fixtures pinning `iterate-review`'s deterministic lens selection, plus a
reference implementation that runs them.

```bash
./check-selection.py                 # run all goldens; exit 1 on any mismatch
./check-selection.py 02-*.diff       # explain why a diff selects what it selects
```

## Why this exists

`../../lenses/README.md` makes a falsifiable claim:

> Two implementations applying these rules to the same diff MUST select the same
> lens set — that is the determinism guarantee.

At runtime there is exactly one implementation: Opus reading that README during
step 9 of `../../SKILL.md`. Prose read by a language model is precisely the kind
of implementation that drifts. `check-selection.py` is a genuine second
implementation, so the guarantee can be tested instead of asserted. **If the
script and Opus disagree about a diff, one of them misread the rules** — that
disagreement is the signal this directory exists to produce.

It also closes plan risk **R5 (selection rules misroute)**, whose stated
mitigation is "worked-example fixtures pin the routing." Pinning implies
something enforces it.

## Accepted diff formats

The checker parses three forms. This list is the contract — Codex asked in review
pass 2 whether the accepted format was narrower than the tooling implied, and it
was, silently. Each form now has a fixture or a self-test.

| Form | Example header | Notes |
|---|---|---|
| git | `--- a/lib/foo.py` | the `a/` / `b/` prefix is stripped per side |
| git, C-quoted | `--- "a/lib/my foo.py"` | git quotes when a path holds a space, quote, backslash or non-printable byte; escapes and octal UTF-8 are decoded |
| plain unified | `--- lib/foo.py<TAB>2026-07-28 …` | no `diff --git` line; the tab-separated timestamp is dropped |

**Side-prefix stripping is keyed on format, not on the header.** `--- a/lib/foo.py`
is genuinely ambiguous: in a git diff the `a/` is a side prefix, while in a plain
diff it is a real directory named `a`. The header cannot settle it, so the parser
strips the prefix only when the input contains a `diff --git` line. A consequence:
`git diff --no-prefix` output is **not** supported — it is git format without the
prefixes the format implies.

Two further behaviours worth knowing:

- **`---`/`+++` headers are authoritative for line attribution**; `diff --git` is a
  best-effort supplement. An unparseable `diff --git` line costs nothing for any
  diff carrying content — it matters only for a pure rename with no hunks, which
  contributes no changed lines but can still match a `path_glob`.
- **Each diff side is classified by its own path.** A `-` line belongs to the *old*
  path and a `+` line to the *new* one, so a source file renamed out of
  `source_exts` still counts the side that genuinely was source. Attributing both
  sides to the new path was a real bug (fixture 11).

Anything outside these three forms is not supported. Two residual limitations, both
accepted deliberately:

- A removed line whose content begins `--- ` is disambiguated from a file header by
  tracking whether the parser is inside a hunk. Correct for well-formed diffs, but a
  heuristic rather than a full diff grammar.
- Format detection is **per input, not per file section**. A single file
  concatenating a git diff *and* a plain diff would be classified as git format
  throughout, so a plain header later in the bundle would have a real `a/` component
  stripped. Curated single-format fixtures are the supported workflow; if mixed
  bundles ever become one, compute the format per section instead. (Note this is not
  triggered by a *content* line reading `diff --git …` — hunk content always carries
  a `+`, `-` or space prefix, so it never matches at position 0.)

## This is test-only

The skill does **not** call `check-selection.py` during a real review. Selection
stays Opus's judgment at runtime, deliberately — the rules include *"when a
heuristic is borderline, run the lens"*, which is a judgment call a pattern
matcher cannot make. Wiring the script into the runtime path would make the
system more predictable and slightly dumber; it was considered and declined.

## Drift discipline

Two copies of a rule is how a checker starts lying. The script therefore
**reads** the rule data rather than restating it:

| Rule data | Lives in | Script behaviour |
|---|---|---|
| `path_globs`, `content_regexes`, `non_trivial_without_tests`, `always` | `../../lenses/<id>.md` frontmatter | parsed at runtime |
| `source_exts`, `test_globs`, non-trivial line threshold, match-span bound + overlap | `../../lenses/README.md` | parsed at runtime |
| Evaluation algorithm (glob semantics, case-insensitivity, which diff lines count) | `check-selection.py` | the only duplication |

Consequences worth knowing:

- **Editing a lens's globs/regexes needs no script change.** The fixtures may
  legitimately start failing — that is the checker doing its job. Update
  `expected.tsv` deliberately, not reflexively.
- **Adding a lens is picked up automatically** (any `../../lenses/*.md` that
  isn't `README.md`). Add fixtures covering its selection surface.
- **Unparseable rule data is a hard error (exit 2), never a silent default.** If
  someone reformats the README's `source_exts` line beyond recognition, the
  script fails loudly rather than quietly matching nothing.
- **The threshold is read from the bullet that *defines* it**, anchored on
  "non-trivial source change" rather than the first phrase in the file matching
  `≥ N changed non-blank`. An unanchored search would let a future worked example
  or caveat mentioning a different count silently become the threshold — which
  would break the source-of-truth claim in the exact way that is hardest to
  notice. Pinned by a self-test in `tools/test-checkers.py` using a decoy phrase.
- The README and lens frontmatter are **always the source of truth**. If the
  algorithm here disagrees with them, the algorithm is wrong.

## Fixture inventory

`expected.tsv` is the golden file: fixture, expected lens set, and the rule the
row isolates. Rows 01–07 mirror the README's worked-examples table one-for-one.
Rows 08–10 pin the "Glob/extension semantics" bullet — cases a naive
implementation gets wrong:

| Fixture | Isolates |
|---|---|
| `01-local-rename` | floor lens alone; below the non-trivial threshold |
| `02-unauth-endpoint` | security via SQL regex; qa via `**/routes/**` |
| `03-parse-csv-no-tests` | qa via `non_trivial_without_tests` **only** |
| `04-lockfile-bump` | `.json` is outside `source_exts` → non-trivial count is 0 |
| `05-error-string` | qa via `content_regexes`, no security surface |
| `06-helper-plus-test` | the "no accompanying test change" clause, with a genuinely non-trivial (9-line) source change |
| `07-request-regex` | security via `parse_qs`; qa via `**/handlers/**` |
| `08-root-auth-file` | leading `**/` matches **zero** segments |
| `09-uppercase-paths` | `path_globs` are case-insensitive |
| `10-mixed-case-test-file` | `test_globs`/`source_exts` are case-insensitive (`src/Foo.TEST.TS`) |
| `11-source-to-nonsource-rename` | each diff side is classified by **its own** path — a rename out of `source_exts` still counts its removed source lines |
| `12-quoted-path-rename` | git C-quoted paths (a space in the filename) |
| `13-plain-unified-with-timestamps` | a non-git unified diff with tab-separated timestamps and no `diff --git` line |
| `14-minified-json-span` | the content-regex **match-span bound** — a pattern must not bridge a whole minified-JSON file (issue #5) |

Rows 11–13 all came out of the Phase 4 code review, and all three shared one
failure mode: the checker returned a **wrong answer silently**, reporting zero
changed source lines and quietly not selecting `qa`. For a tool whose only value
is being a trustworthy second opinion, silently wrong is the worst possible
behaviour — worse than crashing. Row 11 was the parser attributing a rename's `-`
lines to the new path; rows 12–13 were unhandled header formats.

Each fixture is a real unified diff, so the same file can be fed to `git apply`
or to a live `iterate-review` run if you want to compare the script's answer
against Opus's.

## Adding a fixture

1. Write the `.diff`. Make it isolate **one** rule — if two rules would select
   the same lens, the fixture can't tell you which one broke.
2. Add a row to `expected.tsv` (tab-separated), including the rule it isolates.
3. Run `./check-selection.py`. If it fails, decide which side is wrong before
   changing either.
