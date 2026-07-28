---
name: iterate-review
description: Iterate a code review between Opus (folds findings) and Codex (reviewer) until convergence. Use whenever the user wants Codex to review code changes — a working-tree edit, a feature branch, or a merged PR — and would otherwise be copying diffs + Codex's response back and forth manually. Trigger phrases: "/iterate-review", "have Codex review this", "code-review this branch", "what does Codex think of this PR", "review my changes with Codex", "Codex review the working tree." V1 is standalone-only (no plan-bound mode); plan-bound (`--plan` / `--phase` flags, plan-side Status updates) is deferred to v2.
---

# `iterate-review`

Formalizes the proven Opus⇄Codex review loop, applied to code review (sibling of `iterate-plan`, which applies the same loop to plan design review). Opus is the sole writer of fold actions; Codex is the technical reviewer — provides structured feedback via `codex exec --output-schema`, never edits files.

## When to invoke

User wants Codex's review on a code change and would otherwise be copying the diff + Codex's response back and forth manually.

Typical trigger phrases: "have Codex review this," "code-review this branch with Codex," "what does Codex think of this PR," `/iterate-review --scope=working`.

Do NOT invoke for plan design review — that's `iterate-plan`'s job. iterate-review reviews code; iterate-plan reviews plan markdown.

## How to invoke

The skill surfaces in-session via the available-skills list at session start (slash command + Skill tool both work). User typically triggers with one of:

- `iterate-review --scope=working` — review uncommitted working-tree changes
- `iterate-review --scope=branch` — review the current branch's diff against `main`
- `iterate-review --scope=pr:<n>` — review a merged or open PR by number (uses `gh pr diff`)
- `iterate-review --scope=<...> --once` — single-pass review, no Continue/Converge/Abort loop
- `iterate-review --scope=<...> --log-path=<path>` — custom pass log location
- `iterate-review --scope=<...> --loop` (alias `--until-approve`) — loop mode: auto-continue REVISE passes, stopping at the first APPROVE for the human's Converge call
- `iterate-review --scope=<...> --max-passes=N` — loop-mode safety cap (default 6, fresh budget per loop activation)

If the user invokes without a `--scope` flag, ask them which scope they want before proceeding. Default suggestion: `--scope=working` if there are uncommitted changes (`git status --porcelain` non-empty), `--scope=branch` if the current branch is ahead of main, otherwise prompt for `pr:<n>`.

## Setup (once per skill invocation)

1. **Parse args.** Extract `--scope=<value>`, `--once` (flag), `--log-path=<path>`, `--loop`/`--until-approve` (flag), `--max-passes=N`. Reject `--plan` / `--phase` flags with a clear "v1 is standalone-only; plan-bound deferred to v2" message and exit. Reject `--once` together with `--loop` (mutually exclusive — one opts out of the loop, the other automates it).

2. **Verify Codex CLI is available.** Run `codex --version` via Bash. If the command fails, surface a clear error: "Codex CLI not found — install it before invoking iterate-review." Exit. (Pin: tested against codex-cli 0.125.0+.)

3. **Resolve diff scope** based on `--scope` value:

   | Scope value      | Diff command                                      | Notes                                         |
   |------------------|---------------------------------------------------|-----------------------------------------------|
   | `working`        | `git diff`                                        | Uncommitted working-tree changes only         |
   | `branch`         | `git diff $(git merge-base HEAD main)...HEAD`     | Branch's commits vs main                      |
   | `pr:<n>`         | `gh pr diff <n>`                                  | Works on open AND merged PRs                  |

   Capture the diff content into a variable (or temp file) for the per-pass loop. If the diff is empty, surface a clear message ("nothing to review — scope `<value>` produced an empty diff") and exit without invoking Codex.

4. **Compute scope-tag.** This becomes part of the pass log filename:

   - `--scope=working` → tag `working`
   - `--scope=branch` → tag `branch-<currentbranch>` (slugified — replace non-alphanumerics with `-`)
   - `--scope=pr:<n>` → tag `pr-<n>`

5. **Determine pass log path.** Default: `<cwd>/code-review-<scope-tag>.md`. Override: `--log-path=<path>`. Surface the resolved path to the user before the first pass.

6. **Determine state file path.** Compute `scope-hash` = sha1 of `<scope-tag>|<pass-log-path>`. State file: `~/.claude/skills/iterate-review/state/<scope-hash>.json`. State file is written at convergence/abort only — see Step 12.

7. **Detect prior passes.** If the pass log file exists at the resolved path, read it to determine the next pass number (`prior_passes + 1`). Capture its content as the `=== PRIOR PASSES ===` block for the Codex input. If the file doesn't exist, this is pass 1 with no prior passes.

8. **Surface scope summary to user.** Before the first pass, output a brief block:

   ```
   iterate-review starting:
   - Scope: <scope value>
   - Diff size: <N lines>
   - Pass log: <pass log path>
   - This is pass <N> (previous passes detected: <0 / 1 / 2 / ...>)
   ```

   Lets the user sanity-check before Codex spins up.

## Per-pass loop

Each pass selects the applicable **persona lenses** (see `lenses/` — `senior-dev` always; `security` / `qa` by the deterministic selection rules in `lenses/README.md`), fans out one Codex call per selected lens, and Opus merges their findings into one list. Steps 10–14 (fan-out, per-response validation, merge + worst-of verdict + `FAILED` handling, one HISTORICAL block, and the loop-mode checkpoint) are the **SHARED MACHINERY** — the same *rules* (fan-out, semantic merge, worst-of verdict, `FAILED` handling, one HISTORICAL block, one checkpoint, loop mode + guardrails) hold in the sibling `iterate-plan` skill's steps 6–10. Keep them in **semantic parity** — the prose legitimately differs where each skill's folding / pass-log / `--once` details differ; a Phase 4 fixture checks the shared *rules* are present in both, **not** byte-identity. Only lens selection + input composition (step 9) is skill-specific.

9. **Select lenses + compose per-lens input.** Apply the selection rules in `~/.claude/skills/iterate-review/lenses/README.md` (Matching semantics) to the captured diff: `senior-dev` always runs; `security` / `qa` run when their `path_globs` / `content_regexes` / `non_trivial_without_tests` match. Ambiguity biases toward inclusion.

   **Selection mechanic (deterministic).** Derive from the diff: (a) the **changed paths** — `git diff --name-only` for `working`/`branch`, `gh pr diff --name-only <n>` for `pr:<n>`; and (b) the **changed content lines** — diff lines matching `^[+-]` minus the `+++`/`---` headers. A candidate lens (`security`, `qa`) is selected if **any** of its `path_globs` matches a changed path **or any** `content_regex` matches a changed content line (case-insensitive; `**` = any depth). For `qa` also apply `non_trivial_without_tests` (README Matching semantics: ≥ 8 changed non-blank lines in `source_exts` files with no `test_globs` change). `senior-dev` is always selected. A borderline match → include the lens.

   Then, for each selected lens, compose its input by concatenating (in order):

   - Contents of `~/.claude/skills/iterate-review/reviewer-prompt.md`
   - The lens's ROLE/FOCUS fragment (`lenses/<lensid>.md`)
   - A `---` delimiter line
   - `=== INTENT ===` header + intent context (best-effort, per scope), with the lens's `matched_context` framing prepended so the lens reads the diff through its lane:
     - `--scope=working` → "Standalone code review of working-tree changes; no commit message yet."
     - `--scope=branch` → output of `git log $(git merge-base HEAD main)..HEAD --pretty=format:"%h %s%n%b%n---"` (commit messages on the branch)
     - `--scope=pr:<n>` → output of `gh pr view <n> --json title,body --jq '"\(.title)\n\n\(.body)"'` (PR title + description)
   - `=== DIFF ===` header + the captured diff content
   - `=== PRIOR PASSES ===` header + prior pass log content (empty if pass 1)

   In practice write each lens's composed input to `/tmp/iterate-review-input-pass-<N>-<lensid>.txt`.

10. **Fan out — one Codex call per selected lens, concurrently.** Run the selected lenses in parallel (background subprocesses), each writing `$STATE_DIR/pass-$PASS_N.<lensid>.response.json`:

    ```bash
    PASS_N=<current pass number>
    STATE_DIR=~/.claude/skills/iterate-review/state/<scope-hash>
    mkdir -p "$STATE_DIR"

    cat "/tmp/iterate-review-input-pass-$PASS_N-<lensid>.txt" \
      | codex -a never exec \
          -s read-only \
          --skip-git-repo-check \
          --output-schema ~/.claude/skills/iterate-review/reviewer-output.schema.json \
          --json \
          --output-last-message "$STATE_DIR/pass-$PASS_N.<lensid>.response.json" \
          -
    ```

    Notes: `-a never` precedes the `exec` subcommand (root-level flag in codex-cli 0.125.0+); `--skip-git-repo-check` if cwd isn't a git repo; the trailing `-` reads stdin.

11. **Read, validate, and merge the lens responses.**
    - **Per response:** read each `$STATE_DIR/pass-$PASS_N.<lensid>.response.json` (schema-validated by `--output-schema`). Apply belt-and-suspenders patch-marker rejection — scan for `*** Begin Patch`, `--- a/` or `+++ b/`, `@@ -` followed by digits, `<<<<<<<` or `=======` or `>>>>>>>`. If any are present in a lens response, abort with: "Codex response contains patch-shaped output, which violates the reviewer contract. Aborting. Inspect the offending `pass-$PASS_N.<lensid>.response.json`." Do not proceed.
    - **Lens failure:** a lens that crashes or returns malformed/off-schema output is **retried once**; if it still fails, record it as `FAILED` orchestration metadata — not a verdict (the reviewer schema is untouched).
    - **Merge (Opus, semantic judgment — not a mechanical key):** collapse findings that target the same location and assert the same defect; keep distinct concerns separate; a co-reported finding retains **all** contributing lens ids. Produce one merged findings list.
    - **Dedupe `code_corrections` too.** Two lenses can file the same tactical correction. Corrections are applied *mechanically*, so a surviving duplicate can double-apply the same edit. Collapse by location + intended fix. (iterate-plan carries an additional rule for conflicting `open_question_answers`; the reviewer schema here has `new_questions` but no answer field, so that collision cannot arise.)
    - **Route `new_questions` by `settled_by`.** Each carries a class saying who can settle it. Dedupe across lenses first (two lenses often ask the same thing); on a class conflict for the same question, take the **most escalating** label (`needs_human` > `needs_lookup` > `resolvable_in_fold`) — the cautious label is the safe one. Then:
      - **`resolvable_in_fold`** — answer it now by **reading the repository**. The lens saw only the diff; you can read the surrounding code, the callers, and the tests. *Reading any file in the repo is this class, not `needs_lookup`.* Record the answer in the HISTORICAL block.
      - **`needs_lookup`** — the fact is **outside the repository**: it needs a network or API call, or executing something (running the test suite, a benchmark, a command whose output isn't already on disk). Perform it and answer. If it fails or isn't available, **reclassify to `needs_human`** and escalate rather than guessing.
      - **`needs_human`** — surface it at the checkpoint for the user, with the lens's `why` and, where you can, a concrete proposal to accept or change. Never answer it yourself.
      - **Sanity-check the label, don't trust it.** The `why` exists to be audited. If a question labelled `resolvable_in_fold` plainly needs the author's intent, treat it as `needs_human`; a mislabel that licenses a fabricated answer is the failure mode this routing exists to prevent.
    - **Aggregate verdict = worst-of** the lens verdicts (BLOCK > REVISE > APPROVE). A `FAILED` selected lens raises the aggregate to **at least REVISE** — BLOCK is preserved if any *completed* lens returned BLOCK — and blocks Converge (step 14).

12. **Fold merged findings + append ONE HISTORICAL block to the pass log.** Opus is the sole writer: fold findings into the working code and `code_corrections` mechanically. If the pass log doesn't exist, create it with a `# Code Review — <scope-tag>` H1 header, then append a single pass section (each finding tagged with its originating lens id):

    ```markdown
    ## Pass <N> — <YYYY-MM-DD HH:MM> [HISTORICAL]

    **Scope:** <scope value> · **Diff size:** <N lines> · **Verdict:** <APPROVE/REVISE/BLOCK> (worst-of; note any FAILED lenses) · **Lenses:** <senior-dev[, security][, qa]>

    ### Findings

    1. **<title>** — <severity> · lens: <lensid(s)>: <description>
       → Opus: <incorporated|skipped|disputed> — <reasoning, written by Opus when folding>
    2. ...

    ### Code corrections applied

    - <location> — <issue> → <fix description>

    ### New questions Codex raised

    - <question> — <settled_by> (lens: <lensid>): <resolution — the answer if `resolvable_in_fold`/`needs_lookup`, or "escalated to the user" if `needs_human`. Note any label you overrode, and why.>

    ### Lens run summary

    - senior-dev: <APPROVE|REVISE|BLOCK|FAILED>[ · security: <...>][ · qa: <...>]

    ### Diff snapshot reference

    Diff captured at <YYYY-MM-DD HH:MM>; head SHA `<git rev-parse HEAD>` (or PR head SHA for `--scope=pr:<n>`).
    ```

    Dispositions: **`incorporated`** — apply the code edit (required for HIGH unless explicitly disputed with reasoning; recommended for MEDIUM; optional for LOW). **`skipped`** — acknowledge, don't act (typically LOW). **`disputed`** — reject with reasoning (Codex misread intent or a constraint not visible in the diff). `code_corrections` are applied mechanically.

13. **Recompute pass log content.** The pass log now reflects the latest pass for subsequent passes' `=== PRIOR PASSES ===` context.

14. **Checkpoint — Continue / Converge / Abort / (L)oop**, with a recommendation:

    - Recommend **Converge** when aggregate `verdict == APPROVE`, no lens is `FAILED`, and no further folds are pending.
    - Recommend **Continue** otherwise. Never auto-decide convergence.

    Surface a brief summary: "Pass <N>: <verdict> across <lenses>, <X> findings, <Y> corrections. Recommendation: <Continue|Converge>. Choose: (C)ontinue / (V)Converge / (A)bort[ / (L)oop]."

    **Loop mode (opt-in).** If invoked with `--loop` / `--until-approve`, or if the user picks **(L)oop from here**, auto-continue without prompting between passes — but **automate `Continue` only, never `Converge`.** The loop halts and hands back to the human when any guardrail fires:
    - **APPROVE reached** → stop, present the Converge decision.
    - **Max-pass cap** (default 6, `--max-passes=N`) — a *fresh per-activation budget* counting auto-continued passes (the activating pass doesn't count; manual/historical passes don't deplete it) → stop, "hit cap without converging."
    - **BLOCK verdict** → stop.
    - **Non-convergence** — the merged **HIGH+MEDIUM** finding count fails to strictly decrease across two consecutive transitions (LOW / `FAILED` / open-questions excluded; a `FAILED`-lens pass is skipped in the comparison but still counts toward the cap) → stop, surface the stall.
    - **Fold needs human judgment** — any HIGH finding was *not incorporated*, or a `new_question` classified **`needs_human`** survived the fold (after the label sanity-check and any override in step 11) → stop, escalate. `resolvable_in_fold` and `needs_lookup` questions do **not** halt the loop: Opus resolves them and continues. If a `needs_lookup` resolution *fails*, it becomes `needs_human` and then halts. This is the whole point of the classification — an unattended loop shouldn't stop for a question it could have answered, and must never continue past one only the user can.

15. **If `--once` was set**, skip the checkpoint entirely — write the state file (step 16) with `final_action: "once-mode-exit"` and exit immediately after step 13, regardless of verdict. (`--once` and `--loop` are mutually exclusive — reject both together.)

16. **On Continue** (manual or loop-auto): increment pass count, loop to step 9. The next pass's `=== PRIOR PASSES ===` block now includes this pass's HISTORICAL section.

    **On Converge or Abort:** write the state file at `~/.claude/skills/iterate-review/state/<scope-hash>.json` with these fields:

    ```json
    {
      "scope": "<scope value>",
      "scope_tag": "<scope-tag>",
      "pass_log_path": "<absolute path>",
      "pass_count": <N>,
      "last_verdict": "<APPROVE/REVISE/BLOCK>",
      "final_action": "<converged|aborted|once-mode-exit>",
      "started_at": "<ISO timestamp of pass 1>",
      "completed_at": "<ISO timestamp of final action>"
    }
    ```

    Then exit. Pass log file remains in place; per-lens response files (`pass-N.<lensid>.response.json`) under `state/<scope-hash>/` stay on disk for inspection.

## Hard rules

- **Codex never edits any files.** Enforced by `-s read-only -a never` Codex sandbox + reviewer prompt + skill-side patch-marker rejection on the response.
- **Skill never silently iterates.** After every pass, prompt user: Continue / Converge / Abort. Two opt-in exceptions: `--once` exits after pass 1 (user opted out of the loop), and **loop mode** (`--loop` / `(L)oop from here`) auto-continues REVISE passes — but loop mode is *not silent*: every pass appends its HISTORICAL block, and it always halts and returns to the human at APPROVE or any guardrail (step 14). Loop mode automates `Continue` only.
- **Skill never decides convergence.** Suggests when verdict=APPROVE + Opus reports no further folds; human always confirms. **Loop mode never auto-converges** — it stops at APPROVE and presents the Converge decision.
- **Fan-out is one Codex call per selected lens.** Opus merges (semantic dedupe, worst-of verdict, lens attribution). A selected lens that fails after one retry is `FAILED` metadata that forces at-least-REVISE (BLOCK preserved) and blocks Converge. Exactly one HISTORICAL block and one checkpoint per pass, regardless of lens count.
- **v1 is standalone-only.** Refuse `--plan` / `--phase` flags with a clear "deferred to v2" message and exit. Don't half-implement plan-bound features.
- **Opus folds findings.** Codex provides findings; Opus (you) reads them and applies code edits via Edit/Write tools to the working code, then writes the disposition (`incorporated|skipped|disputed`) into the pass log's HISTORICAL block. This is the same Opus-as-sole-writer discipline as iterate-plan.
- **Pass log lives next to where you invoked from**, not inside the skill directory. The skill directory holds machinery (prompt, schema, state); the pass log is a project artifact the user owns.

## Using in plan-driven workflows (v1 — manual coordination)

A plan written by `create-plan` has `**Status:**` fields under each Phase heading and a `## Review checkpoints` section. In v1, those are authored and maintained **by hand** since iterate-review doesn't yet read or write plan-side state. Workflow:

1. Build a phase, ship its commits.
2. Manually invoke iterate-review against the just-shipped diff: `iterate-review --scope=branch` (if the branch is still local) or `iterate-review --scope=pr:<n>` (if a PR was opened, including merged PRs).
3. Loop with Codex until APPROVE; pass log lands as a sibling file (`code-review-<scope-tag>.md`) wherever you invoked from.
4. Manually edit the plan: change the phase's `**Status:** in progress` → `**Status:** reviewed`. Add a row to the `## Review checkpoints` table with a link to the pass log.
5. Repeat for the next phase.
6. When the plan itself archives, move `code-review-<scope-tag>.md` alongside it (per the project's archive convention). The pass log is part of the plan's artifact bundle — keeping it next to the plan preserves the review-trail-vs-shipped-work link. Repo root accumulates cruft otherwise.

A plan can explicitly call out iterate-review in its Phasing section — e.g., "Phase 1 deliverable: run iterate-review on the merged PR before marking Phase complete." That's a fully valid plan instruction in v1.

In v2, steps 2 and 4 collapse to a single `iterate-review --plan=<path> --phase=N` invocation that handles the plan-side updates automatically. Same outcome, no manual coordination.

## Pointers

- `reviewer-prompt.md` — canonical reviewer prompt sent to Codex on every pass.
- `reviewer-output.schema.json` — JSON Schema enforced by `codex exec --output-schema`.
- `lenses/` — persona lens records + the deterministic selection rules (`lenses/README.md`).
- `examples/` — fixtures (see `examples/README.md`). `examples/selection/` pins lens
  routing and ships a runnable reference implementation (`check-selection.py`);
  `examples/merge/` holds merge/verdict goldens. Validate with `tools/check-examples.py`.
- `state/<scope-hash>/pass-N.response.json` — per-pass raw Codex responses, kept for inspection.
- `state/<scope-hash>.json` — per-invocation final state, written at convergence/abort.

Sibling skills:
- `~/.claude/skills/iterate-plan/SKILL.md` — architectural model.
- `~/.claude/skills/create-plan/SKILL.md` — first-in-trinity, scaffolds plans this skill reviews against.
