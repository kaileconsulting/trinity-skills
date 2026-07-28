---
name: iterate-plan
description: Iterate a plan file between Opus (editor) and Codex (reviewer) until convergence, with mandatory human checkpoints. Use when the user has a plan in markdown and wants Codex's review folded back in without manually shuttling content.
---

# `iterate-plan`

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
`/iterate-plan <plan-path>`.

Optional flags:
- `--loop` (alias `--until-approve`) — start in **loop mode**: auto-continue
  through REVISE passes without prompting, stopping at the first APPROVE for
  the human's Converge call (see per-pass step 10). Loop mode can also be
  entered mid-run via the `(L)oop from here` checkpoint option.
- `--max-passes=N` — loop-mode safety cap (default 6), a fresh budget per loop
  activation.

## Setup (once per skill invocation)

1. Read the plan file at the user's specified path.
2. Soft-validate plan format (warns if Status / TL;DR / Sequencing /
   Open Questions sections are missing; allows `--no-validate`).
3. Compute `plan_content_hash` (sha256 of file contents) and remember it
   in-session — used for manual-edit detection between passes.
4. Load state file at `~/.claude/skills/iterate-plan/state/<sha1-of-abs-path>.json`
   if present. If absent, this is pass 1; initialize an empty in-session
   state record. (State is *written* only at convergence/abort — see step 9.
   Light-shape; can harden later if cross-session resume becomes
   load-bearing.)

## Per-pass loop

Each pass fans out across the **persona lenses** for design review (see
`lenses/` — `architect` + `product-manager`, both always selected per
`lenses/README.md`), then Opus merges their findings into one list. Steps
6–10 (fan-out, per-response validation, merge + worst-of verdict + `FAILED`
handling, one HISTORICAL block, and the loop-mode checkpoint) are the
**SHARED MACHINERY** — the same *rules* (fan-out, semantic merge, worst-of
verdict, `FAILED` handling, one HISTORICAL block, one checkpoint, loop mode +
guardrails) hold in the sibling `iterate-review` skill's steps 10–14. Keep
them in **semantic parity** — the prose legitimately differs where each
skill's folding / pass-log / `--once` details differ; a Phase 4 fixture checks
the shared *rules* are present in both, **not** byte-identity. Only lens
selection + matched-context composition (step 5) is skill-specific.

5. **Select lenses + compose matched context.** Read the lens records in
   `~/.claude/skills/iterate-plan/lenses/*.md` and apply the selection table.
   For iterate-plan both lenses always run.

   For each lens, build a matched-context file by **extracting the plan H2
   sections named in its `requires_sections`** — match a line `## <title>`
   (title compared with the `## ` marker stripped) and take everything from
   that heading up to the next `## ` heading. Write the concatenated slices to
   `$STATE_DIR/pass-$N.<lensid>.context.md` under a header
   `=== MATCHED CONTEXT (sections for the <lensid> lens) ===`, and use it as
   `$MATCHED_CONTEXT_FILE` in step 6. A shell helper for one section:

   ```bash
   extract_section() {  # $1 = bare H2 title, $2 = plan path
     awk -v t="## $1" '$0==t{f=1;print;next} /^## /&&f{f=0} f{print}' "$2"
   }
   ```

   **If a required section is absent** (the helper prints nothing), still build
   the file but include a line `NOTE: required section "<title>" is absent —
   flag this gap` so the lens reports the omission rather than inventing
   content. Never skip a lens, never hand it an empty file.

6. **Fan out — one Codex call per selected lens, concurrently.** For each lens,
   compose its input = the shared `reviewer-prompt.md` + the lens's ROLE/FOCUS
   fragment + its matched-context slice + the plan. Run the calls in parallel
   (background subprocesses), each writing
   `$STATE_DIR/pass-$N.<lensid>.response.json`:

   ```bash
   cat ~/.claude/skills/iterate-plan/reviewer-prompt.md \
       ~/.claude/skills/iterate-plan/lenses/<lensid>.md \
       "$MATCHED_CONTEXT_FILE" "$PLAN_PATH" \
     | codex -a never exec \
         -C "$(dirname "$PLAN_PATH")" \
         -s read-only --skip-git-repo-check \
         --output-schema ~/.claude/skills/iterate-plan/reviewer-output.schema.json \
         --json --output-last-message "$STATE_DIR/pass-$N.<lensid>.response.json" \
         -
   ```

   Notes (unchanged from single-lens): `-a never` precedes `exec`;
   `--skip-git-repo-check` when the plan dir isn't a git repo; the trailing `-`
   reads stdin. If a manual edit was detected at the top of this pass (current
   plan hash ≠ post-fold hash from the previous pass), prepend a
   `Note: human edits since last pass — diff:` block to every lens's input.

7. **Read, validate, and merge the lens responses.**
   - **Per response:** read each `pass-$N.<lensid>.response.json` (already
     schema-validated by `--output-schema`). Apply belt-and-suspenders
     patch-marker rejection (`*** Begin Patch`, `--- a/`, `+++ b/`, `@@`,
     `<<<<<<<`).
   - **Lens failure:** a lens that crashes or returns malformed/off-schema
     output is **retried once**; if it still fails, record it as `FAILED`
     orchestration metadata — **not** a verdict (the reviewer schema is
     untouched).
   - **Merge (Opus, semantic judgment — not a mechanical key):** collapse
     findings that target the same location and assert the same defect; keep
     distinct concerns separate; a co-reported finding retains **all**
     contributing lens ids. Produce one merged findings list.
   - **Dedupe `plan_corrections` too.** Two lenses can file the same tactical
     correction. Corrections are applied *mechanically*, so a surviving
     duplicate can double-apply the same edit. Collapse by location +
     intended fix.
   - **Conflicting open-question answers.** When two lenses answer the same
     `question_id`, record **both** with lens attribution. If they agree,
     merge into one answer. If they **disagree**, state the disagreement
     explicitly and escalate — never average them, pick the more
     authoritative-sounding lens, or let the last-read answer win. A
     cross-lane disagreement is usually the plan's own unresolved tension
     surfacing, which is what fanning out is for; it is a human-judgment fold
     under step 10's guardrail, not a merge to resolve silently.
   - **Route `new_questions` by `settled_by`.** Each carries a class saying
     who can settle it. Dedupe across lenses first (two lenses often ask the
     same thing); on a class conflict for the same question, take the **most
     escalating** label (`needs_human` > `needs_lookup` >
     `resolvable_in_fold`) — the cautious label is the safe one. Then:
     - **`resolvable_in_fold`** — answer it now from the full plan + repo. The
       lens saw only its required sections; you have everything. Record the
       answer in the HISTORICAL block.
     - **`needs_lookup`** — perform the lookup (read a file, query an API, run
       the command) and answer it. If the lookup fails or isn't available,
       **reclassify to `needs_human`** and escalate rather than guessing.
     - **`needs_human`** — carry it into the plan's `## Open questions` as a
       numbered Q for Kyle, with the lens's `why` and, where you can, a
       concrete proposal to accept or change. Never answer it yourself.
     - **Sanity-check the label, don't trust it.** The `why` exists to be
       audited. If a question labelled `resolvable_in_fold` plainly needs the
       author's preference, treat it as `needs_human`; a mislabel that
       licenses a fabricated answer is the failure mode this routing exists to
       prevent.
   - **Aggregate verdict = worst-of** the lens verdicts (BLOCK > REVISE >
     APPROVE). A `FAILED` selected lens raises the aggregate to **at least
     REVISE** — BLOCK is preserved if any *completed* lens returned BLOCK —
     and blocks Converge (step 10).

8. **Fold merged findings + append ONE HISTORICAL block.** Opus is the sole
   writer. Fold `plan_corrections` mechanically; incorporate HIGH/MEDIUM
   findings (skip/dispute only with explicit reasoning); LOW is informational.
   Append a single HISTORICAL section for the whole pass, each finding tagged
   with its originating **lens id(s)** and fold disposition:

   ```markdown
   ## Codex review pass N — answers (YYYY-MM-DD) [HISTORICAL]

   ### Verdict
   APPROVE / REVISE / BLOCK   (worst-of; note any FAILED lenses)

   ### Findings
   1. **<title>** — <severity> · lens: <architect|product-manager|both>: <description>
      → Opus: <incorporated|skipped|disputed> — <reasoning>
   ...

   ### Plan corrections applied
   - <location>: <fix description>

   ### Open-question answers
   1. <answer>

   ### New questions Codex raised
   - <question> — <settled_by> (lens: <lensid>): <resolution — the answer if
     `resolvable_in_fold`/`needs_lookup`, or "carried to Open questions as Qn"
     if `needs_human`. Note any label you overrode, and why.>

   ### Lens run summary
   - architect: <APPROVE|REVISE|BLOCK|FAILED> · product-manager: <APPROVE|REVISE|BLOCK|FAILED>
   ```

9. **Recompute `plan_content_hash` post-fold.** Stash for the next pass's
   manual-edit detection.

10. **Checkpoint — Continue / Converge / Abort / (L)oop.** Present the
    aggregate verdict + a recommendation:
    - Recommend **Converge** when aggregate `verdict == APPROVE`, no lens is
      `FAILED`, and Opus has no further changes pending. One APPROVE +
      no-further-changes is enough.
    - Recommend **Continue** otherwise. Never auto-decide convergence.

    **Loop mode (opt-in).** If invoked with `--loop` / `--until-approve`, or if
    the user picks **(L)oop from here** at this checkpoint, auto-continue
    without prompting between passes — but **automate `Continue` only, never
    `Converge`.** The loop halts and hands back to the human when any guardrail
    fires:
    - **APPROVE reached** → stop, present the Converge decision.
    - **Max-pass cap** (default 6, `--max-passes=N`) — a *fresh per-activation
      budget* counting auto-continued passes (the activating pass doesn't
      count; manual/historical passes don't deplete it) → stop, "hit cap
      without converging."
    - **BLOCK verdict** → stop.
    - **Non-convergence** — the merged **HIGH+MEDIUM** finding count fails to
      strictly decrease across two consecutive transitions (LOW / `FAILED` /
      open-questions excluded; a `FAILED`-lens pass is skipped in the
      comparison but still counts toward the cap) → stop, surface the stall.
    - **Fold needs human judgment** — any HIGH finding was *not incorporated*,
      or a `new_question` classified **`needs_human`** survived the fold (after
      the label sanity-check and any override in step 7) → stop, escalate.
      `resolvable_in_fold` and `needs_lookup` questions do **not** halt the
      loop: Opus resolves them and continues. If a `needs_lookup` resolution
      *fails*, it becomes `needs_human` and then halts. This is the whole point
      of the classification — an unattended loop shouldn't stop for a question
      it could have answered, and must never continue past one only Kyle can.

    On **Continue** (manual or loop-auto): increment pass count, loop to step 5.
    On **Converge**: enter the Sonnet-handoff sub-flow (Phase 3, below).
    On **Abort**: write the state file with final values (`pass_count`,
    `last_verdict`, `plan_abs_path`, `plan_content_hash`, `started_at`,
    `last_pass_at`, `convergence.handoff_decision="aborted"`), exit.

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
    `<plan-path>.handoff-prompt.md`. Default content is summary +
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
- `examples/` — fixtures (see `examples/README.md`). `pass-4-response.json` is a
  real pre-Axis-2 Codex response; `examples/merge/` holds multi-lens merge
  goldens. Validate with `tools/check-examples.py`.

## Hard rules

- Codex never edits the plan file. Enforced by `-s read-only -a never`
  sandbox + reviewer prompt + skill-side patch-marker rejection.
- Skill never silently iterates. After every pass, prompt user:
  Continue / Converge / Abort. **Loop mode is the one opt-in exception**
  (via `--loop` or the `(L)oop from here` choice): it auto-continues REVISE
  passes without prompting, but it is *not silent* — every pass appends its
  HISTORICAL block, and the loop always halts and returns to the human at
  APPROVE or any guardrail (step 10). Loop mode automates `Continue` only.
- Skill never decides convergence. Suggests when verdict=APPROVE +
  Opus reports no further changes; human always confirms. **Loop mode never
  auto-converges** — it stops at APPROVE and presents the Converge decision.
- Fan-out is one Codex call per selected lens; Opus merges (semantic dedupe,
  worst-of verdict, lens attribution). A selected lens that fails after one
  retry is `FAILED` metadata that forces at-least-REVISE (BLOCK preserved) and blocks Converge. Exactly
  one HISTORICAL block and one checkpoint per pass, regardless of lens count.
- Sonnet-handoff at convergence is fully user-driven: skill writes
  the handoff prompt to disk, user copies into a fresh session and
  performs the `/clear` + model swap themselves.
