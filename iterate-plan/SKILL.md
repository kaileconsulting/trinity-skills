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
- `--ignore-register` — compose with an explicitly empty accepted-risks
  register, bypassing HEAD resolution entirely (step 5). Never automatic:
  the editor passes this only after the human selects *proceed with no
  register* at the malformed/unavailable-register-source decision card
  (step 8) — without it, a malformed or unavailable register always halts
  the pass before any lens runs.

## Setup (once per skill invocation)

1. Read the plan file at the user's specified path.
2. Soft-validate plan format (warns if Status / TL;DR / Sequencing /
   Open Questions sections are missing; allows `--no-validate`).
3. Compute `plan_content_hash` (sha256 of file contents) and remember it
   in-session — used for manual-edit detection between passes.
4. Load state file at `~/.claude/skills/iterate-plan/state/<sha1-of-abs-path>.json`
   if present. If absent, this is pass 1; initialize an empty in-session
   state record. (State is *written* only at convergence/abort — see step 9.)

   **Then, before any fan-out, check the plan for an unfinished pass** —
   the state file is written only at exit, so it can never show one.
   If the plan's last `## Codex review pass N` block is still tagged `[IN
   PROGRESS]` (step 8), pass N was interrupted. **Abandon it and rerun;
   never resume it.** Retag the block `[ABORTED]` with a one-line reason
   beneath its header ("interrupted; superseded by pass N+1"), then start
   pass N+1 normally. An aborted pass is **not a completed pass**: it is
   skipped for streak and stall accounting exactly like a `FAILED`-lens
   pass, contributes no state-summary row, and everything it recorded —
   dispositions, `AR-<n>` proposals, card answers — is void. What it
   *did* to the plan stays: the plan is the reviewed artifact, so pass
   N+1 reviews whatever the interrupted folds left in it, and any finding
   they didn't fix is simply re-reported. A card that was pending is not
   bypassed by this: it is voided with its pass, and it fires again from
   pass N+1's own count if its findings are re-reported (the committed
   streak is unchanged, and the aborted pass is skipped). The cost is
   deliberate and small: one extra Codex pass per interruption, and an
   answer given just before the crash is asked again. (This replaced a
   resume procedure whose every fold opened a smaller hole — the
   simplification card fired on it during 2.5.0's own review.)

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
   never skipped, never handed silence) + the optional staged note +
   **the accepted-risks register, per the HEAD-sourced flow below** + the
   full plan under `=== PLAN ===`, assembled **byte-deterministically**
   (goldens in `examples/composition/`; composed inputs land in the state
   dir as `pass-N.<lensid>.input.txt`). Prior passes need no separate block:
   the plan's own HISTORICAL sections arrive with the plan.

   **Register composition — HEAD-sourced, never the working tree (Q5).**
   `run-pass` reads `## Accepted risks` from `git show HEAD:docs/risk-posture.md`
   at the plan's repo root and, when it resolves, appends an
   `=== ACCEPTED RISKS ===` block to every lens's composed input, immediately
   before `=== PLAN ===`. Composition and the register-match provenance gate
   (step 7) **share this one trusted source** — reading the working tree
   instead would let a dirty, uncommitted register edit reach a lens's input
   the same pass a gate exists to reject it, and would let the gate compare a
   working-tree entry against a digest derived from that same entry. This is
   why `create-plan`'s seeding guidance (Step 3) ends with "commit the
   scaffolded plan and its register entry together before invoking
   `iterate-plan`" — a freshly seeded, uncommitted entry is exactly the
   dirty-worktree case below, invisible to every lens until it lands at HEAD.

   Register loading resolves to one of four states, never a silent
   fallback between them:
   - **loaded** — the blob exists at HEAD and parses; its `## Accepted
     risks` section text composes into the block, verbatim.
   - **confirmed-absent** — `docs/risk-posture.md` does not exist at HEAD
     (a real repo state, not an error). No block is composed — the input is
     **byte-identical** to what it would be without this feature at all
     (the no-register golden). A file that exists but carries no `##
     Accepted risks` section composes identically to this case.
   - **malformed** — the blob exists at HEAD but the register itself is
     broken (duplicate `RR-<id>` bullets — a register-integrity problem
     independent of anything else in the file).
   - **operational failure** — anything else that isn't a confirmed
     absence: the repo root doesn't resolve, there is no `HEAD` yet (e.g. a
     freshly-initialized repo with no commits), or `git show` fails for a
     reason other than the path not existing at that revision.

   **malformed and operational-failure both halt before any fan-out** —
   `run-pass`/`run-lens` abort (non-zero exit, no summary published, no
   lens ever invoked, no pass number consumed) with the failing state and
   its reason on stderr, distinguished as `register malformed: ...` vs
   `register unavailable: ...` so the card below can name the actual
   problem rather than a generic one. **Never fall back to composing
   without the register *silently* — but an explicit human choice to do
   so, made at the card, is the one legitimate way past this halt, and it
   needs its own mechanism because register resolution lives in the
   runner, not the editor** (unlike `iterate-review`'s editor-composed
   posture, which the editor can simply choose not to compose): the runner
   gains an `--ignore-register` flag on both `run-pass` and `run-lens`
   that short-circuits `resolve_register()` entirely and composes with an
   explicitly empty register, regardless of the underlying git state — the
   editor passes it only after the human selects *proceed with no
   register* at the malformed/unavailable-register-source card (step 8),
   never on its own initiative. Without that flag, there is no other path
   past a malformed or unavailable register — the default is always to
   halt, not to guess.

   **This card is the one case where a HISTORICAL block opens before any
   lens has run** (the plan-side analog of `iterate-review`'s own
   pre-fan-out exception for its malformed-posture card, scoped down to
   fit `iterate-plan`'s one-block-per-pass model): the instant `run-pass`
   reports this abort, the editor opens this pass's block (tagged `[IN
   PROGRESS]`, like every open block — step 8) containing *only* the card — no `### Findings`, `### Verdict`, or
   `### Lens run summary`, since none exist yet — with `chosen: (pending)`,
   per the usual two-phase persistence discipline (step 8), so the
   decision is on record. If the session is interrupted before the
   human's answer, Setup step 4 abandons the pass, and the fresh pass's
   `run-pass` meets the same register failure and presents the card
   again. Once answered: *fix the source now* →
   the editor does not retry until the source is actually fixed, then
   re-invokes `run-pass` with the **same** pass number (nothing was
   consumed by the aborted attempt, so this *is* that pass's real
   fan-out) and the pass's remaining sections fill in normally; *proceed
   with no register* → re-invoke with `--ignore-register` under the same
   pass number; *abort* → the plan's iteration ends per the abort path,
   and this pass's block — the card alone — is its final, sealed content;
   *discuss* → paused.

6. **Fan out — one `run-pass` invocation.** The runner makes **one Codex
   call per selected lens, concurrently** (all lens futures awaited; one
   lens failing never cancels its siblings), each writing
   `$STATE_DIR/pass-$N.<lensid>.response.json` with the exact sandbox flags
   (`codex -a never exec -C <plan-dir> -m gpt-5.6-sol -s read-only --skip-git-repo-check
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
   - **Validate `register_ref` on findings — three gates, in order, all must
     pass** (ported from `iterate-review` step 11, adapted for plan review's
     lack of a diff). For each finding carrying a `register_ref`, look it up
     in `docs/risk-posture.md`'s `## Accepted risks` section **at HEAD** —
     the same blob step 5 composed from. Unknown id, malformed id, or a
     missing register file → treat the finding as untagged (drop the ref;
     note in the HISTORICAL block, e.g. "register_ref RR-x not found,
     treated as untagged") and disposition it normally.
     1. **HEAD-provenance gate.** There is no diff and no base revision for
        a plan, so HEAD itself is the trust boundary: the entry must
        already exist, with matching digest (recipe below), in
        `docs/risk-posture.md` **at HEAD**. A working-tree-only or
        HEAD-divergent entry fails this gate regardless of how well the
        behavior otherwise fits — including a register-only file itself
        being newly introduced but not yet committed. This is the plan-side
        analog of the provenance gate that makes `create-plan`'s "commit the
        scaffolded plan and its register entry together" guidance load-bearing
        rather than a suggestion.
     2. **Behavior gate.** Confirm the finding's behavior genuinely falls
        within the entry's recorded behavior/bound/recovery — not merely the
        same named area (per `reviewer-prompt.md`'s ON RISK POSTURE
        guidance; a finding presenting evidence the entry's bound or
        recovery is false is never a match, regardless of what
        `register_ref` the lens set).
     3. **Trust-boundary gate.** A register-match must never apply to plan
        content named as a trust boundary by the plan's own `PF-shipbar`.
        Check the finding against **both** this pass's resulting
        `PF-shipbar` text **and** `PF-shipbar` as it read at the *start* of
        this pass (before this pass's own fold) — the plan-text analog of
        iterate-review's current-vs-base-revision dual-check, since a plan's
        posture text mutates in place rather than living in a diff: a
        same-pass fold that narrows or removes `PF-shipbar`'s coverage must
        not retroactively legalize a register-match for the defect that
        narrowing conveniently exempts. If neither version yields a
        `PF-shipbar` field at all, there is nothing to exclude against and
        the gate doesn't block matching.

     If all three gates pass: compute a canonical digest of the entry's
     complete logical bullet using the **same recipe `iterate-review` step
     11 defines** — starting at the line matching `- **RR-<id>** — `,
     include every subsequent line up to (but not including) the next
     `- **RR-` bullet or the end of the `## Accepted risks` section;
     normalize by stripping trailing whitespace per line, join with `\n`;
     digest = sha256 hex of the normalized UTF-8 text. Record the
     disposition as `register-match (RR-<n>, entry-digest <hash>)` — no
     plan edit, no fresh human confirmation.

     **Before trusting a `register-match` carried from a prior pass's
     HISTORICAL block, re-run all three gates against the current pass's
     context** — provenance (recompute the digest, reconfirm the entry
     still exists unchanged at the current HEAD), behavior (re-read the
     carried finding against the entry's current recorded fit), and
     trust-boundary (reapply gate 3 against the current pass's posture).
     Any one gate failing invalidates the match: the finding reverts to
     needing a fresh disposition this pass and blocks Converge until it
     receives one, exactly like a newly-filed finding.
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
     - **The streak counts consecutive *counted passes*, not pairwise
       comparisons — the first answered pass after any reset trivially
       becomes counted-pass #1.** It has nothing to differ from yet, so
       it can't fail the equivalence check; it simply establishes the
       baseline every subsequent pass is compared against. Concretely:
       pass 4 answers a question for the first time (streak = 1); pass 5
       answers equivalently (streak = 2); pass 6 answers equivalently
       again (streak = 3 = N) — **frozen at pass 6**, exactly as the
       worked example below states. Reading this as "N consecutive
       *matches*," which would require N+1 answered passes to reach N=3
       (needing a 4th pass here), is the wrong reading — `tools/freeze_tracker.py`
       (fixture-pinned by `tools/check-question-freeze.py`) is the
       normative reference if this prose and an implementation ever
       seem to disagree.
     - **A pass counts toward the freeze threshold (N=3) only when the
       full selected lens set completed and this pass's *answer to the
       question* — after step 7's existing cross-lane merge (agree →
       one answer; disagree → escalated, never silently averaged) —
       is equivalent to the prior counted pass's answer.** The
       comparison unit is the merged, per-pass answer, not each lens's
       individual phrasing: by the time freeze-counting ever sees a
       pass, step 7 has already reconciled the lenses into one answer
       or an escalated disagreement. A lens rephrasing its reasoning
       between passes doesn't itself break the streak if the merged
       answer stays the same — that's exactly the semantic-equivalence
       judgment the "Identical" bullet above already describes, applied
       at the same unit merging already produces. **An escalated
       cross-lane disagreement is never a neutral skip — it resets the
       streak to no baseline at all**, the same as any other answer
       that isn't equivalent to the prior one, because there is no
       settled answer this pass to compare against or to count from;
       treating it as a skip (like a `FAILED` lens) would let answers on
       either side of a genuinely unresolved disagreement form one
       continuous streak and freeze a question that was never actually
       settled. Only a `FAILED` lens gets the neutral-skip treatment —
       a `FAILED` lens means codex didn't answer at all, which is
       nothing to disagree *about*; a disagreement means every lens
       answered and they conflicted, which is the opposite signal. A
       pass with a `FAILED` lens neither counts nor resets the streak
       — mirroring the stall guardrail's own treatment of `FAILED`
       passes (step 10). **The two reset cases land differently, and
       it matters which pass becomes the new baseline:**
       - **An ordinary differing (but settled) answer** resets the
         streak, and — because it *is* a real, settled answer — that
         same pass immediately becomes the new baseline, counted-pass
         #1 of the new streak (no pass is "wasted" re-establishing it).
       - **A disagreement** resets to *no* baseline at all, because
         this pass produced no settled answer to start counting from;
         the next pass that *does* settle an answer becomes counted-pass
         #1, one pass later than the differing-answer case above.
       Conflating these — treating a disagreement's reset the same as
       an ordinary differing answer's — would delay freezing by one
       pass after every ordinary answer change, which is wrong: only
       the disagreement case has that one-pass delay, because only it
       lacks a settled answer to serve as an immediate baseline.
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
   2. **Invariant walk** (`iterate-plan`-only — a rule restated in code
      comments or docs already falls under item 1's sweep, so code review
      needs no separate walk). If this fold states or changes a rule that
      other sections restate — an id format, a lifecycle, an accounting
      rule — does the rule now read correctly in **every** section that
      restates it?

   **Before folding any finding, check whether it would materially alter
   approved scope — a plan-shaping fold (Q3, ported from `iterate-review`'s
   design-shaped-fold escalation, adapted to what "shaped" means for a
   plan instead of code).** If it does, don't fold *that finding* yet —
   pause **at that finding**, present it as a decision card (step 8's
   shared contract below, with a cheaper alternative sketched when one
   exists), and get the human's answer before folding it. This pause is
   scoped to that one finding, not the whole pass: once answered, folding
   continues with the pass's remaining findings — no new Codex call
   needed, they were already returned in the current lens responses.

   **"Plan-shaping" has an operational boundary** — these are the signals:
   - adding or removing a phase
   - changing `## Goals` or `## Non-goals`
   - moving acceptance coverage between phases

   **Non-plan-shaping — fold normally, no escalation:** clarifications,
   wording fixes, and corrections of a mapping the plan already approved
   (a phase's deliverables, an acceptance bullet's wording, a risk's
   description) — ordinary editorial work that doesn't change what was
   approved. On a genuinely ambiguous case, use the signals above as a
   checklist; if none clearly apply and you're still unsure, err toward
   escalating — the same asymmetry as `needs_human`: an unnecessary card
   costs one decision, a missed one commits to a structural change nobody
   approved. This is precisely the churn class the 2026-08-21 retro found
   in passes 9–12 of the runtime-pipeline plan (acceptance-coverage
   redistribution and vocabulary hygiene folded silently, four passes
   running) — the escalation exists so that class of fold gets a human's
   eyes on it, once, before it happens rather than being discovered after.

   **Classification happens before the fold, and the pending card is
   persisted before any structural mutation** — an escalation that fires
   after the plan is already changed would defeat its purpose. Outcome
   mapping (shared with the other five card types, step 8 below): *adopt
   the mechanism* → the fold proceeds this pass; *cheaper alternative*
   (when one exists) → the alternative is folded instead, recorded as
   `incorporated (via alternative)`, and re-reviewed next pass; *accept
   the risk* → routes to the `accepted-risk` lifecycle below — **excluded
   from the card entirely** when the finding concerns plan content named
   as a trust boundary by `PF-shipbar` (checked both current-pass and
   start-of-pass, same dual-check as the register-match trust-boundary
   gate in step 7, so a same-pass posture edit can't create the exception
   either); *discuss* → loop stays paused, no fold this pass.

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
   as does the human. **Reopening removes the inline `— FROZEN...`
   annotation from the question's line in `## Open questions`** — the
   question returns to its plain, unannotated form, eligible for lenses
   to answer again on the next pass; the freeze *event* and the reopen
   *event* both stay on the record regardless, in the HISTORICAL blocks
   of the passes that made them, which is the durable audit trail —
   the inline annotation is a live-state marker, not history, so it
   doesn't persist past the state it describes. (Re-freezing later, if
   the streak reaches N again, writes a fresh annotation naming the new
   freezing pass.) Freezing never resolves a question: `needs_human`
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

   This worked example isn't only prose: `tools/freeze_tracker.py` is a
   reference implementation of the counting algorithm above (editor-side
   judgment, not runner code), boundary-case-tested — including this exact
   pass-4/5/6 sequence — by `tools/check-question-freeze.py`. **Scope of
   that coverage, stated precisely rather than overclaimed:** it pins the
   streak-counting state machine — when a pass counts, resets, or reaches
   N — using an opaque token standing in for "the editor's merged-answer
   equivalence judgment" (that judgment itself, and the mechanics of
   writing/removing the inline annotation in the plan file, are editor
   actions verified by inspection at review time, the same standard this
   skill already holds every other fold-time write to — HISTORICAL
   blocks, dispositions, plan_corrections — to; none of those have
   automated plan-mutation tests either, and freeze annotations aren't a
   special case).

   **New disposition: `accepted-risk`** (ported from `iterate-review`,
   nearly verbatim — the port this section exists to make) —
   "real finding, disproportionate to this plan's posture; not fixing."
   Requires a written rationale that references the posture via the
   dependency descriptor below — never a bare "not worth it."

   **Identity and lifecycle.** Each proposal gets a stable id, `AR-<n>` —
   numbered sequentially across the whole plan (read existing `AR-`
   mentions in the plan's HISTORICAL blocks to find the next number; **the
   plan file is the sole id allocator**, since the plan is `iterate-plan`'s
   pass log — no concurrent-allocation problem arises within one plan).
   Matching is by id, never by prose.
   - `proposed` (editor, at fold time) → `confirmed` or `rejected` (human
     only, at a checkpoint).
   - `rejected` → **`reopened`** — an explicitly unresolved state that
     blocks the Converge recommendation exactly as `proposed` does, and
     immediately restores the finding to the open ledgers (re-enters the
     non-convergence count, fails the HIGH guardrail) the moment the
     rejection is recorded.
   - A `reopened` finding needs a subsequent disposition on a later pass:
     `incorporated` or `disputed` (both terminal), or a fresh
     `accepted-risk` proposal under a **new** `AR-<n>` id — itself resolved
     only through its own proposed → confirmed lifecycle; prior
     confirmation never carries over. Pick the terminal disposition for
     what actually happened, not for convenience: `disputed` means the
     finding was never valid — it does not mean "resolved some other way."
     If the underlying defect genuinely got fixed as a side effect of a
     *different* fold, that's `incorporated`, with a parenthetical naming
     what actually resolved it (e.g. `incorporated (superseded by finding
     4's mechanism)`).
   - A **materially changed** finding (different location, mechanism, or
     claimed bound) is always a new proposal under a new id, never a reuse
     of a prior one. "Bound" here means the *finding's own* claimed bound —
     never the posture text a rationale rests on. The two senses are
     separate triggers with opposite outcomes: *the finding changed* → new
     `AR-<n>` id; *the posture changed* → same `AR-<n>` id, returned to
     `proposed` (below). Reading a posture edit as "the finding's bound
     changed" mints a new id, discarding confirmation history for a
     finding that never actually changed — don't.

   **Posture-dependency descriptor — the confirmation's evidentiary basis.**
   Every confirmation persists (1) the list of posture *field ids* the
   rationale relies on (`PF-shipbar`, `RR-2026-08-06-seq-poison`, …) and
   (2) a canonical-content digest of exactly those fields as confirmed.
   Per-field content extraction reuses step 7's register-match recipe
   exactly (a `PF-` field: its full field text, read from the plan's own
   `## Risk posture` section; an `RR-` entry: its complete logical bullet,
   every wrapped continuation line, read from `docs/risk-posture.md` **at
   HEAD** — the same trusted source step 5 and step 7 already share).
   - **Descriptor names exactly one field**: digest = sha256 hex of that
     field's canonical content directly.
   - **Descriptor names two or more fields**: length-prefix every part —
     sort the descriptor's field ids lexicographically; for each `(id,
     content)` pair, UTF-8-encode both and emit `len(id_bytes)` + `:` +
     `id_bytes` + `len(content_bytes)` + `:` + `content_bytes` (decimal
     ASCII lengths, no separator ever scanned for); concatenate in sorted
     order; digest = sha256 hex of the concatenated bytes. (Identical
     recipe to `iterate-review` step 12 — the same netstring-framing
     rationale applies unchanged: a bare separator can appear inside a
     field's content with no defined escaping.)

   On any later pass, the descriptor re-selects the same fields **by id**
   from the current posture source (the plan's own `## Risk posture` for
   `PF-` fields; `docs/risk-posture.md` at HEAD for `RR-` entries) and
   recomputes the digest: a mismatch, or a field that no longer resolves,
   invalidates the confirmation and returns the item to `proposed` for
   fresh confirmation. Posture edits **outside** the descriptor's named
   fields never invalidate.

   **Invalidation always preserves the `AR-<n>` id.** What changed is the
   posture, not the finding, so there is no new proposal to mint: the same
   item returns to `proposed`, carrying its id and history, re-confirmed
   (or not) on its own merits against the new posture text. The new-id
   rule above fires only when the finding itself materially changes.

   **Converge predicate**: zero items in `proposed` or `reopened` state —
   wired into step 10's Converge recommendation exactly as the accounting
   table below states.

   **Pushback guidance.** The editor is expected to spend `disputed` and
   `accepted-risk` when warranted — this loop's findings are real, but not
   everything real is worth fixing here, and pretending otherwise is its
   own failure mode. Criteria (any one is sufficient): the finding
   contradicts the documented posture; the fix's cost clearly exceeds the
   defect's own bounded blast radius; the finding re-litigates a register
   entry without new evidence. **Anti-criteria (never push back for these
   reasons):** never on plan content named as a trust boundary in the ship
   bar (`accepted-risk` is unavailable there entirely — same exclusion as
   the plan-shaping-fold escalation above and the register-match
   trust-boundary gate); never to avoid a small, honest fix — proportionality
   argues against over-building, not against a fix that's cheap and
   correct. This anti-criteria pair is the one piece R6 (plan-review
   proportionality has a weaker case than code-review proportionality,
   since plans are cheaper to fix than code) most depends on: it's what
   keeps `accepted-risk` from becoming a way to skip fixes that were
   nearly free.

   **Accounting is defined per ledger, per state — one table, three
   consumers**, wired to `iterate-plan`'s own step-10 guardrails (the
   equivalent of `iterate-review`'s per-pass HIGH guardrail, non-convergence
   counter, and Converge predicate):

   | State | Fold-needs-human-judgment guardrail (step 10) | Non-convergence count (step 10) | Converge recommendation (step 10) |
   |---|---|---|---|
   | `proposed` (incl. deferred) | satisfied — loop may continue | excluded (dispositioned, not open) | **blocks** |
   | `confirmed` | satisfied | excluded | clear |
   | `reopened` | **not satisfied** — fresh disposition required | **re-included** | **blocks** |
   | register-match, all step-7 gates valid | satisfied | excluded | clear |
   | register-match, any gate broken/missing on recheck | treated as `reopened` | treated as `reopened` | **blocks** |

   Accepting a risk therefore can't read as a stall (`proposed`/`confirmed`
   items leave the non-convergence count) while remaining impossible to
   converge past unconfirmed. **`incorporated (by simplification)`** — a
   finding a simplification card's chosen operation resolves, per that
   operation's per-finding accounting — and **`incorporated (moved to
   <stub path>)`** — a finding carried to a new plan by the card's *split
   the plan* scope transfer — are each an `incorporated` in every ledger
   (and in the state summary's `incorporated` key).

   **Worked example — the accounting table state by state**, the same
   inspection standard the freeze tracker's worked example above and every
   other fold-time editor write in this skill already holds to (none of
   these have automated plan-mutation tests, and this isn't a special
   case): a pass proposes `AR-1` (dependency descriptor: `PF-shipbar`) for
   a HIGH finding — the guardrail is satisfied so the loop continues past
   that finding, `AR-1` is excluded from the non-convergence count, and
   Converge is blocked. At the checkpoint the human confirms it: `AR-1`
   moves to `confirmed`, clearing the Converge block. A later pass proposes
   `AR-2`; the human rejects it: `AR-2` becomes `reopened`, immediately
   re-entering the non-convergence count and failing the guardrail again —
   the same finding now needs a fresh disposition. The next pass
   dispositions the reopened `AR-2` as `incorporated` (a plan edit resolves
   it directly) — terminal, both ledgers clear. Separately, a fold later in
   the same plan narrows `PF-shipbar`'s wording that `AR-1`'s confirmation
   depended on: the descriptor's digest no longer matches, so `AR-1`
   reverts from `confirmed` to `proposed` — re-entering Converge-blocking
   status under its **same** id (the posture changed, not the finding, so
   §8's material-change rule doesn't apply) — and needs re-confirmation
   against the new posture text before Converge can succeed again.

   **Decision cards — the shared contract for every human-judgment moment**
   (ported from `iterate-review` step 12 verbatim; **six** total moments,
   as below — the plan-shaping-fold escalation above stands in for
   `iterate-review`'s design-shaped-fold escalation, and there is no
   plan-side equivalent of a mid-review posture-source malformed-*field*
   case, only the register). Whenever the loop hands back to the human with something
   needing judgment, it arrives in a fixed shape: (1) the editor's
   **recommendation**, with a one-line why; (2) **up to 3 genuine
   alternatives**, each with its trade-off; (3) an always-available
   **discuss** path. Selecting any option other than *discuss* resumes the
   loop deterministically per that card type's outcome mapping; *discuss*
   pauses into conversation, and when it concludes, the card is
   re-presented with the agreed direction as the new recommendation.

   **Cardinality is bound by the harness, both ends of the range.** The
   interactive structured-question mechanism accepts at most 4 explicit
   options — recommendation + alternatives together must never exceed 4
   (at most 3 alternatives when there's a recommendation). `discuss` is
   never a listed option — it's the harness's free-form response, so it
   never counts against the cap. "2–3" alternatives is a target, not a
   hard minimum: context-sensitive omission can reduce the listed
   alternatives to zero (recommendation + discuss is the floor and is
   *never* skipped, including in that degenerate case — an unpresented
   card would mean silently committing to a decision nobody approved,
   exactly what every one of these moments exists to prevent).

   **Persistence, uniformly across all six card types below: two
   phases**, written into the plan's *current pass* HISTORICAL block under
   a `### Decision cards` subsection (only present when a card was
   presented that pass):
   1. **Pending write, before presentation.** Append the card with
      `chosen: (pending)` — recommendation, alternatives, and the item id,
      no outcome. This records exactly what the human is being asked. If
      the session is interrupted before the answer, the pass is abandoned
      (Setup step 4) and the card is void with it; it is presented again
      only if its trigger recurs in the fresh pass.
   2. **Resolution write, once answered.** Update that same entry in
      place — replace `(pending)` with the actual `<option> (<one-line
      outcome>)`. Within the live pass, a card with a real `chosen:`
      value is settled and never re-presented.

   **The six named human-judgment moments and their outcome mappings**
   (plan-shaping-fold escalation specified above; malformed/unavailable
   register source specified in step 5; the simplification card specified
   after the component-streak rules below — all under this same shared
   contract, alongside the three below):
   - **Accepted-risk confirmation**: *confirm, this plan only* →
     `confirmed` (plan's HISTORICAL block; register untouched); *confirm +
     add to register* → `confirmed` and the `RR-` entry published to
     `docs/risk-posture.md` **as part of the transition** (a write failure
     surfaces at the checkpoint and the confirmation does not complete);
     *reject* → `reopened`; *defer* → the item **stays `proposed`** under
     the same `AR-<n>`, re-presented at every subsequent checkpoint where a
     proposed item exists; *discuss* → paused. **Batched, surfaced at every
     checkpoint** where a `proposed` item exists (step 10), not only at the
     Converge recommendation — but confirmation is only *required* before
     Converge can succeed.
   - **`needs_human` question** (step 7's existing routing, now carded):
     *adopt the recommendation* or *pick an alternative* → recorded in the
     HISTORICAL block and the plan's `## Open questions`, loop resumes;
     *defer* → stays open and Converge-blocking, re-presented next
     checkpoint; *discuss* → paused.
   - **Non-convergence stall** (step 10's existing guardrail, now carded):
     *continue anyway* → loop resumes with a fresh two-transition
     comparison window; *switch to manual* → loop mode ends, per-pass
     checkpoints resume; *abort* → the plan's iteration ends per the abort
     path; *discuss* → paused. The card carries step 10's cluster section.
   - **Simplification card**: *simplify (remove | narrow | replace)* → one
     fold applies that operation, findings dispositioned by its per-finding
     accounting; *fold once more* (reason `premature` or `deliberate`) →
     ordinary fold, streak continues; *split the plan* → a scope transfer:
     the mechanism and its findings move to a new plan stub, findings
     `incorporated (moved to <stub>)`, label retired here; *discuss* →
     paused. Full
     rules below, after the component streak.
   - **Malformed or unavailable register source** (step 5) — one card
     type covering both of `resolve_register()`'s failure states, named
     accurately at presentation time so the options read correctly for
     whichever actually occurred (`malformed`: duplicate `RR-` ids to fix
     in `docs/risk-posture.md`; `operational_failure`: no `HEAD` yet, an
     unresolvable repo root, or another git failure to fix in the
     environment): *fix the source now* → the editor retries `run-pass`
     under the same pass number once the human confirms the fix is in
     place; *proceed with no register* → retry with `--ignore-register`
     under the same pass number (step 5's runner-side mechanism — never
     automatic); *abort* → the plan's iteration ends per the abort path;
     *discuss* → paused. Persisted before presentation (step 5's pre-fan-out
     block-opening exception), so the decision and the choice made are on
     record; an interrupted session abandons the pass and meets the same
     failure again on the rerun.

   Fold `plan_corrections` mechanically; incorporate HIGH/MEDIUM
   findings (skip/dispute only with explicit reasoning); LOW is informational.
   Open a single section for the whole pass, each finding tagged with its
   originating **lens id(s)** and fold disposition. **The block is tagged
   `[IN PROGRESS]` from the moment it opens — right after step 7's merge,
   before any fold, with every merged finding listed and its `→ Editor:`
   slot empty — and flips to `[HISTORICAL]` as the last write of the
   pass**, after every disposition, `retired:` line and correction, and
   after step 10's checkpoint cards are written and answered. The tag, not
   any single slot, is the pass-completion marker: a block still `[IN
   PROGRESS]` is unfinished work however complete its slots look (the
   same rule `iterate-review` step 12 uses). Unlike `iterate-review`,
   this skill never resumes an open block: Setup step 4 abandons it and
   reruns.

   ```markdown
   ## Codex review pass N — answers (YYYY-MM-DD) [HISTORICAL]

   <!-- Tagged `[IN PROGRESS]` from the moment the block opens (right after
   the merge) until the pass's last write — dispositions, `retired:` lines,
   and the checkpoint's cards all recorded — then flipped to `[HISTORICAL]`.
   A block still `[IN PROGRESS]` at Setup is an interrupted pass; Setup
   step 4 retags it `[ABORTED]` and reruns. -->

   ### Verdict
   APPROVE / REVISE / BLOCK   (worst-of; note any FAILED lenses)

   ### Findings
   1. **<title>** — <severity> · lens: <architect|product-manager|both>: <description>
      → Editor: <incorporated|skipped|disputed|accepted-risk (AR-<n>)|register-match (RR-<n>, entry-digest <hash>)> — <reasoning> [introduced_by_pass: <N | null>] [component: <label>]
   ...

   retired: <label> (<why>)   <!-- one line per component label retired this pass; omit when none -->

   ### Plan corrections applied
   - <location>: <fix description>

   ### Open-question answers
   1. <answer>

   ### New questions Codex raised
   - <question> — <settled_by> (lens: <lensid>): <resolution — the answer if
     `resolvable_in_fold`/`needs_lookup`, or "carried to Open questions as Qn"
     if `needs_human`. Note any label you overrode, and why.>

   ### Decision cards

   <!-- Only present when a card was presented this pass — plan-shaping-fold
   escalation, accepted-risk confirmation, needs_human question,
   non-convergence stall, malformed or unavailable register source, or
   simplification card. One
   entry per card, written in two phases per the shared contract above: appended as
   `(pending)` before presentation, then updated in place once answered. -->

   - **<card type>** (<item id, e.g. AR-2 or finding title>): recommendation — <text>; alternatives — <text>; chosen: (pending) | <option> (<one-line outcome>).

   ### Lens run summary
   - architect: <APPROVE|REVISE|BLOCK|FAILED> · product-manager: <APPROVE|REVISE|BLOCK|FAILED>
   ```

   Dispositions: **`incorporated`** — apply the plan edit (required for
   HIGH unless explicitly disputed with reasoning; recommended for MEDIUM;
   optional for LOW). **`skipped`** — acknowledge, don't act (typically
   LOW). **`disputed`** — reject with reasoning. **`accepted-risk
   (AR-<n>)`** — real finding, disproportionate to posture; not fixing
   (full lifecycle above). **`register-match (RR-<n>, entry-digest
   <hash>)`** — the finding matches a recorded accepted risk in
   `docs/risk-posture.md` at HEAD (validated per step 7); no plan edit, no
   fresh human confirmation. If a match is later invalidated (any of the
   three step-7 gates fails on recheck), it reverts to needing a fresh
   disposition and blocks Converge until one is given. `plan_corrections`
   are applied mechanically.

   **`introduced_by_pass` — fold-provenance, per finding.** `N` when the
   defect this finding describes was created by an edit a previous pass's
   fold made; `null` when the defect pre-existed this review or arrived
   with the plan's original draft. This is the same judgment call every
   long loop's pass log already recorded in prose — make it at fold time,
   while the causal chain from "what did pass N-1 change" to "what does
   this finding complain about" is freshest. When genuinely uncertain,
   record `null` with a one-line note rather than guessing `N` — under-
   claiming keeps the data conservative. **Provenance is evidence, never a
   trigger.** Component-based triggering is permitted and is the only
   trigger: the simplification card fires on the component streak alone.
   Provenance fields are consumed as card evidence and for measurement
   only — the card shows each streak finding's `introduced_by_pass` and how
   many are fold-caused, and `tools/provenance-recipe.jq` tallies them —
   but no guardrail, checkpoint, budget or card trigger in this skill
   decides anything from them. (Issue #6's pure fold-provenance trigger was
   deliberately not built: fold-caused findings are sometimes load-bearing.)

   **`[component: <label>]` — the mechanism a finding targets, per
   finding.** Beside `introduced_by_pass`, every merged finding's
   `→ Editor:` line carries a short, stable slug naming the *mechanism*
   the finding targets — the mechanism or invariant a plan decision
   describes (a named lock, a classifier, a recovery path, an ordering
   invariant) — chosen at the same fold-time judgment moment, while the
   causal chain is freshest. Labeling rules:
   - **Same mechanism, same label**, regardless of how the finding is
     worded or which lens raised it. Six findings with six different
     titles on one SQL classifier are all `get-lock-sql-classifier`.
   - **A replacement mechanism gets a new label.** When a fold (or a
     decision card) replaces a mechanism with a different one, the
     replacement starts a fresh streak under its own label; reusing the
     old label would carry the dead mechanism's history onto it.
   - **A label names a mechanism, never a location.** A D-number or
     section may *cite* it, but numbering and headings change while the
     mechanism stays the same, so location never *defines* identity;
     unrelated mechanisms that happen to sit under one broad decision get
     separate labels.
   - **Label lifecycles follow what happened to the mechanism.**
     *Removed* → the label **retires**. *Replaced* → the old label
     retires and the replacement gets a **new label with a fresh
     streak**. Both are facts about the mechanism, recorded whenever
     they happen, on any pass. Two further outcomes exist only as the
     human's answer to a simplification card: *narrowed* (kept, with a
     smaller surface) in answer to the card → the label is **retained**
     and its streak **resets to 0**; *split into its own plan* in
     answer to the card → the label **retires** here, and the new plan
     tracks it from 0. No other outcome resets a streak (a pass with no
     HIGH/MEDIUM finding on the label still does, per the streak rules
     below) — not an ordinary fold, even one that narrows the
     mechanism, and not an `accepted-risk` proposal or confirmation on
     one of its findings, since the `AR-<n>` lifecycle owns only that
     finding: a reset without a card answer would let the editor defer
     the card, so the streak keeps counting.
   - **Retirement is explicit and persisted; absence is only a reset.**
     When a component leaves the plan's scope (a fold deletes it, it moves
     to another plan), write `retired: <label> (<why>)` in that pass's
     HISTORICAL block; a later session reconstructs identity from that
     record. A retired label is never reused. A pass on which a label
     merely draws no HIGH/MEDIUM finding resets its streak and nothing
     more.
   - **When uncertain, use the name the finding cites** — the decision's
     or mechanism's own name in the plan. Under-clustering is the
     conservative error, but its cost is not bounded to one pass —
     persistent label drift can hide a streak indefinitely — so reuse an
     existing label whenever the mechanism is genuinely the same.
   - `plan_corrections` are not tagged; only merged findings count.

   **Component streak.** A label's streak counts **consecutive completed
   passes** on which it appears on at least one HIGH or MEDIUM merged
   finding. **One pass is one observation**, however many findings on the
   label it carries. **LOW findings never count**: a pass on which the
   label appears only on LOW findings, or not at all, resets its streak to
   0. A pass with a `FAILED` lens after retry is **skipped** for streak
   purposes — it neither counts nor resets (a lens that didn't run says
   nothing about the component) — though its findings are still
   dispositioned normally and any retirement recorded on it still
   persists. An `[ABORTED]` pass (Setup step 4) is skipped the same way,
   and nothing recorded on it persists. The committed record is the plan's own HISTORICAL blocks,
   never the state file. A streak reaching **the cluster threshold, 3,**
   triggers the simplification card below. This threshold is stated
   here as a literal because a copied install of this skill has no
   `tools/`; the counting semantics are pinned by
   `../tools/cluster_tracker.py`, whose development-side `CLUSTER_N` must
   equal this number (and `iterate-review`'s), which
   `../tools/check-cluster-streak.py` enforces.

   *Worked example* (impersonation-c1b, an 11-pass `iterate-review` run;
   the counting is identical here, and the sequence is a fixture in
   `check-cluster-streak.py`):

   | Pass | Merged HIGH/MEDIUM findings by label | Streaks after the pass |
   |---|---|---|
   | 1 | — | — |
   | 2 | `account-fallback` HIGH | `account-fallback` 1 |
   | 3 | `reload-guard` HIGH + MEDIUM (two findings, one observation) | `account-fallback` 0 · `reload-guard` 1 |
   | 4 | `reload-guard` HIGH | `reload-guard` 2 |
   | 5 | `reload-guard` MEDIUM | `reload-guard` **3** — reaches the cluster threshold |
   | 6 | `reload-guard` MEDIUM | `reload-guard` 4 |
   | 7 | `reload-guard` MEDIUM; the fold replaces the guard with in-memory recovery → `retired: reload-guard (replaced by in-memory-recovery)` | `in-memory-recovery` 0 |
   | 8 | `in-memory-recovery` HIGH | `in-memory-recovery` 1 |
   | 9 | `in-memory-recovery` HIGH | `in-memory-recovery` 2 |
   | 10 | `in-memory-recovery` HIGH | `in-memory-recovery` **3** |
   | 11 | — | `in-memory-recovery` 0 |

   The redesign actually came at pass 7; the guard's streak first reached
   the threshold at pass 5. The replacement's new label is what lets its
   own streak form on passes 8–10 instead of inheriting the guard's. Under
   the simplification card below, the guard's card is presented at pass 5
   — two passes before the redesign actually came.

   **Simplification card — the sixth named human-judgment moment.** When
   one component keeps drawing findings pass after pass, each fold
   patching one more edge case, the loop is saying the mechanism is wrong,
   not the wording — and the HIGH+MEDIUM stall counter can't see it,
   because every fold produces a new, distinct finding. This card makes
   "stop refining and simplify" a structural question instead of one the
   human has to think to ask.

   **Trigger.** At fold time, a label's **candidate streak** — its
   committed streak from prior completed passes (the plan's HISTORICAL
   blocks) plus 1 if
   this pass's merged findings carry it at HIGH or MEDIUM — reaches the
   cluster threshold, 3, and the card fires before the first fold on that
   label this pass. It fires again on every further pass on which a label
   left at or past the threshold by *fold once more* draws a HIGH/MEDIUM
   finding. It never fires on a pass skipped for streak purposes (a
   `FAILED` lens after retry), and never from a checkpoint lifecycle
   event: an `AR-<n>` rejection or posture invalidation changes ledger
   state exactly as the accounting table above says and nothing else,
   and a reopened finding folded later without a reviewer re-reporting it
   is not an observation. The one observation source is merged HIGH/MEDIUM
   findings at fold time.

   **Transition order — counting and presentation happen exactly once.**
   1. Step 7's merge produces the pass's findings; the block opens with
      them, `→ Editor:` slots empty.
   2. Classify every merged finding's component label and compute each
      label's candidate streak, **before any fold**.
   3. For each label whose candidate streak reaches the threshold, write
      the card to this pass's `### Decision cards` with `chosen:
      (pending)`, naming the label, the streak and the findings it
      comprises. The tag lives in the card entry; the findings' `→
      Editor:` slots **stay empty**, so an empty slot still means
      unfinished work and a persisted classification never reads as a
      completed disposition.
   4. Present the card. Folding of *other* labels' findings may proceed
      meanwhile — the pause is scoped to this label, like the
      plan-shaping-fold escalation.
   5. On the answer, resolve the card in place naming the chosen
      operation, then disposition this label's findings **by that
      operation's per-finding accounting as persisted in the pending card
      — never the recommendation's by default, and never as a batch.** A
      finding the chosen operation resolves → `incorporated (by
      simplification)` (one implementation fold covers all of those; no
      per-finding patches follow). A finding it does **not** resolve keeps
      its ordinary path — an ordinary fold, `disputed` with reasoning, or
      an `accepted-risk` proposal under that lifecycle's own rules and
      trust-boundary exclusions — and is never marked incorporated by
      association. For *fold once more*, every finding takes its ordinary
      path. For *split the plan*, every same-label finding of this pass is
      a **scope transfer** (outcome mapping below).
   6. The sealed block is what the next pass's candidate streak reads.

   A card is identified by `(pass, component)`. Within the live pass, a
   `(pending)` card is presented once and the streak is never recounted.
   Across an interruption the whole pass is abandoned (Setup step 4): the
   card is void with it and fires again only from the rerun pass's own
   count, which reads the committed record with the aborted pass skipped.

   **Required content — a card missing any of it is malformed and is not
   presented:**
   - **The streak's findings** — every finding on the label across the
     streak's passes — each with pass number, lens, severity and
     fold-provenance, plus one line: "`<k>` of this streak's `<m>`
     findings are fold-caused." The human sees the pattern, not just the
     count.
   - **Recommendation: simplify** — remove, narrow or replace the
     component, with a concrete sketch of the change.
   - **For every simplification operation the card offers, recommended or
     alternative, three sub-fields:** *the guarantee lost*; *which
     remaining layer covers it* (or "none," stated plainly); and a
     **per-finding accounting** — one line per streak finding stating
     whether *that operation* resolves it and how, or does not. Sharing a
     mechanism doesn't mean one change closes every defect: narrowing a
     classifier's inputs can close one bypass and leave another inside
     the retained inputs, and removal and narrowing resolve different
     subsets. *Fold once more* and *split the plan* carry no accounting;
     they change nothing about the mechanism.

   **Options** — at most four listed, `discuss` the harness's free-form
   response as for every card:
   - **Mandatory on every card:** *remove the mechanism* (the
     recommendation, or else the first alternative) and *fold once more*
     (always listed, **never the recommendation**).
   - **Remaining slots, in priority order when the four-option cap
     bites:** *split the plan* (this skill's escape hatch, and the reason
     issue #6 named it: the mechanism may deserve its own plan rather than
     a smaller place in this one); then the other simplify operation
     (*narrow*, or *replace with a named cheaper mechanism*) when one
     exists. `iterate-plan`'s card does not offer *accept the risk* — the
     four slots are spent on the options above.
   - Context-sensitive omission may drop optional options only, never the
     two mandatory ones. A card recommending narrowing therefore reads:
     recommendation narrow; alternatives remove, fold once more, and
     split the plan.

   **Outcome mapping:**
   - *simplify (remove)*, *simplify (narrow)*, *simplify (replace)* → one
     fold applies exactly that operation, and the resolution records which
     (`chosen: simplify (remove)`, …). The label follows the lifecycle the
     component-tag rules give that operation — remove → retired
     (`retired:` line); narrow → retained, streak 0; replace → retired,
     the replacement labeled fresh at 0 — never a rule of its own. The
     next pass reviews the simplified plan with both lenses.
   - *fold once more* → ordinary folds; the streak is **not** reset, and
     the card returns on the next pass that draws HIGH/MEDIUM on the
     label. The human also picks a one-word reason, recorded with the
     outcome: `premature` (the card wasn't warranted) or `deliberate`
     (warranted, but one more targeted fold is the right call). The state
     summary's false-positive measure reads `premature` alone.
   - *split the plan* → a **scope transfer**, in this order, each write
     durable before the next:
     1. **the card's resolution is written first**, naming the destination:
        `chosen: split the plan (→ <stub path>)` — the human's choice is on
        disk before anything is changed, so no mutation ever sits under a
        card that still reads `(pending)`;
     2. the new plan stub is created (`create-plan` scaffolds it), with the
        component's decisions and open questions, and a `## Carried
        findings` section holding every same-label finding of this pass
        verbatim (title, severity, lens, description, `introduced_by_pass`)
        — the defect travels with the mechanism, and the new plan's first
        review must address each one;
     3. this plan's text drops the mechanism's decisions, references the
        stub where they were, and gains an `## Out of scope` entry naming
        the stub;
     4. each carried finding is dispositioned here `incorporated (moved to
        <stub path>)` — only once its text is in the stub; the plan edit
        that removed the mechanism from this plan *is* this plan's fold,
        and the finding is not dropped, it is carried;
     5. the label **retires** here (`retired:` line — the mechanism has left
        this plan's scope; the new plan tracks it from 0) and the loop
        resumes on what remains.

     If the session is interrupted mid-transfer, the pass is abandoned
     like any other (Setup step 4); writes already made stay. The rerun
     reviews the plan as it stands, the stub keeps whatever carried
     findings reached it, and any mechanism decision still in this plan
     is reviewed afresh. Recording the resolution first (write 1) keeps
     the record honest: no plan edit ever sits under a card that still
     reads `(pending)`. This is the shape every
     split-off in the evidence took (a remainder named at a durable new
     home, the originating finding `incorporated`), with a plan stub as
     the home.
   - *discuss* → paused.

   Persistence is the shared two-phase contract: pending write before
   presentation, resolution write on the answer.

   **Never an auto-stop, never an auto-simplify.** The card presents; the
   human decides. Nothing in this skill ends a loop, removes or narrows a
   mechanism, or suppresses or downgrades a finding because of a streak.
   The worst case of a card fired too early is one card the human answers
   *fold once more (premature)*.

   Worked example: `examples/merge/02-simplification-card/` — the CSRF
   plan review's SQL-parsing classifier, a card at pass 6 (the real review
   removed it at pass 10) whose per-finding accounting for *remove*
   resolves three of the streak's four findings and leaves the fourth to
   an ordinary fold, plus the same card answered *split the plan*.


9. **Recompute `plan_content_hash` post-fold.** Stash for the next pass's
   manual-edit detection.

10. **Checkpoint — Continue / Converge / Abort / (L)oop.** Present the
    aggregate verdict + a recommendation:

    **Batched accepted-risk confirmation, before the Continue/Converge/Abort
    choice.** Surface every `AR-<n>` currently in `proposed` state as a
    decision card (per the accepted-risk confirmation outcome mapping in
    step 8) — this happens at **every** checkpoint where a proposed item
    exists, not only when recommending Converge, but confirmation is only
    *required* before Converge can succeed; deferring is a legitimate
    outcome that leaves the item queued for the next checkpoint.

    - Recommend **Converge** when aggregate `verdict == APPROVE`, no lens is
      `FAILED`, the editor has no further changes pending, and **no `AR-<n>`
      remains in `proposed` or `reopened` state** (step 8's accounting
      table). One APPROVE + no-further-changes + no open accepted-risk item
      is enough.
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
      without converging," with the cluster section below.
    - **BLOCK verdict** → stop.
    - **Non-convergence** — the merged **HIGH+MEDIUM** finding count fails to
      strictly decrease across two consecutive transitions (LOW / `FAILED` /
      open-questions excluded; a `FAILED`-lens pass is skipped in the
      comparison but still counts toward the cap) → stop, surface as the
      non-convergence-stall decision card (step 8's shared contract), with
      the cluster section below.
    - **Simplification card** — a label's candidate streak reached the
      cluster threshold this pass (step 8) → the fold of that label's
      findings pauses **immediately**, mid-fold, like a plan-shaping-fold
      escalation, and the loop does not continue to another pass until the
      card is answered. Never an auto-stop and never an auto-simplify: the
      card is the whole effect.
    - **Fold needs human judgment** — any HIGH finding was *not incorporated*,
      *not* a fresh `accepted-risk` proposal, and *not* a valid
      `register-match` (i.e. it's `disputed`, or awaiting a
      plan-shaping-fold escalation card), or a `new_question` classified
      **`needs_human`** survived the fold (after the label sanity-check and
      any override in step 7) → stop, escalate. A HIGH dispositioned
      `accepted-risk (proposed)` or a valid `register-match` does **not**,
      by itself, halt the loop — accepted-risk proposals continue and batch
      for confirmation at the next checkpoint (no HIGH silently vanishes:
      the proposal is persisted immediately under a stable id and blocks
      Converge until confirmed). A **plan-shaping-fold escalation does halt
      immediately**, unlike an accepted-risk proposal — continuing there
      would commit to an unapproved scope change, which is exactly what the
      immediate halt exists to prevent. `resolvable_in_fold` and
      `needs_lookup` questions do **not** halt the loop: the editor resolves
      them and continues. If a `needs_lookup` resolution *fails*, it becomes
      `needs_human` and then halts. This is the whole point of the
      classification — an unattended loop shouldn't stop for a question it
      could have answered, and must never continue past one only Kyle can.

    **Cluster section — on the max-pass cap hand-back and the
    non-convergence stall card.** When either fires, the hand-back carries
    the HIGH/MEDIUM findings from the last three passes grouped by
    component label, each label with its committed streak, side by side so
    two names for one mechanism are visible to the human (label drift is
    the one failure the labeling rules can't fully prevent); a retired
    label is listed as retired, with the pass it retired on. Then the
    status lines that apply:
    - "no live component has reached one below the cluster threshold, 2,
      — no simplification card is one pass away" (when no tracked label
      is at 2 or more);
    - "`<label>` at one below the cluster threshold, 2, — one more
      HIGH/MEDIUM pass on it triggers the simplification card", one per
      tracked label at 2;
    - "`<label>` — simplification card presented at pass `<p>` at streak
      `<n>`, chosen: `<outcome>`", one per card presented in the window,
      `<n>` being the streak at fire (a *fold once more* label keeps
      climbing, and this line shows the decision already taken; a removed
      or split label reads as retired above).

    This turns the cap into a trigger for the cluster check rather than a
    bare budget number. It adds a section; it changes no guardrail's
    condition or outcome.

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

    **`confirmed_accepted_risks`** (Phase 1) — mirrors `iterate-review`'s
    field of the same name exactly: one entry per `AR-<n>` whose `confirmed`
    state still holds at the moment the file is written — `{id,
    register_ref (RR-<id> if confirmed with confirm + add to register, else
    null), dependency_descriptor (list of posture field ids), dependency_digest
    (sha256 hex over those fields as confirmed)}`. **Current-state, not
    historical**: an item confirmed earlier and later returned to `proposed`
    by a posture-digest mismatch is absent, even though it "was confirmed" at
    some point. Empty when the plan never proposed one. Converge is
    impossible while any `AR-<n>` remains `proposed` or `reopened` (step 8's
    accounting table), so every entry here is `confirmed` at Converge time by
    construction — Abort may still leave `proposed`/`reopened` items
    unresolved, in which case the plan's own HISTORICAL blocks remain the
    authority on what's pending.

    **Per-pass summary (`summary_schema: 2`) — the data half of issue #6.**
    At Converge and Abort alike, the state file additionally carries:
    - `summary_schema: 2` — versions this row shape. Schema 2 is schema 1
      plus the component fields below, additively; a schema-1 file still
      reads, with the missing fields as empty (`cards` as `[]`).
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
      int, zero when unused. Phase 0 shipped `accepted-risk` and
      `register-match` at a standing `0` (the disposition didn't exist
      yet); Phase 1 populates those same keys with real counts — the row
      shape itself never changed.
    - Component fields per row (schema 2): `observation` (bool — `true`
      when every selected lens completed, `false` when any lens was
      `FAILED` after retry, read from the block's Lens run summary line;
      this is what tells a skipped pass from a quiet one, which the
      verdict alone cannot); `components` (object — one entry per label on
      that pass's merged findings, all severities: `{worst_severity,
      findings, fold_caused}` — `worst_severity` the label's worst
      severity, `HIGH|MEDIUM|LOW`; `findings` and `fold_caused`
      **counts**, not booleans, so mixed provenance on one label is
      visible); `streaks` (object — each
      tracked label's committed streak at the end of the pass; retired
      labels drop out); `retired` (array — labels retired on that pass);
      `cards` (array — one row per simplification card presented that
      pass: `{type: "simplification", component, streak_at_fire,
      findings_in_streak, fold_caused_in_streak, chosen:
      remove|narrow|replace|fold-once-more|split-plan|pending|aborted,
      reason: premature|deliberate|null}`, `[]` when none).

      Rows are **derived from the plan's own HISTORICAL blocks** by a
      deterministic, idempotent procedure (re-deriving the same blocks
      always produces the same rows) — never hand-authored, and the plan
      file remains the durable authority the rows are only a summary of. The component fields derive from the same blocks: `components`
      from the `[component: <label>]` tags, `retired` from the `retired:`
      lines, `observation` from the Lens run summary, `cards` from the
      `### Decision cards` entries, and `streaks` by replaying the
      component-streak rules (step 8) over the blocks in pass order.
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
    skills' state files — and the simplification-card measures
    (`cluster_hits`, outcome mix, the `premature` false-positive rate; pass
    the threshold with `--arg n 3`). **These rows are derived at exit, so
    no guardrail, checkpoint, budget or card trigger in this skill consults
    any field defined in this paragraph.** The simplification card's
    trigger reads the component streak from the plan's HISTORICAL blocks,
    its committed record; component-based triggering is permitted and is
    the only trigger, and provenance fields (`introduced_by_pass`,
    `fold_caused_count`, `fold_caused`) are consumed as card evidence and
    for measurement only, never as a trigger. This closes
    [issue #6](https://github.com/kaileconsulting/trinity-skills/issues/6)
    without its pure-provenance trigger.

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
- `../tools/freeze_tracker.py` — reference implementation of the §4
  open-question freeze *counting* semantics above (editor-side judgment,
  not runner code); boundary-case-tested by
  `tools/check-question-freeze.py`. Covers the streak state machine only
  — not the plan-file annotation write/removal, which is editor-verified
  by inspection like every other fold-time write this skill makes.
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
  goldens; `examples/composition/` pins byte-deterministic input assembly,
  including the register-present and register-absent cases (Phase 1).
  Validate with `tools/check-examples.py`.
- `docs/risk-posture.md` (per-repo, not part of this skill's own files) —
  the accepted-risks register (`## Accepted risks`, `RR-<date>-<slug>`
  entries), read **at HEAD only, never the working tree** (Phase 1, Q5) by
  both composition (step 5) and the register-match provenance gate
  (step 7) — the same trusted source, so a dirty uncommitted register
  edit can never reach a lens input or pass the gate it exists to satisfy.
  Section shape matches `create-plan/template.md`'s `## Risk posture`; see
  the Trinity v2.4 plan (Approach §6) for the full design and
  `iterate-review/SKILL.md`'s sibling register-reading prose (its own
  copy is editor-composed rather than runner-composed, since that skill's
  input has an intent file to augment and this one doesn't).

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
- **The simplification card presents; it never stops or simplifies
  anything by itself.** When one component draws HIGH/MEDIUM findings on
  consecutive completed passes up to the cluster threshold, 3, the fold of
  that component's findings pauses for a card whose options always include
  *remove the mechanism* and *fold once more* — and *fold once more* is
  never the recommendation. *Split the plan* is this skill's escape hatch
  on the card. No path ends a loop, removes or narrows a mechanism, or
  suppresses or downgrades a finding because of a streak without the human
  answering that card.
- **Component-based triggering is permitted and is the only trigger;
  provenance is evidence only.** `introduced_by_pass`, `fold_caused_count`
  and the per-pass summary's provenance fields are shown on the card and
  measured by `tools/provenance-recipe.jq`; no guardrail, checkpoint,
  budget or card trigger decides anything from them.
- **`accepted-risk` requires a posture-referencing rationale and human
  confirmation to converge** (Phase 1, ported from `iterate-review`). The
  editor may propose it, but only the human confirms or rejects; the
  Converge recommendation is impossible while any `AR-<n>` remains
  `proposed` or `reopened` (accounting table, step 8). Both `accepted-risk`
  and `register-match` are unavailable for plan content named as a trust
  boundary in `PF-shipbar` — no exception, checked against both the
  current pass's and this pass's starting `PF-shipbar` so a same-pass edit
  can't create the exception either.
- **The register is always read from HEAD, never the working tree**
  (Phase 1, Q5). `bin/plan_runner.py`'s `compose_input()` and its assembly
  structure are otherwise untouched by this feature — the `=== ACCEPTED
  RISKS ===` block is an additive part of the same deterministic assembly.
  Malformed register content or an operational read failure halts before
  fan-out with a decision card rather than silently composing without the
  register; `--ignore-register` is the one way past that halt, and it is
  never automatic — the editor passes it only after an explicit human
  choice at the card.
- **Every named human-judgment moment (accepted-risk confirmation,
  plan-shaping-fold escalation, `needs_human` question, non-convergence
  stall, malformed or unavailable register source, simplification card)
  uses the same decision-card contract**
  (Phase 1, step 8) — recommendation + why, up to 3 alternatives
  (context-sensitive omission can reduce this to zero listed alternatives;
  recommendation + discuss is the floor and is always presented, never
  skipped), a standing discuss option, written to the plan's HISTORICAL
  block as pending before presentation and resolved once answered.
  Selecting any option but discuss resumes the loop deterministically;
  discuss pauses into conversation.
- **Phase 1's success is measured by plan-loop pass counts and
  re-litigation counts on future plans — never by code-review pass
  counts.** The 2026-08-21 retro is explicit that code-review churn is
  driven by fold-chaining (Phase 0 items 2 and 5), not by plan quality;
  judging this port by downstream code-review passes would blame it for a
  variable it doesn't control. The measurement contract (cohort: the first
  three `iterate-plan` loops run after v2.4 ships; baseline: the retro's
  plan-loop dataset; measures: pass count + settled-decision re-litigation
  count; recorded at each loop's Converge; feeds issue #6's decision
  review) is a learning contract, never a ship gate.
