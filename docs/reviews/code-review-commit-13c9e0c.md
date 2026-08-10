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
