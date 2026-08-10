# Code Review — commit-13c9e0c

## Pass 1 — 2026-08-10 10:03 [HISTORICAL]

**Scope:** commit 13c9e0c (Phase 2 — prune-state), standalone · **Diff size:** 856 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Lenses:** senior-dev, security, qa

### Findings

1. **Path validation is vulnerable to post-check replacement (TOCTOU)** — HIGH · lens: senior-dev: `resolve_scope_dir` validates once, then lock/deletion reopen by pathname; a component swapped for a symlink mid-operation could redirect deletion outside `state/`.
   → Opus: incorporated — deletion rewritten to dir_fd-relative traversal: the scope dir and every child directory are opened `O_NOFOLLOW|O_DIRECTORY`, files/links removed via `unlink(dir_fd=)` (a planted symlink is unlinked as a link, its target never entered). Boundary stated honestly in code: displacing a whole *real* directory into the walk requires rename rights inside the skill install — filesystem write access no argument to the pre-approved tool grants. Fixture: nested symlink to an outside dir; canary survives, scope fully removed.
2. **Valid JSON without `pid` crashes inspection (claimed KeyError DoS)** — HIGH · lens: security, qa (co-filed): `_pid_state` reads `parsed["pid"]` catching only ValueError/TypeError; `{}` would crash `describe_lock`/`force_unlock`, making a scope unrecoverable.
   → Opus: incorporated — **with the premise corrected**: the crash was never reachable — `runner_shared._read_lock` nullifies any JSON lacking `pid`/`token` before `_pid_state` sees it, verified by live repro before folding (`{}` → "MALFORMED lock", exit 0, all three paths). The suggested action was applied anyway because self-contained validation is better engineering: `_pid_state` now uses `.get()` and full type checks, with a fixture sweeping `{}`, `{"role":…}`, and mistyped pids across overview/`--scope`/`--force-unlock`.
3. **PID validation accepts values documented as malformed** — MEDIUM · lens: senior-dev: `int(parsed["pid"])` coerces numeric strings, truncates floats (1.9 → probes pid 1), accepts bools.
   → Opus: incorporated — pid must be exactly a positive JSON integer (bool excluded); anything else reads MALFORMED. Fixture covers float/string/bool variants (folded into the finding-2 sweep).
4. **Raw lock metadata can inject terminal control sequences** — MEDIUM · lens: security: force-unlock echoes raw lock bytes; a crafted lock could drive ANSI/OSC sequences into the operator's terminal at the recovery-decision moment.
   → Opus: incorporated — control characters escaped (`\xNN`) in the raw echo and in `describe_lock`'s untrusted `role` interpolation. Fixture: lock with embedded ESC/BEL; stdout carries no raw control bytes, escaped forms present.
5. **Partial force-unlock refusal path not behaviorally covered; diagnostic inaccurate** — MEDIUM · lens: qa: marker can be removed before the lock refuses; the old message said "nothing further touched," hiding the marker removal; only the primitive was tested.
   → Opus: incorporated — force-unlock now reports `removed:` and `refused:` per file. CLI-level adversarial fixture: hold `flock` on the lock, start force-unlock, swap lock content mid-flight, release — marker removal reported, lock refused with successor content intact, exit 1.

### Code corrections applied

- (none filed by any lens)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-10 09:55; head SHA `13c9e0c` (reviewing that commit's own diff; folds land as follow-up commits on `docs/runner-scripts-brief`).

## Pass 2 — 2026-08-10 10:12 [HISTORICAL]

**Scope:** commit series 13c9e0c^..HEAD (Phase 2 + pass-1 folds), standalone · **Diff size:** 1070 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Lenses:** senior-dev, security, qa

### Findings

1. **Force-unlock still has a scope-directory TOCTOU path escape** — HIGH · lens: senior-dev: pass 1's dir_fd hardening covered `delete_scope` but `force_unlock` still read and removed locks by re-traversed pathname.
   → Opus: incorporated — force-unlock now anchors to one `O_NOFOLLOW|O_DIRECTORY` descriptor: reads via fd-relative `_read_lock_at` (a symlinked lock is reported as SYMLINK, never followed or read, and `--yes` refuses), removals via `_locked_mutation`'s new `dir_fd` variant (basename-relative, `O_NOFOLLOW`, same flock+inode+byte-identity fences). Fixtures: symlinked `run.lock` → dry-run reports SYMLINK without leaking target content; `--yes` refuses with link and out-of-state target intact; primitive-level `dir_fd` refusal pinned.
2. **Dry runs omit directories and directory symlinks that `--yes` deletes** — HIGH · lens: qa: only files were printed, violating the "exactly what would be deleted" contract (a planted `debug` dir-symlink would be removed undisclosed).
   → Opus: incorporated — new `disclose()` lists every removable entry (real dirs marked with `/`, symlinks listed as entries) in both `--scope` and `--older-than` output; counts now say "entries". Fixture compares the disclosed set against what a confirmed prune removes, symlink target surviving.
3. **Lock metadata can still forge diagnostic lines (LF/tab excluded from sanitize)** — MEDIUM · lens: security, qa (co-filed): `[\x00-\x08\x0b-\x1f\x7f]` deliberately skipped `\n`/`\t`, so raw lock bytes or a JSON-escaped `\n` in `role` could inject fake `removed:`/`cleared:` records at the recovery-decision moment.
   → Opus: incorporated — sanitize now escapes all of `[\x00-\x1f\x7f]`; every diagnostic record is one unforgeable line, `out()` alone ends it. Fixtures: raw bytes embedding a fake `removed:` record render as one escaped line; a parsed `role` with a decoded newline stays single-line in the overview.

### Code corrections applied

- (none filed by any lens)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-10 10:07; head SHA `d9e6138`.

## Pass 3 — 2026-08-10 10:48 [HISTORICAL]

**Scope:** commit series 13c9e0c^..HEAD (Phase 2 + folds), standalone · **Diff size:** 1326 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Lenses:** senior-dev, security, qa

### Findings

1. **Age sweep can delete a scope that became fresh after candidate selection** — HIGH · lens: senior-dev: candidates were aged before locking; a run starting AND finishing in the scan-to-lock window left fresh, unlocked state the sweep would still delete. Real concurrent-use logic bug, no adversary required.
   → Opus: incorporated — `delete_scope` gains `only_if`, re-checked after lock acquisition; the sweep passes a freshness recheck via new `newest_content_mtime` (deliberately blind to the mtime bumps prune's own lock creation causes — dir mtime and the fresh `run.lock` — otherwise the sweep becomes a permanent no-op). Fixtures: backdated scope still swept (the no-op regression trap); `only_if=False` under the lock leaves content intact and no lock behind.
2. **Non-regular lock entries crash or hang every inspection/recovery path** — HIGH · lens: qa (HIGH) + security (MEDIUM), merged: a directory named `run.lock` crashed `_read_lock` (uncaught `IsADirectoryError`); a FIFO blocked inspection indefinitely — the documented recovery path becomes unusable exactly when needed.
   → Opus: incorporated — `runner_shared._read_lock` now opens `O_NONBLOCK`, verifies `S_ISREG` before reading, and classifies anything else as malformed; `_read_lock_at` does the same fd-relatively and reports `NOT A REGULAR FILE`; destructive modes refuse with the object untouched. Fixtures: directory and FIFO at `run.lock` across overview, targeted prune, and force-unlock — no crash, no hang, refusal pinned.
3. **Deletion errors misreported as successful new-run handoff** — MEDIUM · lens: senior-dev: `_delete_tree_fd` swallowed every `OSError`, so EACCES/EIO surfaced as "a new run owns it now", exit 0 — violating the exit contract's `1 = failed`.
   → Opus: incorporated — errno triage (`ENOENT`/`ENOTEMPTY`/`EEXIST` benign; everything else collected as `(entry, error)`); `delete_scope` returns a four-way outcome (`deleted|skipped|survived|failed`); both CLI paths report failing entries and exit 1, and the handoff message appears only when deletion was clean. Fixture: unwritable subdirectory → exit 1 naming the stuck entry, then succeeds once cleared.
4. **Filesystem-derived and argument-derived names echoed unsanitized** — MEDIUM · lens: security: scope/entry names (and the echoed `--force-unlock` argument) could carry control bytes into diagnostics — the pass-2 forgery vector through a different source.
   → Opus: incorporated — `sanitize()` applied at every print site interpolating scope names, entry names, or error strings. Fixture: scope named with embedded ESC containing a file with embedded LF — overview and dry run emit escaped forms only, and the scope remains deletable.

### Code corrections applied

- (none filed by any lens)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-10 10:23; head SHA `8aa5dfb` (pass-2 fold).
