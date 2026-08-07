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

No network and no real codex: subprocess tests run against a COPY of the
skill directory (which doubles as the plain-copy install layout check) with a
fake `codex` on PATH that replays canned responses.

Usage:
    tools/check-runners.py            # exit 0 all pass, 1 failures, 2 setup error
"""

from __future__ import annotations

import importlib.util
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
        self.diff = os.path.join(self.repo, "diff.txt")
        with open(self.diff, "w") as fh:
            fh.write("diff --git a/lib/plain.py b/lib/plain.py\n"
                     "--- a/lib/plain.py\n+++ b/lib/plain.py\n"
                     "@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n")
        self.intent = os.path.join(self.repo, "intent.txt")
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
    # must live inside THAT boundary (the fallback root is the cwd).
    nongit = tempfile.mkdtemp(dir=env.root)
    shutil.copy(env.diff, os.path.join(nongit, "diff.txt"))
    shutil.copy(env.intent, os.path.join(nongit, "intent.txt"))
    proc = env.run("run-pass", "--diff", os.path.join(nongit, "diff.txt"),
                   "--intent", os.path.join(nongit, "intent.txt"),
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
    env.set_mode("sleep")
    env_path = dict(os.environ)
    env_path["PATH"] = env.fakebin + os.pathsep + env_path["PATH"]
    slow = subprocess.Popen(
        [os.path.join(env.bin, "run-pass"), "--diff", env.diff,
         "--intent", env.intent, "--scope-tag", "t9", "--pass-num", "1"],
        cwd=env.repo, env=env_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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

    # Standalone run-lens during a live run-pass leaves published state alone.
    scope4_lock = shared.ScopeLock(
        os.path.join(state_root, "livescope"), role="run-pass")
    scope4_lock.acquire()
    env.set_mode("ok")
    proc = env.run("run-lens", "--diff", env.diff, "--intent", env.intent,
                   "--lens", "senior-dev", "--scope-tag", "t9")
    published_before = sorted(os.listdir(t9_dir))
    record("lifecycle: standalone run-lens during a live run-pass succeeds "
           "and touches no published state",
           proc.returncode == 0 and sorted(
               f for f in os.listdir(t9_dir) if f.startswith("pass-"))
           == [f for f in published_before if f.startswith("pass-")])
    scope4_lock.release()


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
    env.set_mode("sleep3")
    known = set(env.state_dirs())
    slow = subprocess.Popen(
        [os.path.join(env.bin, "run-pass"), "--diff", env.diff,
         "--intent", env.intent, "--scope-tag", "imm4", "--pass-num", "1"],
        cwd=env.repo, env=env_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
