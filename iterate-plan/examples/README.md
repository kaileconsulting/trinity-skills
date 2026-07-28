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

**Audited in Phase 4:** validated cleanly against the schema as it stood then. The
shared-contract/per-lens split changed how the reviewer *prompt* is assembled and
left the output schema untouched, so it asserted nothing that split removed.

**Reshaped for question classification (2.1).** Its one `new_questions` entry went
from a bare string to the `{question, settled_by, why}` object the schema now
requires. The question **text is verbatim**; only the container changed, and a
`settled_by` of `resolvable_in_fold` plus a `why` were added. Flagging it because
this is the repo's only *real* Codex capture, and it is now a lightly-reshaped
artifact rather than a byte-exact one — the frozen copy at
`../../v1/iterate-plan-v1/examples/pass-4-response.json` remains untouched if you
need the original shape.

## Fixture naming conventions

Shared with the sibling skill — see
[`../../iterate-review/examples/README.md`](../../iterate-review/examples/README.md#fixture-naming-conventions).
