# iterate-plan lenses

Persona lenses for design-time review (Axis 2). Each lens is a **data-shaped record**: YAML frontmatter (identity + deterministic selection + matched-context spec) followed by a **persona-prompt fragment** that layers onto the shared reviewer contract in `../reviewer-prompt.md`.

The shared contract (HARD RESTRICTIONS — structural + behavioral, the output schema, convergence guidance) stays common across all lenses. A lens fragment replaces the **ROLE**, supplies a **FOCUS** list — *what this lens looks for* — and may add a short **lens-specific guidance** note after FOCUS. At fan-out time the skill concatenates: shared contract → lens ROLE → lens FOCUS (+ guidance) → the plan (with the lens's matched context sliced in).

## Lens record format

```yaml
---
id: <slug>                       # unique lens id, also its attribution tag
skill: iterate-plan              # owning skill
role: <one-line role title>      # replaces the ROLE line in the shared contract
selection:
  always: true|false             # true = runs on every pass
  requires_sections: [ ... ]     # iterate-plan: sections that feed this lens.
                                  #   If absent from the plan, the lens still runs
                                  #   with degraded context and MUST flag the gap
                                  #   (never skipped, never fed empty context).
matched_context: <what this lens is fed, sliced from the plan>
---
<persona-prompt fragment: ROLE + FOCUS>
```

## Selection rules (deterministic — no LLM router)

| Lens | Runs when | `requires_sections` (canonical H2 names) |
|---|---|---|
| `architect` | **always** | `Approach`, `Phasing` |
| `product-manager` | **always** | `Who / Use cases`, `Goals (MVP)`, `Acceptance criteria` |

Both lenses run on every `iterate-plan` pass; the merge collapses overlap.

**Canonical section names.** `requires_sections` values are the **normalized H2 title text — without the leading `## ` marker** — exactly as the `create-plan` template writes them: `Who / Use cases`, `Goals (MVP)`, `Approach`, `Acceptance criteria`, `Phasing`, …. Slicing strips the `## ` marker from each plan heading and compares against these bare strings (exact, case-sensitive). If a required section is absent (non-template plan), the lens still runs with degraded context and **flags the absence as a finding** — never skipped, never fed empty context. (The architect's sub-topics — Architecture / Stack decisions / Repo layout — are subsections *under* `Approach`, so `Approach` covers them.)

### Worked examples (incl. borderline)

- **Template-conformant plan** → architect + PM both run with full context.
- **Plan missing "Acceptance criteria"** → both run; PM is told the section is missing and flags "no verifiable acceptance criteria" rather than inventing them.
- **Pure-refactor design doc with no user surface** → both still run (selection is unconditional for iterate-plan); PM will legitimately return APPROVE with at most LOW nits if there's genuinely no product surface. That is the intended floor, not a misroute.

## Merge & attribution

Findings from both lenses are merged by Opus (semantic dedupe; co-reported findings retain **all** contributing lens ids). Every folded finding records its originating lens id in the HISTORICAL block — this is the attribution that powers the ROI metric (fraction of incorporated findings from a non-default lens).
