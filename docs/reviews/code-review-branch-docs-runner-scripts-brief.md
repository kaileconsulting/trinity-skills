# Code Review — branch-docs-runner-scripts-brief

## Pass 1 — 2026-08-06 17:52 [HISTORICAL]

**Scope:** branch · **Diff size:** 3763 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Lenses:** senior-dev, security, qa

First review executed through the Phase 1 runners themselves: one `run-pass` invocation, zero Bash permission prompts beyond the single allowlist rule. Selection (deterministic, `bin/selection_engine.py`): senior-dev (floor), security (crypto-terms content regex — matched the lens file's own regex prose in the diff), qa (response-pattern content regex — matched plan prose).

### Findings

1. **Explicit `--pass-num` can overwrite committed pass artifacts** — HIGH · lens: senior-dev, security, qa (co-reported): `run-pass` used a caller-supplied pass number unchecked; a repeated/stale/negative value could replace published inputs, responses, and even `pass-N.summary.json`, violating the never-overwrite invariant and making the summary commit point mutable.
   → Opus: incorporated — explicit pass numbers are validated at the argument boundary (must be ≥ 1) and refused under the scope lock if **any** `pass-N.*` artifact exists ("published pass state is immutable"; omit the flag to allocate, or prune first). `pass_number_in_use()` added to `runner_shared.py`. Fixtures: repeated `--pass-num` refused with bytes byte-identical; `--pass-num 0` rejected; allocation skips past used numbers.
2. **Codex responses bypassed atomic publication and ownership verification** — HIGH · lens: senior-dev, security, qa (co-reported): `--output-last-message` pointed at the final response path, so codex wrote the published artifact in place — a killed codex could leave a readable partial, and a force-unlocked run's still-writing child could clobber a successor's artifact.
   → Opus: incorporated — codex now writes to a run-unique staging path (`.stage-<pid>-<rand>.tmp`); the runner re-verifies the ownership token after codex completes and only then `os.replace()`s the staged response into place. Fixtures: killed codex leaves no readable final response (staging only, no summary); ownership revoked mid-codex → run aborts non-zero with no summary and no published response, revoking lock untouched.
3. **Exit contract violable while printing stdout** — MEDIUM · lens: senior-dev: `run-pass` re-read the summary file *after* releasing the lock; a concurrent prune in that window would exit 1 despite a published summary, breaking exit-0 ⇔ summary-published.
   → Opus: incorporated — the committed summary bytes are captured while still holding the lock; stdout emission can no longer fail on post-release cleanup.
4. **Structural rejection misreported as patch-marker violation** — MEDIUM · lens: senior-dev (as correction), qa (as finding; merged): SKILL.md step 11's abort message always claimed patch-shaped output even when `status: rejected` was a structural failure.
   → Opus: incorporated — step 11 now reports the actual cause from the summary's `reject_reasons`, distinguishing patch-marker rejection from structural validation failure.

### Code corrections applied

- `iterate-review/bin/run-pass` `--pass-num` — accepted 0/negative values → `positive_int` argparse type (senior-dev; folded into finding 1's fix).
- `iterate-review/SKILL.md` step 11 rejected-response message — folded into finding 4.

### New questions Codex raised

(none — all three lenses returned empty `new_questions`)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-06 17:45; head SHA `bd98f4666e4b48f9ea42f1ad792f2887f57d20a8`.

## Pass 2 — 2026-08-06 18:02 [HISTORICAL]

**Scope:** branch · **Diff size:** 3961 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Lenses:** senior-dev, security, qa

### Findings

1. **Ownership verification separated from mutation by TOCTOU windows** — HIGH · lens: senior-dev: token fencing was read-check-then-mutate — a `--force-unlock` landing between `release()`'s token check and its `os.unlink` could delete a successor's lock, and a revocation between `verify()` and `atomic_publish`/`os.replace` still let a displaced run commit a summary or response.
   → Opus: incorporated — every conditional lock mutation now runs inside one critical section: `_locked_mutation()` takes an `fcntl.flock` on the lock file's inode, confirms the path still names that inode (unlink+recreate = different inode), re-reads content, and mutates only if the predicate accepts — all under the flock. `release()`, stale-reclaim's unlink, marker removal, and `verify_and()` (which fences the actual publication callback) all go through it; `revoke_token()` (the force-unlock primitive prune-state will use) takes the same flock, so revocation either lands before a fenced publication (refused) or blocks until it completes (publish-before-revoke linearization). Fixtures: revocation blocks until the fenced publication completes; post-revocation publication refuses; post-revocation release leaves the revoked lock intact.
2. **Pre-approved runner usable to exfiltrate arbitrary local files** — HIGH · lens: security: `--diff`/`--intent`/`--log-path` accepted any host path; since the runner is covered by a standing allowlist rule and feeds file contents to the network-backed codex process, an injected invocation could read sensitive files with no human gate.
   → Opus: incorporated — `ensure_trusted_path()`: every runner-readable path must realpath-resolve (symlinks and traversal included) inside the invoking repo root or the skill state root; `--log-path` overrides must stay inside the repo root. `state/inbox/` added as the conventional model→runner handoff area; SKILL.md step 9 documents the boundary and its rationale. Fixtures: outside-path refused, symlink escape from inside the repo refused, outside `--log-path` refused, `run-lens` enforces identically.
3. **Structural-rejection path unexercised** — MEDIUM · lens: qa: only the patch-marker rejection mode had fixtures; a regression could restore pass 1's misreporting undetected.
   → Opus: incorporated — new `structural` fake-codex mode (valid JSON, missing required arrays); fixtures assert `run-lens` exit 2 with a structural (not patch-marker) reason and `run-pass` carrying structural `reject_reasons` as data with exit 0.

### Code corrections applied

(none filed this pass)

### New questions Codex raised

(none — all three lenses returned empty `new_questions`)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-06 17:57; head SHA `59641af` (pass-1 fold commit).

## Pass 3 — 2026-08-06 18:10 [HISTORICAL]

**Scope:** branch · **Diff size:** 4235 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Lenses:** senior-dev, security, qa

Inputs handed off through the new `state/inbox/` boundary introduced by the pass-2 fold.

### Findings

1. **Default pass-log path escapes the trusted boundary through a symlink** — HIGH · lens: senior-dev, security, qa (co-reported): only an explicit `--log-path` was boundary-checked; the *default* `docs/reviews/…` path went straight to `read_prior_passes()`, so a repo-controlled symlink there could pull out-of-repo file contents into the codex prompt.
   → Opus: incorporated — both CLIs now pass the resolved log path (default or override) through `ensure_trusted_path()` before any read; the realpath'd result is what feeds `scope_hash` and PRIOR PASSES. Fixture: symlinked default log → refused.
2. **Standalone `--lens` accepts path-traversing identifiers** — HIGH · lens: security, senior-dev (co-reported): `run-lens` interpolated an arbitrary id into `lenses/<id>.md` and the debug artifact names — `../` components could read Markdown outside `lenses/` and write artifacts outside `debug/`.
   → Opus: incorporated — `run-lens` validates the id against `load_lenses()` (same rule as `run-pass --lenses`), and `read_lens_record()` rejects separator/traversal components outright as defense in depth. Fixture: `--lens ../evil` → refused.
3. **Summary publication could still exit non-zero after committing** — MEDIUM · lens: senior-dev: the post-publish `read_text()` could fail (I/O error, not just the prune race pass 1 fixed), breaking exit-0 ⇔ summary-published.
   → Opus: incorporated — `publish_summary()` now returns the committed bytes alongside the path; `run-pass` never re-reads anything after publication.

### Code corrections applied

(none filed this pass)

### New questions Codex raised

(none — all three lenses returned empty `new_questions`)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-06 18:04; head SHA `6df0a27` (pass-2 fold commit).

## Pass 4 — 2026-08-06 18:20 [HISTORICAL]

**Scope:** branch · **Diff size:** 4316 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Lenses:** senior-dev, security, qa

### Findings

1. **Committed summary can still exit non-zero when stdout emission fails** — HIGH · lens: senior-dev: a broken stdout consumer (e.g. a pipe whose reader exited) raises `BrokenPipeError` from the post-commit `print`, so a published pass read as aborted — the third and final corner of the exit-0 ⇔ summary-published contract.
   → Opus: incorporated — the post-commit stdout emission is wrapped (`BrokenPipeError`/`OSError` swallowed, stdout pointed at devnull to avoid a shutdown re-raise); the summary on disk is the source of truth. Fixture: `run-pass` with its stdout pipe pre-closed still exits 0.
2. **Standalone-overlap fixture didn't create the overlap it claimed to test** — MEDIUM · lens: qa: the fixture held a lock on scope `livescope` while running `run-lens` against scope `t9` — different directories, no live `run-pass` — so it could pass even if standalone handling regressed.
   → Opus: incorporated — fixture rewritten: a sleeping `run-pass` holds the lock on scope `live1`, standalone `run-lens` runs against the *same* scope mid-flight, asserting exit 0, debug/-only artifacts in that same scope dir (realpath-compared), and a byte-stable published `pass-N.*` set.

### Code corrections applied

(none filed this pass)

### New questions Codex raised

(none — all three lenses returned empty `new_questions`)

### Lens run summary

- senior-dev: REVISE · security: APPROVE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-06 18:13; head SHA `670d6c5` (pass-3 fold commit).
