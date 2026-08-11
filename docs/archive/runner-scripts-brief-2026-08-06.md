# Plan brief — runner scripts + artifact hygiene for the trinity skills

> **This is a brief, not a plan.** It captures the context, evidence, and open questions
> from a heavy dogfooding day (2026-08-06, `Adminformatics/doc-bot`) so a fresh session
> can run `/create-plan` against it. Written by the session that felt the pain, for the
> session that will fix it.

## Problem statement

Three compounding frictions, all structural to how the skills currently execute:

1. **Every review pass improvises unique shell, and unique shell cannot be pre-approved.**
   `iterate-review` steps 9–10 have the model compose per-lens Codex inputs with ad-hoc
   compound commands — `for`-loops over lenses, heredocs, `awk` frontmatter extraction,
   per-pass file paths. Each is a one-off string, so the permission system prompts on
   every one, and an "always allow" click records an **exact-match rule that never
   matches again** (the `--output-last-message` path embeds pass number + lens + scope
   hash). Observed result in doc-bot's `settings.local.json`: **~40 dead one-shot codex
   rules accumulated (89 rules → 49 after cleanup)**, plus a steady stream of prompts for
   the composition blocks themselves. The user's words: *"every time I have to approve
   the write of these temp review files … it's just a lot of clicking yes and I don't
   always understand what I'm clicking yes to."* A non-engineer driver approving opaque
   shell walls is the opposite of what a permission prompt is for.

2. **Pass logs accumulate at the invoking repo's root by default.** doc-bot's root now
   holds five `code-review-*.md` files. The default (`<cwd>/code-review-<scope-tag>.md`)
   is the only thing users will ever hit; repo-root clutter is the default experience.

3. **State directories accumulate forever.** `state/<scope-hash>/pass-N.<lens>.response.json`
   files persist after convergence with no pruning story. One doc-bot review produced
   30 response files (10 passes × 3 lenses); nothing ever deletes them.

## Workload profile (real, from 2026-08-06)

The doc-bot write-path Phase 0 review: **10 passes × 3 lenses = 30 Codex invocations**,
each preceded by a unique composition block and followed by log-append heredocs. Every
one of those was a potential permission prompt. A same-day dependency review (2 passes)
and a CodeQL review (2 passes + a `--once`) had the same texture. Multiply by every
future phase of every plan.

Example of what the model currently improvises per pass (abridged; the real block is
~40 lines and differs every time):

```bash
for LENS in senior-dev security qa; do
  MC=$(awk '/^matched_context:/{...}' $SKILL/lenses/$LENS.md | tr '\n' ' ')
  { cat $SKILL/reviewer-prompt.md; awk 'c==2{print} /^---$/{c++}' $SKILL/lenses/$LENS.md
    echo "=== INTENT ==="; ...; cat $SCRATCH/diff; cat <pass log>
  } > /tmp/iterate-review-input-pass-N-$LENS.txt
done
cat /tmp/...-senior-dev.txt | codex -a never exec -s read-only --output-schema ... \
  --output-last-message ~/.claude/skills/iterate-review/state/<hash>/pass-N.senior-dev.response.json -
```

## Proposed shape (for the plan to iterate, not to rubber-stamp)

**Python over shell** (decided with the user 2026-08-06): more portable, testable, and
the repo already has Python tooling precedent (`tools/check-examples.py`,
`examples/selection/check-selection.py`, `requirements-dev.txt`). Runtime scripts should
stay **stdlib-only**.

New `iterate-review/bin/` (all paths derived from the script's own location — zero
hardcoded user paths; `codex` resolved from PATH):

- `run-lens` — given scope inputs (diff file, intent file, pass number, lens id,
  log path): compose the lens input deterministically (shared contract + lens fragment +
  matched-context framing + INTENT/DIFF/PRIOR PASSES), create the state dir, invoke
  Codex with the exact sandbox flags (`-a never exec -s read-only --output-schema …`),
  and **perform the patch-marker rejection check in code** (today it's prose the model
  must remember). Emit the response path + a machine-readable result to stdout.
- `run-pass` — fan out `run-lens` for the selected lenses concurrently; one command per
  pass instead of 3 + N.
- `prune-state` — delete state for converged/aborted runs older than a threshold.

`SKILL.md` rewires steps 9–11 to call the runners; every behavioral rule (fan-out,
merge, worst-of, FAILED handling, checkpoints, loop guardrails) stays with the model.
**The runner composes and invokes; it never folds, never writes logs, never decides.**
Opus-as-sole-writer discipline is unchanged.

**Pass-log default moves off the repo root** — proposed `docs/reviews/code-review-<scope-tag>.md`
(created on demand), `--log-path` override retained, existing logs untouched.

**Scope: BOTH skills, iterate-review first** (decided with the user 2026-08-06).
`iterate-review` SKILL.md declares steps 10–14 as SHARED MACHINERY in semantic parity
with `iterate-plan` steps 6–10, checked by fixture — a runner for one but not the other
creates drift pressure. Phasing should land iterate-review, then port the runner pattern
to iterate-plan.

**The single-rule payoff:** each user adds ONE documented allowlist line (e.g.
`Bash(~/.claude/skills/iterate-review/bin/* *)` — README ships the snippet, the path is
theirs) and an entire review runs with zero further prompts. The prompts that remain are
the ones worth reading.

## Constraints the plan must hold

- No hardcoded user paths; skill root derived from script location; macOS + Linux.
- Codex invocation flags preserved exactly (read-only sandbox is a hard rule).
- Deterministic composition: same inputs → byte-identical lens input files (this is a
  *feature*: the skill already demands two implementations agree on lens selection).
- Lens selection stays deterministic per `lenses/README.md`; the plan should decide
  whether `run-pass` embeds it (promoting `check-selection.py`'s logic) or the model
  keeps selecting and passes lens ids explicitly.
- Backwards compatible: `--once`, `--loop`, `--max-passes`, `--log-path`, state-file
  format, and the pass-log HISTORICAL format all unchanged.
- Fixtures: existing `examples/` + `tools/check-examples.py` must stay green; new
  runner behavior gets its own fixtures (composition golden files would pin the
  byte-determinism claim).

## Open questions for `/create-plan`

1. Does `run-pass` embed deterministic lens selection, or does the model select and
   pass explicit lens ids? (Reference impl exists: `examples/selection/check-selection.py`.)
2. Concurrency inside `run-pass` (threads/subprocesses) vs. the harness running three
   background `run-lens` calls — which keeps failure attribution cleaner?
3. `docs/reviews/` naming: right default? Migration guidance for repos with root logs?
4. Prune policy for `prune-state`: age-based, converged-only, or both? Auto-prune on
   convergence, or manual only?
5. Should the runner validate the response against `reviewer-output.schema.json` itself
   (belt-and-suspenders beyond codex `--output-schema`), given jsonschema isn't stdlib?
6. iterate-plan port: identical `bin/` pattern, or a shared `lib/` both skills import?
   (Watch the symlink layout: `~/.claude/skills/<name>` → repo subdirs.)

## Acceptance sketch

- A full multi-pass iterate-review on a real repo runs with **one pre-approved command
  shape** and **zero other permission prompts** end to end.
- Composition golden-file fixtures prove byte-deterministic input assembly.
- Patch-marker rejection is exercised by a fixture (malformed response → non-zero exit).
- Parity fixture between the two skills still passes after both phases.
- CHANGELOG entry per repo convention; README documents the one allowlist line.

## Source material for the planning session

- Real pass logs (workload + format examples): `Adminformatics/doc-bot` repo root,
  `code-review-*.md` — especially `code-review-editor-write-path-phase-0.md` (10 passes).
- The accumulated-rules artifact: doc-bot `.claude/settings.local.json` history
  (git-ignored file; the 89→49 cleanup happened 2026-08-06 in-session).
- State-dir sprawl: `~/.claude/skills/iterate-review/state/` on the authoring machine.
- The permission-rule fix that motivated the single-rule design:
  `Bash(codex -a never exec *)` prefix rule replaced ~40 one-shot exact rules.
