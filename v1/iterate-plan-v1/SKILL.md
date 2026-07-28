---
name: iterate-plan-v1
description: FROZEN V1 (single-reviewer) plan review. Do NOT use this unless the user explicitly asks for the V1, original, simple, or single-reviewer variant by name. The current skill is `iterate-plan`, which fans out to multiple persona lenses per pass and merges their findings — prefer it in every other case, including any generic request to review or iterate a plan. This variant runs exactly one Codex call per pass: no lens selection, no fan-out, no merge, no loop mode. Kept installable for anyone who wants the original basic loop.
---

# `iterate-plan-v1`

Formalizes the proven Opus⇄Codex review loop. Opus is the sole editor of
the plan file. Codex is the technical reviewer — provides structured
feedback via `codex exec --output-schema`, never edits.

## When to invoke

User wants Codex's review on a plan document and would otherwise be
copying plan content + Codex's response back and forth manually.

Typical trigger phrases: "send this to Codex," "what does Codex think
of this plan," "iterate this plan with Codex."

## How to invoke

The skill surfaces in-session via the available-skills list at session
start (slash command + Skill tool both work). User typically triggers
with a phrase like "iterate this plan with Codex" or
`/iterate-plan-v1 <plan-path>`.

## Setup (once per skill invocation)

1. Read the plan file at the user's specified path.
2. Soft-validate plan format (warns if Status / TL;DR / Sequencing /
   Open Questions sections are missing; allows `--no-validate`).
3. Compute `plan_content_hash` (sha256 of file contents) and remember it
   in-session — used for manual-edit detection between passes.
4. Load state file at `~/.claude/skills/iterate-plan-v1/state/<sha1-of-abs-path>.json`
   if present. If absent, this is pass 1; initialize an empty in-session
   state record. (State is *written* only at convergence/abort — see step 9.
   Light-shape; can harden later if cross-session resume becomes
   load-bearing.)

## Per-pass loop

5. **Invoke Codex** with the reviewer prompt + plan content piped through
   stdin:

```bash
cat ~/.claude/skills/iterate-plan-v1/reviewer-prompt.md "$PLAN_PATH" \
  | codex -a never exec \
      -C "$(dirname "$PLAN_PATH")" \
      -s read-only \
      --skip-git-repo-check \
      --output-schema ~/.claude/skills/iterate-plan-v1/reviewer-output.schema.json \
      --json \
      --output-last-message "$STATE_DIR/pass-$N.response.json" \
      -
```

   Notes:
   - `-a never` precedes the `exec` subcommand because it's a
     root-level flag in codex-cli 0.125.0+.
   - `--skip-git-repo-check` is required when `$PLAN_PATH` is in a
     directory that isn't a git repo.
   - Reviewer prompt is concatenated with plan content and piped
     through stdin via the `cat ... | codex ... -` pattern (the
     trailing `-` argument tells `codex exec` to read from stdin).
   - If a manual-edit was detected at the top of this pass (current
     plan hash ≠ post-fold hash from previous pass), prepend a
     `Note: human-edits since last pass — diff:` block + diff to the
     `cat` pipeline so Codex sees the divergence.

6. **Read + validate response.** Read `pass-$N.response.json` — already
   schema-structured. Reject the pass if response contains patch markers
   (`*** Begin Patch`, unified diff `--- a/`, `+++ b/`, `@@`,
   merge-conflict `<<<<<<<`). Belt-and-suspenders against schema bypass.

7. **Auto-fold findings into the plan via Edit tool.** Opus is the sole
   writer. For each item:
   - **`plan_corrections`** — apply mechanically inline. These are
     non-controversial typo / broken-ref / contradiction fixes.
   - **`findings`** — apply revisions inline for HIGH and MEDIUM
     severity (skip / dispute only with explicit reasoning, captured in
     the audit trail). LOW is informational; address if cheap, document
     either way.
   - **Append HISTORICAL section** to the plan using this exact template:

   ```markdown
   ## Codex review pass N — answers (YYYY-MM-DD) [HISTORICAL]

   ### Verdict
   APPROVE / REVISE / BLOCK

   ### Findings
   1. **<title>** — <severity>: <description>
      → Opus: <incorporated|skipped|disputed> — <reasoning>
   ...

   ### Plan corrections applied
   - <location>: <fix description>

   ### Open-question answers
   1. <answer>

   ### New questions Codex raised
   - <question>
   ```

8. **Recompute `plan_content_hash` post-fold.** Stash this for the next
   pass's manual-edit detection.

9. **Present Continue / Converge / Abort to the user**, with a
   recommendation:
   - Recommend **Converge** when `verdict == APPROVE` AND Opus has no
     further changes pending. One APPROVE + no-further-changes is enough
     — don't require two consecutive APPROVEs.
   - Recommend **Continue** otherwise.
   - Never auto-decide. Human always confirms.

10. On **Continue**: increment pass count, loop to step 5.
    On **Converge**: enter the Sonnet-handoff sub-flow (Phase 3, below).
    On **Abort**: skip Phase 3, write state file with final values
    (`pass_count`, `last_verdict`, `plan_abs_path`, `plan_content_hash`,
    `started_at`, `last_pass_at`, `convergence.handoff_decision="aborted"`),
    exit.

## On Converge — Sonnet-handoff sub-flow (Phase 3)

11. **Assess plan complexity, recommend handoff vs stay.** Opus
    surfaces a one-paragraph recommendation framed by these signals:
    - **Handoff to Sonnet** when the plan is well-specified, execution
      is largely mechanical, and a fresh session helps (lower context
      cost during execution, cleaner separation of design vs build).
      Long plans (~500+ lines) touching many files usually fit here.
    - **Stay with Opus** when the plan is short, execution overlaps
      with ongoing design judgment, or there's load-bearing in-session
      context that's expensive to re-establish. Plans drafted and
      executed in a single sitting often fit here.

12. **Prompt user: (H)andoff to Sonnet / (S)tay with Opus / (A)bort.**
    Always surface all three. Never auto-pick — Opus's recommendation
    is advisory only.

13. On **Handoff**: generate the handoff prompt and write to
    `<plan-path>.handoff-prompt-v1.md`. Default content is summary +
    pointer (full plan inline only if user explicitly requests it):

    ```markdown
    # Handoff: <plan title>

    ## Summary
    <one-paragraph summary of what the plan accomplishes>

    ## Plan
    Full plan at: `<absolute plan path>`
    Read this first.

    ## Current step
    <which phase / step the next session starts at — typically
    "Phase 1, step 1" of the plan's Sequencing section>

    ## Shipped commits referenced by the plan
    - `<sha>` — <one-line message>
    - ...

    ## Remaining risks
    - <risk the executor session should know about>
    - ...

    ## First action
    <exact first command or file edit the next session should take>
    ```

    Then surface the absolute path with a one-line instruction:

    > Handoff prompt written to `<path>`. Open a fresh Claude Code
    > session, run `/clear` + `/model sonnet`, then paste the
    > contents of that file. The skill cannot perform the model
    > swap or session clear itself.

14. On **Stay**: no handoff file written. Plan is green-lit; user
    proceeds with implementation in the same session.

15. Write state file with final values
    (`pass_count`, `last_verdict`, `plan_abs_path`, `plan_content_hash`,
    `started_at`, `last_pass_at`,
    `convergence.handoff_decision` ∈ `{handoff, stay, aborted}`,
    `convergence.handoff_path` if applicable). Exit.

State file shape: see `state/example.json`. Per-pass response files
(`pass-N.response.json`) are written by `codex --output-last-message`
during the loop and stay on disk for inspection / debugging.

## Pointers

- `reviewer-prompt.md` — canonical reviewer prompt sent to Codex.
- `reviewer-output.schema.json` — JSON Schema enforced by `--output-schema`.
- `state/<plan-path-hash>.json` — per-plan iteration state (written at
  convergence/abort only).
- `state/example.json` — illustrative state file showing the schema.
- `examples/pass-4-response.json` — a real Codex response, fixture for testing.

## Hard rules

- Codex never edits the plan file. Enforced by `-s read-only -a never`
  sandbox + reviewer prompt + skill-side patch-marker rejection.
- Skill never silently iterates. After every pass, prompt user:
  Continue / Converge / Abort.
- Skill never decides convergence. Suggests when verdict=APPROVE +
  Opus reports no further changes; human always confirms.
- Sonnet-handoff at convergence is fully user-driven: skill writes
  the handoff prompt to disk, user copies into a fresh session and
  performs the `/clear` + model swap themselves.
