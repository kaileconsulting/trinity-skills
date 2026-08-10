# trinity-skills

Three Claude Code skills that formalize the **Opus ⇄ Codex review loop** for planning and code review:

| Skill | What it does |
|---|---|
| **`create-plan`** | Scaffold a new plan markdown file in `docs/` using a canonical template (phases, iterate-review markers, HISTORICAL stubs). |
| **`iterate-plan`** | Iterate a plan between Opus (sole editor) and Codex (structured reviewer) until APPROVE. Runs an **architect** and a **product-manager** lens per pass, each fed the plan sections it needs, and merges their findings into one list. Codex never edits — it returns JSON-schema-validated findings + plan corrections + question answers; Opus folds them in. |
| **`iterate-review`** | Same loop applied to **code changes** — a working-tree diff, a feature branch, or a PR (open or merged). Deterministically selects **senior-dev** (always) plus **security** and **QA** based on what the diff touches, then merges their findings. Opus folds them into the working code. |

They're independent — install any one of them — but compose naturally:

```
                              human
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
         create-plan ──▶ iterate-plan ──▶ iterate-review
         (scaffold)      (design review)   (code review)
```

Version history, including the breaking changes and the known gaps, is in [`CHANGELOG.md`](CHANGELOG.md).

## Why this exists

Sending a plan or diff to Codex for review is high-value but tedious to do by hand: copy the markdown out, paste into a Codex prompt, copy the response back, manually decide what to incorporate, repeat. The trinity skills automate the shuttle while preserving the load-bearing invariants:

- **Opus is the sole editor.** Codex runs in a `-s read-only -a never` sandbox with `--output-schema` enforcement. It returns structured findings; Opus does every file edit.
- **No silent iteration.** After every pass the human is prompted to Continue / Converge / Abort. The skills never decide convergence themselves.
- **HISTORICAL audit trail.** Every pass appends a `[HISTORICAL]` block to the plan (or pass log) so subsequent passes see the full review history and can spot regressions or unfolded findings.

## Persona lenses

One reviewer persona means one framing's blind spots applied to every issue category: an architect framing underweights product fit, a general staff-engineer framing underweights QA edge cases and security trust boundaries. So each pass now runs **several personas concurrently** and merges what they find.

```
                     ┌─ senior-dev ── codex exec ─┐
  select lenses ────▶├─ security ──── codex exec ─┤──▶ Opus merges ──▶ one findings list ──▶ ONE checkpoint
  (deterministic)    └─ qa ────────── codex exec ─┘    (dedupe, worst-of verdict,
                                                        lens attribution)
```

Four properties make this more than "ask the model twice":

- **Selection is a deterministic rules table, never an LLM router.** Lenses are picked by matching changed paths and changed diff lines against globs and regexes declared in each lens file. A router that mis-routes skips the lens that would have caught the bug, so routing is not left to judgment. `senior-dev` always runs as a floor, and genuinely borderline cases **include** the lens — a wasted Codex call is cheaper than a missed category.
- **One pass, one checkpoint.** N lenses produce exactly one merged findings list, one HISTORICAL block, and one Continue/Converge/Abort prompt. Fan-out must not multiply your workload.
- **Worst-of verdict.** The aggregate is the worst lens verdict, so one lens approving cannot carry a pass that another wants revised. Convergence requires every selected lens to approve.
- **A lens that fails is not silently skipped.** It is retried once; if it still fails it is recorded as `FAILED`, forces at-least-REVISE, and **blocks Converge** with a retry option. The loop never converges having quietly dropped a selected lens.

Lenses are data-shaped records in `<skill>/lenses/<id>.md` — frontmatter declaring selection rules and required context, then a persona fragment layered onto the shared reviewer contract. Adding one is a new file. (A pluggable persona-pack loader is [issue #1](https://github.com/kaileconsulting/trinity-skills/issues/1).)

Every folded finding records which lens raised it, so you can measure whether the added lenses are earning their cost.

## Loop mode

Both skills accept `--loop` (alias `--until-approve`), and every checkpoint offers `(L)oop from here`. Loop mode **automates `Continue` only — never `Converge`.** It auto-continues through REVISE passes and halts, handing back to you, on any of five guardrails:

- **APPROVE reached** — stops so you make the Converge call.
- **Max-pass cap** — default 6, `--max-passes=N`, a fresh budget per activation.
- **BLOCK verdict.**
- **Non-convergence** — the merged HIGH+MEDIUM count fails to strictly decrease across two consecutive transitions.
- **A fold needing human judgment** — an un-incorporated HIGH, or an open question only you can settle (see below).

Every auto-continued pass still appends its HISTORICAL block, so the loop is unattended but not silent.

### Which questions stop the loop

A reviewer that raises a question classifies it by **who can settle it**, and that label decides whether an unattended loop stops:

| `settled_by` | Meaning | Loop behavior |
|---|---|---|
| `resolvable_in_fold` | answerable from the full plan / the repo — the reviewer only saw a slice | Opus answers it and **continues** |
| `needs_lookup` | a fact settles it, but reaching it needs a call the reviewer can't make | Opus performs the lookup and **continues**; if the lookup fails it becomes `needs_human` |
| `needs_human` | no fact settles it — your preference, risk tolerance, or product judgment | **halts**, always |

Without this, the guardrail read "a question Opus can't answer from the plan + repo context," which lumped all three together: an unattended loop would stop to ask something one file read would have answered. **When a reviewer is unsure, the contract requires `needs_human`** — an unnecessary escalation costs a question, while mislabeling your decision as machine-resolvable invites a fabricated answer. Each label carries a one-line `why` so it can be audited rather than trusted, and Opus overrides a label it doesn't believe.

## Prerequisites

- [Claude Code](https://claude.com/claude-code) (the skills run inside it)
- [Codex CLI](https://github.com/openai/codex) — tested against `codex-cli 0.125.0+`. The skills shell out via `codex -a never exec ... --output-schema ...`.
- `python3` ≥ **3.9** — required by the `bin/` runner scripts (stdlib only, no pip installs). macOS ships no interpreter by default; the Xcode Command Line Tools' 3.9.6 clears the floor, as does any Homebrew or distro python3. Runners fail fast with a clear message below the floor.
- `git`, `bash`, and `gh` (only needed for `iterate-review --scope=pr:<n>`).

## Install

```bash
git clone https://github.com/kaileconsulting/trinity-skills.git
cd trinity-skills
./install.sh
```

`install.sh` creates symlinks from `~/.claude/skills/{create-plan,iterate-plan,iterate-review}/` into the cloned repo, so your local Claude Code sees them as installed skills and any `git pull` updates them immediately. It refuses to overwrite existing non-symlink directories (so a hand-edited skill of the same name won't be clobbered).

Because it symlinks rather than copies, **the installed skills track your checked-out branch** — switching to a branch without these skills changes the installed behavior with no warning.

Restart Claude Code after installing for the skills to appear in the available-skills list.

Want the original single-reviewer versions too? `./install.sh --with-v1` — see [V1](#v1--the-original-single-reviewer-skills).

## Quick start

Inside any Claude Code session:

```
/create-plan refactor-payments
```

walks you through plan-type selection (`initiative` or `fix`), phase metadata, and writes `docs/refactor-payments-YYYY-MM-DD.md`. Fill in TL;DR / Why / Approach, then:

```
/iterate-plan docs/refactor-payments-2026-05-19.md
```

sends the plan to Codex; Opus folds Codex's structured findings back into the file; you confirm Continue / Converge after each pass. On convergence, Opus optionally writes a handoff prompt for a fresh Sonnet session to execute the plan.

Per phase, ship commits then:

```
/iterate-review --scope=branch
```

runs the same loop against `git diff $(git merge-base HEAD main)...HEAD`. Pass log lands at `code-review-branch-<name>.md` next to your work. Other scopes:

- `--scope=working` — uncommitted working-tree changes
- `--scope=pr:123` — open or merged GitHub PR (uses `gh pr diff`)
- `--once` — single-pass review, no loop
- `--loop` — auto-continue REVISE passes, stop at APPROVE (see [Loop mode](#loop-mode))

## Runner scripts & the one-rule permission model

Historically each review pass improvised unique shell to compose lens inputs and invoke Codex — commands that could never be pre-approved, so a 10-pass review meant dozens of opaque permission prompts and a settings file full of dead one-shot rules. The runner scripts replace that with three stable executables under each skill's `bin/` (`run-lens`, `run-pass`, `prune-state`; stdlib-only Python ≥ 3.9). A stable script accepts *arguments*, so one documented allowlist rule per skill covers every invocation:

```json
// .claude/settings.json → permissions.allow — adjust the path to YOUR install:
// symlink install (default ./install.sh):
"Bash(~/.claude/skills/iterate-review/bin/* *)"
"Bash(~/.claude/skills/iterate-plan/bin/* *)"
// copied-directory install: use the directory you copied to, e.g.
"Bash(/path/to/your/skills/iterate-review/bin/* *)"
"Bash(/path/to/your/skills/iterate-plan/bin/* *)"
```

With those rules in place, the review machinery generates **zero further Bash permission prompts** end to end. What remains is deliberate: scope selection at the start, the skills' mandated human checkpoints, and pass-log / plan appends via Claude Code's normal file-edit permissions. The runner composes and invokes; it never folds, never writes pass logs, never decides.

The two skills share their runner machinery literally: `runner_shared.py` and `prune-state` are duplicated **byte-identically** between the two `bin/` directories and hash-checked by `tools/check-parity.py`, so both skills always run the same reviewed lock/publication/validation code. The adapted halves (`review_runner.py` vs `plan_runner.py` — composition and selection) are pinned by per-skill behavioral fixtures instead.

**Pass-log default is off the repo root.** New pass logs default to `<repo-root>/docs/reviews/code-review-<scope-tag>.md` (created on demand); `--log-path` still overrides. **Existing logs are untouched** — no migration, no renames; move old root-level `code-review-*.md` files yourself if and when you want them gathered.

**State cleanup is part of the loop.** On Converge the skill prunes the review's state directory (`prune-state --scope <hash> --yes`) — the pass log is the durable record; composed inputs, raw responses, and pass summaries are intermediates. Pass `--keep-state` to keep them for auditing or debugging a bad merge. For runs that were aborted or abandoned, `prune-state` is age-based and dry-run by default: `prune-state --older-than 30 --yes` removes state untouched for 30 days (30 is an example, not policy — pick your own threshold). It never touches pass logs, `state/<hash>.json` records, anything outside `state/`, or a scope holding a live run lock; `prune-state --force-unlock <scope>` is the explicit recovery path for a wedged lock. Bare `prune-state` prints a read-only overview of accumulated state.

## Directory layout

```
trinity-skills/
├── create-plan/
│   ├── SKILL.md
│   └── template.md
├── iterate-plan/
│   ├── SKILL.md
│   ├── bin/                        # runner scripts: run-lens, run-pass, prune-state
│   ├── reviewer-prompt.md          # shared contract; defers ROLE/FOCUS to the lens
│   ├── reviewer-output.schema.json
│   ├── lenses/                     # architect, product-manager + selection rules
│   ├── examples/                   # merge + composition goldens, a real Codex response
│   └── state/                      # gitignored at runtime; only example.json tracked
├── iterate-review/
│   ├── SKILL.md
│   ├── bin/                        # runner scripts: run-lens, run-pass, prune-state
│   ├── reviewer-prompt.md
│   ├── reviewer-output.schema.json
│   ├── lenses/                     # senior-dev, security, qa + selection rules
│   ├── examples/
│   │   ├── selection/              # routing fixtures + runnable reference impl
│   │   ├── composition/            # byte-deterministic assembly goldens
│   │   └── merge/                  # merge / verdict-aggregation goldens
│   └── state/                      # gitignored at runtime
├── v1/                             # frozen single-reviewer skills (see below)
├── tools/                          # dev-time checks (see below)
└── docs/                           # plans; archive/ holds shipped ones
```

`state/` directories hold per-invocation run state (per-lens Codex response JSON, final state files). They're populated at runtime through the symlink and excluded from version control.

## Dev checks

The skills are prose, so two failure modes are invisible without tooling: the two skills' shared machinery drifting apart, and fixtures quietly ceasing to mean anything. `tools/` guards both.

```bash
tools/check-all.sh          # everything; requires python3 + pip install jsonschema
```

Its output is the live count of what's covered — deliberately not restated here, since a number in prose goes stale the first time a fixture is added.

| Check | What it asserts |
|---|---|
| `iterate-review/examples/selection/check-selection.py` | A **second implementation** of the deterministic selection rules, run against a set of golden diff fixtures. The rules claim any two implementations agree; until this existed there was one, and it was a language model reading prose. |
| `tools/check-examples.py` | Every fixture validates against its skill's schema — and fixtures whose *names* make a claim have that claim verified. |
| `tools/check-parity.py` | Every shared-machinery rule is present in **both** skills' per-pass loops (semantic parity, not byte-identity: prose may differ, rules may not) — and the designated shared runner files (`runner_shared.py`, `prune-state`) are **byte-identical** across both `bin/` directories, by content hash. |
| `tools/check-runners.py` | The iterate-review runner scripts' promised behavior: byte-deterministic composition, exit contracts, lock lifecycle, pass-log resolution, prune safety — against a copied install with a fake `codex`. |
| `tools/check-plan-runners.py` | The iterate-plan port's adapted behavior: section extraction, always-all selection, `--plan`/`--note` boundaries, plus a wiring smoke over the shared contracts. |
| `tools/test-checkers.py` | Tests that the checkers above actually fail when they should. |

Worth knowing what they don't cover: `check-parity.py` checks a rule is *stated*, not that it is *correct*, and the merge step is deliberately not scripted — semantic dedupe is Opus's judgment, so it ships worked goldens to compare against rather than assertions. See `tools/README.md`.

## V1 — the original single-reviewer skills

`v1/` holds `iterate-plan` and `iterate-review` frozen as they shipped before persona lenses: one Codex call per pass, no selection, no fan-out, no merge, no loop mode.

```bash
./install.sh --with-v1
```

They install as `iterate-plan-v1` / `iterate-review-v1` and coexist with the current skills — separate state, separate pass logs, and descriptions written so a generic "review this" request routes to the current version. For a short diff where one reviewer pass is plainly enough, V1 is the smaller tool.

To roll back entirely instead: `git checkout v1.0 && ./install.sh`. Details and the full list of what differs from the snapshot are in [`v1/README.md`](v1/README.md).

## How it works under the hood

Each iterate-* skill invokes Codex as one subprocess **per selected lens**, each with three structural guarantees:

1. **Sandbox** — `codex -a never exec -s read-only --skip-git-repo-check` makes file writes structurally impossible from Codex's side.
2. **Output schema** — `--output-schema <reviewer-output.schema.json>` forces Codex's response into a strict JSON shape (verdict + findings + corrections + answers). Free-form prose is rejected by Codex's runtime before it reaches Opus.
3. **Patch-marker rejection** — Opus scans each response for `*** Begin Patch`, unified-diff markers, and merge-conflict markers before folding. Defense in depth against a Codex response that smuggles a patch into a description field.

This makes the editor/reviewer separation a structural property of the system, not a trust property. Even an out-of-contract response gets caught at the gateway.

The lens fan-out sits on top without weakening any of it: the shared `reviewer-prompt.md` carries the contract and defers only ROLE and FOCUS to the lens fragment, so every lens runs under identical restrictions and returns the same schema. Merging N responses into one findings list is Opus's job, consistent with Opus-as-sole-editor — dedupe collapses findings that share **both** a location and an asserted defect, so two distinct concerns about the same line stay distinct, and a finding both lenses raised keeps both attributions.

## License

MIT — see [LICENSE](LICENSE).

## Contributing

Issues and PRs welcome. Two things to know:

- **Run `tools/check-all.sh`** before opening a PR, and add a check's own failure mode to `tools/test-checkers.py` in the same change that adds the check. A check never observed failing has not been shown to work.
- **Don't edit `state/`** in PRs — it's runtime artifact. Only `state/example.json` is tracked, and that's reference documentation, not test data.
- **Reviewer prompts (`reviewer-prompt.md`), schemas (`reviewer-output.schema.json`), and lens records (`lenses/*.md`) are load-bearing** — changing them changes how every plan / diff is reviewed going forward. Treat edits to those files as protocol changes, not refactors. `lenses/README.md` is the source of truth for selection semantics; `check-selection.py` reads its rule data rather than restating it, so a rules change may legitimately fail the fixtures. Update the goldens deliberately, not reflexively.
- **Keep the two skills' shared machinery in semantic parity.** `iterate-plan` steps 5–10 and `iterate-review` steps 9–16 describe the same machine in deliberately different prose. Editing one and forgetting the other produces no error anywhere except `tools/check-parity.py`.
- **Don't fix bugs in `v1/`.** It's a frozen snapshot; its value is behaving the way it behaved. See [`v1/README.md`](v1/README.md).
