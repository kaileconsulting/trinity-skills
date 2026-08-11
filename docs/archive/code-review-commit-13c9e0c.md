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

## Pass 4 — 2026-08-10 10:56 [HISTORICAL]

**Scope:** commit series 13c9e0c^..HEAD (Phase 2 + folds), standalone · **Diff size:** 1592 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Lenses:** senior-dev, security, qa

### Findings

1. **Targeted prune can delete a newly completed run selected after disclosure** — HIGH · lens: senior-dev: pass 3 gave the age sweep an under-lock freshness recheck, but `--scope` still deleted unconditionally — a run finishing between disclosure and lock acquisition lost undisclosed fresh state.
   → Opus: incorporated — exact-disclosure fence: the deletion runs under `only_if` comparing the under-lock entry set against the disclosed baseline (our own lock files excluded; vanished entries fine). Undisclosed entries → refuse with exit 1 and a re-disclose pointer. Fixtures: stale-disclosure wiring test (nothing deleted, no lock left) and clean re-run.
2. **Lock acquisition itself is pathname-based — the swap class reaches ScopeLock before fd anchoring starts** — HIGH · lens: security: `delete_scope` acquired via path, so a scope swapped for a symlink post-validation could make lock create/reclaim/release touch files outside `state/`.
   → Opus: incorporated — `ScopeLock` gains a `dir_fd` mode: create, read, reclaim, verify, and release all address `run.lock` by basename relative to an `O_NOFOLLOW|O_DIRECTORY` descriptor opened *before* any lock operation; `_read_lock` gains the same fd-relative variant. `run-pass` continues path-based (it creates its own state dir), pinned by the untouched Phase 1 fixtures. Fixture: descriptor taken, scope renamed away, symlink swapped in — the lock is created and released inside the anchored directory, never through the link.
3. **Interrupted age prune reports partial deletion as "skipped … never touched"** — HIGH · lens: qa: a force-unlock displacing an in-progress prune raised `LockError` after some removals, which the sweep reported as a skip — false reporting the skip-safety contract depends on.
   → Opus: incorporated — `delete_scope` now distinguishes acquire-time refusal (true skip, nothing touched — the only path that still reports skip) from mid-deletion revocation, which returns a `failed` outcome carrying an explicit "removal was PARTIAL" problem; both CLI paths exit 1 on it. Fixture: simulated mid-delete revocation — one entry gone, one surviving, PARTIAL reported, "skipped" absent.

### Code corrections applied

- (none filed by any lens)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-10 10:49; head SHA `d19037d` (pass-3 fold).

## Pass 5 — 2026-08-10 12:31 [HISTORICAL]

**Scope:** commit series 13c9e0c^..HEAD (Phase 2 + folds), standalone · **Diff size:** 1891 lines · **Verdict:** REVISE (worst-of; no FAILED lenses) · **Lenses:** senior-dev, security, qa

### Findings

1. **Destructive lock acquisition still coerces malformed pid values** — HIGH · lens: senior-dev: `ScopeLock.acquire` used `int(parsed["pid"])`, so metadata prune-state classifies as malformed was coerced (1.9 → probes pid 1) or crashed (non-numeric string → uncaught ValueError) exactly on the `--yes` path.
   → Opus: incorporated — shared `_lock_pid()` (exact positive JSON integer, bool excluded) now guards both the lock and reclaim-marker branches of `acquire`; malformed metadata refuses with the recovery pointer, never probes. `prune-state`'s `_pid_state` delegates to it — one validator. Fixtures: string/float/bool pids on `--scope --yes` refuse without coercion or traceback; malformed marker pid refuses as abandoned; force-unlock recovery then prunes clean.
2. **Concurrent age sweeps crash when a selected scope disappears** — HIGH · lens: qa: two `--older-than --yes` sweeps racing over the same candidates produced uncaught errors (and the fixture then caught what the fold missed twice: `openat` inside an unlinked directory returns EINVAL on APFS, and APFS keeps `st_nlink=2` on removed directories, so neither errno-matching nor link-count disambiguation works).
   → Opus: incorporated — vanished candidates are benign at every step: `newest_mtime` returns 0.0 for a missing dir, the sweep loop reports "already gone (concurrent cleanup)", `delete_scope` treats open-ENOENT as already-deleted, and an acquire-time OSError is disambiguated by whether the *pathname* still names the anchored inode (gone → deleted; different inode → survived, untouched; same inode → genuine error, raised). Fixture: two concurrent sweeps over 12 backdated scopes — no tracebacks, both exit 0, all swept; verified stable across six suite runs.
3. **Final scope removal abandons the anchored descriptor** — MEDIUM · lens: senior-dev: the closing `os.rmdir(state_dir)` was pathname-based — a new real directory swapped in at the name could be removed despite never being disclosed.
   → Opus: incorporated — final removal is identity-fenced while the descriptor is still open: rmdir only if the pathname still names the anchored inode; otherwise the outcome is `survived` and the replacement is left alone. Survived message updated to name both causes (refilled vs displaced). Fixture: rename-plus-replace during deletion — replacement intact, outcome survival.
4. **Refusal diagnostics emit unsanitized scope paths** — MEDIUM · lens: security: `PruneError`/`LockError` texts and open-failure messages interpolated raw paths, so a control-byte scope name could inject via the refusal path.
   → Opus: incorporated — `sanitize()` applied at every final output boundary: `refused:`/`skipped:` prints, force-unlock open failures, and both stderr handlers in `main`. Fixture: ESC-bearing symlinked scope refuses with escaped bytes only.

### Code corrections applied

- (none filed by any lens)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: REVISE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-10 10:57; head SHA `aa99e53` (pass-4 fold).

## Pass 6 — 2026-08-10 12:49 [HISTORICAL]

**Scope:** commit series 13c9e0c^..HEAD (Phase 2 + folds), standalone · **Diff size:** 2120 lines · **Verdict:** REVISE (worst-of; security APPROVE — its first — senior-dev REVISE, qa REVISE; no FAILED lenses)

### Findings

1. **Final scope removal still has an identity-check TOCTOU race** — HIGH · lens: senior-dev: the pass-5 stat-then-rmdir identity fence leaves a window in which a replacement directory installed at the pathname could be removed.
   → Opus: **disputed** — the window exists as stated, but its claimed impact ("removal of a replacement never disclosed or owned") cannot reach any state, by POSIX semantics rather than by timing: `rmdir` removes only EMPTY directories (`ENOTEMPTY` otherwise, unconditional — verified live), so no directory containing anything can ever be the victim. The only in-protocol collision is a `run-pass` whose freshly-mkdir'ed, still-empty scope dir vanishes before its lock create: verified live, it aborts non-zero with no summary — which the result contract explicitly defines as a pass that never ran (cosmetically a traceback; contract-safe). An actor installing empty directories inside the skill install requires filesystem write access, the documented out-of-protocol boundary since pass 1. POSIX offers no remove-by-inode to close the window "atomically"; the two-layer argument (identity fence narrows it, ENOTEMPTY voids its harm) is now stated in the code. Escalated to the human at this checkpoint per the disputed-HIGH rule.
2. **Age calculation follows nested symlinks outside the scope** — MEDIUM · lens: qa: an old scope containing an old symlink to a recently-modified external target read as fresh, making it permanently ineligible for `--older-than` cleanup — age depended on files outside `state/`.
   → Opus: incorporated — `newest_mtime` now uses `follow_symlinks=False` throughout (matching `newest_content_mtime` and the link-not-target deletion semantics). Fixture: old scope with an old symlink to a fresh target is swept, target intact.

### Code corrections applied

- (none filed by any lens)

### New questions Codex raised

- (none)

### Lens run summary

- senior-dev: REVISE · security: APPROVE · qa: REVISE

### Diff snapshot reference

Diff captured at 2026-08-10 12:32; head SHA `d822cba` (pass-5 fold).
