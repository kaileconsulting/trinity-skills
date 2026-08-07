#!/usr/bin/env python3
"""Shared runner machinery: state lifecycle, codex invocation, validation.

This module is the SHARED half of the runner design (see
docs/runner-scripts-artifact-hygiene-2026-08-06.md, "State lifecycle & result
contract"): everything here is skill-agnostic and is duplicated byte-identically
into the sibling skill's bin/ when the runner pattern ports (checked by content
hash in tools/check-parity.py from that phase on). Skill-specific behavior —
lens selection, input composition, pass-log naming — lives in the adapted
modules, never here.

The contract in one line: **the runner composes and invokes; it never folds,
never writes pass logs, never decides.**

Key invariants implemented here:

- One ownership protocol for every actor that mutates a scope directory:
  an exclusive `run.lock` (O_CREAT|O_EXCL) recording pid + ISO timestamp +
  role + an unforgeable random token. Every mutation re-verifies the token;
  release is conditional on token match, never unconditional.
- Race-safe stale reclaim through an intermediate `run.lock.reclaim` marker
  with byte-identity re-verification, so a successor's fresh lock is never
  deleted. A dead-owner reclaim marker gets NO automatic cleanup — actors
  refuse and point at `prune-state --force-unlock`.
- Atomic publication: every artifact is written to `<name>.tmp` and
  os.replace()d into place; readers never see partials.
- A pass exists iff its summary exists: `pass-N.summary.json` is published
  last, under a valid token — the pass's single commit point.

Stdlib-only, Python >= 3.9.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------
# Codex invocation — flags preserved exactly per SKILL.md; the read-only
# sandbox is a hard rule. One named constant so drift is a one-line diff.
# --------------------------------------------------------------------------

CODEX_BASE_ARGS = (
    "-a", "never", "exec",
    "-s", "read-only",
    "--skip-git-repo-check",
)

STDERR_TAIL_CHARS = 2000


def codex_command(schema_path: Path, response_path: Path) -> list:
    """The exact codex argv for one lens invocation; input arrives on stdin."""
    return [
        "codex", *CODEX_BASE_ARGS,
        "--output-schema", str(schema_path),
        "--json",
        "--output-last-message", str(response_path),
        "-",
    ]


def staging_path_for(response_path: Path) -> Path:
    """A run-unique staging target for one codex invocation. Codex writes
    here — never to the final published path — so a killed codex leaves only
    an ignorable staging file, and a displaced run's still-writing child can
    never collide with a successor's artifacts (pid + random suffix)."""
    suffix = f".stage-{os.getpid()}-{secrets.token_hex(4)}.tmp"
    return response_path.with_name(response_path.name + suffix)


def invoke_codex(input_text: str, schema_path: Path, staging_path: Path) -> dict:
    """Run one codex invocation writing to a STAGING path (see
    staging_path_for). Returns {exit_code, stderr_tail}. The caller verifies
    ownership and atomically publishes the staged response afterwards."""
    proc = subprocess.run(
        codex_command(schema_path, staging_path),
        input=input_text.encode("utf-8"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    tail = proc.stderr.decode("utf-8", "replace")[-STDERR_TAIL_CHARS:]
    return {"exit_code": proc.returncode, "stderr_tail": tail}


# --------------------------------------------------------------------------
# Response validation — belt-and-suspenders beyond codex --output-schema.
# --------------------------------------------------------------------------

# Patch-marker rejection, exactly the SKILL.md step list: *** Begin Patch,
# `--- a/` / `+++ b/`, `@@ -` followed by a digit, and merge-conflict markers.
PATCH_MARKER_PATTERNS = (
    re.compile(r"\*\*\* Begin Patch"),
    re.compile(r"^(--- a/|\+\+\+ b/)", re.MULTILINE),
    re.compile(r"@@ -\d"),
    re.compile(r"^(<{7}|={7}|>{7})", re.MULTILINE),
)

VERDICTS = ("APPROVE", "REVISE", "BLOCK")


def scan_patch_markers(text: str) -> list:
    """Return the patterns (as strings) found in the raw response text."""
    return [p.pattern for p in PATCH_MARKER_PATTERNS if p.search(text)]


def structural_check(schema_path: Path, response: object) -> list:
    """Cheap stdlib structural validation of a parsed response against the
    schema's top level: required keys present, verdict in its enum, array
    fields are arrays. codex --output-schema does the deep enforcement; this
    catches a missing/empty/hand-mangled response file."""
    problems = []
    with open(schema_path, encoding="utf-8") as fh:
        schema = json.load(fh)
    if not isinstance(response, dict):
        return [f"response is {type(response).__name__}, expected object"]
    for key in schema.get("required", []):
        if key not in response:
            problems.append(f"missing required key: {key}")
    verdict = response.get("verdict")
    if verdict is not None and verdict not in VERDICTS:
        problems.append(f"verdict {verdict!r} not in {VERDICTS}")
    for key, spec in schema.get("properties", {}).items():
        if spec.get("type") == "array" and key in response \
                and not isinstance(response[key], list):
            problems.append(f"{key} is not an array")
    return problems


def validate_response_file(schema_path: Path, response_path: Path) -> list:
    """All rejection reasons for a response file (empty list = valid)."""
    try:
        raw = response_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"response unreadable: {exc}"]
    markers = scan_patch_markers(raw)
    if markers:
        return [f"patch marker present: {m}" for m in markers]
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        return [f"response is not valid JSON: {exc}"]
    return structural_check(schema_path, parsed)


# --------------------------------------------------------------------------
# Atomic publication
# --------------------------------------------------------------------------

def atomic_publish(path: Path, data: str) -> None:
    """Write to `<name>.tmp`, then os.replace() into place. Readers never see
    a partial artifact; a crash leaves only a `.tmp` that readers ignore and
    prune sweeps."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    os.replace(tmp, path)


# --------------------------------------------------------------------------
# Lock lifecycle
# --------------------------------------------------------------------------

class LockError(Exception):
    """Scope ownership could not be acquired/verified. Message is user-facing."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_lock(path: Path):
    """Return (raw_bytes, parsed_dict_or_None). Missing file -> (None, None)."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None, None
    try:
        parsed = json.loads(raw.decode("utf-8"))
        if not isinstance(parsed, dict) or "pid" not in parsed or "token" not in parsed:
            parsed = None
    except (ValueError, UnicodeDecodeError):
        parsed = None
    return raw, parsed


class ScopeLock:
    """Exclusive ownership of one scope's state directory.

    Usage:
        lock = ScopeLock(state_dir, role="run-pass")
        lock.acquire()          # O_EXCL create, or race-safe reclaim of a
                                # dead-pid lock; raises LockError otherwise
        ...mutate, calling lock.verify() before each publication...
        lock.release()          # conditional on token match — in a finally
    """

    LOCK_NAME = "run.lock"
    RECLAIM_NAME = "run.lock.reclaim"

    def __init__(self, state_dir: Path, role: str):
        self.state_dir = Path(state_dir)
        self.role = role
        self.token = secrets.token_hex(16)
        self.lock_path = self.state_dir / self.LOCK_NAME
        self.reclaim_path = self.state_dir / self.RECLAIM_NAME
        self._held = False

    # -- helpers ----------------------------------------------------------

    def _payload(self) -> bytes:
        record = {
            "pid": os.getpid(),
            "timestamp": _utc_now(),
            "role": self.role,
            "token": self.token,
            "owner_name": os.path.basename(sys.argv[0]) or "python3",
        }
        return (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")

    def _try_create(self, path: Path) -> bool:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        try:
            os.write(fd, self._payload())
        finally:
            os.close(fd)
        return True

    def _refuse(self, why: str):
        raise LockError(
            f"{why} (scope dir: {self.state_dir}). No automatic reclaim is "
            f"attempted for ambiguous locks — if you are sure no run is live, "
            f"recover explicitly with: prune-state --force-unlock "
            f"{self.state_dir.name}"
        )

    # -- protocol ---------------------------------------------------------

    def acquire(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # A reclaim marker means recovery is in progress (live pid) or died
        # mid-recovery (dead pid). Neither case is ours to clean up: the
        # recursion terminates by refusing to recurse.
        marker_raw, marker = _read_lock(self.reclaim_path)
        if marker_raw is not None:
            if marker is not None and _pid_alive(int(marker["pid"])):
                self._refuse("a stale-lock reclaim is in progress")
            self._refuse("an abandoned reclaim marker exists")

        if self._try_create(self.lock_path):
            self._held = True
            return

        raw, parsed = _read_lock(self.lock_path)
        if raw is None:
            # Lock vanished between the failed create and the read — the owner
            # released it. Take the clean-create path again, once.
            if self._try_create(self.lock_path):
                self._held = True
                return
            self._refuse("the scope is locked by a concurrent run")
        if parsed is None:
            self._refuse("the scope lock has malformed metadata")
        if _pid_alive(int(parsed["pid"])):
            # Any live pid — even a name mismatch, which PID reuse can produce —
            # is ambiguous. The recorded name is diagnostic only.
            self._refuse(
                f"the scope is locked by a live run (pid {parsed['pid']}, "
                f"role {parsed.get('role', '?')}, since {parsed.get('timestamp', '?')})"
            )
        self._reclaim(raw)

    def _reclaim(self, observed_raw: bytes) -> None:
        """Race-safe reclaim of a dead-pid lock: win the reclaim marker,
        re-verify the lock is byte-identical to what we observed (a successor's
        fresh lock differs and is never touched), unlink, then attempt our own
        O_EXCL creation. Losing that creation race is a clean back-off."""
        if not self._try_create(self.reclaim_path):
            self._refuse("another reclaim of this scope is in progress")
        try:
            current_raw, _ = _read_lock(self.lock_path)
            if current_raw != observed_raw:
                self._refuse("the scope lock changed while reclaiming — a "
                             "successor owns it")
            os.unlink(self.lock_path)
            if not self._try_create(self.lock_path):
                self._refuse("lost the lock-creation race to a newly starting run")
            self._held = True
        finally:
            # Conditional removal of OUR marker only — same rule as the lock.
            marker_raw, marker = _read_lock(self.reclaim_path)
            if marker is not None and marker.get("token") == self.token:
                os.unlink(self.reclaim_path)

    def verify(self) -> None:
        """Re-verify ownership immediately before publishing an artifact.
        A displaced run (force-unlock revoked our token) must abort without
        publishing anything further — in particular, never a summary."""
        _raw, parsed = _read_lock(self.lock_path)
        if parsed is None or parsed.get("token") != self.token:
            raise LockError(
                "scope ownership was revoked (force-unlock or displacement) — "
                "aborting without publishing"
            )

    def release(self) -> None:
        """Conditional on token match, never unconditional: a displaced run
        must not unlink a successor's lock."""
        if not self._held:
            return
        _raw, parsed = _read_lock(self.lock_path)
        if parsed is not None and parsed.get("token") == self.token:
            os.unlink(self.lock_path)
        self._held = False


# --------------------------------------------------------------------------
# Pass numbering & summary contract
# --------------------------------------------------------------------------

_PASS_ARTIFACT = re.compile(r"^pass-(\d+)\.")


def allocate_pass_number(state_dir: Path) -> int:
    """max over ALL pass-N.* names (artifacts and summaries alike) + 1, so
    orphan artifacts from a displaced run are never overwritten — their
    numbers are simply skipped. Call while holding the scope lock."""
    highest = 0
    try:
        names = os.listdir(state_dir)
    except FileNotFoundError:
        names = []
    for name in names:
        m = _PASS_ARTIFACT.match(name)
        if m:
            highest = max(highest, int(m.group(1)))
    return highest + 1


def pass_number_in_use(state_dir: Path, pass_num: int) -> bool:
    """True if ANY pass-<N>.* artifact exists (input, response, summary, or
    staging leftovers). An explicit --pass-num that collides is refused —
    published pass state is immutable; orphaned numbers are skipped, never
    reused. Call while holding the scope lock."""
    prefix = f"pass-{pass_num}."
    try:
        names = os.listdir(state_dir)
    except FileNotFoundError:
        return False
    return any(n.startswith(prefix) for n in names)


def summary_path(state_dir: Path, pass_num: int) -> Path:
    return state_dir / f"pass-{pass_num}.summary.json"


def publish_summary(lock: ScopeLock, state_dir: Path, pass_num: int,
                    scope_hash: str, log_path: Path, warnings: list,
                    lenses: dict) -> Path:
    """Publish pass-N.summary.json — the pass's single commit point. A pass
    exists iff its summary exists; readers discover passes only through
    summaries. Published atomically, last, under a verified token."""
    lock.verify()
    payload = {
        "pass": pass_num,
        "scope_hash": scope_hash,
        "log_path": str(log_path),
        "warnings": list(warnings),
        "lenses": lenses,
        "complete": True,
    }
    path = summary_path(state_dir, pass_num)
    atomic_publish(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


# --------------------------------------------------------------------------
# Invoking-repo root resolution (distinct from skill-root resolution)
# --------------------------------------------------------------------------

def resolve_repo_root(cwd=None):
    """Return (root_path, warnings). `git rev-parse --show-toplevel` from the
    cwd — handles subdirectory and worktree invocation — falling back to the
    cwd with a warning when not in a git repo."""
    cwd = Path(cwd) if cwd is not None else Path.cwd()
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd), capture_output=True, text=True,
        )
    except OSError as exc:
        return cwd, [f"git unavailable ({exc}); pass-log default falls back to the cwd"]
    if proc.returncode != 0:
        return cwd, ["not inside a git repository; pass-log default falls back to the cwd"]
    return Path(proc.stdout.strip()), []
