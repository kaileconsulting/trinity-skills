---
name: iterate-review-v1
description: FROZEN V1 (single-reviewer) code review. Do NOT use this unless the user explicitly asks for the V1, original, simple, or single-reviewer variant by name. The current skill is `iterate-review`, which deterministically selects persona lenses and merges their findings — prefer it in every other case, including any generic request to have Codex review code. This variant runs exactly one Codex call per pass: no lens selection, no fan-out, no merge, no loop mode. Kept installable for anyone who wants the original basic loop.
---

# `iterate-review-v1`

Formalizes the proven Opus⇄Codex review loop, applied to code review (sibling of `iterate-plan-v1`, which applies the same loop to plan design review). Opus is the sole writer of fold actions; Codex is the technical reviewer — provides structured feedback via `codex exec --output-schema`, never edits files.

## When to invoke

User wants Codex's review on a code change and would otherwise be copying the diff + Codex's response back and forth manually.

Typical trigger phrases: "have Codex review this," "code-review this branch with Codex," "what does Codex think of this PR," `/iterate-review-v1 --scope=working`.

Do NOT invoke for plan design review — that's `iterate-plan-v1`'s job. iterate-review-v1 reviews code; iterate-plan-v1 reviews plan markdown.

## How to invoke

The skill surfaces in-session via the available-skills list at session start (slash command + Skill tool both work). User typically triggers with one of:

- `iterate-review-v1 --scope=working` — review uncommitted working-tree changes
- `iterate-review-v1 --scope=branch` — review the current branch's diff against `main`
- `iterate-review-v1 --scope=pr:<n>` — review a merged or open PR by number (uses `gh pr diff`)
- `iterate-review-v1 --scope=<...> --once` — single-pass review, no Continue/Converge/Abort loop
- `iterate-review-v1 --scope=<...> --log-path=<path>` — custom pass log location

If the user invokes without a `--scope` flag, ask them which scope they want before proceeding. Default suggestion: `--scope=working` if there are uncommitted changes (`git status --porcelain` non-empty), `--scope=branch` if the current branch is ahead of main, otherwise prompt for `pr:<n>`.

## Setup (once per skill invocation)

1. **Parse args.** Extract `--scope=<value>`, `--once` (flag), `--log-path=<path>`. Reject `--plan` / `--phase` flags with a clear "v1 is standalone-only; plan-bound deferred to v2" message and exit.

2. **Verify Codex CLI is available.** Run `codex --version` via Bash. If the command fails, surface a clear error: "Codex CLI not found — install it before invoking iterate-review-v1." Exit. (Pin: tested against codex-cli 0.125.0+.)

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

5. **Determine pass log path.** Default: `<cwd>/code-review-v1-<scope-tag>.md`. Override: `--log-path=<path>`. Surface the resolved path to the user before the first pass.

6. **Determine state file path.** Compute `scope-hash` = sha1 of `<scope-tag>|<pass-log-path>`. State file: `~/.claude/skills/iterate-review-v1/state/<scope-hash>.json`. State file is written at convergence/abort only — see Step 12.

7. **Detect prior passes.** If the pass log file exists at the resolved path, read it to determine the next pass number (`prior_passes + 1`). Capture its content as the `=== PRIOR PASSES ===` block for the Codex input. If the file doesn't exist, this is pass 1 with no prior passes.

8. **Surface scope summary to user.** Before the first pass, output a brief block:

   ```
   iterate-review-v1 starting:
   - Scope: <scope value>
   - Diff size: <N lines>
   - Pass log: <pass log path>
   - This is pass <N> (previous passes detected: <0 / 1 / 2 / ...>)
   ```

   Lets the user sanity-check before Codex spins up.

## Per-pass loop

9. **Compose Codex input.** Concatenate (in order):

   - Contents of `~/.claude/skills/iterate-review-v1/reviewer-prompt.md`
   - A `---` delimiter line
   - `=== INTENT ===` header followed by intent context. For v1 standalone, intent is best-effort:
     - `--scope=working` → "Standalone code review of working-tree changes; no commit message yet. The diff below should be reviewed for correctness/clarity on its own merits."
     - `--scope=branch` → output of `git log $(git merge-base HEAD main)..HEAD --pretty=format:"%h %s%n%b%n---"` (commit messages on the branch)
     - `--scope=pr:<n>` → output of `gh pr view <n> --json title,body --jq '"\(.title)\n\n\(.body)"'` (PR title + description)
   - `=== DIFF ===` header followed by the captured diff content
   - `=== PRIOR PASSES ===` header followed by the prior pass log content (empty if pass 1)

10. **Invoke Codex via subprocess.** Use the same pattern as iterate-plan-v1:

    ```bash
    PASS_N=<current pass number>
    STATE_DIR=~/.claude/skills/iterate-review-v1/state/<scope-hash>
    mkdir -p "$STATE_DIR"

    cat <(echo "<composed input from step 9>") \
      | codex -a never exec \
          -s read-only \
          --skip-git-repo-check \
          --output-schema ~/.claude/skills/iterate-review-v1/reviewer-output.schema.json \
          --json \
          --output-last-message "$STATE_DIR/pass-$PASS_N.response.json" \
          -
    ```

    Notes (carried from iterate-plan-v1's hard-won lessons):
    - `-a never` precedes the `exec` subcommand because it's a root-level flag in codex-cli 0.125.0+.
    - `--skip-git-repo-check` is required if the cwd isn't a git repo.
    - The trailing `-` argument tells `codex exec` to read from stdin.
    - In practice, write the composed input to a temp file (`/tmp/iterate-review-v1-input-pass-<N>.txt`) and `cat` it, rather than building the heredoc inline — easier to debug if Codex misbehaves.

11. **Read + validate response.** Read `$STATE_DIR/pass-$PASS_N.response.json`. The response is already JSON-schema-validated by `codex exec --output-schema`, but apply belt-and-suspenders rejection: scan the entire response for any of these patch-shaped markers:

    - `*** Begin Patch`
    - `--- a/` or `+++ b/`
    - `@@ -` followed by digits
    - `<<<<<<<` or `=======` or `>>>>>>>` (merge conflict markers)

    If any are present, abort the loop with: "Codex response contains patch-shaped output, which violates the reviewer contract. Aborting. Inspect `$STATE_DIR/pass-$PASS_N.response.json` to debug." Do not proceed.

12. **Append HISTORICAL block to pass log.** Use the Edit or Write tool to append a new section to the pass log file. If the file doesn't exist yet, create it with a `# Code Review — <scope-tag>` H1 header at the top, then append the pass section. Format the pass section like this:

    ```markdown
    ## Pass <N> — <YYYY-MM-DD HH:MM> [HISTORICAL]

    **Scope:** <scope value> · **Diff size:** <N lines> · **Verdict:** <APPROVE/REVISE/BLOCK>

    ### Findings

    1. **<title>** — <severity>: <description>
       → Opus: <incorporated|skipped|disputed> — <reasoning, written by Opus when folding>
    2. ...

    ### Code corrections applied

    - <location> — <issue> → <fix description>
    - ...

    ### New questions Codex raised

    - <question>
    - ...

    ### Diff snapshot reference

    Diff captured at <YYYY-MM-DD HH:MM>; head SHA `<git rev-parse HEAD>` (or PR head SHA for `--scope=pr:<n>`).
    ```

    For each finding, Opus (you) decides the disposition:
    - **`incorporated`** — apply changes to the working code via Edit/Write. Required for HIGH severity unless explicitly disputed with reasoning. Recommended for MEDIUM. Optional for LOW.
    - **`skipped`** — acknowledge the finding but don't act on it (typically LOW polish items the user explicitly waves away).
    - **`disputed`** — reject the finding with reasoning (e.g., "this is intentional because <reason>"). Reserved for cases where Codex misunderstood intent or constraints not visible in the diff.

    For `code_corrections`, apply mechanically — they're non-controversial by definition.

13. **Recompute pass log content.** After appending, the pass log now reflects the latest pass for use in subsequent passes' `=== PRIOR PASSES ===` context.

14. **Present Continue / Converge / Abort to the user**, with a recommendation:

    - Recommend **Converge** when `verdict == APPROVE` AND no further folds are pending.
    - Recommend **Continue** otherwise.
    - Never auto-decide. Human always confirms.

    Surface a brief summary: "Pass <N> verdict: <V>. <X> findings, <Y> corrections applied. Recommendation: <Continue|Converge>. Choose: (C)ontinue / (V)Converge / (A)bort."

15. **If `--once` flag was set**, skip the prompt entirely — write the state file (Step 16) with `final_action: "once-mode-exit"` and exit immediately after Step 12, regardless of verdict.

16. **On Continue:** increment pass count, loop to step 9. The next pass's `=== PRIOR PASSES ===` block now includes this pass's HISTORICAL section.

    **On Converge or Abort:** write the state file at `~/.claude/skills/iterate-review-v1/state/<scope-hash>.json` with these fields:

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

    Then exit. Pass log file remains in place; per-pass response files (`pass-N.response.json`) under `state/<scope-hash>/` stay on disk for inspection.

## Hard rules

- **Codex never edits any files.** Enforced by `-s read-only -a never` Codex sandbox + reviewer prompt + skill-side patch-marker rejection on the response.
- **Skill never silently iterates.** After every pass, prompt user: Continue / Converge / Abort. Exception: `--once` mode exits after pass 1 without prompting (the user opted out of the loop explicitly).
- **Skill never decides convergence.** Suggests when verdict=APPROVE + Opus reports no further folds; human always confirms.
- **v1 is standalone-only.** Refuse `--plan` / `--phase` flags with a clear "deferred to v2" message and exit. Don't half-implement plan-bound features.
- **Opus folds findings.** Codex provides findings; Opus (you) reads them and applies code edits via Edit/Write tools to the working code, then writes the disposition (`incorporated|skipped|disputed`) into the pass log's HISTORICAL block. This is the same Opus-as-sole-writer discipline as iterate-plan-v1.
- **Pass log lives next to where you invoked from**, not inside the skill directory. The skill directory holds machinery (prompt, schema, state); the pass log is a project artifact the user owns.

## Using in plan-driven workflows (v1 — manual coordination)

A plan written by `create-plan` has `**Status:**` fields under each Phase heading and a `## Review checkpoints` section. In v1, those are authored and maintained **by hand** since iterate-review-v1 doesn't yet read or write plan-side state. Workflow:

1. Build a phase, ship its commits.
2. Manually invoke iterate-review-v1 against the just-shipped diff: `iterate-review-v1 --scope=branch` (if the branch is still local) or `iterate-review-v1 --scope=pr:<n>` (if a PR was opened, including merged PRs).
3. Loop with Codex until APPROVE; pass log lands as a sibling file (`code-review-v1-<scope-tag>.md`) wherever you invoked from.
4. Manually edit the plan: change the phase's `**Status:** in progress` → `**Status:** reviewed`. Add a row to the `## Review checkpoints` table with a link to the pass log.
5. Repeat for the next phase.
6. When the plan itself archives, move `code-review-v1-<scope-tag>.md` alongside it (per the project's archive convention). The pass log is part of the plan's artifact bundle — keeping it next to the plan preserves the review-trail-vs-shipped-work link. Repo root accumulates cruft otherwise.

A plan can explicitly call out iterate-review-v1 in its Phasing section — e.g., "Phase 1 deliverable: run iterate-review-v1 on the merged PR before marking Phase complete." That's a fully valid plan instruction in v1.

In v2, steps 2 and 4 collapse to a single `iterate-review-v1 --plan=<path> --phase=N` invocation that handles the plan-side updates automatically. Same outcome, no manual coordination.

## Pointers

- `reviewer-prompt.md` — canonical reviewer prompt sent to Codex on every pass.
- `reviewer-output.schema.json` — JSON Schema enforced by `codex exec --output-schema`.
- `state/<scope-hash>/pass-N.response.json` — per-pass raw Codex responses, kept for inspection.
- `state/<scope-hash>.json` — per-invocation final state, written at convergence/abort.

Sibling skills:
- `~/.claude/skills/iterate-plan-v1/SKILL.md` — architectural model.
- `~/.claude/skills/create-plan/SKILL.md` — first-in-trinity, scaffolds plans this skill reviews against.
