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
| `register.txt` | synthetic `## Accepted risks` section text (Phase 1, Q5) |
| `golden-plain.txt` | expected bytes: sections `Approach` + `Phasing`, no note, no register — this doubles as the **no-register golden**: `compose_input()` called with `register=""` (the default) must still produce these exact bytes, so the register feature adds zero bytes when absent |
| `golden-with-note.txt` | expected bytes: same, with the staged-note block |
| `golden-absent-section.txt` | expected bytes: sections `Approach` + `Acceptance criteria` (absent → NOTE line) |
| `golden-with-register.txt` | expected bytes: `golden-plain.txt`'s sections, with an `=== ACCEPTED RISKS ===` block (from `register.txt`) inserted immediately before `=== PLAN ===` |

Unlike iterate-review there is no PRIOR PASSES golden: iterate-plan's
HISTORICAL sections live inside the plan itself, so prior-pass context
always arrives with the `=== PLAN ===` block.

**Register composition (Phase 1, Q5)** is pinned by two goldens working
together, not one: `golden-plain.txt` proves the *absent* case is
byte-identical to composition without the feature at all (call
`compose_input()` with no `register` argument, or `register=""`);
`golden-with-register.txt` proves the *present* case inserts the register
block in exactly one place, verbatim, with no other byte disturbed. The
register content itself is always read from `git show HEAD:docs/risk-posture.md`
at the plan's repo root (`bin/plan_runner.py::resolve_register()`) — never
the working tree; `tools/check-plan-runners.py` exercises all four
resolution states (loaded / confirmed-absent / malformed / operational
failure) against real scratch git repos, since this is runner control
flow, not editor prose.

Checked by `tools/check-plan-runners.py` (run via `tools/check-all.sh`).
