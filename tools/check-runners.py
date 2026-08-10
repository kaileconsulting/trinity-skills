#!/usr/bin/env python3
"""Fixtures for the iterate-review runner scripts (bin/).

Pins the behavior the runner-scripts plan promises
(docs/runner-scripts-artifact-hygiene-2026-08-06.md):

  composition   — byte-deterministic assembly (goldens in
                  iterate-review/examples/composition/)
  exit contracts— run-lens 0/2/1 at its boundary; run-pass exit 0 iff a
                  summary was published (per-lens failure/rejection is data)
  lifecycle     — exclusive scope lock, fail-fast on concurrent runs, lock
                  released on completion, no summary on abort, adversarial
                  stale reclaim, ownership-token displacement, standalone
                  run-lens isolation (debug/ namespace)
  pass-log      — docs/reviews/ default resolved from a subdirectory, --log-path
                  override, non-git cwd fallback warning, existing root logs
                  untouched, runner never creates/writes the log
  prune         — converged --scope cleanup under the prune lock, dry-run
                  exactness, pass logs + state/<hash>.json never touched,
                  live locks refused/skipped, run-start vs. prune fail-fast,
                  stale-lock reclaim, force-unlock recovery (byte-identity
                  conditional removal; displaced live run commits no summary)

No network and no real codex: subprocess tests run against a COPY of the
skill directory (which doubles as the plain-copy install layout check) with a
fake `codex` on PATH that replays canned responses.

Usage:
    tools/check-runners.py            # exit 0 all pass, 1 failures, 2 setup error
"""

from __future__ import annotations

import contextlib
import fcntl
import glob
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)
SKILL = os.path.join(REPO, "iterate-review")
COMPOSITION = os.path.join(SKILL, "examples", "composition")
BAD_RESPONSE = os.path.join(SKILL, "examples",
                            "pass-1-patch-marker-violation.response.json")

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


def load(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Environment: a copied skill install + a fake codex + a scratch git repo
# ---------------------------------------------------------------------------

class Env:
    def __init__(self, root: str):
        self.root = root
        # Plain-copy install layout: the same tree a user gets from cp -r.
        self.skill = os.path.join(root, "iterate-review")
        shutil.copytree(SKILL, self.skill,
                        ignore=shutil.ignore_patterns("state"))
        os.makedirs(os.path.join(self.skill, "state"), exist_ok=True)
        self.bin = os.path.join(self.skill, "bin")

        self.fakebin = os.path.join(root, "fakebin")
        os.makedirs(self.fakebin)
        self.mode_file = os.path.join(root, "codex-mode")
        self._write_fake_codex()

        self.repo = os.path.join(root, "repo")
        os.makedirs(os.path.join(self.repo, "sub"))
        subprocess.run(["git", "init", "-q", self.repo], check=True,
                       stdout=subprocess.DEVNULL)
        # Inputs live in the ENFORCED per-repo handoff dir.
        self.handoff = os.path.join(self.repo, ".git", "iterate-review")
        os.makedirs(self.handoff)
        self.diff = os.path.join(self.handoff, "diff.txt")
        with open(self.diff, "w") as fh:
            fh.write("diff --git a/lib/plain.py b/lib/plain.py\n"
                     "--- a/lib/plain.py\n+++ b/lib/plain.py\n"
                     "@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n")
        self.intent = os.path.join(self.handoff, "intent.txt")
        with open(self.intent, "w") as fh:
            fh.write("Standalone code review of working-tree changes.\n")

    def _write_fake_codex(self) -> None:
        path = os.path.join(self.fakebin, "codex")
        with open(path, "w") as fh:
            fh.write(f'''#!/usr/bin/env python3
import json, os, sys, time
args = sys.argv[1:]
out = None
for i, a in enumerate(args):
    if a == "--output-last-message":
        out = args[i + 1]
sys.stdin.read()
mode = "ok"
try:
    with open({self.mode_file!r}) as fh:
        mode = fh.read().strip()
except OSError:
    pass
if mode in ("sleep", "sleep3"):
    # Readiness handshake: the marker appears only after this process has
    # READ its mode and committed to the blocking path — fixtures wait for
    # it before flipping the shared mode or racing a competitor.
    with open({self.mode_file!r} + ".sleeping-" + str(os.getpid()), "w"):
        pass
if mode == "sleep":
    time.sleep(30)
if mode == "sleep3":
    time.sleep(3)
if mode == "fail":
    sys.exit(3)
if mode == "partial":
    with open(out, "w") as fh:
        fh.write('{{"verdict": "APPRO')
        fh.flush()
        time.sleep(30)
if mode == "structural":
    with open(out, "w") as fh:
        fh.write('{{"verdict": "APPROVE", "findings": []}}')
    sys.exit(0)
if mode == "patchmarkers":
    with open({BAD_RESPONSE!r}) as fh:
        body = fh.read()
    with open(out, "w") as fh:
        fh.write(body)
    sys.exit(0)
resp = {{"verdict": "APPROVE", "findings": [], "code_corrections": [],
        "new_questions": []}}
with open(out, "w") as fh:
    json.dump(resp, fh)
''')
        os.chmod(path, 0o755)

    def set_mode(self, mode: str) -> None:
        with open(self.mode_file, "w") as fh:
            fh.write(mode)

    def clear_sleep_markers(self) -> None:
        for p in glob.glob(self.mode_file + ".sleeping-*"):
            os.remove(p)

    def wait_sleeper(self, timeout: float = 10) -> bool:
        """Wait for the fake codex's readiness marker — proof it read a
        sleep mode and entered the blocking path."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if glob.glob(self.mode_file + ".sleeping-*"):
                return True
            time.sleep(0.02)
        return False

    def run(self, script: str, *args, cwd=None, timeout=60):
        env = dict(os.environ)
        env["PATH"] = self.fakebin + os.pathsep + env["PATH"]
        return subprocess.run(
            [os.path.join(self.bin, script), *args],
            cwd=cwd or self.repo, env=env, timeout=timeout,
            capture_output=True, text=True)

    def state_dirs(self):
        state = os.path.join(self.skill, "state")
        return [os.path.join(state, d) for d in os.listdir(state)
                if os.path.isdir(os.path.join(state, d))]


# ---------------------------------------------------------------------------
# Composition goldens (module-level, pure)
# ---------------------------------------------------------------------------

def test_composition(rr) -> None:
    prompt = read(os.path.join(COMPOSITION, "prompt.txt"))
    body = read(os.path.join(COMPOSITION, "lens-body.txt"))
    mc = read(os.path.join(COMPOSITION, "matched-context.txt")).strip()
    intent = read(os.path.join(COMPOSITION, "intent.txt"))
    diff = read(os.path.join(COMPOSITION, "diff.txt"))
    prior = read(os.path.join(COMPOSITION, "prior.txt"))

    got = rr.compose_input(prompt, "test-lens", body, mc, intent, diff, prior)
    record("composition: golden with prior passes (byte-identical)",
           got == read(os.path.join(COMPOSITION, "golden-with-prior.txt")))
    got = rr.compose_input(prompt, "test-lens", body, mc, intent, diff, "")
    record("composition: golden first pass uses the no-prior sentinel",
           got == read(os.path.join(COMPOSITION, "golden-first-pass.txt"))
           and rr.NO_PRIOR_PASSES in got)

    # Determinism against the REAL skill inputs: composing twice is bytewise
    # stable for every lens record.
    lens_ids = sorted(
        f[:-3] for f in os.listdir(os.path.join(SKILL, "lenses"))
        if f.endswith(".md") and f != "README.md")
    stable = all(
        rr.compose_for_lens(lid, intent, diff, prior)
        == rr.compose_for_lens(lid, intent, diff, prior)
        for lid in lens_ids)
    record("composition: real-lens composition is repeat-stable", stable,
           f"lenses: {', '.join(lens_ids)}")

    body2, mc2 = rr.read_lens_record("security")
    record("composition: matched_context folded to one line",
           "\n" not in mc2 and mc2.startswith("The diff, intent"))
    record("composition: lens body starts after frontmatter",
           body2.startswith("## ROLE"))


# ---------------------------------------------------------------------------
# Exit contracts + pass-log behavior (subprocess, fake codex)
# ---------------------------------------------------------------------------

def test_contracts(env: Env) -> None:
    # run-pass happy path: summary published, exit 0, log resolved to
    # docs/reviews/ under the repo root even from a subdirectory.
    env.set_mode("ok")
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "t1", "--pass-num", "1",
                   cwd=os.path.join(env.repo, "sub"))
    summary = json.loads(proc.stdout or "{}") if proc.returncode == 0 else {}
    record("run-pass: exit 0 and summary published on success",
           proc.returncode == 0 and summary.get("complete") is True,
           proc.stderr.strip()[-200:])
    expected_log = os.path.join(env.repo, "docs", "reviews",
                                "code-review-t1.md")
    record("pass-log: default resolves to <repo-root>/docs/reviews from a subdir",
           os.path.realpath(summary.get("log_path", "")) == os.path.realpath(expected_log)
           and summary.get("warnings") == [],
           summary.get("log_path", "(no summary)"))
    record("pass-log: the runner never creates the log file",
           not os.path.exists(expected_log))
    record("run-pass: lock released on completion",
           all(not os.path.exists(os.path.join(d, "run.lock"))
               for d in env.state_dirs()))

    # Pre-existing root log untouched + --log-path override honored.
    root_log = os.path.join(env.repo, "code-review-old.md")
    with open(root_log, "w") as fh:
        fh.write("legacy root log\n")
    override = os.path.join(env.repo, "custom", "my-log.md")
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "t2", "--pass-num", "1",
                   "--log-path", override)
    summary = json.loads(proc.stdout or "{}") if proc.returncode == 0 else {}
    record("pass-log: --log-path override echoed back",
           os.path.realpath(summary.get("log_path", ""))
           == os.path.realpath(override))
    record("pass-log: pre-existing root logs untouched — no migration, no rename",
           read(root_log) == "legacy root log\n")

    # Non-git cwd: fallback to cwd with a warning in the summary. The inputs
    # must live in THAT boundary's handoff dir (<cwd>/.iterate-review/).
    nongit = tempfile.mkdtemp(dir=env.root)
    nongit_handoff = os.path.join(nongit, ".iterate-review")
    os.makedirs(nongit_handoff)
    shutil.copy(env.diff, os.path.join(nongit_handoff, "diff.txt"))
    shutil.copy(env.intent, os.path.join(nongit_handoff, "intent.txt"))
    proc = env.run("run-pass", "--diff",
                   os.path.join(nongit_handoff, "diff.txt"),
                   "--intent", os.path.join(nongit_handoff, "intent.txt"),
                   "--scope-tag", "t3", "--pass-num", "1", cwd=nongit)
    summary = json.loads(proc.stdout or "{}") if proc.returncode == 0 else {}
    record("pass-log: non-git invocation reports the cwd-fallback warning",
           proc.returncode == 0 and len(summary.get("warnings", [])) == 1
           and "not inside a git repository" in summary["warnings"][0],
           str(summary.get("warnings")))

    # Patch-marker rejection at BOTH command boundaries.
    env.set_mode("patchmarkers")
    proc = env.run("run-lens", "--diff", env.diff, "--intent", env.intent,
                   "--lens", "senior-dev", "--scope-tag", "t4")
    record("run-lens: malformed response -> exit 2 (rejected)",
           proc.returncode == 2 and '"status": "rejected"' in proc.stdout,
           f"exit={proc.returncode}")
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "t5", "--pass-num", "1")
    summary = json.loads(proc.stdout or "{}") if proc.returncode == 0 else {}
    statuses = {k: v["status"] for k, v in summary.get("lenses", {}).items()}
    record("run-pass: rejected lens is data in a completed summary, exit 0",
           proc.returncode == 0 and statuses
           and all(s == "rejected" for s in statuses.values()),
           str(statuses))

    # A failing codex is per-lens data too.
    env.set_mode("fail")
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "t6", "--pass-num", "1")
    summary = json.loads(proc.stdout or "{}") if proc.returncode == 0 else {}
    statuses = {k: v["status"] for k, v in summary.get("lenses", {}).items()}
    record("run-pass: failed lens is data in a completed summary, exit 0",
           proc.returncode == 0 and statuses
           and all(s == "failed" for s in statuses.values()),
           str(statuses))
    env.set_mode("fail")
    proc = env.run("run-lens", "--diff", env.diff, "--intent", env.intent,
                   "--lens", "senior-dev", "--scope-tag", "t6b")
    record("run-lens: codex failure -> exit 1", proc.returncode == 1)

    # Selection override: unknown lens id refuses.
    env.set_mode("ok")
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "t7", "--lenses", "nope")
    record("run-pass: unknown --lenses id -> exit 1, no summary",
           proc.returncode == 1 and "unknown lens id" in proc.stderr)

    # Standalone run-lens writes only to debug/, never pass-N.*.
    proc = env.run("run-lens", "--diff", env.diff, "--intent", env.intent,
                   "--lens", "senior-dev", "--scope-tag", "t8")
    out = json.loads(proc.stdout or "{}")
    sdir = os.path.dirname(os.path.dirname(out["response_path"]))
    published = [f for f in os.listdir(sdir) if f.startswith("pass-")]
    record("run-lens: standalone artifacts land in debug/, no pass-N.* published",
           proc.returncode == 0
           and f"{os.sep}debug{os.sep}" in out["response_path"]
           and published == [],
           str(published))


# ---------------------------------------------------------------------------
# Lifecycle (locks, aborts, reclaim, displacement)
# ---------------------------------------------------------------------------

def test_lifecycle(env: Env, shared) -> None:
    state_root = os.path.join(env.skill, "state")

    # Concurrent second run of the same scope fails fast.
    env.clear_sleep_markers()
    env.set_mode("sleep")
    env_path = dict(os.environ)
    env_path["PATH"] = env.fakebin + os.pathsep + env_path["PATH"]
    slow = subprocess.Popen(
        [os.path.join(env.bin, "run-pass"), "--diff", env.diff,
         "--intent", env.intent, "--scope-tag", "t9", "--pass-num", "1"],
        cwd=env.repo, env=env_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Readiness handshake: only flip the shared mode once the fake codex has
    # READ "sleep" and committed to blocking — otherwise the "live" run could
    # finish before the competitor starts and the fixture would be vacuous.
    record("lifecycle: sleeping codex signalled readiness", env.wait_sleeper())
    # t9 is the only scope with a live run at this point in the suite, so any
    # present lock is its lock.
    deadline = time.time() + 10
    lock_path = None
    while time.time() < deadline and lock_path is None:
        for d in env.state_dirs():
            p = os.path.join(d, "run.lock")
            if os.path.exists(p):
                lock_path = p
        time.sleep(0.05)
    record("lifecycle: live run holds run.lock", lock_path is not None)

    env.set_mode("ok")
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "t9", "--pass-num", "1")
    record("lifecycle: concurrent same-scope run fails fast, no summary",
           proc.returncode == 1 and "locked by a live run" in proc.stderr,
           proc.stderr.strip()[-160:])

    # Interrupt the slow run: no summary may exist — the pass never ran.
    slow.send_signal(signal.SIGKILL)
    slow.wait(timeout=10)
    t9_dir = os.path.dirname(lock_path)
    record("lifecycle: interrupted run publishes no summary",
           not any(f.endswith(".summary.json") for f in os.listdir(t9_dir)))
    published = [f for f in os.listdir(t9_dir)
                 if f.startswith("pass-") and not f.endswith(".tmp")]
    record("lifecycle: interrupted run's published artifacts are complete "
           "(atomic publication — partials only ever exist as .tmp)",
           all(os.path.getsize(os.path.join(t9_dir, f)) > 0 for f in published),
           str(published))

    # The dead run's lock is stale; a new run reclaims it and completes.
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "t9", "--pass-num", "2")
    record("lifecycle: dead-pid lock reclaimed, next run completes",
           proc.returncode == 0, proc.stderr.strip()[-160:])
    record("lifecycle: reclaim leaves no marker behind",
           not os.path.exists(os.path.join(t9_dir, "run.lock.reclaim")))

    # Adversarial reclaim: two simultaneous reclaimers, one winner, and the
    # successor's fresh lock is never deleted.
    scope = os.path.join(state_root, "adversarial")
    os.makedirs(scope, exist_ok=True)
    dead_pid = spawn_dead_pid()
    stale = json.dumps({"pid": dead_pid, "timestamp": "t", "role": "run-pass",
                        "token": "deadbeef", "owner_name": "x"}) + "\n"
    with open(os.path.join(scope, "run.lock"), "w") as fh:
        fh.write(stale)

    locks = [shared.ScopeLock(scope, role="run-pass") for _ in range(2)]
    outcomes = [None, None]
    barrier = threading.Barrier(2)

    def attempt(i):
        try:
            barrier.wait()
            locks[i].acquire()
            outcomes[i] = "won"
        except shared.LockError:
            outcomes[i] = "refused"

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)
    winners = [i for i, o in enumerate(outcomes) if o == "won"]
    record("lifecycle: adversarial reclaim has exactly one winner",
           len(winners) == 1 and all(o in ("won", "refused") for o in outcomes),
           str(outcomes))
    # Winner's lock survives: token matches the winning lock object.
    if winners:
        w = locks[winners[0]]
        with open(os.path.join(scope, "run.lock")) as fh:
            current = json.load(fh)
        record("lifecycle: successor's lock never deleted by the losing reclaimer",
               current.get("token") == w.token)
        w.release()
    else:
        record("lifecycle: successor's lock never deleted by the losing reclaimer",
               False, "no winner")

    # Ownership displacement: revoked token -> verify raises, release leaves
    # the foreign lock intact, and NO summary can be published.
    scope2 = os.path.join(state_root, "displaced")
    lock = shared.ScopeLock(scope2, role="run-pass")
    lock.acquire()
    foreign = json.dumps({"pid": os.getpid(), "timestamp": "t",
                          "role": "run-pass", "token": "other",
                          "owner_name": "x"}) + "\n"
    with open(os.path.join(scope2, "run.lock"), "w") as fh:
        fh.write(foreign)
    displaced_raises = False
    try:
        lock.verify()
    except shared.LockError:
        displaced_raises = True
    record("lifecycle: revoked token -> verify() aborts before publication",
           displaced_raises)
    lock.release()
    record("lifecycle: displaced run never unlinks the successor's lock",
           os.path.exists(os.path.join(scope2, "run.lock")))
    summary_raises = False
    try:
        shared.publish_summary(lock, scope2, 1, "h", "log", [], {})
    except shared.LockError:
        summary_raises = True
    record("lifecycle: displaced run commits no summary", summary_raises)
    os.unlink(os.path.join(scope2, "run.lock"))

    # An abandoned reclaim marker refuses with the recovery pointer.
    scope3 = os.path.join(state_root, "orphanmarker")
    os.makedirs(scope3, exist_ok=True)
    with open(os.path.join(scope3, "run.lock.reclaim"), "w") as fh:
        fh.write(json.dumps({"pid": spawn_dead_pid(), "timestamp": "t",
                             "role": "run-pass", "token": "z",
                             "owner_name": "x"}) + "\n")
    lock3 = shared.ScopeLock(scope3, role="run-pass")
    msg = ""
    try:
        lock3.acquire()
    except shared.LockError as exc:
        msg = str(exc)
    record("lifecycle: abandoned reclaim marker -> refuse + force-unlock pointer",
           "abandoned reclaim marker" in msg and "--force-unlock" in msg,
           msg[:120])

    # Standalone run-lens during a live run-pass on the SAME scope: the
    # standalone invocation must succeed without the lock and must leave
    # that scope's published pass-N.* set untouched (debug/ only).
    env.clear_sleep_markers()
    env.set_mode("sleep")
    live = subprocess.Popen(
        [os.path.join(env.bin, "run-pass"), "--diff", env.diff,
         "--intent", env.intent, "--scope-tag", "live1", "--pass-num", "1"],
        cwd=env.repo, env=env_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    record("lifecycle: live1 sleeping codex signalled readiness",
           env.wait_sleeper())
    deadline = time.time() + 10
    live_dir = None
    while time.time() < deadline and live_dir is None:
        for d in env.state_dirs():
            if os.path.exists(os.path.join(d, "run.lock")) and d != t9_dir:
                live_dir = d
        time.sleep(0.05)
    published_before = sorted(
        f for f in os.listdir(live_dir) if f.startswith("pass-")
        and not f.endswith(".tmp"))
    env.set_mode("ok")  # safe: the readiness marker proves "sleep" was read
    proc = env.run("run-lens", "--diff", env.diff, "--intent", env.intent,
                   "--lens", "senior-dev", "--scope-tag", "live1")
    out = json.loads(proc.stdout or "{}")
    published_after = sorted(
        f for f in os.listdir(live_dir) if f.startswith("pass-")
        and not f.endswith(".tmp"))
    record("lifecycle: standalone run-lens during a live same-scope run-pass "
           "succeeds and touches no published state",
           proc.returncode == 0
           and f"{os.sep}debug{os.sep}" in out.get("response_path", "")
           and os.path.realpath(os.path.dirname(os.path.dirname(
               out["response_path"]))) == os.path.realpath(live_dir)
           and published_after == published_before,
           f"exit={proc.returncode} resp={out.get('response_path')} "
           f"before={published_before} after={published_after}")
    live.send_signal(signal.SIGKILL)
    live.wait(timeout=10)
    os.unlink(os.path.join(live_dir, "run.lock"))


def test_immutability(env: Env, shared) -> None:
    """Pass-1 review fold: published pass state is immutable; responses are
    staged and published atomically under a verified token."""
    # A used explicit --pass-num is refused and existing bytes stay put.
    env.set_mode("ok")
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "imm1", "--pass-num", "1")
    summary = json.loads(proc.stdout or "{}")
    resp = summary["lenses"]["senior-dev"]["response_path"]
    before = read(resp)
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "imm1", "--pass-num", "1")
    record("immutability: repeated --pass-num refused, no summary overwrite",
           proc.returncode == 1 and "already has artifacts" in proc.stderr,
           proc.stderr.strip()[-140:])
    record("immutability: refused rerun leaves existing artifacts byte-identical",
           read(resp) == before)
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "imm1")
    summary = json.loads(proc.stdout or "{}")
    record("immutability: omitting --pass-num allocates past the used number",
           proc.returncode == 0 and summary.get("pass") == 2,
           f"pass={summary.get('pass')}")

    # Zero/negative pass numbers never reach scope state.
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "imm2", "--pass-num", "0")
    record("immutability: --pass-num 0 rejected at the argument boundary",
           proc.returncode == 2 and "must be >= 1" in proc.stderr)

    # A codex killed mid-write leaves NO readable final response — the
    # partial exists only at the run-unique staging path.
    env.set_mode("partial")
    env_path = dict(os.environ)
    env_path["PATH"] = env.fakebin + os.pathsep + env_path["PATH"]
    slow = subprocess.Popen(
        [os.path.join(env.bin, "run-pass"), "--diff", env.diff,
         "--intent", env.intent, "--scope-tag", "imm3", "--pass-num", "1"],
        cwd=env.repo, env=env_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.time() + 10
    staged = []
    while time.time() < deadline and not staged:
        for d in env.state_dirs():
            staged = [f for f in os.listdir(d) if ".stage-" in f]
            if staged:
                imm3_dir = d
                break
        time.sleep(0.05)
    slow.send_signal(signal.SIGKILL)
    slow.wait(timeout=10)
    finals = [f for f in os.listdir(imm3_dir)
              if f.endswith(".response.json")] if staged else ["(no staging seen)"]
    record("staging: killed codex leaves no readable final response",
           staged != [] and finals == [], f"staged={staged} finals={finals}")
    record("staging: killed run publishes no summary",
           not any(f.endswith(".summary.json") for f in os.listdir(imm3_dir)))
    os.unlink(os.path.join(imm3_dir, "run.lock"))

    # Ownership revoked while codex runs: the pass aborts with no summary and
    # no final response artifact — the staged bytes never publish.
    env.clear_sleep_markers()
    env.set_mode("sleep3")
    known = set(env.state_dirs())
    slow = subprocess.Popen(
        [os.path.join(env.bin, "run-pass"), "--diff", env.diff,
         "--intent", env.intent, "--scope-tag", "imm4", "--pass-num", "1"],
        cwd=env.repo, env=env_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    record("staging: imm4 sleeping codex signalled readiness",
           env.wait_sleeper())
    deadline = time.time() + 10
    lock_file = None
    while time.time() < deadline and lock_file is None:
        for d in set(env.state_dirs()) - known:
            p = os.path.join(d, "run.lock")
            if os.path.exists(p):
                lock_file, imm4_dir = p, d
        time.sleep(0.05)
    with open(lock_file, "w") as fh:
        fh.write(json.dumps({"pid": os.getpid(), "timestamp": "t",
                             "role": "prune", "token": "revoked",
                             "owner_name": "test"}) + "\n")
    slow.wait(timeout=30)
    finals = [f for f in os.listdir(imm4_dir) if f.endswith(".response.json")
              or f.endswith(".summary.json")]
    record("displacement: revoked-mid-codex run aborts (non-zero, no summary, "
           "no published response)",
           slow.returncode != 0 and finals == [],
           f"exit={slow.returncode} finals={finals}")
    record("displacement: displaced run leaves the revoking lock untouched",
           os.path.exists(lock_file) and "revoked" in read(lock_file))
    os.unlink(lock_file)


def test_pass2_fold(env: Env, shared) -> None:
    """Pass-2 review fold: structural rejection exercised at both command
    boundaries, the trusted-path boundary, and flock-fenced publication."""
    # Structural-only rejection (valid JSON, off-schema): run-lens exit 2
    # with a structural reason, run-pass rejected-as-data with the reason.
    env.set_mode("structural")
    proc = env.run("run-lens", "--diff", env.diff, "--intent", env.intent,
                   "--lens", "senior-dev", "--scope-tag", "s1")
    record("structural: run-lens off-schema response -> exit 2 with structural reason",
           proc.returncode == 2 and "missing required key" in proc.stdout
           and "patch marker" not in proc.stdout,
           f"exit={proc.returncode}")
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "s2", "--pass-num", "1")
    summary = json.loads(proc.stdout or "{}") if proc.returncode == 0 else {}
    entry = summary.get("lenses", {}).get("senior-dev", {})
    record("structural: run-pass reports structural reject_reasons, exit 0",
           proc.returncode == 0 and entry.get("status") == "rejected"
           and any("missing required key" in r
                   for r in entry.get("reject_reasons", [])),
           str(entry.get("reject_reasons")))

    # Trusted boundary: inputs outside repo root + state root are refused,
    # symlink escapes included; --log-path must stay inside the repo.
    env.set_mode("ok")
    outside = os.path.join(env.root, "outside.diff")
    with open(outside, "w") as fh:
        fh.write("diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n")
    proc = env.run("run-pass", "--diff", outside, "--intent", env.intent,
                   "--scope-tag", "s3")
    record("boundary: --diff outside repo/state roots refused",
           proc.returncode == 1 and "trusted boundaries" in proc.stderr)
    secret = os.path.join(env.root, "secret.txt")
    with open(secret, "w") as fh:
        fh.write("hunter2\n")
    link = os.path.join(env.repo, "evil.diff")
    os.symlink(secret, link)
    proc = env.run("run-pass", "--diff", link, "--intent", env.intent,
                   "--scope-tag", "s4")
    record("boundary: symlink escape from inside the repo refused",
           proc.returncode == 1 and "trusted boundaries" in proc.stderr)
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "s5",
                   "--log-path", os.path.join(env.root, "elsewhere.md"))
    record("boundary: --log-path outside the repo root refused",
           proc.returncode == 1 and "trusted boundaries" in proc.stderr)
    record("boundary: run-lens enforces the same refusal",
           env.run("run-lens", "--diff", outside, "--intent", env.intent,
                   "--lens", "senior-dev", "--scope-tag", "s6").returncode == 1)

    # The DEFAULT log path is boundary-checked too: a repo-controlled symlink
    # at docs/reviews/code-review-<tag>.md pointing outside is refused.
    reviews_dir = os.path.join(env.repo, "docs", "reviews")
    os.makedirs(reviews_dir, exist_ok=True)
    os.symlink(secret, os.path.join(reviews_dir, "code-review-s7.md"))
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "s7")
    record("boundary: symlinked DEFAULT pass log refused",
           proc.returncode == 1 and "trusted boundaries" in proc.stderr,
           proc.stderr.strip()[-140:])

    # run-lens validates the lens id — a traversal component can't address a
    # file outside lenses/ or smuggle separators into debug artifact names.
    proc = env.run("run-lens", "--diff", env.diff, "--intent", env.intent,
                   "--lens", "../evil", "--scope-tag", "s8")
    record("boundary: traversal --lens id refused by run-lens",
           proc.returncode == 1 and "unknown lens id" in proc.stderr)

    # The boundary is the repo root ONLY: another scope's state artifacts —
    # and even a would-be shared inbox — are other repositories' review
    # material and must not be readable as inputs.
    foreign = None
    for d in env.state_dirs():
        for f in os.listdir(d):
            if f.endswith(".input.txt"):
                foreign = os.path.join(d, f)
                break
        if foreign:
            break
    proc = env.run("run-pass", "--diff", foreign, "--intent", env.intent,
                   "--scope-tag", "s10")
    record("boundary: another scope's state artifact refused as input",
           foreign is not None and proc.returncode == 1
           and "trusted boundaries" in proc.stderr)
    inbox = os.path.join(env.skill, "state", "inbox")
    os.makedirs(inbox, exist_ok=True)
    shutil.copy(env.diff, os.path.join(inbox, "diff.txt"))
    proc = env.run("run-pass", "--diff", os.path.join(inbox, "diff.txt"),
                   "--intent", env.intent, "--scope-tag", "s11")
    record("boundary: a shared state/inbox file is refused (repo-root only)",
           proc.returncode == 1 and "trusted boundaries" in proc.stderr)
    proc = env.run("run-pass", "--diff", env.diff,
                   "--intent", env.intent, "--scope-tag", "s11b",
                   "--pass-num", "1")
    record("boundary: .git/iterate-review/ handoff accepted",
           proc.returncode == 0, proc.stderr.strip()[-140:])

    # In-repo files OUTSIDE the handoff dir are refused too: the standing
    # allowlist must not read an untracked .env or .git/config into a
    # codex prompt.
    dotenv = os.path.join(env.repo, ".env")
    with open(dotenv, "w") as fh:
        fh.write("SECRET=hunter2\n")
    proc = env.run("run-pass", "--diff", dotenv, "--intent", env.intent,
                   "--scope-tag", "s14")
    record("boundary: in-repo file outside the handoff dir refused (.env)",
           proc.returncode == 1 and "trusted boundaries" in proc.stderr)
    proc = env.run("run-pass", "--diff",
                   os.path.join(env.repo, ".git", "config"),
                   "--intent", env.intent, "--scope-tag", "s15")
    record("boundary: .git/config refused (inside .git, outside handoff)",
           proc.returncode == 1 and "trusted boundaries" in proc.stderr)
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "s16", "--log-path", dotenv)
    record("boundary: non-.md --log-path refused (prior-pass read guard)",
           proc.returncode == 1 and "must be a .md file" in proc.stderr)
    proc = env.run("run-lens", "--diff", env.diff, "--intent", env.intent,
                   "--lens", "senior-dev", "--scope-tag", "s16b",
                   "--log-path", dotenv)
    record("boundary: run-lens enforces the .md log guard too",
           proc.returncode == 1 and "must be a .md file" in proc.stderr)

    # The pass-log header is the read capability: an existing .md that is
    # not THIS review's log is refused; a genuine log is read fine.
    notes = os.path.join(env.repo, "design-notes.md")
    with open(notes, "w") as fh:
        fh.write("# Private design notes\nvery sensitive prose\n")
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "s17", "--log-path", notes)
    record("boundary: unrelated in-repo .md refused as pass log (header capability)",
           proc.returncode == 1 and "not this review's pass log" in proc.stderr)
    genuine = os.path.join(env.repo, "docs", "reviews", "code-review-s18.md")
    os.makedirs(os.path.dirname(genuine), exist_ok=True)
    with open(genuine, "w") as fh:
        fh.write("# Code Review — s18\n\n## Pass 1 — earlier [HISTORICAL]\nprior content\n")
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "s18", "--pass-num", "1")
    record("boundary: a genuine pass log (matching header) is read fine",
           proc.returncode == 0, proc.stderr.strip()[-140:])

    # Scope tags are constrained to a boring charset — a crafted tag can't
    # smuggle path components or masquerade as an arbitrary heading.
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "../weird tag")
    record("boundary: crafted scope tag refused (charset validation)",
           proc.returncode == 1 and "invalid scope tag" in proc.stderr)
    proc = env.run("run-lens", "--diff", env.diff, "--intent", env.intent,
                   "--lens", "senior-dev", "--scope-tag", "../weird tag")
    record("boundary: run-lens refuses a crafted scope tag too",
           proc.returncode == 1 and "invalid scope tag" in proc.stderr)
    # Header comparison is exact — leading whitespace does not pass.
    padded = os.path.join(env.repo, "docs", "reviews", "code-review-s19.md")
    with open(padded, "w") as fh:
        fh.write("  # Code Review — s19\ncontent\n")
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "s19", "--pass-num", "1")
    record("boundary: padded pass-log header refused (exact comparison)",
           proc.returncode == 1 and "not this review's pass log" in proc.stderr)

    # Two concurrent lockless standalone runs never share artifact paths.
    lens_env2 = dict(os.environ)
    lens_env2["PATH"] = env.fakebin + os.pathsep + lens_env2["PATH"]
    procs = [subprocess.Popen(
        [os.path.join(env.bin, "run-lens"), "--diff", env.diff,
         "--intent", env.intent, "--lens", "senior-dev",
         "--scope-tag", "s13"],
        cwd=env.repo, env=lens_env2,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
    outs = [json.loads(p.communicate(timeout=60)[0] or "{}") for p in procs]
    paths = {o.get("response_path") for o in outs} | {o.get("input_path") for o in outs}
    record("debug: two concurrent standalone runs use distinct artifact paths",
           all(p.returncode == 0 for p in procs) and len(paths) == 4,
           f"{len(paths)} distinct paths")

    # run-lens honors the exit contract with a vanished stdout consumer too.
    lens_env = dict(os.environ)
    lens_env["PATH"] = env.fakebin + os.pathsep + lens_env["PATH"]
    read_end, write_end = os.pipe()
    os.close(read_end)
    lens_proc = subprocess.run(
        [os.path.join(env.bin, "run-lens"), "--diff", env.diff,
         "--intent", env.intent, "--lens", "senior-dev",
         "--scope-tag", "s12"],
        cwd=env.repo, env=lens_env, stdout=write_end,
        stderr=subprocess.PIPE, timeout=60)
    os.close(write_end)
    record("contract: run-lens broken stdout pipe after commit still exits 0",
           lens_proc.returncode == 0,
           f"exit={lens_proc.returncode}")

    # Fencing: a revocation during a fenced publication blocks until the
    # publication completes (publish-before-revoke), then ownership is gone.
    scope = os.path.join(env.skill, "state", "fenced")
    lock = shared.ScopeLock(scope, role="run-pass")
    lock.acquire()
    times = {}

    def slow_publish():
        time.sleep(0.5)
        times["publish_done"] = time.monotonic()

    def publisher():
        lock.verify_and(slow_publish)

    def revoker():
        time.sleep(0.15)  # let the publisher take the flock first
        shared.revoke_token(lock.lock_path)
        times["revoke_done"] = time.monotonic()

    threads = [threading.Thread(target=publisher),
               threading.Thread(target=revoker)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)
    record("fencing: revocation blocks until the fenced publication completes",
           "publish_done" in times and "revoke_done" in times
           and times["revoke_done"] >= times["publish_done"],
           str(times))
    revoked_raises = False
    try:
        lock.verify_and(lambda: None)
    except shared.LockError:
        revoked_raises = True
    record("fencing: post-revocation fenced publication refuses", revoked_raises)
    lock.release()
    record("fencing: post-revocation release leaves the revoked lock intact",
           os.path.exists(lock.lock_path))
    os.unlink(lock.lock_path)

    # exit 0 iff summary published — even when the stdout consumer is gone
    # (broken pipe after the commit point must not read as an aborted pass).
    env.set_mode("ok")
    env_path = dict(os.environ)
    env_path["PATH"] = env.fakebin + os.pathsep + env_path["PATH"]
    read_end, write_end = os.pipe()
    os.close(read_end)
    proc = subprocess.run(
        [os.path.join(env.bin, "run-pass"), "--diff", env.diff,
         "--intent", env.intent, "--scope-tag", "s9", "--pass-num", "1"],
        cwd=env.repo, env=env_path, stdout=write_end,
        stderr=subprocess.PIPE, timeout=60)
    os.close(write_end)
    record("contract: broken stdout pipe after commit still exits 0",
           proc.returncode == 0, f"exit={proc.returncode} "
           f"stderr={proc.stderr.decode()[-120:]}")


def test_prune(env: Env, shared) -> None:
    """Phase 2 fixture set (runner-scripts plan): prune-state."""
    state_root = os.path.join(env.skill, "state")
    env_path = dict(os.environ)
    env_path["PATH"] = env.fakebin + os.pathsep + env_path["PATH"]

    # -- converged-scope flow: dry run first, then --scope --yes ------------
    env.set_mode("ok")
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "pr1", "--pass-num", "1")
    shash = json.loads(proc.stdout)["scope_hash"]
    sdir = os.path.join(state_root, shash)
    log = os.path.join(env.repo, "docs", "reviews", "code-review-pr1.md")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "w") as fh:
        fh.write("# Code Review — pr1\ndurable audit record\n")
    model_state = os.path.join(state_root, shash + ".json")
    with open(model_state, "w") as fh:
        fh.write("{}\n")

    contents = os.listdir(sdir)
    proc = env.run("prune-state", "--scope", shash)
    record("prune: dry run lists every file and deletes nothing",
           proc.returncode == 0 and "dry run" in proc.stdout
           and all(name in proc.stdout for name in contents)
           and sorted(os.listdir(sdir)) == sorted(contents),
           proc.stdout[-200:])
    proc = env.run("prune-state", "--scope", shash, "--yes")
    record("prune: converged scope fully removed (--scope --yes)",
           proc.returncode == 0 and not os.path.exists(sdir),
           proc.stdout[-160:])
    record("prune: pass log untouched",
           read(log) == "# Code Review — pr1\ndurable audit record\n")
    record("prune: model state file (state/<hash>.json) untouched",
           os.path.exists(model_state))
    proc = env.run("prune-state", "--scope", shash, "--yes")
    record("prune: re-prune of a gone scope is idempotent success",
           proc.returncode == 0 and "nothing to prune" in proc.stdout)

    # -- nothing outside state/ is addressable ------------------------------
    proc = env.run("prune-state", "--scope", "../evil", "--yes")
    record("prune: path components in a scope name refused",
           proc.returncode == 1 and "invalid scope name" in proc.stderr)
    outside = os.path.join(env.root, "outside-dir")
    os.makedirs(outside, exist_ok=True)
    canary = os.path.join(outside, "canary.txt")
    with open(canary, "w") as fh:
        fh.write("do not delete\n")
    link = os.path.join(state_root, "linked")
    os.symlink(outside, link)
    proc = env.run("prune-state", "--scope", "linked", "--yes")
    record("prune: symlinked scope dir refused, link target untouched",
           proc.returncode == 1 and "symlink" in proc.stderr
           and os.path.exists(canary))
    os.unlink(link)

    # -- run-pass starting during an in-flight prune fails fast -------------
    env.set_mode("ok")
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "pr3", "--pass-num", "1")
    sdir3 = os.path.join(state_root, json.loads(proc.stdout)["scope_hash"])
    plock = shared.ScopeLock(sdir3, role="prune")
    plock.acquire()
    proc = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                   "--scope-tag", "pr3")
    record("prune: run-pass starting mid-prune fails fast on the prune lock",
           proc.returncode == 1 and "locked by a live run" in proc.stderr
           and "role prune" in proc.stderr,
           proc.stderr.strip()[-160:])
    plock.release()

    # -- live-locked scopes are never touched -------------------------------
    env.clear_sleep_markers()
    env.set_mode("sleep")
    live = subprocess.Popen(
        [os.path.join(env.bin, "run-pass"), "--diff", env.diff,
         "--intent", env.intent, "--scope-tag", "pr2", "--pass-num", "1"],
        cwd=env.repo, env=env_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    record("prune: pr2 sleeping codex signalled readiness", env.wait_sleeper())
    deadline = time.time() + 10
    live_dir = None
    while time.time() < deadline and live_dir is None:
        for d in env.state_dirs():
            if os.path.exists(os.path.join(d, "run.lock")):
                live_dir = d
        time.sleep(0.05)
    before = sorted(os.listdir(live_dir))
    proc = env.run("prune-state", "--scope", os.path.basename(live_dir),
                   "--yes")
    record("prune: live-locked scope refused (--scope --yes), state intact",
           proc.returncode == 1 and "live run" in proc.stdout
           and sorted(os.listdir(live_dir)) == before,
           proc.stdout[-160:])

    # Age sweep (threshold 0 = everything): removes every unlocked scope —
    # earlier suites' leftovers included — but SKIPS the live one AND any
    # scope bearing a reclaim marker (markers get no automatic cleanup;
    # force-unlock is their only recovery). First clear test_lifecycle's
    # orphan-marker scope the documented way, then pin the marker behavior
    # with a marker-bearing scope of our own.
    env.run("prune-state", "--force-unlock", "orphanmarker", "--yes")
    marked = os.path.join(state_root, "prmarker")
    os.makedirs(marked)
    marked_marker = os.path.join(marked, "run.lock.reclaim")
    with open(marked_marker, "w") as fh:
        fh.write(json.dumps({"pid": spawn_dead_pid(), "timestamp": "t",
                             "role": "run-pass", "token": "m",
                             "owner_name": "x"}) + "\n")
    proc = env.run("prune-state", "--older-than", "0", "--yes")
    remaining = sorted(d for d in os.listdir(state_root)
                       if os.path.isdir(os.path.join(state_root, d)))
    expected = sorted([os.path.basename(live_dir), "prmarker"])
    record("prune: age sweep removes unlocked scopes, skips live + marked, exit 0",
           proc.returncode == 0 and "skipped" in proc.stdout
           and remaining == expected and os.path.exists(marked_marker),
           f"remaining={remaining}")
    record("prune: age sweep never touches state/<hash>.json files",
           os.path.exists(model_state))
    env.run("prune-state", "--force-unlock", "prmarker", "--yes")
    os.rmdir(marked)

    # Kill the live run: its lock is now a dead-pid stale lock, which a
    # targeted prune reclaims and removes in one invocation.
    live.send_signal(signal.SIGKILL)
    live.wait(timeout=10)
    proc = env.run("prune-state", "--scope", os.path.basename(live_dir),
                   "--yes")
    record("prune: dead-pid stale lock reclaimed, scope removed",
           proc.returncode == 0 and not os.path.exists(live_dir),
           proc.stdout[-160:])

    # -- force-unlock: stale lock + abandoned marker ------------------------
    fu = os.path.join(state_root, "fu1")
    os.makedirs(fu)
    fu_lock = os.path.join(fu, "run.lock")
    fu_marker = os.path.join(fu, "run.lock.reclaim")
    dead = spawn_dead_pid()
    with open(fu_lock, "w") as fh:
        fh.write(json.dumps({"pid": dead, "timestamp": "t", "role": "run-pass",
                             "token": "deadbeef", "owner_name": "x"}) + "\n")
    with open(fu_marker, "w") as fh:
        fh.write(json.dumps({"pid": dead, "timestamp": "t", "role": "run-pass",
                             "token": "feed", "owner_name": "x"}) + "\n")
    proc = env.run("prune-state", "--force-unlock", "fu1")
    record("force-unlock: dry run prints both files' state, clears nothing",
           proc.returncode == 0 and "dry run" in proc.stdout
           and "run.lock:" in proc.stdout and "run.lock.reclaim:" in proc.stdout
           and "dead" in proc.stdout
           and os.path.exists(fu_lock) and os.path.exists(fu_marker),
           proc.stdout[-200:])
    proc = env.run("prune-state", "--force-unlock", "fu1", "--yes")
    record("force-unlock: clears marker and lock together",
           proc.returncode == 0 and "cleared" in proc.stdout
           and not os.path.exists(fu_lock) and not os.path.exists(fu_marker))

    # Byte-identity primitive: a successor's fresh lock content never passes
    # a conditional removal predicated on the previously observed bytes.
    observed = b'{"pid": 1, "token": "old"}\n'
    with open(fu_lock, "wb") as fh:
        fh.write(b'{"pid": 2, "token": "successor"}\n')
    removed = shared._locked_mutation(
        fu_lock, lambda raw: raw == observed,
        lambda fd: os.unlink(fu_lock))
    record("force-unlock: byte-identity refuses a successor's fresh lock",
           removed is False and os.path.exists(fu_lock))

    # Two concurrent force-unlocks of the same stale lock: at most one
    # "cleared"; the loser refuses on mismatch/absence — never a crash,
    # never a second delete.
    with open(fu_lock, "w") as fh:
        fh.write(json.dumps({"pid": spawn_dead_pid(), "timestamp": "t",
                             "role": "run-pass", "token": "stale2",
                             "owner_name": "x"}) + "\n")
    procs = [subprocess.Popen(
        [os.path.join(env.bin, "prune-state"), "--force-unlock", "fu1",
         "--yes"],
        cwd=env.repo, env=env_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(2)]
    outs = [p.communicate(timeout=30)[0] for p in procs]
    cleared = sum("cleared" in o for o in outs)
    record("force-unlock: concurrent recoveries self-serialize (one winner)",
           cleared <= 1 and all(p.returncode in (0, 1) for p in procs)
           and not os.path.exists(fu_lock),
           f"cleared={cleared} exits={[p.returncode for p in procs]}")
    os.rmdir(fu)

    # -- force-unlock of a GENUINELY LIVE run (the plan's adversarial case):
    # the displaced run commits no summary and never unlinks the successor's
    # lock; the successor completes normally.
    env.clear_sleep_markers()
    env.set_mode("sleep3")
    displaced = subprocess.Popen(
        [os.path.join(env.bin, "run-pass"), "--diff", env.diff,
         "--intent", env.intent, "--scope-tag", "pr4", "--pass-num", "1"],
        cwd=env.repo, env=env_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    record("force-unlock: pr4 sleeping codex signalled readiness",
           env.wait_sleeper())
    deadline = time.time() + 10
    pr4_dir = None
    while time.time() < deadline and pr4_dir is None:
        for d in env.state_dirs():
            if os.path.exists(os.path.join(d, "run.lock")):
                pr4_dir = d
        time.sleep(0.05)
    proc = env.run("prune-state", "--force-unlock",
                   os.path.basename(pr4_dir), "--yes")
    record("force-unlock: live lock cleared under explicit --yes",
           proc.returncode == 0 and "ALIVE" in proc.stdout
           and "cleared" in proc.stdout,
           proc.stdout[-200:])
    env.set_mode("ok")  # safe: the readiness marker proves sleep3 was read
    successor = env.run("run-pass", "--diff", env.diff, "--intent", env.intent,
                        "--scope-tag", "pr4")
    _out, derr = displaced.communicate(timeout=30)
    summaries = sorted(f for f in os.listdir(pr4_dir)
                       if f.endswith(".summary.json"))
    succ_pass = json.loads(successor.stdout or "{}").get("pass")
    record("force-unlock: displaced run aborts — revocation detected, no summary",
           displaced.returncode != 0 and "revoked" in derr,
           f"exit={displaced.returncode} stderr={derr.strip()[-160:]}")
    record("force-unlock: successor completes; the only summary is the successor's",
           successor.returncode == 0 and succ_pass is not None
           and summaries == [f"pass-{succ_pass}.summary.json"],
           f"pass={succ_pass} summaries={summaries}")
    record("force-unlock: displaced run never unlinked the successor's state",
           not os.path.exists(os.path.join(pr4_dir, "run.lock")))


def test_prune_fold1(env: Env, shared) -> None:
    """Phase 2 review, pass-1 fold: malformed-metadata classification,
    terminal-safe inspection output, accurate partial force-unlock
    reporting, no-follow deletion."""
    state_root = os.path.join(env.skill, "state")
    env_path = dict(os.environ)
    env_path["PATH"] = env.fakebin + os.pathsep + env_path["PATH"]

    # Structurally incomplete or wrongly-typed pid metadata reads as
    # MALFORMED everywhere — never a crash, never a truncated/coerced pid
    # (1.9 must not be probed as pid 1; true must not be probed as pid 1).
    mf = os.path.join(state_root, "mf1")
    os.makedirs(mf)
    mf_lock = os.path.join(mf, "run.lock")
    for content in ('{}', '{"role": "run-pass"}',
                    '{"pid": 1.9, "token": "x"}',
                    '{"pid": "123", "token": "x"}',
                    '{"pid": true, "token": "x"}'):
        with open(mf_lock, "w") as fh:
            fh.write(content + "\n")
        o = env.run("prune-state")
        s = env.run("prune-state", "--scope", "mf1")
        f = env.run("prune-state", "--force-unlock", "mf1")
        if not (o.returncode == s.returncode == f.returncode == 0
                and "MALFORMED" in o.stdout and "MALFORMED" in s.stdout
                and "MALFORMED" in f.stdout):
            record("prune-fold1: incomplete/mistyped lock metadata reads "
                   "MALFORMED in overview, --scope, --force-unlock",
                   False, f"content={content} exits="
                   f"{[o.returncode, s.returncode, f.returncode]}")
            break
    else:
        record("prune-fold1: incomplete/mistyped lock metadata reads "
               "MALFORMED in overview, --scope, --force-unlock", True)

    # Control characters in lock bytes are escaped on output — a crafted
    # lock can't drive the operator's terminal during a recovery decision.
    with open(mf_lock, "w") as fh:
        fh.write('{"pid": %d, "token": "[31mEVIL]8;;x", '
                 '"role": "r"}\n' % os.getpid())
    proc = env.run("prune-state", "--force-unlock", "mf1")
    record("prune-fold1: inspection output escapes control characters",
           proc.returncode == 0 and "\x1b" not in proc.stdout
           and "\\x1b" in proc.stdout,
           proc.stdout[-160:])
    os.unlink(mf_lock)
    os.rmdir(mf)

    # Partial force-unlock under a mid-flight lock change: the marker's
    # removal is reported, the changed lock refuses, exit 1, and the new
    # lock content survives untouched.
    fu2 = os.path.join(state_root, "fu2")
    os.makedirs(fu2)
    fu2_lock = os.path.join(fu2, "run.lock")
    fu2_marker = os.path.join(fu2, "run.lock.reclaim")
    with open(fu2_marker, "w") as fh:
        fh.write(json.dumps({"pid": spawn_dead_pid(), "timestamp": "t",
                             "role": "run-pass", "token": "m2",
                             "owner_name": "x"}) + "\n")
    original = json.dumps({"pid": spawn_dead_pid(), "timestamp": "t",
                           "role": "run-pass", "token": "stale3",
                           "owner_name": "x"}) + "\n"
    with open(fu2_lock, "w") as fh:
        fh.write(original)
    successor = json.dumps({"pid": os.getpid(), "timestamp": "t",
                            "role": "run-pass", "token": "successor3",
                            "owner_name": "x"}) + "\n"
    hold = os.open(fu2_lock, os.O_RDWR)
    fcntl.flock(hold, fcntl.LOCK_EX)
    proc = subprocess.Popen(
        [os.path.join(env.bin, "prune-state"), "--force-unlock", "fu2",
         "--yes"],
        cwd=env.repo, env=env_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.time() + 10
    while time.time() < deadline and os.path.exists(fu2_marker):
        time.sleep(0.02)  # marker removal = force-unlock reached the lock
    marker_removed_first = not os.path.exists(fu2_marker)
    os.lseek(hold, 0, os.SEEK_SET)
    os.truncate(hold, 0)
    os.write(hold, successor.encode())
    fcntl.flock(hold, fcntl.LOCK_UN)
    os.close(hold)
    stdout, _ = proc.communicate(timeout=30)
    record("prune-fold1: partial force-unlock reports the marker removal AND "
           "the lock refusal, exit 1, successor content intact",
           marker_removed_first and proc.returncode == 1
           and "removed: run.lock.reclaim" in stdout
           and "refused: run.lock" in stdout
           and read(fu2_lock) == successor,
           f"exit={proc.returncode} out={stdout.strip()[-200:]}")
    os.unlink(fu2_lock)
    os.rmdir(fu2)

    # No-follow deletion: a nested symlink planted inside a scope is
    # unlinked as a LINK — its out-of-state target is never entered.
    outside = os.path.join(env.root, "outside-fold1")
    os.makedirs(outside)
    canary = os.path.join(outside, "canary.txt")
    with open(canary, "w") as fh:
        fh.write("survive\n")
    sym = os.path.join(state_root, "prsym")
    os.makedirs(sym)
    with open(os.path.join(sym, "pass-9.stray.input.txt"), "w") as fh:
        fh.write("orphan\n")
    os.symlink(outside, os.path.join(sym, "debug"))
    proc = env.run("prune-state", "--scope", "prsym", "--yes")
    record("prune-fold1: nested symlink unlinked as a link; target and its "
           "contents survive, scope fully removed",
           proc.returncode == 0 and not os.path.exists(sym)
           and read(canary) == "survive\n",
           proc.stdout[-160:])


def test_prune_fold2(env: Env, shared) -> None:
    """Phase 2 review, pass-2 fold: full dry-run disclosure, line-forgery-
    proof diagnostics (LF/tab), fd-anchored force-unlock."""
    state_root = os.path.join(env.skill, "state")

    # Dry run discloses EVERY removable entry — files, empty dirs, and
    # directory symlinks — and a confirmed prune removes exactly that set
    # without entering any symlink target.
    outside = os.path.join(env.root, "outside-fold2")
    os.makedirs(outside, exist_ok=True)
    canary = os.path.join(outside, "canary.txt")
    with open(canary, "w") as fh:
        fh.write("survive\n")
    sc = os.path.join(state_root, "disc1")
    os.makedirs(os.path.join(sc, "emptydir"))
    with open(os.path.join(sc, "pass-1.x.input.txt"), "w") as fh:
        fh.write("x\n")
    os.symlink(outside, os.path.join(sc, "linkdir"))
    proc = env.run("prune-state", "--scope", "disc1")
    record("prune-fold2: dry run discloses files, empty dirs, and dir symlinks",
           proc.returncode == 0
           and "pass-1.x.input.txt" in proc.stdout
           and "disc1/emptydir/" in proc.stdout
           and "disc1/linkdir" in proc.stdout
           and os.path.exists(os.path.join(sc, "linkdir")),
           proc.stdout[-240:])
    proc = env.run("prune-state", "--scope", "disc1", "--yes")
    record("prune-fold2: confirmed prune removes the disclosed set; symlink "
           "target untouched",
           proc.returncode == 0 and not os.path.exists(sc)
           and read(canary) == "survive\n")

    # LF/tab in untrusted lock bytes cannot forge diagnostic lines: raw
    # malformed content embedding a fake 'removed:' record renders as ONE
    # escaped line.
    fj = os.path.join(state_root, "forge1")
    os.makedirs(fj)
    fj_lock = os.path.join(fj, "run.lock")
    with open(fj_lock, "wb") as fh:
        fh.write(b'junk\nremoved: run.lock.reclaim\n\tcleared: scope forge1')
    proc = env.run("prune-state", "--force-unlock", "forge1")
    lines = proc.stdout.splitlines()
    record("prune-fold2: embedded LF/tab in raw lock bytes escaped — no "
           "forged output records",
           proc.returncode == 0 and "\\x0a" in proc.stdout
           and "\\x09" in proc.stdout
           and not any(ln.startswith(("removed:", "cleared:"))
                       for ln in lines),
           proc.stdout[-240:])
    # Same for a PARSED field: a JSON-escaped newline in role decodes to a
    # real newline before display; overview must keep the record one line.
    with open(fj_lock, "w") as fh:
        fh.write(json.dumps({"pid": os.getpid(), "timestamp": "t",
                             "role": "r\nFAKE-RECORD", "token": "x",
                             "owner_name": "x"}) + "\n")
    proc = env.run("prune-state")
    record("prune-fold2: newline inside a parsed lock field is escaped in "
           "the overview",
           proc.returncode == 0 and "\\x0a" in proc.stdout
           and not any(ln.startswith("FAKE-RECORD")
                       for ln in proc.stdout.splitlines()),
           proc.stdout[-200:])
    os.unlink(fj_lock)
    os.rmdir(fj)

    # fd-anchored force-unlock: a symlink sitting where run.lock should be
    # is reported, never followed, never acted on — the out-of-state target
    # survives with the link intact.
    real_lock = os.path.join(outside, "run.lock")
    with open(real_lock, "w") as fh:
        fh.write(json.dumps({"pid": spawn_dead_pid(), "timestamp": "t",
                             "role": "run-pass", "token": "victim",
                             "owner_name": "x"}) + "\n")
    sl = os.path.join(state_root, "symlock1")
    os.makedirs(sl)
    os.symlink(real_lock, os.path.join(sl, "run.lock"))
    proc = env.run("prune-state", "--force-unlock", "symlock1")
    record("prune-fold2: symlinked run.lock reported as SYMLINK on dry run, "
           "not read",
           proc.returncode == 0 and "SYMLINK" in proc.stdout
           and "victim" not in proc.stdout,
           proc.stdout[-200:])
    proc = env.run("prune-state", "--force-unlock", "symlock1", "--yes")
    record("prune-fold2: --yes on a symlinked lock refuses; link and target "
           "both intact",
           proc.returncode == 1 and "refused" in proc.stdout
           and os.path.islink(os.path.join(sl, "run.lock"))
           and os.path.exists(real_lock))
    # Primitive pin: the fd-anchored fencing helper refuses a symlink at
    # the lock name outright.
    sfd = os.open(sl, os.O_RDONLY | os.O_DIRECTORY)
    try:
        ran = shared._locked_mutation(
            os.path.join(sl, "run.lock"), lambda raw: True,
            lambda fd: None, dir_fd=sfd)
    finally:
        os.close(sfd)
    record("prune-fold2: _locked_mutation(dir_fd=...) refuses a symlinked "
           "lock file",
           ran is False and os.path.exists(real_lock))
    os.unlink(os.path.join(sl, "run.lock"))
    os.rmdir(sl)


def test_prune_fold3(env: Env, shared) -> None:
    """Phase 2 review, pass-3 fold: under-lock freshness recheck, non-regular
    lock classification, genuine-failure reporting, name sanitization."""
    state_root = os.path.join(env.skill, "state")

    # Age-sweep regression trap: a genuinely old scope MUST still be swept —
    # the under-lock freshness recheck must not be fooled by the mtime bumps
    # prune's own lock acquisition causes (dir mtime + fresh run.lock).
    old = os.path.join(state_root, "old1")
    os.makedirs(old)
    with open(os.path.join(old, "pass-1.x.input.txt"), "w") as fh:
        fh.write("x\n")
    backdate = time.time() - 2 * 86400
    os.utime(os.path.join(old, "pass-1.x.input.txt"), (backdate, backdate))
    os.utime(old, (backdate, backdate))
    proc = env.run("prune-state", "--older-than", "1", "--yes")
    record("prune-fold3: backdated scope swept — recheck ignores its own "
           "lock's mtime bumps",
           proc.returncode == 0 and not os.path.exists(old),
           proc.stdout[-200:])

    # The under-lock recheck itself: only_if=False under the lock -> scope
    # untouched, 'skipped', and no lock left behind.
    loader = importlib.machinery.SourceFileLoader(
        "ps_mod", os.path.join(env.bin, "prune-state"))
    spec = importlib.util.spec_from_loader("ps_mod", loader)
    ps = importlib.util.module_from_spec(spec)
    loader.exec_module(ps)
    fresh = os.path.join(state_root, "fresh1")
    os.makedirs(fresh)
    keep = os.path.join(fresh, "pass-1.x.input.txt")
    with open(keep, "w") as fh:
        fh.write("keep\n")
    outcome, problems = ps.delete_scope(ps.Path(fresh),
                                        only_if=lambda: False)
    record("prune-fold3: only_if=False under the lock skips — nothing "
           "deleted, lock released",
           outcome == "skipped" and problems == []
           and read(keep) == "keep\n"
           and not os.path.exists(os.path.join(fresh, "run.lock")))
    os.unlink(keep)
    os.rmdir(fresh)

    # Non-regular objects at lock names: classified without crashing or
    # hanging, and destructive modes refuse.
    for maker, kind in ((os.mkdir, "directory"), (os.mkfifo, "fifo")):
        nr = os.path.join(state_root, "nr1")
        os.makedirs(nr)
        maker(os.path.join(nr, "run.lock"))
        o = env.run("prune-state")
        s = env.run("prune-state", "--scope", "nr1")
        fdry = env.run("prune-state", "--force-unlock", "nr1")
        fyes = env.run("prune-state", "--force-unlock", "nr1", "--yes")
        pyes = env.run("prune-state", "--scope", "nr1", "--yes")
        still = os.path.exists(os.path.join(nr, "run.lock"))
        record(f"prune-fold3: {kind} at run.lock — inspected without "
               f"crash/hang, destructive modes refuse, object untouched",
               o.returncode == 0 and "MALFORMED" in o.stdout
               and s.returncode == 0
               and fdry.returncode == 0 and "NOT A REGULAR FILE" in fdry.stdout
               and fyes.returncode == 1 and pyes.returncode == 1 and still,
               f"exits={[o.returncode, s.returncode, fdry.returncode, fyes.returncode, pyes.returncode]}")
        if kind == "directory":
            os.rmdir(os.path.join(nr, "run.lock"))
        else:
            os.unlink(os.path.join(nr, "run.lock"))
        os.rmdir(nr)

    # Genuine removal failures surface as exit 1 with the failing entry —
    # never as the benign "a new run owns it now" handoff.
    fl = os.path.join(state_root, "faildel")
    os.makedirs(os.path.join(fl, "sub"))
    with open(os.path.join(fl, "sub", "stuck.txt"), "w") as fh:
        fh.write("stuck\n")
    os.chmod(os.path.join(fl, "sub"), 0o555)
    proc = env.run("prune-state", "--scope", "faildel", "--yes")
    record("prune-fold3: undeletable entry -> exit 1 naming the entry, no "
           "false new-run handoff",
           proc.returncode == 1 and "failed" in proc.stdout
           and "stuck.txt" in proc.stdout
           and "new run" not in proc.stdout,
           proc.stdout[-240:])
    os.chmod(os.path.join(fl, "sub"), 0o755)
    proc = env.run("prune-state", "--scope", "faildel", "--yes")
    record("prune-fold3: after the obstacle clears, the same prune succeeds",
           proc.returncode == 0 and not os.path.exists(fl))

    # Filesystem-derived names are sanitized: a scope/entry name carrying
    # ESC or LF cannot forge output records.
    weird = os.path.join(state_root, "ev\x1bil")
    os.makedirs(weird)
    with open(os.path.join(weird, "fi\nle.txt"), "w") as fh:
        fh.write("x\n")
    o = env.run("prune-state")
    s = env.run("prune-state", "--scope", "ev\x1bil")
    record("prune-fold3: control chars in scope/entry names escaped in "
           "overview and dry run",
           o.returncode == 0 and s.returncode == 0
           and "\x1b" not in o.stdout and "\x1b" not in s.stdout
           and "\\x1b" in o.stdout and "\\x1b" in s.stdout
           and "\\x0a" in s.stdout,
           s.stdout[-200:])
    proc = env.run("prune-state", "--scope", "ev\x1bil", "--yes")
    record("prune-fold3: weird-named scope still deletable",
           proc.returncode == 0 and not os.path.exists(weird))


def _load_prune_module(env: Env):
    loader = importlib.machinery.SourceFileLoader(
        "ps_mod4", os.path.join(env.bin, "prune-state"))
    spec = importlib.util.spec_from_loader("ps_mod4", loader)
    ps = importlib.util.module_from_spec(spec)
    loader.exec_module(ps)
    return ps


def test_prune_fold4(env: Env, shared) -> None:
    """Phase 2 review, pass-4 fold: exact-disclosure fence on targeted prune,
    fd-anchored lock acquisition, honest partial-deletion reporting."""
    state_root = os.path.join(env.skill, "state")
    ps = _load_prune_module(env)

    # Targeted prune refuses when entries exist that disclosure didn't list
    # (a run reused the scope between disclosure and lock acquisition).
    tp = os.path.join(state_root, "tp1")
    os.makedirs(tp)
    with open(os.path.join(tp, "pass-1.a.input.txt"), "w") as fh:
        fh.write("a\n")
    with open(os.path.join(tp, "extra.txt"), "w") as fh:
        fh.write("appeared-after-disclosure\n")
    orig_disclose = ps.disclose
    calls = {"n": 0}

    def stale_first(d):
        calls["n"] += 1
        entries = orig_disclose(d)
        if calls["n"] == 1:  # the disclosure pass has a stale view
            return [e for e in entries if "extra" not in e]
        return entries       # the under-lock recheck sees reality

    ps.disclose = stale_first
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = ps.prune_one("tp1", True)
    ps.disclose = orig_disclose
    record("prune-fold4: undisclosed entries under the lock -> refuse, "
           "nothing deleted",
           rc == 1 and "not disclosed" in buf.getvalue()
           and os.path.exists(os.path.join(tp, "pass-1.a.input.txt"))
           and os.path.exists(os.path.join(tp, "extra.txt"))
           and not os.path.exists(os.path.join(tp, "run.lock")),
           buf.getvalue().strip()[-160:])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = ps.prune_one("tp1", True)
    record("prune-fold4: re-run after re-disclosure deletes cleanly",
           rc == 0 and not os.path.exists(tp))

    # fd-anchored lock acquisition: with the scope pathname swapped for a
    # symlink AFTER the descriptor was taken, every lock operation stays
    # inside the original (anchored) directory — nothing is ever created
    # through the symlink.
    outside = os.path.join(env.root, "outside-fold4")
    os.makedirs(outside, exist_ok=True)
    anchor = os.path.join(state_root, "anchor1")
    os.makedirs(anchor)
    fd = os.open(anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    moved = os.path.join(state_root, "anchor1-moved")
    os.rename(anchor, moved)
    os.symlink(outside, anchor)  # the validated pathname now points OUT
    try:
        lk = shared.ScopeLock(anchor, role="prune", dir_fd=fd)
        lk.acquire()
        created_inside = os.path.exists(os.path.join(moved, "run.lock"))
        created_outside = os.path.exists(os.path.join(outside, "run.lock"))
        lk.release()
        released_inside = not os.path.exists(os.path.join(moved, "run.lock"))
    finally:
        os.close(fd)
    record("prune-fold4: dir_fd-anchored ScopeLock never operates through a "
           "swapped-in symlink",
           created_inside and not created_outside and released_inside)
    os.unlink(anchor)
    os.rmdir(moved)

    # Ownership revoked AFTER deletion began is a PARTIAL failure (exit 1),
    # never reported as a skip.
    pd = os.path.join(state_root, "pd1")
    os.makedirs(pd)
    with open(os.path.join(pd, "pass-1.a.input.txt"), "w") as fh:
        fh.write("a\n")
    with open(os.path.join(pd, "pass-1.b.input.txt"), "w") as fh:
        fh.write("b\n")
    orig_tree = ps._delete_tree_fd

    def partial_then_revoked(dir_fd, lock, problems, at, skip=None):
        os.unlink("pass-1.a.input.txt", dir_fd=dir_fd)
        raise ps.shared.LockError("simulated revocation")

    ps._delete_tree_fd = partial_then_revoked
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = ps.prune_one("pd1", True)
    ps._delete_tree_fd = orig_tree
    text = buf.getvalue()
    record("prune-fold4: revocation mid-deletion reports PARTIAL failure, "
           "exit 1, never a skip",
           rc == 1 and "PARTIAL" in text and "skipped" not in text
           and not os.path.exists(os.path.join(pd, "pass-1.a.input.txt"))
           and os.path.exists(os.path.join(pd, "pass-1.b.input.txt")),
           text.strip()[-200:])
    shutil.rmtree(pd)


def test_prune_fold5(env: Env, shared) -> None:
    """Phase 2 review, pass-5 fold: no pid coercion on destructive paths,
    prune-vs-prune disappearance, identity-fenced final rmdir, sanitized
    refusal diagnostics."""
    state_root = os.path.join(env.skill, "state")
    env_path = dict(os.environ)
    env_path["PATH"] = env.fakebin + os.pathsep + env_path["PATH"]

    # Malformed pid variants on the DESTRUCTIVE path: refused as malformed —
    # never coerced into a probe-able pid, never a traceback.
    mp = os.path.join(state_root, "mp1")
    os.makedirs(mp)
    mp_lock = os.path.join(mp, "run.lock")
    for content in ('{"pid": "abc", "token": "x"}',
                    '{"pid": 1.9, "token": "x"}',
                    '{"pid": true, "token": "x"}'):
        with open(mp_lock, "w") as fh:
            fh.write(content + "\n")
        proc = env.run("prune-state", "--scope", "mp1", "--yes")
        if not (proc.returncode == 1 and "malformed metadata" in proc.stdout
                and "Traceback" not in proc.stderr
                and os.path.exists(mp_lock)):
            record("prune-fold5: malformed pid on --scope --yes refuses "
                   "without coercion or traceback", False,
                   f"content={content} exit={proc.returncode} "
                   f"{(proc.stdout + proc.stderr).strip()[-160:]}")
            break
    else:
        record("prune-fold5: malformed pid on --scope --yes refuses "
               "without coercion or traceback", True)
    os.unlink(mp_lock)
    # Marker with a malformed pid refuses as abandoned (never probed).
    with open(os.path.join(mp, "run.lock.reclaim"), "w") as fh:
        fh.write('{"pid": "abc", "token": "x"}\n')
    proc = env.run("prune-state", "--scope", "mp1", "--yes")
    record("prune-fold5: malformed reclaim-marker pid -> abandoned-marker "
           "refusal on the destructive path",
           proc.returncode == 1 and "reclaim marker" in proc.stdout
           and "Traceback" not in proc.stderr)
    proc = env.run("prune-state", "--force-unlock", "mp1", "--yes")
    proc = env.run("prune-state", "--scope", "mp1", "--yes")
    record("prune-fold5: after force-unlock recovery the same scope prunes",
           proc.returncode == 0 and not os.path.exists(mp))

    # Two concurrent age sweeps over the same candidates: no tracebacks,
    # both complete, everything old is gone exactly once.
    backdate = time.time() - 2 * 86400
    for i in range(12):
        d = os.path.join(state_root, f"race{i:02d}")
        os.makedirs(d)
        f = os.path.join(d, "pass-1.x.input.txt")
        with open(f, "w") as fh:
            fh.write("x\n")
        os.utime(f, (backdate, backdate))
        os.utime(d, (backdate, backdate))
    procs = [subprocess.Popen(
        [os.path.join(env.bin, "prune-state"), "--older-than", "1", "--yes"],
        cwd=env.repo, env=env_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(2)]
    outs = [p.communicate(timeout=60) for p in procs]
    leftovers = [d for d in os.listdir(state_root) if d.startswith("race")]
    record("prune-fold5: two concurrent age sweeps — no tracebacks, all "
           "candidates swept",
           all(p.returncode == 0 for p in procs)
           and not any("Traceback" in e for _, e in outs)
           and leftovers == [],
           f"exits={[p.returncode for p in procs]} leftovers={leftovers}")

    # Identity-fenced final rmdir: if the pathname stops naming the anchored
    # inode mid-deletion, the replacement is NOT removed and the outcome is
    # 'survived', never 'deleted'.
    ps = _load_prune_module(env)
    idf = os.path.join(state_root, "idf1")
    os.makedirs(idf)
    moved = os.path.join(state_root, "idf1-moved")
    orig_tree = ps._delete_tree_fd

    def swap_during_delete(dir_fd, lock, problems, at, skip=None):
        os.rename(idf, moved)
        os.makedirs(idf)  # a NEW real directory now sits at the name

    ps._delete_tree_fd = swap_during_delete
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = ps.prune_one("idf1", True)
    ps._delete_tree_fd = orig_tree
    record("prune-fold5: swapped-in real directory at the name is never "
           "rmdir'd — outcome is survival, not deletion",
           rc == 0 and os.path.isdir(idf)
           and "not removed" in buf.getvalue()
           and not os.path.exists(os.path.join(moved, "run.lock")),
           buf.getvalue().strip()[-160:])
    os.rmdir(idf)
    os.rmdir(moved)

    # Refusal diagnostics are sanitized: a control-char scope name that hits
    # the symlink-refusal path leaks no raw control bytes on stderr.
    weird = "sym\x1blnk"
    os.symlink(os.path.join(env.root, "outside-fold4"),
               os.path.join(state_root, weird))
    proc = env.run("prune-state", "--scope", weird, "--yes")
    record("prune-fold5: refusal diagnostics escape control bytes",
           proc.returncode == 1 and "\x1b" not in proc.stderr
           and "\\x1b" in proc.stderr,
           proc.stderr.strip()[-160:])
    os.unlink(os.path.join(state_root, weird))


def test_prune_fold6(env: Env, shared) -> None:
    """Phase 2 review, pass-6 fold: scope age never follows symlinks."""
    state_root = os.path.join(env.skill, "state")
    outside = os.path.join(env.root, "outside-fold6")
    os.makedirs(outside)
    hot = os.path.join(outside, "hot.txt")
    with open(hot, "w") as fh:
        fh.write("recently modified\n")  # fresh target
    ag = os.path.join(state_root, "agesym1")
    os.makedirs(ag)
    link = os.path.join(ag, "linked")
    os.symlink(hot, link)
    backdate = time.time() - 2 * 86400
    os.utime(link, (backdate, backdate), follow_symlinks=False)
    os.utime(ag, (backdate, backdate))
    proc = env.run("prune-state", "--older-than", "1", "--yes")
    record("prune-fold6: old scope with old symlink to a FRESH target is "
           "still swept; target survives",
           proc.returncode == 0 and not os.path.exists(ag)
           and read(hot) == "recently modified\n",
           proc.stdout[-200:])


def spawn_dead_pid() -> int:
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    try:
        rr = load(os.path.join(SKILL, "bin", "review_runner.py"), "rr_check")
        shared = load(os.path.join(SKILL, "bin", "runner_shared.py"), "shared_check")
    except Exception as exc:  # noqa: BLE001
        print(f"setup error loading runner modules: {exc}", file=sys.stderr)
        return 2

    tmp = tempfile.mkdtemp(prefix="check-runners-")
    try:
        env = Env(tmp)
        test_composition(rr)
        test_contracts(env)
        test_lifecycle(env, shared)
        test_immutability(env, shared)
        test_pass2_fold(env, shared)
        test_prune(env, shared)
        test_prune_fold1(env, shared)
        test_prune_fold2(env, shared)
        test_prune_fold3(env, shared)
        test_prune_fold4(env, shared)
        test_prune_fold5(env, shared)
        test_prune_fold6(env, shared)
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f"setup error: {exc}", file=sys.stderr)
        return 2
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    width = max(len(n) for n, _, _ in results)
    failed = [n for n, ok, _ in results if not ok]
    for name, ok, detail in results:
        mark = "ok  " if ok else "FAIL"
        extra = f"  ({detail})" if detail and not ok else ""
        print(f"  {mark}  {name:<{width}}{extra}")
    print()
    if failed:
        print(f"{len(results) - len(failed)}/{len(results)} passed -- "
              f"FAILED: {', '.join(failed)}")
        return 1
    print(f"{len(results)}/{len(results)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
