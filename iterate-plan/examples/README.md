# iterate-plan fixtures

Validate everything here with `tools/check-examples.py` from the repo root.

## Layout

| Path | What it covers |
|---|---|
| [`merge/`](merge/) | Semantic merge, co-report attribution, degraded context, conflicting open-question answers — goldens, read not run |
| `pass-4-response.json` | A real Codex response, kept as ground truth |

There is no `selection/` directory here. `iterate-plan`'s selection is
unconditional — both `architect` and `product-manager` run on every pass — so
there is no routing to pin. The routing fixtures and their reference
implementation live under `../../iterate-review/examples/selection/`.

## `pass-4-response.json`

A **real** Codex response from pass 4 of `iterate-plan`'s own v3/v4 development —
not synthetic. Worth keeping for two reasons the hand-written fixtures can't
serve:

- It shows what genuine Codex output looks like: single-line JSON, real prose
  register, the actual level of specificity in `suggested_action`.
- It is a check on the synthetic fixtures. If a hand-written response reads
  noticeably unlike this one, the fixture is modelling an idealised reviewer.

**Pre-dates Axis 2.** Captured before persona lenses existed, hence no lens
segment in the filename; the current runtime writes
`pass-N.<lensid>.response.json`. Not renamed — no lens produced it, and
relabelling it would be revisionist.

**Audited in Phase 4:** validates cleanly against the current
`../reviewer-output.schema.json`. The shared-contract/per-lens split changed how
the reviewer *prompt* is assembled and left the output schema untouched, so this
fixture asserts nothing the split removed. No update needed.

## Fixture naming conventions

Shared with the sibling skill — see
[`../../iterate-review/examples/README.md`](../../iterate-review/examples/README.md#fixture-naming-conventions).
