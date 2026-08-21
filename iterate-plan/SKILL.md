---
name: iterate-plan
description: Iterate a plan file between Claude (editor) and Codex (reviewer) until convergence, with mandatory human checkpoints. Use when the user has a plan in markdown and wants Codex's review folded back in without manually shuttling content.
---

# `iterate-plan`

Formalizes the proven Claude⇄Codex review loop. Claude — whichever model
drives the session — is **the editor**, sole editor of the plan file. Codex
is the technical reviewer — provides structured feedback via
`codex exec --output-schema`, never edits.

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
- `--keep-state` — on Converge, skip the state-dir prune and keep the
  per-pass inputs/responses for audit or debugging.

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
`lenses/README.md`), then the editor merges their findings into one list. Steps
6–10 (fan-out, per-response validation, merge + worst-of verdict + `FAILED`
handling, one HISTORICAL block, and the loop-mode checkpoint) are the
**SHARED MACHINERY** — the same *rules* (fan-out, semantic merge, worst-of
verdict, `FAILED` handling, one HISTORICAL block, one checkpoint, loop mode +
guardrails) hold in the sibling `iterate-review` skill's steps 10–14. Keep
them in **semantic parity** — the prose legitimately differs where each
skill's folding / pass-log / `--once` details differ; `tools/check-parity.py`
checks the shared *rules* are present in both, **not** byte-identity. Only
lens selection + input composition (step 5) is skill-specific — and both are
performed by the runner, deterministically.

5. **Prepare the pass input — the runner selects lenses and composes.** The
   plan file itself is the pass input; it must live **inside the invoking
   repo root** (the runner refuses any `--plan` path — symlinks resolved —
   outside it, and refuses non-`.md` files, so the pre-approved allowlist
   rule can never be used to read arbitrary files into a network-backed
   codex prompt).

   **Only if a manual edit was detected** at the top of this pass (current
   plan hash ≠ post-fold hash from the previous pass): write a
   `Note: human edits since last pass — diff:` block to a note file — **in
   the per-repository handoff directory, enforced**: `<git-dir>/iterate-plan/`
   (worktree-aware; invisible to git, uncommittable; in a non-git cwd:
   `<cwd>/.iterate-plan/`). The runner refuses `--note` paths anywhere else —
   including elsewhere *inside* the repo — and prepends the staged note to
   every lens's input.

   **Lens selection is deterministic and performed by `run-pass`** — every
   iterate-plan lens is `always: true` per `lenses/README.md`, so selection
   is the full lens set; pass `--lenses <ids>` only to deliberately force a
   subset (e.g. retrying one lens). Composition is likewise the runner's:
   shared `reviewer-prompt.md` + the lens's ROLE/FOCUS fragment + a
   `=== MATCHED CONTEXT ===` block (the lens's `matched_context` framing
   line plus the plan H2 sections named in its `requires_sections` — exact
   `## <title>` match, sub-headings kept with their parent; an absent
   section contributes `NOTE: required section "<title>" is absent — flag
   this gap` so the lens reports the omission rather than inventing content;
   never skipped, never handed silence) + the optional staged note + the
   full plan under `=== PLAN ===`, assembled **byte-deterministically**
   (goldens in `examples/composition/`; composed inputs land in the state
   dir as `pass-N.<lensid>.input.txt`). Prior passes need no separate block:
   the plan's own HISTORICAL sections arrive with the plan.

6. **Fan out — one `run-pass` invocation.** The runner makes **one Codex
   call per selected lens, concurrently** (all lens futures awaited; one
   lens failing never cancels its siblings), each writing
   `$STATE_DIR/pass-$N.<lensid>.response.json` with the exact sandbox flags
   (`codex -a never exec -C <plan-dir> -s read-only --skip-git-repo-check
   --output-schema … --json --output-last-message … -`), then publishes
   `pass-$N.summary.json` last:

   ```bash
   ~/.claude/skills/iterate-plan/bin/run-pass \
     --plan "$PLAN_PATH" [--note "$NOTE_FILE"] [--lenses <ids>]
   ```

   Contract: **the runner composes and invokes; it never folds, never writes
   the plan, never decides.** Exit 0 means exactly "the summary was
   published" — per-lens failure/rejection is *data* inside it
   (`status: ok|failed|rejected`, with exit code + stderr tail). Non-zero
   exit / absent summary means the pass **aborted**: treat it as never-ran
   and surface the runner's stderr to the user (e.g. the scope is locked by
   a concurrent run, or an ambiguous lock needs `prune-state
   --force-unlock`). **A pass exists iff its summary exists.** The summary
   echoes `scope_hash` (sha1 of the plan's absolute path — the same per-plan
   key as the state file) and `log_path` (the plan path — iterate-plan's
   HISTORICAL record lives in the plan itself). This one command shape is
   what the README's single allowlist rule pre-approves; requires `python3`
   ≥ 3.9 and `codex` on PATH.

7. **Read, validate, and merge the lens responses.**
   - **Per response:** read the summary's per-lens entries. For
     `status: ok`, read that lens's `pass-$N.<lensid>.response.json`
     (schema-validated by `--output-schema`; the runner has already applied
     belt-and-suspenders **patch-marker rejection** in code — `*** Begin
     Patch`, `--- a/` or `+++ b/`, `@@ -` followed by digits, `<<<<<<<` or
     `=======` or `>>>>>>>` — plus structural checks, both fixture-pinned).
   - **Rejected response:** `status: rejected` means that lens's response
     violated the reviewer contract. Report the actual cause from the
     summary's `reject_reasons` — patch-marker rejection ("Codex response
     contains patch-shaped output, which violates the reviewer contract") vs
     structural failure — then abort: "Aborting. Inspect the offending
     `pass-$N.<lensid>.response.json`." Do not proceed.
   - **Lens failure:** a lens with `status: failed` (codex crashed or
     returned nothing — exit code + stderr tail are in the summary) is
     **retried once**, standalone: `bin/run-lens --plan … --lens <id>
     [--note …]` (exit 0 = valid, 2 = rejected, 1 = error; its artifacts
     land in the isolated `debug/` namespace, never `pass-N.*`). A
     successful retry's response merges normally — note the debug response
     path in the HISTORICAL block. If the retry also fails, record the lens
     as `FAILED` orchestration metadata — **not** a verdict (the reviewer
     schema is untouched).
   - **Merge (the editor, semantic judgment — not a mechanical key):** collapse
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
   - **Open-question freeze tracking.** For each existing Q-numbered question
     that isn't already frozen or marked keep-active, compare this pass's
     merged answer to the answer counted at the most recently *counted*
     pass (below). Feed the result to the freeze decision made at fold
     time (step 8). Counting semantics — read carefully, since the
     defaults all point toward *not* freezing:
     - **"Identical" is the editor's semantic-equivalence judgment** — same
       resolution, no new rationale, no new conditions — the same judgment
       already applied to merging findings above. Byte equality is too
       strict (lenses rephrase); **when in doubt, the answers are not
       identical and the streak resets** — the conservative direction is
       not-freezing.
     - **A pass counts toward the freeze threshold (N=3) only when the
       full selected lens set completed and every lens's answer is
       equivalent to the prior counted pass.** A pass with a `FAILED` lens
       neither counts nor resets the streak — mirroring the stall
       guardrail's own treatment of `FAILED` passes (step 10). A differing
       answer resets the streak, with that pass starting a new one.
   - **Route `new_questions` by `settled_by`.** Each carries a class saying
     who can settle it. Dedupe across lenses first (two lenses often ask the
     same thing); on a class conflict for the same question, take the **most
     escalating** label (`needs_human` > `needs_lookup` >
     `resolvable_in_fold`) — the cautious label is the safe one. Then:
     - **`resolvable_in_fold`** — answer it now by **reading the plan and the
       repository**. The lens saw only its required sections; you have
       everything on disk. *Reading any file in the repo is this class, not
       `needs_lookup`.* Record the answer in the HISTORICAL block.
     - **`needs_lookup`** — the fact is **outside the repository**: it needs a
       network or API call, or executing something (a benchmark, a test run, a
       command whose output isn't already on disk). Perform it and answer. If
       it fails or isn't available, **reclassify to `needs_human`** and
       escalate rather than guessing.
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

8. **Fold merged findings + append ONE HISTORICAL block.** The editor is the sole
   writer.

   **Fold-time hygiene checklist — apply to every finding before writing its
   disposition.** Deliberately two items, not ten — a long checklist gets
   skimmed:
   1. **Claims-vs-behavior sweep (shared with `iterate-review`).** Did every
      description of the changed behavior change with it — test name,
      docstring, log line, comment (and, plan-side, the plan prose that
      describes the mechanism)? A correct fix that leaves its own
      description lying seeds the next pass's finding, and no passing test
      could have caught it.
   2. **Invariant walk (`iterate-plan`-only** — a rule restated in code
      comments or docs already falls under item 1's sweep, so code review
      needs no separate walk). If this fold states or changes a rule that
      other sections restate — an id format, a lifecycle, an accounting
      rule — does the rule now read correctly in **every** section that
      restates it?

   **Open-question freeze — the write action.** When step 7's tracking puts
   a question's streak at N=3 consecutive counted passes, mark it frozen in
   the plan's `## Open questions` section: append an inline annotation
   naming the freezing pass and the reopen rule, e.g. `— FROZEN at pass 7
   (answered identically ×3; reopens on any edit touching this question or
   new evidence)`. Frozen questions **stay visible** in the plan — freezing
   is never deletion. Note the freeze in this pass's HISTORICAL block too.
   `reviewer-prompt.md` instructs lenses not to re-answer a frozen question
   absent genuinely new evidence; a lens that *does* have new evidence
   answers anyway, and that answer reopens the question.

   **Reopening.** Any plan edit touching the frozen question's subject
   matter reopens it — editor judgment at fold time, noted in the
   HISTORICAL block — as does a lens answering with genuinely new evidence,
   as does the human. Freezing never resolves a question: `needs_human`
   escalation (step 7) and the final human answer at Converge are
   untouched; freezing only stops the loop paying full lens-input cost for
   the 5th–12th identical restatement of an answer already settled.

   **The human overrides all of it, in both directions.** At any
   checkpoint (step 10) Kyle can freeze a question early, mark one
   **keep-active** (permanently exempt from freeze tracking), or unfreeze
   one already frozen — record the action in the HISTORICAL block, noting
   explicitly that it was human-directed rather than the editor's own
   streak-based judgment.

   **Worked example.** Q4 asks whether a timeout should be configurable
   per-environment. Passes 4, 5, and 6 each return the identical answer
   from both lenses, no new rationale — the streak reaches N=3 at pass 6,
   and the editor annotates `— FROZEN at pass 6 (answered identically ×3;
   reopens on any edit touching this question or new evidence)`. **Pass
   7:** per `reviewer-prompt.md`'s instruction, neither lens re-answers
   Q4 — nothing new to say, so nothing is filed. **Pass 8:** the architect
   lens is `FAILED` (retried once, still failed) while checking on a
   separate, still-live Q5 — that pass neither counts toward nor resets
   Q5's streak, `FAILED` or not. **Pass 9:** the editor's own fold, made
   for an unrelated finding, rewrites the paragraph Q4's answer actually
   depends on — that edit reopens Q4 (noted in pass 9's HISTORICAL block),
   and pass 10's lenses answer it fresh. Separately, at the pass 5
   checkpoint Kyle decides Q2 should stay live regardless of how many
   times it's answered the same way; the editor records `— KEEP-ACTIVE
   (human-directed, pass 5 checkpoint)` next to it, exempting it from
   freeze tracking from that point on.

   Fold `plan_corrections` mechanically; incorporate HIGH/MEDIUM
   findings (skip/dispute only with explicit reasoning); LOW is informational.
   Append a single HISTORICAL section for the whole pass, each finding tagged
   with its originating **lens id(s)** and fold disposition:

   ```markdown
   ## Codex review pass N — answers (YYYY-MM-DD) [HISTORICAL]

   ### Verdict
   APPROVE / REVISE / BLOCK   (worst-of; note any FAILED lenses)

   ### Findings
   1. **<title>** — <severity> · lens: <architect|product-manager|both>: <description>
      → Editor: <incorporated|skipped|disputed> — <reasoning> [introduced_by_pass: <N | null>]
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

   **`introduced_by_pass` — fold-provenance, per finding.** `N` when the
   defect this finding describes was created by an edit a previous pass's
   fold made; `null` when the defect pre-existed this review or arrived
   with the plan's original draft. This is the same judgment call every
   long loop's pass log already recorded in prose — make it at fold time,
   while the causal chain from "what did pass N-1 change" to "what does
   this finding complain about" is freshest. When genuinely uncertain,
   record `null` with a one-line note rather than guessing `N` — under-
   claiming keeps the data conservative. This is data collection only
   (the issue #6 decision it feeds): no guardrail, checkpoint, or budget
   in this skill consults `introduced_by_pass`, and none may until that
   issue is resolved.

9. **Recompute `plan_content_hash` post-fold.** Stash for the next pass's
   manual-edit detection.

10. **Checkpoint — Continue / Converge / Abort / (L)oop.** Present the
    aggregate verdict + a recommendation:
    - Recommend **Converge** when aggregate `verdict == APPROVE`, no lens is
      `FAILED`, and the editor has no further changes pending. One APPROVE +
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
      loop: the editor resolves them and continues. If a `needs_lookup` resolution
      *fails*, it becomes `needs_human` and then halts. This is the whole point
      of the classification — an unattended loop shouldn't stop for a question
      it could have answered, and must never continue past one only Kyle can.

    On **Continue** (manual or loop-auto): increment pass count, loop to step 5.
    On **Converge**: enter the Sonnet-handoff sub-flow (Phase 3, below).
    On **Abort**: write the state file with final values (`pass_count`,
    `last_verdict`, `plan_abs_path`, `plan_content_hash`, `started_at`,
    `last_pass_at`, `convergence.handoff_decision="aborted"`), **plus the
    `summary_schema`/`scope_class`/`passes` fields defined in step 15 —
    Abort produces that array exactly as Converge does**, covering every
    pass that completed before the abort, exit.

## On Converge — Sonnet-handoff sub-flow (Phase 3)

11. **Assess plan complexity, recommend handoff vs stay.** The editor
    surfaces a one-paragraph recommendation framed by these signals:
    - **Handoff to Sonnet** when the plan is well-specified, execution
      is largely mechanical, and a fresh session helps (lower context
      cost during execution, cleaner separation of design vs build).
      Long plans (~500+ lines) touching many files usually fit here.
    - **Stay with the editor** when the plan is short, execution overlaps
      with ongoing design judgment, or there's load-bearing in-session
      context that's expensive to re-establish. Plans drafted and
      executed in a single sitting often fit here.

12. **Prompt user: (H)andoff to Sonnet / (S)tay with the editor / (A)bort.**
    Always surface all three. Never auto-pick — the editor's recommendation
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
    `convergence.handoff_path` if applicable).

    **Per-pass summary (`summary_schema: 1`) — the data half of issue #6.**
    At Converge and Abort alike, the state file additionally carries:
    - `summary_schema: 1` — versions this row shape so a future change
      (e.g. Phase 1's proportionality port) populates existing keys rather
      than reshaping the row.
    - `scope_class: null` — iterate-plan has no diff to classify. The
      field exists in both skills' schemas (iterate-review's is
      `production`/`non-production`, per its own §3) so the cross-skill
      `jq` recipe never has to branch on which skill produced the file.
    - `passes` — an array with one row per pass that actually ran (a
      `FAILED`-lens pass still gets a row). Each row: `pass` (int),
      `verdict` (string), `high_medium_count` (int — that pass's merged
      HIGH+MEDIUM findings), `findings_total` (int — all severities),
      `fold_caused_count` (int — findings in that pass with a non-null
      `introduced_by_pass`), and `dispositions` (object) — a **fixed key
      set present in both skills' rows**: `incorporated`, `skipped`,
      `disputed`, `accepted-risk`, `register-match`, every key always an
      int, zero when unused. iterate-plan has no `accepted-risk` or
      `register-match` disposition until Phase 1 ships — those two keys
      carry `0` until then, so Phase 1 populates keys that already exist
      instead of reshaping the row.

      Rows are **derived from the plan's own HISTORICAL blocks** by a
      deterministic, idempotent procedure (re-deriving the same blocks
      always produces the same rows) — never hand-authored, and the plan
      file remains the durable authority the rows are only a summary of.
      **Abort produces the array exactly as Converge does**, covering
      every pass that completed before the abort. One stated limitation:
      a run interrupted before reaching Converge or Abort has no state-
      file row at all — it's represented only by its HISTORICAL blocks in
      the plan file, which is acceptable for instrumentation and said
      here rather than discovered later.

    See `state/example.json` (Converge path) and `state/example-aborted.json`
    (Abort path) for worked examples, and the shared
    `tools/provenance-recipe.jq` recipe (Pointers) for the documented `jq`
    query that reproduces per-pass tallies from these rows across both
    skills' state files. **No guardrail, checkpoint, or budget in this
    skill consults `introduced_by_pass`, `fold_caused_count`, or any field
    defined in this paragraph** — this ships data collection only; the
    stop-condition decision stays with [issue #6](https://github.com/kaileconsulting/trinity-skills/issues/6).

    **On Converge (Handoff or Stay), additionally prune the scope's state
    directory** — the plan's HISTORICAL sections are the durable audit
    record; the per-pass inputs, responses, and summaries under
    `state/<scope-hash>/` are intermediates:

    ```
    ~/.claude/skills/iterate-plan/bin/prune-state --scope <scope-hash> --yes
    ```

    Skip the prune when the invocation carried `--keep-state` or the user
    asks to keep the state at the Converge checkpoint (audit/debug trail —
    e.g. investigating a bad merge); say so in the wrap-up either way.
    Convergence is *your* determination confirmed by the human —
    `prune-state` never infers it. A completed `run-pass` leaves no lock, so
    this prune is never blocked; if it reports a refusal anyway, surface it
    rather than retrying.

    **On Abort, leave the state directory in place** — abandoned-run state
    is cleaned up later, explicitly, with `prune-state --older-than <days>
    --yes` (dry-run without `--yes`; it never touches a scope holding a live
    run lock, the plan, or the `state/<scope-hash>.json` files).

    Then exit.

State file shape: see `state/example.json`. The per-scope state directory
(`state/<scope-hash>/`, same sha1-of-plan-path key as the state file) is the
runner's: composed `pass-N.<lensid>.input.txt`, raw
`pass-N.<lensid>.response.json`, the `pass-N.summary.json` commit point (a
pass exists iff its summary exists), `run.lock` (+ transient
`run.lock.reclaim`) for exclusive scope ownership, and a `debug/` namespace
for standalone `run-lens` output. Pruned at Converge (step 15) unless
`--keep-state`; swept later by `prune-state --older-than` for abandoned runs.

## Pointers

- `reviewer-prompt.md` — canonical reviewer prompt sent to Codex.
- `reviewer-output.schema.json` — JSON Schema enforced by `--output-schema`.
- `lenses/` — persona lens records + the selection rules (`lenses/README.md`).
- `state/<plan-path-hash>.json` — per-plan iteration state (written at
  convergence/abort only; never touched by `prune-state`).
- `state/example.json` / `state/example-aborted.json` — illustrative state
  files showing the schema, Converge and Abort paths respectively.
- `../tools/provenance-recipe.jq` — the `jq` recipe (shared with
  `iterate-review`) that reproduces per-pass tallies — pass counts,
  fold-caused share, disposition mix — from the `passes` rows above;
  fixture-pinned by `tools/check-provenance-recipe.py`.
- `state/<scope-hash>/` — the runner's per-scope state directory (see the
  State-file-shape paragraph above); pruned at Converge unless `--keep-state`.
- `bin/` — the runner scripts steps 5–7 invoke: `run-pass` (selection +
  composition + concurrent fan-out + summary), `run-lens` (one lens,
  standalone/debug), `prune-state` (state-dir cleanup: `--scope` at Converge,
  `--older-than` for abandoned runs, `--force-unlock` for ambiguous-lock
  recovery; dry-run unless `--yes`), plus the modules they share
  (`plan_runner.py`, and `runner_shared.py` — a byte-identical copy of
  iterate-review's, hash-checked by `tools/check-parity.py`). Runner behavior
  is fixture-pinned by `tools/check-plan-runners.py`.
- `examples/` — fixtures (see `examples/README.md`). `pass-4-response.json` is a
  real pre-Axis-2 Codex response; `examples/merge/` holds multi-lens merge
  goldens; `examples/composition/` pins byte-deterministic input assembly.
  Validate with `tools/check-examples.py`.

## Hard rules

- Codex never edits the plan file. Enforced by `-s read-only -a never`
  sandbox + reviewer prompt + runner-side patch-marker rejection.
- **The runner composes and invokes; it never folds, never writes the plan,
  never decides.** `bin/run-pass` / `bin/run-lens` own lens selection, input
  composition, Codex invocation, and response validation. Every behavioral
  rule — semantic merge, worst-of verdict, `FAILED` handling, dispositions,
  HISTORICAL blocks, checkpoints, loop control — stays with the model.
- Skill never silently iterates. After every pass, prompt user:
  Continue / Converge / Abort. **Loop mode is the one opt-in exception**
  (via `--loop` or the `(L)oop from here` choice): it auto-continues REVISE
  passes without prompting, but it is *not silent* — every pass appends its
  HISTORICAL block, and the loop always halts and returns to the human at
  APPROVE or any guardrail (step 10). Loop mode automates `Continue` only.
- Skill never decides convergence. Suggests when verdict=APPROVE +
  the editor reports no further changes; human always confirms. **Loop mode never
  auto-converges** — it stops at APPROVE and presents the Converge decision.
- Fan-out is one Codex call per selected lens; the editor merges (semantic dedupe,
  worst-of verdict, lens attribution). A selected lens that fails after one
  retry is `FAILED` metadata that forces at-least-REVISE (BLOCK preserved) and blocks Converge. Exactly
  one HISTORICAL block and one checkpoint per pass, regardless of lens count.
- Sonnet-handoff at convergence is fully user-driven: skill writes
  the handoff prompt to disk, user copies into a fresh session and
  performs the `/clear` + model swap themselves.
- **`introduced_by_pass` is data collection only.** No guardrail,
  checkpoint, or budget in this skill consults `introduced_by_pass`,
  `fold_caused_count`, or any field of the per-pass summary schema —
  Phase 0 of Trinity v2.4 ships instrumentation, not a stop condition;
  that decision stays with issue #6 until the data warrants revisiting it.
