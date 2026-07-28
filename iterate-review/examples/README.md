# iterate-review fixtures

Validate everything here with `tools/check-examples.py` from the repo root.

## Layout

| Path | What it covers |
|---|---|
| [`selection/`](selection/) | Deterministic lens routing — golden fixtures **plus a runnable reference implementation** |
| [`merge/`](merge/) | Semantic merge, worst-of aggregation, `FAILED` handling, attribution — goldens, read not run |
| `pass-1-response.json` | Reference well-formed single-lens Codex response |
| `pass-1-patch-marker-violation.response.json` | Schema-valid response that violates the *behavioral* no-patches rule |

## `pass-1-response.json`

A well-formed Codex response matching `../reviewer-output.schema.json`: a verdict,
all four required arrays, all required fields per item. Useful for exercising the
fold logic (step 12) without invoking real Codex.

**Pre-dates Axis 2.** It was captured when `iterate-review` ran a single reviewer
with no persona lenses, which is why the filename has no lens segment — the
current runtime writes `pass-N.<lensid>.response.json`. It has not been renamed,
because relabelling it as a lens response would be a small fiction: no lens
produced it.

**Reshaped for question classification (2.1):** its one `new_questions` entry is
now a `{question, settled_by, why}` object. Question text verbatim; container only.
The frozen copy under `../../v1/` keeps the original shape.

Its content is nonetheless squarely in the `senior-dev` lane (null deref, a test
assertion contradicting a function name, a missing JSDoc correction), so it doubles
as a realistic example of the **single-lens path** — which is still live whenever
selection picks `senior-dev` alone (see `selection/01`, `06`, `10`) and is an
acceptance criterion in its own right: single-lens behaviour must be a
non-regression against pre-Axis-2.

## `pass-1-patch-marker-violation.response.json`

A response that is **schema-valid but violates a behavioral rule** — it smuggles a
unified diff into a finding's `description` and says "Apply the patch above",
breaching HARD RESTRICTIONS → BEHAVIORAL #3 in `../reviewer-prompt.md`. Step 11's
belt-and-suspenders patch-marker scan must reject it before any fold happens.

Two Phase 4 audit fixes landed on this file:

1. **Renamed** from `pass-malformed.response.json`. The old name was wrong in a way
   that mattered: the file is neither malformed JSON nor schema-invalid. Calling it
   "malformed" invited the reading that schema validation would catch it, when the
   entire point is that schema validation *passes* and only the behavioral scan
   catches it.
2. **Removed a `$comment` key.** The schema sets `additionalProperties: false`, so
   `$comment` made the fixture schema-**invalid** — which meant it would have been
   rejected one step earlier than intended and could never have exercised the
   patch-marker path it exists to test. A fixture that cannot reach its own
   assertion is worse than no fixture, because it reads like coverage.

`tools/check-examples.py` now asserts both halves of its contract: schema-valid,
**and** actually carrying patch markers. If someone "cleans up" the diff out of the
description, the check fails.

## Fixture naming conventions

| Suffix | Contract | Enforced by |
|---|---|---|
| `*.json` | Parses **and** validates against `../reviewer-output.schema.json` | `tools/check-examples.py` |
| `*.json.malformed` | Must **not** parse — represents a lens that failed after retry | `tools/check-examples.py` |
| `*patch-marker-violation*.json` | Schema-valid **and** contains patch markers | `tools/check-examples.py` |
| `*.diff` | A real unified diff; feedable to `git apply` or a live run | — |

Any fixture whose name makes a claim should have that claim checked. The
`$comment` bug above is what happens when it isn't.
