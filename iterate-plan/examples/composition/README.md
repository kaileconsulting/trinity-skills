# Composition goldens — byte-deterministic lens-input assembly

These fixtures pin the **canonical assembly** implemented by
`bin/plan_runner.py::compose_input()`: same inputs → byte-identical lens
input file. That determinism is load-bearing — it is what makes the composed
inputs golden-comparable at all, and what the runner-scripts plan's
acceptance criteria assert.

The inputs are **synthetic** (a two-line stand-in prompt, a stub lens body,
a five-section stub plan) rather than the real `reviewer-prompt.md` / lens
records, deliberately: the goldens pin the *assembly algorithm* — part
ordering, separators, the matched-context framing line, required-section
slicing (exact `## <title>` match; sub-headings kept with their parent; an
absent section contributes its NOTE line), the optional staged-note block,
and newline normalization — not the prose content of the prompt. Editing the
reviewer prompt or a lens must NOT break these fixtures; changing how parts
are stitched together MUST.

| File | Role |
|---|---|
| `prompt.txt`, `lens-body.txt`, `matched-context.txt`, `plan.txt`, `note.txt` | synthetic assembly inputs |
| `golden-plain.txt` | expected bytes: sections `Approach` + `Phasing`, no note |
| `golden-with-note.txt` | expected bytes: same, with the staged-note block |
| `golden-absent-section.txt` | expected bytes: sections `Approach` + `Acceptance criteria` (absent → NOTE line) |

Unlike iterate-review there is no PRIOR PASSES golden: iterate-plan's
HISTORICAL sections live inside the plan itself, so prior-pass context
always arrives with the `=== PLAN ===` block.

Checked by `tools/check-plan-runners.py` (run via `tools/check-all.sh`).
