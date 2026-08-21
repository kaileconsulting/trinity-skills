# tools/

Dev-time checks for the trinity skills. **None of these run during a real skill
invocation** — the skills are prose that the editor follows, and these tools exist to
keep that prose honest.

```bash
tools/check-all.sh          # everything
```

Requires `python3` and `jsonschema` (`pip install jsonschema`), plus `jq` on
PATH for `check-provenance-recipe.py` (that checker reports a clear error,
not a traceback, if `jq` is missing).

| Tool | Checks | Kind |
|---|---|---|
| `../iterate-review/examples/selection/check-selection.py` | Lens routing against golden fixtures | Reference implementation |
| `check-runners.py` | `iterate-review`'s runner scripts (`bin/`): byte-deterministic composition, exit contracts, lock lifecycle, pass-log resolution, prune safety | Behavioral fixtures |
| `check-plan-runners.py` | `iterate-plan`'s adapted runner behavior (composition, section extraction, selection, `--plan`/`--note` boundaries) plus the HEAD-sourced register resolution's four states (loaded / confirmed-absent / malformed / operational-failure) end to end | Behavioral fixtures |
| `check-examples.py` | Every example response validates against its skill's schema; fixtures whose *names* make claims have those claims verified | Schema + contract |
| `check-parity.py` | The shared machinery's rules are present in **both** skills' per-pass loops (semantic parity), plus byte-identity on the designated shared runner files | Drift alarm |
| `check-provenance-recipe.py` | The shared `provenance-recipe.jq` query reproduces per-pass tallies (pass counts, fold-caused share, disposition mix, the non-production rollback query) from real sample state files, across both skills | Reference query |
| `check-scope-classification.py` | `iterate-review`'s production/non-production diff-path heuristic (`scope_classifier.py`), boundary-case-tested | Reference implementation |
| `check-question-freeze.py` | `iterate-plan`'s open-question freeze counting semantics (`freeze_tracker.py`) — the streak state machine, boundary-case-tested | Reference implementation |
| `test-checkers.py` | The checks above actually fail when they should | Self-test |
| `check-all.sh` | Runs all of the above | Runner |

## Why a repo of prose has a test suite

The skills have no executable implementation. That makes two failure modes
invisible without tooling:

1. **Rule drift between the two skills.** `iterate-plan` and `iterate-review`
   describe the *same* machine — fan-out, merge, worst-of, loop guardrails — in
   two files, in deliberately different prose. Editing one and forgetting the
   other produces no error anywhere. `check-parity.py` is the alarm.
2. **Fixtures that quietly stop meaning anything.** Phase 4's audit found a
   fixture whose whole purpose was to exercise the patch-marker rejection path,
   carrying a `$comment` key that made it schema-**invalid** — so it would have
   been rejected a step earlier and could never reach the check it existed to
   test. It had read as coverage for two months. `check-examples.py` now asserts
   both halves of that fixture's contract.

## What these tools cannot do

Worth stating plainly, because a green run is persuasive:

- **`check-parity.py` checks presence, not correctness.** It confirms a rule is
  *stated* in both skills. A rule stated wrongly in both passes.
- **Merge is not tested anywhere.** Semantic dedupe is the editor's judgment by design
  (plan Q3), so it has goldens to compare against, not assertions. See
  `../iterate-review/examples/merge/README.md`.
- **`check-selection.py` is a second opinion, not the authority.** The lens
  frontmatter and `lenses/README.md` are the source of truth. If the script and
  the editor disagree on a diff, that disagreement is the finding — and the script is
  as likely to be the one that's wrong.

## Adding a check

Add its failure mode to `test-checkers.py` in the same change. A check that has
never been observed failing has not been shown to work.
