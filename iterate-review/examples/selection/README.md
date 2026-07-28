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
| `source_exts`, `test_globs`, non-trivial line threshold | `../../lenses/README.md` | parsed at runtime |
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

Each fixture is a real unified diff, so the same file can be fed to `git apply`
or to a live `iterate-review` run if you want to compare the script's answer
against Opus's.

## Adding a fixture

1. Write the `.diff`. Make it isolate **one** rule — if two rules would select
   the same lens, the fixture can't tell you which one broke.
2. Add a row to `expected.tsv` (tab-separated), including the rule it isolates.
3. Run `./check-selection.py`. If it fails, decide which side is wrong before
   changing either.
