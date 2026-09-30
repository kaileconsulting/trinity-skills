# Handoff: Review-Diff Exclusions — Plan

## Summary
Cut Codex usage in `iterate-review` by taking content out of the reviewed diff, mechanically and always disclosed. Phase 0: the runner drops the review's own pass log (already sent as `=== PRIOR PASSES ===`) from the composed diff, but only when every existing endpoint of a section is the log; renames or copies crossing the log's boundary always stay reviewed. Phase 1: the editor passes `--exclude <class>:<path-or-glob>` for three classes (`governing-plan`, `docs`, `generated`), refused fail-closed by the runner, with line-exact intent conventions (`Governing-plan:` line; `=== EXCLUDED SUMMARY ===` per-path audit entries). Phase 2: closeout. Closes issue #10. The design converged after 2 `iterate-plan` passes (5 → 0 HIGH+MEDIUM; 5 findings, all incorporated, none fold-caused; Q1–Q4 answered in agreement both passes).

## Plan
Full plan at: `/Users/adminformatics-pm/code/trinity-skills-wt-exclusions/docs/review-diff-exclusions-2026-09-29.md`
Read it all first, including both HISTORICAL review blocks at the bottom: they record why the rename rule, the parser contract (§0) and the original/reviewed split (§3) are shaped the way they are.

**Work in the worktree, not the main checkout.** The branch is `kyle/review-diff-exclusions` at `~/code/trinity-skills-wt-exclusions`, rebased onto 2.5.0. The installed skills in `~/.claude/skills/` are symlinks to `~/code/trinity-skills` (on `main`), which every project's reviews use, so building there would change live behavior mid-build.

## Current step
Phase 0: the runner's self-exclusion of the pass log. Iterate-review YES: when Phase 0's commits land, run `/iterate-review --scope=branch --loop` from the worktree before moving to Phase 1. Leave the plan doc, its handoff prompt and the review log out of that review's diff by hand, recorded in the `Scope:` line, until this feature ships. That is the practice this plan builds in.

## Shipped commits referenced by the plan
- `be3d494` — author plan
- `14543ed` — rebased onto 2.5.0; archived-path references
- `8603a98` — fold of plan review pass 1
- `b29df5e` — plan review pass 2, APPROVE ×2
- On main: `c74516a` (2.5.0, the simplification gate, PR #11) and `4a34e0f` (its closeout, PR #12).

## Remaining risks
- **`runner_shared.py` is byte-identical across both skills** (`tools/check-parity.py` enforces it). The optional `publish_summary()` argument (§4) must be copied to both, and iterate-plan must never pass it: `check-plan-runners.py` has to show iterate-plan's summary unchanged.
- **The parser is the trust boundary** (§0). If any section's identity is uncertain, exclude nothing: self-exclusion is skipped with a warning, and an explicit `--exclude` aborts. Never best-effort.
- **Selection and classification read the original diff; only composition reads the reviewed one** (§3). Getting this backwards silently trims lenses (an excluded lockfile would stop triggering `security`).
- **Composition is byte-deterministic, golden-pinned.** Update the goldens deliberately, never regenerate them to make a test pass.
- **R1 is the one risk the design doesn't prevent:** an editor labeling a hand-written production file `generated`. Disclosure makes it visible; nothing blocks it.
- Before merging, run the pre-merge doc sweep (README, `iterate-review/SKILL.md`, `tools/README.md`, CHANGELOG, memory).

## First action
Read the plan, then `iterate-review/bin/review_runner.py` (`compose_input()`, `resolve_log_path()`, `read_prior_passes()`), `iterate-review/bin/run-pass`, `bin/runner_shared.py` (`publish_summary()`) and `iterate-review/bin/selection_engine.py`'s diff-path parsing end to end. Confirm `tools/check-all.sh` passes in the worktree, then start Phase 0 with the §0 parser and its `check-runners.py` cases before touching exclusion or SKILL.md.
