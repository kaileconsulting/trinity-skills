# Runner scripts + artifact hygiene for the trinity skills — Plan

## TL;DR

Move the mechanical execution of review passes — lens-input composition, Codex invocation, response validation — out of improvised per-pass shell and into small **stdlib-only Python runners** under each skill's `bin/`. Today every pass invents a unique ~40-line compound command that can never be pre-approved, so a 10-pass review means dozens of opaque permission prompts and a settings file full of dead one-shot rules. After this plan, **one documented allowlist line** (e.g. `Bash(~/.claude/skills/iterate-review/bin/* *)`) lets the review machinery run an entire multi-pass review with **zero further Bash permission prompts**. The interactions that remain — scope selection, the skills' mandated human checkpoints, and standard file-edit approvals for the pass log — are intentional and readable, not permission noise.

The boundary is strict: **the runner composes and invokes; it never folds, never writes pass logs, never decides.** Every behavioral rule — fan-out, semantic merge, worst-of verdict, `FAILED` handling, checkpoints, loop guardrails — stays with the model. Opus-as-sole-writer discipline is unchanged.

Two hygiene fixes ride along: pass logs move off the invoking repo's root to `docs/reviews/` by default, and state directories get pruned on convergence instead of accumulating forever. `iterate-review` lands first (that's where the pain is measured), then the pattern ports to `iterate-plan` with a parity fixture guarding against drift.

## Why / Context

Three compounding frictions, all structural to how the skills execute, all measured on a heavy dogfooding day (2026-08-06, `Adminformatics/doc-bot` — see Current state below):

1. **Unique shell cannot be pre-approved.** `iterate-review` steps 9–10 have the model compose per-lens Codex inputs with ad-hoc compound commands — `for`-loops over lenses, heredocs, `awk` frontmatter extraction, per-pass file paths embedding pass number + lens + scope hash. Each is a one-off string: the permission system prompts on every one, and an "always allow" click records an exact-match rule that never matches again. A non-engineer driver approving opaque shell walls is the opposite of what a permission prompt is for.
2. **Pass logs accumulate at the invoking repo's root.** The default (`<cwd>/code-review-<scope-tag>.md`) is the only path users ever hit; repo-root clutter is the default experience.
3. **State directories accumulate forever.** `state/<scope-hash>/pass-N.<lens>.response.json` files persist after convergence with no pruning story.

A stable script accepts *arguments*, not improvised code — that's what makes it allowlistable once and readable at the prompt. The fix is structural, not behavioral, which is why it can land without touching any review semantics.

## Who / Use cases

The repo is headed for **public/open source**, so the audience is broader than the authoring machine:

- **The non-engineer skill driver** (the measured case): runs multi-pass reviews daily and currently approves shell they can't audit. Success: after one comprehensible, documented allowlist line, the review machinery generates zero Bash permission prompts end to end; the only remaining interactions are the skill's own checkpoints and standard file-edit approvals.
- **A new user installing from the public repo**: clones, symlinks (or copies) the skills, adds the README's one allowlist snippet with their own path, and gets the same zero-prompt experience with no hardcoded-path surprises. Scope of that promise: allowlist matching is a Claude Code string-prefix behavior — OS-independent, varying only with the installed path the snippet parameterizes — so rule matching is *demonstrated* on macOS in both install layouts, while Linux is verified for runner correctness (container matrix) with rule matching following from the same path-prefix argument.
- **The skill maintainer**: deterministic composition means golden-file fixtures can pin byte-identical lens inputs, and the patch-marker rejection check becomes tested code instead of prose the model must remember. Regressions become fixture failures, not dogfooding surprises.

## Goals (MVP)

- A full multi-pass `iterate-review` on a real repo runs with **one documented allowlist rule and zero other Bash permission prompts** end to end (the skills' human checkpoints and standard file-edit approvals are by design and excluded from that count; the one rule covers all three `bin/` executables).
- `iterate-review/bin/` ships `run-lens` (compose + invoke + validate one lens), `run-pass` (select lenses, fan out concurrently), and `prune-state` (cleanup) — all stdlib-only Python 3.9+, zero hardcoded user paths.
- The patch-marker rejection check moves from SKILL.md prose into code, exercised by a fixture (malformed response → non-zero exit).
- Composition is deterministic: same inputs → byte-identical lens input files, pinned by golden-file fixtures.
- Pass logs default to `docs/reviews/code-review-<scope-tag>.md`; `--log-path` override retained; existing root logs untouched.
- State for converged runs is pruned automatically; `prune-state` handles aborted/aged runs.
- The runner pattern ports to `iterate-plan` with the shared-machinery parity fixture extended to cover it.
- Existing `examples/` + `tools/check-examples.py` + `tools/check-parity.py` stay green throughout.

## Non-goals (MVP)

- **No decision logic in runners** — folding, merging, verdicts, `FAILED` handling, checkpoints, and loop control stay with the model. The runner is a dumb, deterministic executor.
- **No third-party dependencies at runtime** — stdlib-only; no `jsonschema`, no packaging/`pyproject`, no CLI framework.
- **No behavior changes to the review loop** — `--once`, `--loop`, `--max-passes`, `--log-path`, the state-file format, and the pass-log HISTORICAL format are all unchanged.
- **No Windows support** — macOS + Linux only; one-line rationale: neither skill has ever run there and the permission-rule story differs.
- **No changes to lens content or selection *rules*** — selection moves into code, but the rules themselves (per `lenses/README.md`) are untouched.
- **No `create-plan` runner** — that skill has no per-pass shell; nothing to fix.

## Current state — evidence from dogfooding (2026-08-06, `Adminformatics/doc-bot`)

- The write-path Phase 0 review ran **10 passes × 3 lenses = 30 Codex invocations**, each preceded by a unique composition block and followed by log-append heredocs — every one a potential permission prompt. A same-day dependency review (2 passes) and a CodeQL review (2 passes + a `--once`) had the same texture.
- doc-bot's `.claude/settings.local.json` accumulated **~40 dead one-shot codex rules (89 rules → 49 after cleanup)**. The cleanup replaced them with a single `Bash(codex -a never exec *)` prefix rule — the direct precedent for this plan's single-rule design.
- doc-bot's repo root holds **five `code-review-*.md` files**.
- One review produced **30 response files** under `~/.claude/skills/iterate-review/state/<scope-hash>/`; nothing ever deletes them.
- Driver's words: *"every time I have to approve the write of these temp review files … it's just a lot of clicking yes and I don't always understand what I'm clicking yes to."*

## Approach

### Architecture — the model/runner boundary

```
model (Opus)                          runner (bin/, Python 3.9+ stdlib)
─────────────────────────────         ─────────────────────────────────
scope selection, intent  ──────────►  run-pass --diff … --intent …
                                        ├─ deterministic lens selection
                                        │  (promoted from check-selection.py;
                                        │   --lenses overrides)
                                        ├─ per-lens: compose input
                                        │  (contract + lens fragment +
                                        │   matched-context + INTENT/DIFF/
                                        │   PRIOR PASSES) → state dir
                                        ├─ concurrent codex invocations
                                        │  (-a never exec -s read-only
                                        │   --output-schema …, exact flags)
                                        ├─ per-response structural checks
                                        │  + patch-marker rejection
                                        └─ JSON summary → stdout
merge, worst-of verdict,  ◄──────────  (response paths + per-lens status)
FAILED handling, HISTORICAL
append, checkpoint, loop control
```

The contract sentence, stated in both SKILL.mds: **the runner composes and invokes; it never folds, never writes logs, never decides.**

All skill paths are derived from the script's own location (`Path(__file__).resolve()` walks to the skill root, which works through the `~/.claude/skills/<name>` symlink or a plain copy); `codex` is resolved from `PATH`. Zero hardcoded user paths. The **invoking repo's root** (for the `docs/reviews/` pass-log default) is a distinct resolution: `git rev-parse --show-toplevel` from the cwd — which handles subdirectory and worktree invocation — falling back to the cwd with a warning in the summary's `warnings` field when not in a git repo. Tests cover both non-root invocation cases.

### State lifecycle & result contract

The state directory is a concurrency and deletion unit, so its lifecycle is explicit:

- **Run ownership — one protocol for every actor.** Anything that mutates a scope directory (`run-pass` starting, stale-lock reclaim, `prune-state` deleting) must hold the same exclusive lock: `state/<scope-hash>/run.lock`, created `O_CREAT|O_EXCL`, containing owner pid + ISO timestamp + role. A second concurrent run of the same scope fails fast with a clear message.
- **Race-safe stale reclaim.** A lock whose recorded pid is dead is stale, but reclaim is never unlink-and-hope: the reclaimer first wins an intermediate `run.lock.reclaim` (`O_EXCL`, recording the same pid/timestamp/token metadata), re-reads `run.lock` and verifies it is byte-identical to the stale content it originally observed — a successor's fresh lock differs and is never touched — and only then unlinks and attempts its own `O_EXCL` creation. Losing that creation race to a newly starting run is a clean back-off, not a steal. Adversarial fixture: two simultaneous reclaimers → one winner, and no successor's lock is ever deleted.
- **Force-unlock is itself race-safe, by the same byte-identity rule.** `prune-state --force-unlock` inspects `run.lock` / `run.lock.reclaim`, prints exactly what it saw (dry-run first, `--yes` to act), and every removal is conditional: immediately before each unlink it re-reads the file and proceeds only if byte-identical to what it inspected — any mismatch (a successor's fresh lock, a competing recovery that already acted) is a refuse-and-re-inspect, never a delete. Unique ownership tokens make content collisions impossible, so a successor's lock can never satisfy the identity check. Two simultaneous force-unlock attempts serialize themselves: each unlink has one winner and the loser refuses on mismatch or absence. No additional coordination file is introduced. Adversarial fixture: two concurrent force-unlocks with a successor starting mid-recovery — the successor's ownership survives.
- **The reclaim marker's own lifecycle terminates the recursion — by refusing to recurse.** The marker is removed in the reclaimer's `finally` (conditional on its own metadata, same rule as the main lock) on every normal and handled path, and reclaim is a sub-second window, so an orphaned marker is a crash-during-crash-recovery corner. That corner gets **no** automatic cleanup and no third coordination file: any actor finding a reclaim marker whose recorded pid is dead (or whose metadata is malformed) refuses and points at `prune-state --force-unlock <scope>`, which alone clears marker and lock together under its token-revoking authority. A live-pid marker simply means reclaim is in progress — back off. Fixtures: reclaimer completes → marker gone; reclaimer killed mid-reclaim → subsequent actors refuse with the recovery pointer; `--force-unlock` clears both files.
- **Prune owns the scope for the entire deletion.** `prune-state` acquires the same `run.lock` (`O_EXCL`, role=prune) before touching anything, deletes contents under it, unlinks its own lock last, then removes the directory. A `run-pass` starting mid-cleanup fails the `O_EXCL` create and backs off; if a new run sneaks into the window between lock-unlink and rmdir, the rmdir fails non-empty and prune leaves the scope intact and reports rather than retrying. Adversarial fixture: run-start vs. prune interleaving never deletes live state.
- **Atomic publication.** Every artifact (input, response, summary) is written to `<name>.tmp` and `os.replace()`d into place — readers never see partials, and `.tmp` files are ignored by readers and swept by prune.
- **Pass numbering.** Allocated under the lock by scanning existing `pass-N.*` and taking max+1; a retried pass never overwrites a published artifact.
- **Result contract.** `run-pass` publishes `pass-N.summary.json` last (atomically): `{pass, scope_hash, log_path, warnings, lenses: {<id>: {status: ok|failed|rejected, response_path, exit_code, stderr_tail}}, complete: true}`. `log_path` is the runner-resolved pass-log destination (the `docs/reviews/` default or the `--log-path` override, echoed back) — the runner *resolves and reports* the destination; the model, sole writer, appends there without re-deriving repo-root logic. `warnings` carries resolution warnings (e.g. the non-git cwd fallback). Exit code 0 means exactly "a summary was published" — per-lens failure/rejection is *data* the model folds under its existing `FAILED` rules, not an orchestration error. Non-zero exit / absent summary means the pass **aborted** (e.g. parent interrupted) and the model treats it as never-ran.
- **Fan-out completion policy.** All lens futures are awaited; one lens failing never cancels its siblings, and successful sibling responses stay usable under the model's `FAILED` handling.
- **Exit contracts differ by command, deliberately.** Standalone `run-lens`: exit 0 = valid response published; exit 2 = response rejected (patch markers or structural failure — the patch-marker fixture asserts this exit); exit 1 = invocation/orchestration error. Aggregate `run-pass`: the published-summary contract above — a rejected lens inside a completed pass is `status: rejected` data with exit 0. The two contracts are stated side by side in each script's `--help` so a caller can't reasonably apply one to the other.
- **Standalone `run-lens` never touches published pass state.** `run-pass` calls the lens logic in-process; the standalone CLI is a debug tool that writes only under `state/<scope-hash>/debug/` (timestamped names, no lock taken, never `pass-N.*`). Prune sweeps `debug/` freely; readers never look there. A standalone invocation during a live `run-pass` therefore cannot overwrite or interleave published artifacts (fixture-pinned).
- **Lock duration & release.** The lock is held only for the duration of a single `run-pass` invocation: acquired before pass-number allocation, released in a `finally` block on every normal and handled-exception path. A completed run leaves no lock — so convergence-time pruning is never blocked by one (fixture-pinned). A lock that exists at all means a run is live *or* its process died unhandled (crash, `kill -9`).
- **Ownership tokens make displacement detectable.** The lock records an unforgeable random token alongside pid/timestamp/role. Every mutating actor re-verifies that `run.lock` still holds *its* token immediately before publishing any artifact and before releasing the lock — the `finally` unlink is conditional on token match, never unconditional. `prune-state --force-unlock` works by *revoking* the token: a displaced-but-still-live `run-pass` fails its next token check and aborts — it publishes nothing *further* (in particular, never a summary) and never touches a successor's lock. Artifacts it staged before revocation may remain; the pass-visibility rule below makes them inert.
- **A pass exists iff its summary exists.** Readers — the model, fixtures, `prune-state` — discover passes *only* through `pass-N.summary.json`; lens artifacts without a summary are orphans: never folded, never treated as a partial pass. Pass-number allocation takes the max over **all** `pass-N.*` names (artifacts and summaries alike), so orphans are never overwritten — their numbers are simply skipped — and prune sweeps them with the rest of the state. This is what makes per-file atomic publication sufficient: the summary, published last under a valid token, is the pass's single commit point. Adversarial fixture: force-unlock of a genuinely live run followed by a successor start — the displaced run commits no summary, its orphans are ignored by allocation and readers, and the successor's lock is never unlinked.
- **Stale-lock policy is conservative.** The lock records pid + ISO timestamp + owner process name; it is reclaimed automatically **only when the pid is dead**. *Any* live pid — including one whose process name doesn't match the record, which PID reuse can produce — makes the lock ambiguous: runners and `prune-state` refuse and point at the explicit manual recovery path, `prune-state --force-unlock <scope>`. The recorded name is a diagnostic shown in the refusal message, never a detection mechanism — no reclaim is ever based on it, and there is no timeout-based reclaim: a slow run must never have its lock stolen. Malformed lock metadata is likewise refuse + manual recovery. All three cases fixture-pinned.

### Stack decisions

- **Python over shell** (decided with Kyle 2026-08-06): portable, testable, and the repo already has Python tooling precedent (`tools/check-examples.py`, `examples/selection/check-selection.py`). Shell rejected because improvised shell is the disease being cured; a shell *script* would work but is untestable against the golden-file bar this plan sets.
- **Python 3.9+ floor, stdlib-only** (decided with Kyle 2026-08-06): a stated *prerequisite*, not an assumption about system Python — macOS ships no interpreter by default (Xcode CLT currently provides 3.9.6, Homebrew newer), so the README lists `python3 ≥ 3.9` as a requirement and every runner fails fast with a clear message via a `sys.version_info` check. Everything needed (`argparse`, `pathlib`, `subprocess`, `concurrent.futures`, `json`) is comfortably inside 3.9.
- **Lens selection embedded in `run-pass`** (settles brief Q1): the selection rules are deterministic and already have a reference implementation with 14 diff fixtures (`examples/selection/check-selection.py`). Promoting that logic into `run-pass` makes it single-source-of-truth code instead of "two implementations must agree." A `--lenses` flag lets the model (or a human) force a set when needed; the 14 fixtures are repointed to exercise the promoted implementation directly.
- **Concurrency inside `run-pass`** (settles brief Q2): a `concurrent.futures` fan-out over `run-lens`'s core function is one command per pass (vs. three backgrounded calls and three notifications) and emits a per-lens structured summary to stdout, which keeps failure attribution *cleaner* — the model reads one JSON object saying which lens succeeded, failed, or was rejected, and applies the existing `FAILED` rules.
- **Composition inputs live in the state dir, not `/tmp`** — `state/<scope-hash>/pass-N.<lens>.input.txt`. They become prunable with the rest of the run's state and make golden-file comparison trivial. On convergence they are pruned with everything else (settles brief Q3, both lenses concurring: the pass log is the audit record; `--keep-state` preserves exact prompt text when debugging a bad merge).
- **No hidden retries in `run-lens`** (settles Q1, both lenses concurring): a failed codex invocation is reported immediately in the summary with exit code + stderr tail; retry judgment stays with the model's existing `FAILED` rules. A hidden retry would make one invocation nondeterministic and blur the dumb-executor boundary; a bounded `--retry` flag can come later if dogfooding shows transient failures are common.
- **Structural validation in stdlib, not `jsonschema`** (settles brief Q5): `run-lens` checks required keys, types, and the verdict enum, and performs the patch-marker scan in code; `codex --output-schema` already does the heavy lifting. Belt-and-suspenders without a dependency.
- **Prune policy** (settles brief Q4; sharpened passes 1–3): convergence is the **model's** determination — worst-of verdict at the checkpoint — and `prune-state` never infers it from state (it would have to duplicate model-owned decision logic to try). On Converge, the SKILL.md step has the model explicitly invoke `prune-state --scope <scope-hash> --yes`, or skip it via the `--keep-state` escape hatch when an audit trail is wanted; the pass log is the durable record, response/input/summary files are intermediates. For aborted/abandoned runs, `prune-state` is age-based: dry-run by default, destructive cleanup requires an explicit `--older-than` — the README offers 30 days as an example without encoding it as policy. It never touches pass logs and never touches a state dir holding a live run lock.
- **Pass-log default `docs/reviews/`** (settles brief Q3): created on demand under the invoking repo's root; `--log-path` override retained; existing root logs untouched, README notes the new default.
- **Self-contained `bin/` per skill, parity-checked** (settles brief Q6): a shared `lib/` at the repo root works while skills are symlinked but breaks for anyone who copies a skill directory standalone. Small shared helpers are duplicated and guarded by extending `tools/check-parity.py` — the same philosophy the repo already applies to SHARED MACHINERY prose.
- **HISTORICAL appends use the Edit/Write tools, not heredocs**: the runner never writes logs, so the model's per-pass log append is the remaining write — routing it through the file-edit tools puts it under file-edit permissions instead of generating one more unique Bash prompt.

### Repo layout (new files)

```
iterate-review/
  bin/
    run-lens          # compose + invoke + validate one lens
    run-pass          # select lenses, fan out run-lens concurrently
    prune-state       # prune converged/aged state dirs
  examples/
    composition/      # golden files: inputs → byte-identical lens input
    runner/           # patch-marker rejection, structural-check fixtures
iterate-plan/
  bin/                # Phase 3 port, same shape
```

`run-lens` stays invocable standalone (debugging a single lens) even though `run-pass` calls its logic in-process — but standalone output goes to the isolated `debug/` namespace, never to published `pass-N.*` state (see State lifecycle).

### The single-rule permission model

Each user adds one documented allowlist line — README ships the snippet, the path is theirs:

```
Bash(~/.claude/skills/iterate-review/bin/* *)
```

Everything the runner does (state-dir writes, codex invocation, validation) happens inside that one approved shape. "Zero prompts" means precisely: **zero Bash permission prompts beyond this one rule** for everything the review machinery does. Three interactions remain by design and are excluded from that count: scope selection at the start, the human checkpoints the skills already mandate, and HISTORICAL pass-log appends — which route through the Edit/Write tools and are governed by the user's normal file-edit permission settings (auto-accepted in acceptEdits mode), never by improvised shell.

## Phasing

### Phase 0 — Foundations & layout decisions (~0.5 day)
**Deliverables:**
- `bin/` scaffolding for `iterate-review` (executable stubs, arg parsing, skill-root resolution from script location).
- State-dir layout extended for composition inputs (`pass-N.<lens>.input.txt`) — documented in `iterate-review/SKILL.md`'s state-file section, no behavior change yet.
- `docs/reviews/` default and migration note drafted in README; single-rule allowlist snippet drafted.
- CHANGELOG entry stub opened per repo convention.

**Acceptance:**
- `tools/check-all.sh` green (existing fixtures untouched).
- README documents the allowlist line + Python 3.9+ requirement.
- No behavior change to either skill yet — stubs are inert until Phase 1 rewires SKILL.md.

**Iterate-review:** NO (rationale: setup/docs only — bin/ scaffolding, state-dir layout, docs/reviews/ default, README allowlist snippet)
**Status:** shipped (2026-08-06; NO-marked phases ship straight to shipped when commits land)

### Phase 1 — iterate-review runners (run-lens, run-pass) + SKILL.md rewire (~1.5 days)
**Deliverables:**
- `run-lens`: deterministic composition (shared contract + lens fragment + matched-context framing + INTENT/DIFF/PRIOR PASSES), state-dir creation, Codex invocation with exact sandbox flags (`-a never exec -s read-only --output-schema …`), structural response checks, patch-marker rejection in code, machine-readable result on stdout.
- `run-pass`: deterministic lens selection promoted from `examples/selection/check-selection.py` (with `--lenses` override), concurrent fan-out, per-lens JSON summary.
- Run lifecycle: exclusive per-scope `run.lock` (fail-fast on concurrent same-scope runs, stale-lock reclaim), atomic tmp + `os.replace()` publication for every artifact, pass-number allocation under the lock, and the `pass-N.summary.json` result contract (exit 0 ⇔ summary published; per-lens `ok|failed|rejected` with exit code + stderr tail; absent summary = aborted pass).
- Invoking-repo root resolution for the pass-log default (`git rev-parse --show-toplevel` from cwd; non-git fallback to cwd with a warning), tested from a subdirectory and a worktree.
- Composition golden-file fixtures (byte-determinism) + patch-marker rejection fixture (malformed response → non-zero exit) + selection fixtures repointed at the promoted implementation.
- `iterate-review/SKILL.md` steps 9–11 rewired to call the runners; contract sentence added; pass-log default moved to `docs/reviews/`; HISTORICAL appends routed through Edit/Write tools.
- `--once`, `--loop`, `--max-passes`, `--log-path`, state-file format, and pass-log HISTORICAL format verified unchanged.

**Acceptance:**
- A full multi-pass iterate-review on a real repo runs with one documented allowlist rule and zero other Bash permission prompts end to end (dogfood on `Adminformatics/doc-bot`).
- Golden-file fixtures prove byte-deterministic composition; the patch-marker fixture exercises **standalone `run-lens`** rejection (malformed response → exit 2) and the corresponding `status: rejected` entry in a `run-pass` summary; all 14 selection fixtures pass against the promoted implementation.
- Lifecycle fixtures: a concurrent second run of the same scope fails fast; an interrupted run leaves no readable partial artifact; a completed `run-pass` releases its lock; the summary contract is pinned by fixture; a standalone `run-lens` invocation during a live `run-pass` leaves published state untouched; adversarial reclaim — two simultaneous stale-lock reclaimers yield one winner and never delete a successor's lock; reclaim-marker lifecycle — completed reclaim leaves no marker, a reclaimer killed mid-reclaim leaves a marker that later actors refuse on (with the `--force-unlock` pointer), and `--force-unlock` clears marker + lock together; concurrent-recovery — two simultaneous force-unlocks with a successor starting mid-recovery never delete the successor's ownership (byte-identity conditional removal).
- Pass-log fixtures, asserted against the `log_path` + `warnings` the summary reports (the component the model actually reads): default resolves to `<repo-root>/docs/reviews/code-review-<scope-tag>.md` (created on demand, correct from a subdirectory invocation); `--log-path` override echoed back honored; non-git invocation reports the cwd-fallback warning; pre-existing root logs left untouched — no migration, no rename.
- `tools/check-all.sh` green.

**Iterate-review:** YES (rationale: core execution code — composition, codex invocation, patch-marker check, embedded lens selection, golden-file fixtures)
**Status:** shipped (2026-08-10 — Kyle's sequencing call: the doc-bot dogfood acceptance item is **deferred, not waived**; it runs opportunistically with the next real doc-bot review instead of gating this project. Code acceptance was met via the 11-pass self-hosted iterate-review, three-lens APPROVE — pass log: `docs/reviews/code-review-branch-docs-runner-scripts-brief.md`. If the dogfood surfaces issues, they fold back as fixes under a fresh iterate-review.)

### Phase 2 — prune-state + auto-prune on convergence (~0.5 day)
**Deliverables:**
- `prune-state`: `--scope <hash>` targeted cleanup (invoked by the model at the convergence step — the pruner never infers convergence itself), age-based cleanup for abandoned runs (dry-run by default; destructive cleanup requires an explicit `--older-than` plus `--yes`), refuses any dir holding a live run lock, and `--force-unlock <scope>` as the explicit manual recovery path for ambiguous locks (live-pid ambiguity including PID reuse, malformed metadata).
- Convergence-step wiring in SKILL.md: on Converge the model invokes `prune-state --scope <hash> --yes` (or records the `--keep-state` decision); because a completed `run-pass` releases its lock, this prune is never blocked (fixture-pinned in Phase 1's lifecycle set).
- Fixtures: prune never touches anything outside `state/`, never touches pass logs; adversarial interleaving — a `run-pass` starting during an in-flight prune either fails fast on the prune's lock or survives with its state intact (nothing live is ever deleted); force-unlock of a genuinely live run — the displaced run detects token revocation, commits no summary (pre-revocation orphan artifacts remain inert and invisible to allocation and readers), and never unlinks the successor's lock.

**Acceptance:**
- A converged review leaves no state directory behind; an aborted run's state is removable by one `prune-state --older-than <n> --yes` invocation.
- Dry-run output lists exactly what would be deleted; nothing outside `state/` is ever touched, and a dir with a live run lock is never touched (both fixture-pinned).

**Iterate-review:** YES (rationale: deletion code warrants review)
**Status:** reviewed (2026-08-10 — iterate-review converged after 6 passes in loop mode, Kyle-confirmed at the max-pass guardrail: 23 findings, 21 incorporated across 6 fold commits, 1 folded with corrected premise, 1 disputed HIGH accepted by Kyle (rmdir TOCTOU — ENOTEMPTY makes the window harmless); security lens APPROVE at pass 6. Pass log: `docs/reviews/code-review-commit-13c9e0c.md`. The convergence prune then ran for real on the review's own 42-entry state dir — Phase 2's first live use.)

### Phase 3 — iterate-plan port + parity fixtures (~1 day)
**Deliverables:**
- `iterate-plan/bin/` with the same runner shape adapted to plan-review composition (steps 6–10's SHARED MACHINERY equivalents).
- Explicit shared-vs-adapted boundary: designated shared helper modules (composition assembly, invocation-flag constants, structural validation + patch-marker scan, lock/atomic-publication lifecycle) are duplicated byte-identically and checked by content hash in `tools/check-parity.py`; adapted parts (lens selection, matched-context composition, log/fold specifics) are covered by per-skill behavioral fixtures, not byte parity.
- `iterate-plan/SKILL.md` rewired; README updated with the second allowlist line.

**Acceptance:**
- A full iterate-plan review runs under its own single allowlist rule with zero other Bash permission prompts — required, not best-effort (dogfood: the first real plan review after Phase 3 lands).
- Extended parity fixture green; both skills' fixtures green; CHANGELOG finalized.

**Iterate-review:** YES (rationale: duplicated bin/ must not drift)
**Status:** not started

## Acceptance criteria

- [ ] A full multi-pass `iterate-review` on a real repo runs with **one documented allowlist rule and zero other Bash permission prompts** end to end (checkpoints and file-edit approvals excluded by design — see "The single-rule permission model").
- [ ] A full `iterate-plan` review runs under its own single allowlist rule with zero other Bash permission prompts (unconditional; mirrors the iterate-review criterion).
- [ ] Composition golden-file fixtures prove byte-deterministic input assembly.
- [ ] Patch-marker rejection is exercised by fixtures at both command boundaries: standalone `run-lens` (malformed response → exit 2) and `run-pass` (completed pass, `status: rejected` in the summary, exit 0).
- [ ] Pass-log behavior fully pinned: default name + `docs/reviews/` location, `--log-path` override, and pre-existing root logs untouched.
- [ ] Lens selection has exactly one implementation, and all 14 selection fixtures pass against it.
- [ ] A converged run leaves no state directory behind (model-invoked `prune-state --scope` at the convergence step).
- [ ] The extended parity fixture passes with both skills' runners in place.
- [ ] `tools/check-all.sh` green; README documents the allowlist snippet(s) + Python floor; CHANGELOG entry per repo convention.
- [ ] No hardcoded user paths anywhere in `bin/`; runners work via symlink and via plain copy, on macOS and Linux — verified by the install/platform matrix: macOS = authoring machine, **including allowlist-rule matching demonstrated in both layouts** (symlink layout via the dogfood review; copy layout via a copied-directory install with its corresponding rule, one scripted review step run without prompts); Linux = `python:3.9-slim` container running `tools/check-all.sh` + runner fixtures in both layouts (Docker verified available on the authoring machine, server 29.6.2). Rule matching on Linux is not separately demonstrable in a container (no harness there) and is covered by the path-prefix argument stated in Who / Use cases.

## Risks

### R1 — Decision logic creeps into the runners
The convenient place to add "just one more rule" is the code that already runs. Once the runner starts making merge or verdict calls, the model/runner boundary — and the reviewability story — collapses.
**Mitigation:** the contract sentence lands in both SKILL.mds and the parity fixture checks for its presence; review lenses are pointed at the boundary explicitly in Phases 1 and 3.

### R2 — Promoted lens selection drifts from `lenses/README.md` prose
The rules live in prose; the implementation lives in `run-pass`. A prose edit that forgets the code (or vice versa) reintroduces exactly the two-implementations problem this plan removes.
**Mitigation:** the 14 selection fixtures run against the promoted implementation in `tools/check-all.sh`; `lenses/README.md` gains a pointer stating the code is normative and fixture-pinned.

### R3 — The allowlist rule doesn't match on other users' machines
Path variance (copy vs. symlink installs, non-default skill locations) could make the README snippet silently not match, recreating the prompt storm for exactly the audience (public users) least equipped to debug it.
**Mitigation:** README shows the snippet with an explicit "your path here" placeholder and both install layouts; acceptance includes demonstrating the rule matches in **both** layouts on the authoring machine (symlink via dogfood, copy via a copied-directory install with its corresponding rule); runners derive paths from their own location so the rule's prefix is the only path that matters, and that prefix argument is OS-independent.

### R4 — Codex CLI flag drift
The invocation flags move from prose into code. If the codex CLI changes flags, the failure now happens inside a runner instead of in front of the model.
**Mitigation:** flags live in one named constant per skill; `run-lens` surfaces the raw codex stderr in its JSON summary on failure so the model (and human) see the real error; the read-only sandbox flags are asserted present by a fixture.

### R5 — Auto-prune deletes state someone wanted
Post-convergence response JSONs are occasionally useful for debugging a bad merge.
**Mitigation:** prune fires only when the model invokes it at a converged checkpoint (the pass log retains the full HISTORICAL record); `--keep-state` escape hatch on the convergence step; `prune-state` is dry-run by default and all destructive cleanup requires `--yes` — targeted convergence cleanup via `--scope <hash>`, while age-based abandoned-run cleanup additionally requires an explicit `--older-than`.

### R6 — Python floor violations sneak in
A 3.11-ism in a runner breaks the stated 3.9 floor on someone else's machine.
**Mitigation:** `tools/check-all.sh` runs the runner test suite; the Linux container check runs it on an actual 3.9 interpreter (`python:3.9-slim`), which catches 3.10+ syntax mechanically; runners fail fast below the floor via a `sys.version_info` check; floor stated in README and in each script's docstring.

## Sequencing decision

`iterate-review` first — that's where the measured pain is (30 invocations/review vs. iterate-plan's lower pass volume), and the port in Phase 3 is cheaper once the pattern is proven. Each phase is independently shippable; the skills are in daily use, so landing Phase 1 alone already removes most of the prompt burden. The brief (`docs/runner-scripts-brief-2026-08-06.md`, currently on the `docs/runner-scripts-brief` branch) merges with or before Phase 0 so the plan's evidence trail is in-repo.

## Open questions

(none at this time — Q1–Q3 were answered unanimously by both lenses on pass 1 and folded into Stack decisions; see the pass 1 HISTORICAL block.)

## Out of scope

- **Windows support** — neither skill has run there; the permission-rule story differs. Revisit on demand.
- **iterate-review v2 plan-bound mode** (`--plan`/`--phase`, auto-Status updates) — separate deferred initiative; the runners neither help nor hinder it.
- **Changing lens content or selection rules** — this plan relocates the selection implementation; the rules themselves are untouched.
- **A `create-plan` runner** — no per-pass shell exists there.
- **Packaging (`pyproject`, pip install)** — the skills install by symlink/copy; packaging is complexity without a consumer.
- **Harness-level permission changes** — the plan works entirely within Claude Code's existing allowlist semantics.

## Closeout

- [ ] Append entry to your project's milestones / changelog index (if you
  keep one): one paragraph covering what shipped, the ship commit, key
  delta, and a link back to the archived plan path.
- [ ] Update memory and/or project notes: mark plan completed, link to
  ship commits, update any related context files this plan touched.
- [ ] Update any backlog / priority queue: remove if it was queued, or
  mark closed inline.
- [ ] Move plan to archive: `git mv docs/<plan>.md docs/archive/<plan>.md`.
- [ ] Final commit with a "shipped" message referencing this plan.

## References

- Plan brief (evidence + open questions, written by the session that felt the pain): `docs/runner-scripts-brief-2026-08-06.md` (branch `docs/runner-scripts-brief` until merged)
- Real pass logs (workload + format examples): `Adminformatics/doc-bot` repo root, `code-review-*.md` — especially `code-review-editor-write-path-phase-0.md` (10 passes)
- The accumulated-rules artifact: doc-bot `.claude/settings.local.json` history (git-ignored; the 89→49 cleanup happened 2026-08-06 in-session); the `Bash(codex -a never exec *)` prefix rule that motivated the single-rule design
- State-dir sprawl: `~/.claude/skills/iterate-review/state/` on the authoring machine
- Lens selection reference implementation + 14 fixtures: `iterate-review/examples/selection/check-selection.py`, `lenses/README.md`
- SHARED MACHINERY parity contract: `iterate-review/SKILL.md` (step 9 intro) ↔ `iterate-plan/SKILL.md` steps 6–10; checker `tools/check-parity.py`
- Overall expansion state: memory `trinity-expansion`

## Review checkpoints

<!-- TOOLING-MAINTAINED by iterate-review for multi-phase plans (v1: by hand). -->

| Phase | Iterate-review | Status | Last pass | Pass log |
|-------|----------------|--------|-----------|----------|
| Phase 0 | NO  | n/a | n/a | n/a |
| Phase 1 | YES | reviewed (converged, 3-lens APPROVE) | Pass 11 — 2026-08-07 | [code-review-branch-docs-runner-scripts-brief.md](reviews/code-review-branch-docs-runner-scripts-brief.md) |
| Phase 2 | YES | reviewed (converged at cap, Kyle-confirmed; 1 disputed HIGH accepted) | Pass 6 — 2026-08-10 | [code-review-commit-13c9e0c.md](reviews/code-review-commit-13c9e0c.md) |
| Phase 3 | YES | not started | — | — |

## Pre-flight review pass (Opus, YYYY-MM-DD) [HISTORICAL]

<!-- OPTIONAL self-review by Opus before execution. Delete if skipped. -->

<!-- TOOLING-MAINTAINED by iterate-plan. Each pass appends a new
"## Codex review pass N — answers (DATE) [HISTORICAL]" section. -->

## Codex review pass 1 — answers (2026-08-06) [HISTORICAL]

### Verdict
REVISE (worst-of; architect REVISE, product-manager REVISE, no FAILED lenses)

### Findings
1. **Zero-prompt promise contradicts the stated remaining prompt surface** — HIGH · lens: product-manager: goal/acceptance said "zero other permission prompts" while TL;DR, the use case, and the permission-model section all acknowledged remaining prompts — an independent tester couldn't tell what success means.
   → Opus: incorporated — promise redefined precisely everywhere as "zero **Bash** permission prompts beyond the single allowlist rule"; checkpoints and file-edit approvals explicitly excluded by design, with the file-edit permission assumption stated in "The single-rule permission model."
2. **State namespace has no collision or interrupted-write protocol** — HIGH · lens: architect: concurrent same-scope runs, retried passes, or interruption mid-write could overwrite or expose partial artifacts; prune treats the dir as a deletion unit.
   → Opus: incorporated — new "State lifecycle & result contract" subsection: exclusive `run.lock` (O_EXCL, pid, stale-reclaim), atomic tmp+`os.replace()` publication, pass-number allocation under the lock, prune refuses live-locked dirs; lifecycle fixtures added to Phase 1 acceptance.
3. **Partial-failure semantics between runner and model underspecified** — HIGH · lens: architect: no completion policy for one-lens-fails, parent interruption, or summary serialization failure.
   → Opus: incorporated — result contract defined: `pass-N.summary.json` published atomically last; exit 0 ⇔ summary published; per-lens `ok|failed|rejected` with exit code + stderr tail; absent summary = aborted pass; all futures awaited, no sibling cancellation.
4. **Iterate-plan user outcome lacks top-level acceptance coverage** — MEDIUM · lens: product-manager: "if timing allows" made the Phase 3 dogfood optional; parity alone can't prove the end-to-end outcome.
   → Opus: incorporated — Phase 3 dogfood made required; unconditional top-level acceptance criterion added mirroring the iterate-review one.
5. **Cross-platform/install criterion needs an explicit test matrix** — MEDIUM · lens: product-manager: 4-cell macOS/Linux × symlink/copy promise had no defined evidence.
   → Opus: incorporated — matrix defined in Acceptance criteria: macOS on the authoring machine (dogfood + copied-dir fixture run), Linux via `python:3.9-slim` container running the check suite in both layouts (Docker availability verified in-fold).
6. **Repository-root discovery is an undefined dependency** — MEDIUM · lens: architect: `docs/reviews/` default needs the invoking repo's root; only skill-root discovery was specified.
   → Opus: incorporated — `git rev-parse --show-toplevel` from cwd (handles subdirectories + worktrees), non-git fallback to cwd with a warning; tests added to Phase 1 deliverables; kept distinct from skill-root resolution.
7. **Aborted-state cleanup underspecified until retention policy settled** — MEDIUM · lens: product-manager: Q2 controlled the meaning of a stated MVP capability.
   → Opus: incorporated — Q2 resolved (see below); prune policy sharpened: dry-run default, destructive cleanup requires explicit `--older-than` + `--yes`, 30 days is a README example not policy; Phase 2 acceptance updated.
8. **Parity checking scope too vague for duplicated executable code** — MEDIUM · lens: architect: "runner behavior" didn't say what must stay identical vs what legitimately differs.
   → Opus: incorporated — shared-vs-adapted boundary defined in Phase 3: designated shared helper modules byte-identical (content-hash check in `check-parity.py`); adapted parts (lens selection, matched-context, log/fold specifics) covered by per-skill behavioral fixtures.

### Plan corrections applied
- Stack decisions — Python floor: "covers macOS system Python" claim replaced — 3.9+ framed as an installation prerequisite (macOS ships no interpreter; Xcode CLT provides 3.9.6) with a fail-fast `sys.version_info` check.
- TL;DR + "The single-rule permission model": "zero further prompts" wording made consistent (Bash permission prompts vs intentional interactions).
- Phase 3 acceptance: "if timing allows" removed; dogfood verification is required.

### Open-question answers
1. **Q1** (both lenses, agreeing) — no hidden retry: `run-lens` reports failure immediately with exit code + stderr tail; retry judgment stays with the model's `FAILED` rules; a bounded explicit `--retry` flag only if dogfooding shows transient failures are common. Folded into Stack decisions.
2. **Q2** (both lenses, agreeing) — destructive cleanup requires an explicit `--older-than`; dry-run stays the default; README documents 30 days as an example, not policy. Folded into Stack decisions + Phase 2.
3. **Q3** (both lenses, agreeing) — composition inputs are pruned with the rest of converged state; `--keep-state` retains everything (inputs included) when an audit/debug trail is needed. Folded into Stack decisions.

### New questions Codex raised
- Does "zero other permission prompts" exclude intentional human checkpoints and assume file-edit operations are separately authorized? — needs_human (lens: product-manager): **label overridden to resolvable_in_fold** — the intent is derivable from the source brief ("the prompts that remain are the ones worth reading") and the skills' own hard rules (checkpoints are mandatory by design, so "zero checkpoints" cannot be the intent). Resolved by finding 1's incorporation: the promise now states its own boundary. Flagged here for Kyle to veto at the Converge checkpoint.
- What verification evidence is required for the Linux portions of the acceptance matrix? — needs_human (lens: product-manager): **resolved via lookup + design decision** — Docker verified available on the authoring machine (server 29.6.2), so Linux evidence = `python:3.9-slim` container running `tools/check-all.sh` + runner fixtures in both install layouts. A concrete, cheap, observable default; Kyle can raise/lower the bar at Converge.

### Lens run summary
- architect: REVISE · product-manager: REVISE

## Codex review pass 2 — answers (2026-08-06) [HISTORICAL]

### Verdict
REVISE (worst-of; architect REVISE, product-manager REVISE, no FAILED lenses)

### Findings
1. **Rejected-response exit semantics contradict the pass result contract** — HIGH · lens: both (architect HIGH + product-manager MEDIUM, merged): "malformed response → non-zero exit" conflicted with run-pass's exit-0-on-published-summary contract; the criterion never named the command under test.
   → Opus: incorporated — separate exit contracts defined per command in State lifecycle (standalone `run-lens`: 0 valid / 2 rejected / 1 orchestration error; `run-pass`: published-summary contract, rejection is data); patch-marker fixtures now assert both boundaries; Phase 1 acceptance and the top-level criterion name the command explicitly.
2. **Standalone `run-lens` can bypass `run-pass` lifecycle ownership** — HIGH · lens: architect: standalone invocation could write `pass-N.*` artifacts without the lock/allocation protocol, reopening the collision failure mode pass 1 closed.
   → Opus: incorporated — standalone `run-lens` writes only to an isolated `state/<scope-hash>/debug/` namespace (timestamped, no lock, never `pass-N.*`); prune sweeps it freely; overlap fixture added to Phase 1 acceptance.
3. **Public-install zero-prompt outcome not verified across the promised matrix** — HIGH · lens: product-manager: the matrix verified runner execution but not allowlist-rule matching per combination; R3 narrowed rule verification to symlink-on-authoring-machine only.
   → Opus: incorporated — promise explicitly scoped in Who / Use cases (rule matching is an OS-independent string-prefix behavior; the variable is the installed path); acceptance now demonstrates rule matching in **both** install layouts on macOS and states why a container can't demonstrate harness rule-matching on Linux; R3 mitigation updated to match.
4. **PID-only stale-lock detection can misclassify reused PIDs** — MEDIUM · lens: architect: a reused pid makes a dead lock look permanently live, blocking reviews and pruning of that scope.
   → Opus: incorporated — lock records pid + timestamp + owner process name; auto-reclaim only when pid is dead; alive-but-wrong-name or malformed metadata → *suspect*, runners refuse and point at `prune-state --force-unlock <scope>`; no timeout-based stealing; both cases fixture-pinned.
5. **Pass-log goal only partially covered by acceptance** — MEDIUM · lens: product-manager: default filename/location, `--log-path` override, and leave-existing-logs-alone had no observable completion conditions.
   → Opus: incorporated — pass-log fixture set added to Phase 1 acceptance (default path from subdirectory invocation, override honored, pre-existing root logs untouched) and mirrored in the top-level criteria.
6. **"One command shape" ambiguous vs the wildcard rule** — LOW · lens: product-manager: the rule authorizes three executables; "one command shape" and "one allowlist line" aren't the same metric.
   → Opus: incorporated — product metric unified to "one documented allowlist rule" in Goals, Phase 1 acceptance, and the top-level criteria, with a note that the rule covers all three `bin/` executables.

### Plan corrections applied
- Phase 1 acceptance + top-level Acceptance criteria: patch-marker criterion now names the executable under test at each boundary (both lenses filed this; applied once).

### Open-question answers
(none raised — Open questions was already "(none at this time)")

### New questions Codex raised
(none)

### Lens run summary
- architect: REVISE · product-manager: REVISE

## Codex review pass 3 — answers (2026-08-06) [HISTORICAL]

### Verdict
REVISE (worst-of; architect REVISE, product-manager APPROVE, no FAILED lenses)

### Findings
1. **Converged-state detection has no valid source of truth** — HIGH · lens: architect: Phase 2's "converged-state detection" would force `prune-state` to duplicate model-owned merge/verdict logic or parse the pass log, violating the plan's own boundary.
   → Opus: incorporated — the pruner never infers convergence. The model (the convergence authority, at the checkpoint) explicitly invokes `prune-state --scope <hash> --yes` on Converge; "converged-state detection" removed from Phase 2 deliverables; the Prune-policy stack decision rewritten to state the control flow.
2. **Lock release and cleanup semantics are missing; process-name identity is weak** — HIGH · lens: architect: nothing said when `run.lock` is released, so convergence-time pruning could be blocked by a completed run's own lock; `comm`-based identity can't reliably detect PID reuse (generic `python3`).
   → Opus: incorporated — lock duration defined (held per `run-pass` invocation, released in a `finally` block on all normal/handled paths; a completed run leaves no lock, fixture-pinned), and the stale policy no longer claims PID-reuse *detection*: auto-reclaim only on dead pid; **any** live pid is ambiguous → refuse + manual `--force-unlock`; the recorded name is diagnostic only.

### Plan corrections applied
- Acceptance criteria: redundant pass-log clause removed from the converged-state bullet (fully pinned in its own bullet) — product-manager correction.

### Open-question answers
(none raised)

### New questions Codex raised
(none)

### Lens run summary
- architect: REVISE · product-manager: APPROVE

## Codex review pass 4 — answers (2026-08-06) [HISTORICAL]

### Verdict
REVISE (worst-of; architect REVISE, product-manager APPROVE, no FAILED lenses)

### Findings
1. **Pass-log destination has no path across the model/runner boundary** — HIGH · lens: architect: the summary schema carried no resolved `log_path` and no field for the promised non-git warning, so the model (sole log writer) would have to re-derive repo-root/default-path logic — a boundary leak — and the Phase 1 pass-log fixtures were disconnected from the component the model reads.
   → Opus: incorporated — summary schema extended with `log_path` (runner-resolved destination: `docs/reviews/` default or echoed `--log-path` override) and `warnings` (e.g. non-git cwd fallback); the runner resolves and reports, the model appends — never the reverse; Phase 1 pass-log fixtures now assert against the summary's `log_path`/`warnings` fields.

### Plan corrections applied
- Risk R5 mitigation: destructive-cleanup gating corrected — all deletion requires `--yes`; `--older-than` gates only age-based abandoned-run cleanup, not the targeted convergence `--scope` flow (product-manager correction).

### Open-question answers
(none raised)

### New questions Codex raised
(none)

### Lens run summary
- architect: REVISE · product-manager: APPROVE

## Codex review pass 5 — answers (2026-08-06) [HISTORICAL]

### Verdict
REVISE (worst-of; architect REVISE, product-manager APPROVE — clean, no findings, no corrections; no FAILED lenses)

### Findings
1. **Lock and prune protocols contain TOCTOU races** — HIGH · lens: architect: two reclaimers can both observe a dead pid and the slower one can unlink a successor's freshly created lock; `prune-state` can check-then-delete while a new `run-pass` concurrently creates its lock and artifacts — either race breaks the exclusive-execution and never-delete-live-state guarantees.
   → Opus: incorporated — one ownership protocol now binds every actor that mutates a scope (run start, stale reclaim, prune): reclaim goes through an intermediate `run.lock.reclaim` (`O_EXCL`) + byte-identical re-verification so a successor's lock is never touched, and prune acquires the scope's own `run.lock` (role=prune) for the entire deletion, unlinking it last, with the rmdir-fails-non-empty window handled by leave-intact-and-report. Adversarial fixtures added to Phase 1 (simultaneous reclaimers) and Phase 2 (run-start vs. prune interleaving).

### Plan corrections applied
(none)

### Open-question answers
(none raised)

### New questions Codex raised
(none)

### Lens run summary
- architect: REVISE · product-manager: APPROVE

## Codex review pass 6 — answers (2026-08-06) [HISTORICAL]

### Verdict
REVISE (worst-of; architect REVISE, product-manager APPROVE; no FAILED lenses). Loop halted after this pass: max-pass budget exhausted **and** non-convergence guardrail (HIGH+MEDIUM count 1 → 1 → 1 across the last two transitions).

### Findings
1. **Force-unlock can create concurrent owners and delete a successor's lock** — HIGH · lens: architect: if the recorded pid belongs to a genuinely live `run-pass`, `--force-unlock` displaces it without fencing — the displaced run keeps publishing and its unconditional `finally` unlink can remove the successor's lock; the reclaim path's byte-identity check doesn't cover the manual-unlock path.
   → Opus: incorporated — lock metadata gains an unforgeable random ownership token; every mutating actor re-verifies its token before publishing any artifact and before releasing (the `finally` unlink is conditional on token match); `--force-unlock` revokes the token so a displaced live run aborts without publishing or unlinking. Adversarial fixture (force-unlock of a live run + successor start) added to Phase 2.

### Plan corrections applied
- Acceptance criteria, first checklist item: "one pre-approved command shape" → "one documented allowlist rule," completing the pass-2 metric unification (product-manager correction).

### Open-question answers
(none raised)

### New questions Codex raised
(none)

### Lens run summary
- architect: REVISE · product-manager: APPROVE

## Codex review pass 7 — answers (2026-08-06) [HISTORICAL]

### Verdict
REVISE (worst-of; architect REVISE, product-manager APPROVE — 5th consecutive clean APPROVE; no FAILED lenses). Manual single-pass continue after the pass-6 halt; user-set stop-and-reassess condition met after this fold.

### Findings
1. **Force-unlock cannot guarantee the displaced run published nothing** — HIGH · lens: architect: token checks before individual publications can't retract artifacts staged before revocation, so "publishes nothing" was unachievable as worded; a successor could see orphan `pass-N.*` artifacts as a consumed/partial pass; the summary-last protection was an unstated reader invariant.
   → Opus: incorporated — pass-level visibility contract made explicit: **a pass exists iff its summary exists**; readers and `prune-state` discover passes only via summaries; orphan artifacts are inert, never folded; allocation takes the max over all `pass-N.*` names so orphans are never overwritten; the summary (published last under a valid token) is the single commit point; force-unlock guarantee narrowed to "commits no summary" with orphans explicitly permitted and swept by prune.

### Plan corrections applied
- State lifecycle ownership-token bullet + Phase 2 fixture: "publishes nothing" claims aligned with the pass-visibility protocol (no-summary-commit + inert orphans) — architect correction.

### Open-question answers
(none raised)

### New questions Codex raised
(none)

### Lens run summary
- architect: REVISE · product-manager: APPROVE

## Codex review pass 8 — answers (2026-08-06) [HISTORICAL]

### Verdict
REVISE (worst-of; architect REVISE, product-manager APPROVE — 6th consecutive clean APPROVE; no FAILED lenses). Manual single-pass continue.

### Findings
1. **Reclaim marker has no cleanup or stale-recovery lifecycle** — HIGH · lens: architect: `run.lock.reclaim` had no removal or crash-recovery story; an orphaned marker (reclaimer killed mid-reclaim) would block every future reclaim of the scope indefinitely.
   → Opus: incorporated — marker lifecycle defined so the recovery recursion *terminates by refusing to recurse*: conditional `finally` removal on all normal/handled paths; an orphaned marker (dead pid or malformed metadata) gets **no** automatic cleanup and no third coordination file — actors refuse and point at `prune-state --force-unlock <scope>`, which clears marker and lock together under its token-revoking authority; live-pid marker = reclaim in progress, back off. Fixtures added: completed reclaim leaves no marker; killed-mid-reclaim → refuse + recovery pointer; force-unlock clears both.

### Plan corrections applied
(none)

### Open-question answers
(none raised)

### New questions Codex raised
(none)

### Lens run summary
- architect: REVISE · product-manager: APPROVE

## Codex review pass 9 — answers (2026-08-06) [HISTORICAL]

### Verdict
REVISE (worst-of; architect REVISE, product-manager APPROVE — 7th consecutive clean APPROVE; no FAILED lenses). Manual single-pass continue.

### Findings
1. **Force-unlock remains unsynchronized under concurrent recovery** — HIGH · lens: architect: two simultaneous `--force-unlock` attempts observing the same ambiguous state could race — after one removes the old lock and a successor acquires a fresh one, the slower recovery could delete the successor's ownership; the reclaim marker can't serialize this because force-unlock must also recover an orphaned marker.
   → Opus: incorporated — force-unlock now uses the same byte-identity conditional-removal rule as automatic reclaim: dry-run prints the inspected state, every unlink re-reads immediately before acting and proceeds only on byte-identical content (unique tokens make collisions impossible, so a successor's lock never passes); concurrent recoveries self-serialize (one winner per unlink, losers refuse on mismatch/absence); no new coordination file. Adversarial fixture added to Phase 2: two concurrent force-unlocks + successor starting mid-recovery.

### Plan corrections applied
(none)

### Open-question answers
(none raised)

### New questions Codex raised
(none)

### Lens run summary
- architect: REVISE · product-manager: APPROVE
