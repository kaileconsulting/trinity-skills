#!/usr/bin/env python3
"""Fixtures for the iterate-plan runner scripts (bin/).

Pins the ADAPTED behavior the runner-scripts plan promises for the Phase 3
port (docs/runner-scripts-artifact-hygiene-2026-08-06.md): composition,
required-section extraction, trivial always-all lens selection, the --plan /
--note trusted boundaries, and a smoke pass over the shared contracts as
wired through the plan CLIs.

The deep shared-machinery behavior (lock lifecycle, adversarial reclaim,
prune fencing, displacement) is NOT re-pinned here: runner_shared.py and
prune-state are byte-identical copies of iterate-review's (hash-checked by
tools/check-parity.py), and tools/check-runners.py pins that behavior once.
This suite proves the iterate-plan WIRING: the CLIs route through the same
machinery and the adapted composition/selection/boundary logic is correct.

No network and no real codex: subprocess tests run against a COPY of the
skill directory (which doubles as the plain-copy install layout check) with a
fake `codex` on PATH that replays canned responses.

Usage:
    tools/check-plan-runners.py       # exit 0 all pass, 1 failures, 2 setup error
"""

from __future__ import annotations

import glob
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)
SKILL = os.path.join(REPO, "iterate-plan")
COMPOSITION = os.path.join(SKILL, "examples", "composition")

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


def load(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_without_codex(env, script, *args):
    """Run a bin/ script with a PATH that contains python3 and git but NO
    codex at all (a shim dir of symlinks — the machine's real codex must not
    be reachable as a fallback)."""
    shim = os.path.join(env.root, "shim-no-codex")
    if not os.path.isdir(shim):
        os.makedirs(shim)
        for tool in ("python3", "git"):
            target = shutil.which(tool)
            if target:
                os.symlink(target, os.path.join(shim, tool))
    e = dict(os.environ)
    e["PATH"] = shim
    return subprocess.run([os.path.join(env.bin, script), *args],
                          cwd=env.repo, env=e, timeout=60,
                          capture_output=True, text=True)


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


PLAN_TEXT = """# Fixture Plan

## Status
draft

## Who / Use cases
Fixture users.

## Approach
The fixture approach.

### Stack decisions
Kept with Approach.

## Acceptance criteria
- fixture criterion

## Phasing
Phase 1: fixture.
"""


# ---------------------------------------------------------------------------
# Environment: a copied skill install + a fake codex + a scratch git repo
# ---------------------------------------------------------------------------

class Env:
    def __init__(self, root: str):
        self.root = root
        # Plain-copy install layout: the same tree a user gets from cp -r.
        self.skill = os.path.join(root, "iterate-plan")
        shutil.copytree(SKILL, self.skill,
                        ignore=shutil.ignore_patterns("state"))
        os.makedirs(os.path.join(self.skill, "state"), exist_ok=True)
        self.bin = os.path.join(self.skill, "bin")

        self.fakebin = os.path.join(root, "fakebin")
        os.makedirs(self.fakebin)
        self.mode_file = os.path.join(root, "codex-mode")
        self._write_fake_codex()

        self.repo = os.path.join(root, "repo")
        os.makedirs(os.path.join(self.repo, "docs"))
        subprocess.run(["git", "init", "-q", self.repo], check=True,
                       stdout=subprocess.DEVNULL)
        self.plan = os.path.join(self.repo, "docs", "plan.md")
        with open(self.plan, "w") as fh:
            fh.write(PLAN_TEXT)
        # Staged notes live in the ENFORCED per-repo handoff dir.
        self.handoff = os.path.join(self.repo, ".git", "iterate-plan")
        os.makedirs(self.handoff)
        self.note = os.path.join(self.handoff, "note.txt")
        with open(self.note, "w") as fh:
            fh.write("Human edits since last pass — diff:\n- fixture edit\n")
        # A committed HEAD, with no docs/risk-posture.md yet: the default
        # state every pre-existing test in this file runs against is
        # register-confirmed-absent (Phase 1, Q5) -- composition stays
        # byte-identical to before the register feature existed, so none of
        # the tests below needed to change. commit_register() (below)
        # layers a register commit on top for the tests that need one.
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "initial")

    def _git(self, *args) -> None:
        subprocess.run(
            ["git", "-c", "user.email=fixture@example.com",
             "-c", "user.name=fixture", *args],
            cwd=self.repo, check=True, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)

    def commit_register(self, text: str) -> None:
        """Write docs/risk-posture.md with `text` and commit it -- moves
        this Env's HEAD from confirmed-absent to whatever state `text`
        represents (loaded, or malformed if it carries duplicate RR- ids)."""
        path = os.path.join(self.repo, "docs", "risk-posture.md")
        with open(path, "w") as fh:
            fh.write(text)
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "register")

    def _write_fake_codex(self) -> None:
        path = os.path.join(self.fakebin, "codex")
        with open(path, "w") as fh:
            fh.write(f'''#!/usr/bin/env python3
import json, os, sys, time
args = sys.argv[1:]
# Record the exact argv (and cwd) of every invocation: the -C contract is
# part of the runner's promise and must be assertable, not assumed.
with open(os.path.join({self.root!r},
                       "codex-argv-%d.json" % os.getpid()), "w") as fh:
    json.dump({{"argv": args, "cwd": os.getcwd()}}, fh)
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
if mode == "sleep3":
    with open({self.mode_file!r} + ".sleeping-" + str(os.getpid()), "w"):
        pass
    time.sleep(3)
if mode == "fail":
    sys.exit(3)
if mode == "structural":
    with open(out, "w") as fh:
        fh.write('{{"verdict": "APPROVE", "findings": []}}')
    sys.exit(0)
if mode == "patchmarkers":
    resp = {{"verdict": "REVISE",
            "findings": [{{"title": "bad", "severity": "HIGH",
                          "description": "*** Begin Patch\\\\n--- a/x\\\\n+++ b/x"}}],
            "plan_corrections": [], "open_question_answers": [],
            "new_questions": []}}
    with open(out, "w") as fh:
        json.dump(resp, fh)
    sys.exit(0)
resp = {{"verdict": "APPROVE", "findings": [], "plan_corrections": [],
        "open_question_answers": [], "new_questions": []}}
with open(out, "w") as fh:
    json.dump(resp, fh)
''')
        os.chmod(path, 0o755)

    def set_mode(self, mode: str) -> None:
        with open(self.mode_file, "w") as fh:
            fh.write(mode)

    def clear_argv_records(self) -> None:
        for p in glob.glob(os.path.join(self.root, "codex-argv-*.json")):
            os.remove(p)

    def argv_records(self):
        out = []
        for p in sorted(glob.glob(os.path.join(self.root, "codex-argv-*.json"))):
            with open(p, encoding="utf-8") as fh:
                out.append(json.load(fh))
        return out

    def clear_sleep_markers(self) -> None:
        for p in glob.glob(self.mode_file + ".sleeping-*"):
            os.remove(p)

    def wait_sleeper(self, timeout: float = 10) -> bool:
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

    def popen(self, script: str, *args, cwd=None):
        env = dict(os.environ)
        env["PATH"] = self.fakebin + os.pathsep + env["PATH"]
        return subprocess.Popen(
            [os.path.join(self.bin, script), *args],
            cwd=cwd or self.repo, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def scope_hash(self) -> str:
        real = os.path.realpath(self.plan)
        return hashlib.sha1(real.encode("utf-8")).hexdigest()

    def state_dir(self) -> str:
        return os.path.join(self.skill, "state", self.scope_hash())


# ---------------------------------------------------------------------------
# Composition goldens + extraction semantics (module-level, pure)
# ---------------------------------------------------------------------------

def test_composition(pr) -> None:
    prompt = read(os.path.join(COMPOSITION, "prompt.txt"))
    body = read(os.path.join(COMPOSITION, "lens-body.txt"))
    mc = read(os.path.join(COMPOSITION, "matched-context.txt")).strip()
    plan = read(os.path.join(COMPOSITION, "plan.txt"))
    note = read(os.path.join(COMPOSITION, "note.txt"))

    sections = pr.extract_required_sections(plan, ["Approach", "Phasing"])
    got = pr.compose_input(prompt, "test-lens", body, mc, sections, plan)
    record("composition: golden plain (byte-identical)",
           got == read(os.path.join(COMPOSITION, "golden-plain.txt")))

    got = pr.compose_input(prompt, "test-lens", body, mc, sections, plan, note)
    record("composition: golden with staged note (byte-identical)",
           got == read(os.path.join(COMPOSITION, "golden-with-note.txt"))
           and "=== NOTE: HUMAN EDITS SINCE LAST PASS ===" in got)

    absent = pr.extract_required_sections(plan,
                                          ["Approach", "Acceptance criteria"])
    got = pr.compose_input(prompt, "test-lens", body, mc, absent, plan)
    record("composition: golden absent-section carries the NOTE line",
           got == read(os.path.join(COMPOSITION, "golden-absent-section.txt"))
           and 'required section "Acceptance criteria" is absent' in got)

    record("composition: empty note composes identically to no note",
           pr.compose_input(prompt, "l", body, mc, sections, plan, "  \n")
           == pr.compose_input(prompt, "l", body, mc, sections, plan))

    # --- register composition (Trinity v2.4 Phase 1, Q5) -------------------
    register = read(os.path.join(COMPOSITION, "register.txt"))
    got = pr.compose_input(prompt, "test-lens", body, mc, sections, plan,
                           register=register)
    record("composition: golden with register (byte-identical)",
           got == read(os.path.join(COMPOSITION, "golden-with-register.txt"))
           and "=== ACCEPTED RISKS ===" in got)
    record("composition: no-register call is byte-identical to golden-plain "
           "(zero register-specific bytes when absent)",
           pr.compose_input(prompt, "test-lens", body, mc, sections, plan)
           == read(os.path.join(COMPOSITION, "golden-plain.txt")))
    record("composition: register='' composes identically to register omitted",
           pr.compose_input(prompt, "l", body, mc, sections, plan, "", "")
           == pr.compose_input(prompt, "l", body, mc, sections, plan))
    record("composition: whitespace-only register composes as absent",
           pr.compose_input(prompt, "l", body, mc, sections, plan, "", "  \n")
           == pr.compose_input(prompt, "l", body, mc, sections, plan))

    # Determinism against the REAL skill inputs: composing twice is bytewise
    # stable for every lens record.
    lens_ids = sorted(
        f[:-3] for f in os.listdir(os.path.join(SKILL, "lenses"))
        if f.endswith(".md") and f != "README.md")
    stable = all(
        pr.compose_for_lens(lid, PLAN_TEXT) == pr.compose_for_lens(lid, PLAN_TEXT)
        for lid in lens_ids)
    record("composition: real-lens composition is repeat-stable", stable,
           f"lenses: {', '.join(lens_ids)}")

    body2, mc2, sel2 = pr.read_lens_record("architect")
    record("lens record: matched_context folded to one line",
           "\n" not in mc2 and mc2.startswith("The Approach section"))
    record("lens record: body starts after frontmatter",
           body2.startswith("## ROLE"))
    record("lens record: selection block parsed",
           sel2 == {"always": True,
                    "requires_sections": ["Approach", "Phasing"]})


def _git_fixture(*, commit_plan=True, register_text=None):
    """A scratch git repo, isolated from the Env class's shared fixture, for
    exercising resolve_register()'s four states directly against real git
    plumbing rather than mocking subprocess. `commit_plan=False` leaves the
    repo with zero commits at all (the no-HEAD-yet operational-failure
    case) -- everything else commits once. `register_text`, when given,
    writes+commits docs/risk-posture.md with that content in the same
    commit as the plan (loaded / malformed, depending on the text)."""
    tmp = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-q", tmp], check=True,
                   stdout=subprocess.DEVNULL)
    if not commit_plan:
        return tmp
    os.makedirs(os.path.join(tmp, "docs"), exist_ok=True)
    with open(os.path.join(tmp, "docs", "plan.md"), "w") as fh:
        fh.write(PLAN_TEXT)
    if register_text is not None:
        with open(os.path.join(tmp, "docs", "risk-posture.md"), "w") as fh:
            fh.write(register_text)
    subprocess.run(["git", "-c", "user.email=fixture@example.com",
                    "-c", "user.name=fixture", "add", "-A"],
                   cwd=tmp, check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "-c", "user.email=fixture@example.com",
                    "-c", "user.name=fixture", "commit", "-q", "-m", "init"],
                   cwd=tmp, check=True, stdout=subprocess.DEVNULL)
    return tmp


def test_register_resolution(pr) -> None:
    """resolve_register()'s four states (Trinity v2.4 Phase 1, Q5), against
    real scratch git repos -- this is runner control flow, not editor
    prose, so it gets the same executable-fixture treatment as every other
    control-flow rule in this repo (scope_classifier.py, freeze_tracker.py)."""
    from pathlib import Path as _Path

    # loaded
    repo = _git_fixture(register_text=(
        "## Accepted risks\n\n"
        "- **RR-2026-08-06-seq-poison** — fixture behavior; bound: n/a; "
        "recovery: n/a.\n"))
    result = pr.resolve_register(_Path(repo))
    record("register: well-formed register resolves to loaded",
           result.state == "loaded"
           and "RR-2026-08-06-seq-poison" in result.text
           and result.text.startswith("## Accepted risks"))
    shutil.rmtree(repo, ignore_errors=True)

    # confirmed_absent — no docs/risk-posture.md at HEAD at all
    repo = _git_fixture()
    result = pr.resolve_register(_Path(repo))
    record("register: missing file at HEAD resolves to confirmed_absent",
           result.state == "confirmed_absent")
    shutil.rmtree(repo, ignore_errors=True)

    # confirmed_absent — the freshly-seeded create-plan case: the file
    # exists UNTRACKED on disk but was never committed. Git phrases this
    # boundary differently from "never existed at any revision" ("exists
    # on disk, but not in 'HEAD'" vs "does not exist in 'HEAD'") -- caught
    # by iterate-review's own code review (pass 6) as a real misrouting to
    # operational_failure before this fix.
    repo = _git_fixture()
    with open(os.path.join(repo, "docs", "risk-posture.md"), "w") as fh:
        fh.write("## Accepted risks\n\n- **RR-2026-08-21-uncommitted** — "
                 "never committed.\n")
    result = pr.resolve_register(_Path(repo))
    record("register: untracked-on-disk (never committed) resolves to "
           "confirmed_absent, not operational_failure",
           result.state == "confirmed_absent")
    shutil.rmtree(repo, ignore_errors=True)

    # confirmed_absent — file exists at HEAD but has no Accepted risks section
    repo = _git_fixture(register_text="# Risk posture\n\nNo register here.\n")
    result = pr.resolve_register(_Path(repo))
    record("register: file with no Accepted risks section is confirmed_absent",
           result.state == "confirmed_absent")
    shutil.rmtree(repo, ignore_errors=True)

    # malformed — duplicate RR- ids
    repo = _git_fixture(register_text=(
        "## Accepted risks\n\n"
        "- **RR-2026-08-06-seq-poison** — first bullet; bound: n/a; "
        "recovery: n/a.\n\n"
        "- **RR-2026-08-06-seq-poison** — duplicate id, second bullet; "
        "bound: n/a; recovery: n/a.\n"))
    result = pr.resolve_register(_Path(repo))
    record("register: duplicate RR- ids resolve to malformed",
           result.state == "malformed"
           and "RR-2026-08-06-seq-poison" in result.reason)
    shutil.rmtree(repo, ignore_errors=True)

    # operational_failure — no HEAD yet (zero commits)
    repo = _git_fixture(commit_plan=False)
    result = pr.resolve_register(_Path(repo))
    record("register: no HEAD yet (fresh repo) resolves to operational_failure",
           result.state == "operational_failure")
    shutil.rmtree(repo, ignore_errors=True)

    # operational_failure — not a git repo at all
    tmp = tempfile.mkdtemp()
    result = pr.resolve_register(_Path(tmp))
    record("register: non-git directory resolves to operational_failure",
           result.state == "operational_failure")
    shutil.rmtree(tmp, ignore_errors=True)

    record("register: find_duplicate_register_ids is empty for a "
           "well-formed section",
           pr.find_duplicate_register_ids(
               "## Accepted risks\n\n- **RR-2026-08-06-a** — x; bound: n/a; "
               "recovery: n/a.\n\n- **RR-2026-08-06-b** — y; bound: n/a; "
               "recovery: n/a.\n") == [])


def test_extraction(pr) -> None:
    record("extraction: exact match is case-sensitive",
           pr.extract_section(PLAN_TEXT, "approach") is None
           and pr.extract_section(PLAN_TEXT, "Approach") is not None)
    record("extraction: sub-headings stay with their parent section",
           "### Stack decisions" in pr.extract_section(PLAN_TEXT, "Approach"))
    record("extraction: slice stops at the next H2",
           "Acceptance criteria" not in pr.extract_section(PLAN_TEXT, "Approach"))
    record("extraction: section at end of file is captured",
           pr.extract_section(PLAN_TEXT, "Phasing").endswith("Phase 1: fixture.\n"))
    record("extraction: an H3 with the same title text is not a section",
           pr.extract_section("## A\nx\n### B\ny\n", "B") is None)
    record("extraction: a repeated identical H2 terminates the slice",
           pr.extract_section("## A\nfirst\n## A\nsecond\n## B\nz\n", "A")
           == "## A\nfirst\n")
    got = pr.extract_required_sections(PLAN_TEXT, ["Phasing", "Approach"])
    record("extraction: declared order preserved",
           got.index("## Phasing") < got.index("## Approach"))


def test_selection(pr) -> None:
    ids, reasons = pr.select_lenses()
    record("selection: every lens always selected",
           ids == ["architect", "product-manager"]
           and all(r == [pr.SELECTION_REASON] for r in reasons.values()))
    ids, reasons = pr.select_lenses("architect")
    record("selection: --lenses forces a subset",
           ids == ["architect"]
           and reasons == {"architect": ["forced via --lenses"]})
    try:
        pr.select_lenses("architect,bogus")
        record("selection: --lenses rejects unknown ids", False)
    except pr.CompositionError as exc:
        record("selection: --lenses rejects unknown ids", "bogus" in str(exc))
    try:
        pr.select_lenses("  ,  ")
        record("selection: --lenses with no ids rejected", False)
    except pr.CompositionError:
        record("selection: --lenses with no ids rejected", True)


# ---------------------------------------------------------------------------
# Identity-anchored trusted reads (module-level, on the shared helper)
# ---------------------------------------------------------------------------

def test_trusted_read(pr) -> None:
    shared = pr.shared
    tmp = tempfile.mkdtemp(prefix="trusted-read-")
    try:
        boundary = os.path.join(tmp, "repo")
        os.makedirs(boundary)
        victim = os.path.join(boundary, "plan.md")
        with open(victim, "w") as fh:
            fh.write("# in boundary\n")
        secret = os.path.join(tmp, "secret.txt")
        with open(secret, "w") as fh:
            fh.write("SECRET\n")

        real, text = shared.read_trusted_text(victim, [boundary], "--plan")
        record("trusted read: benign read returns verified identity",
               text == "# in boundary\n"
               and str(real) == os.path.realpath(victim))

        link = os.path.join(boundary, "link.md")
        os.symlink(victim, link)
        _real, text = shared.read_trusted_text(link, [boundary], "--plan")
        record("trusted read: benign in-boundary symlink still allowed",
               text == "# in boundary\n")

        # Deterministic swap injection: the open lands on an out-of-boundary
        # inode (as a pathname swap in the validate->open window would make
        # it); the post-open identity re-verification must refuse.
        real_open = os.open

        def swapped_open(path, flags, *a, **k):
            if isinstance(path, (str, os.PathLike)) \
                    and os.path.abspath(str(path)) == os.path.realpath(victim):
                return real_open(secret, flags, *a, **k)
            return real_open(path, flags, *a, **k)

        os.open = swapped_open
        try:
            try:
                shared.read_trusted_text(victim, [boundary], "--plan")
                ok = False
            except shared.TrustedPathError as exc:
                ok = "changed between validation and read" in str(exc)
        finally:
            os.open = real_open
        record("trusted read: swapped inode between validation and open "
               "refused", ok)

        fifo = os.path.join(boundary, "fifo.md")
        os.mkfifo(fifo)
        try:
            shared.read_trusted_text(fifo, [boundary], "--plan")
            ok = False
        except shared.TrustedPathError as exc:
            ok = "not a regular file" in str(exc)
        record("trusted read: FIFO refused without hanging", ok)

        _real, text = shared.read_trusted_text(
            os.path.join(boundary, "nope.md"), [boundary], "--plan",
            missing_ok=True)
        record("trusted read: missing_ok reports absence as None",
               text is None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Rule-data drift fails loudly (subprocess against the COPIED skill)
# ---------------------------------------------------------------------------

def test_rule_data_drift(env: Env) -> None:
    lens_dir = os.path.join(env.skill, "lenses")

    bad = os.path.join(lens_dir, "conditional.md")
    with open(bad, "w") as fh:
        fh.write("---\nid: conditional\nskill: iterate-plan\nrole: t\n"
                 "selection:\n  always: false\n  requires_sections: []\n"
                 "matched_context: >\n  x\n---\n## ROLE\n")
    proc = env.run("run-pass", "--plan", env.plan)
    record("rule data: a lens declaring always:false fails loudly",
           proc.returncode == 1 and "always: false" in proc.stderr)
    os.remove(bad)

    bad = os.path.join(lens_dir, "mismatch.md")
    with open(bad, "w") as fh:
        fh.write("---\nid: other\nskill: iterate-plan\nrole: t\n"
                 "selection:\n  always: true\n  requires_sections: []\n"
                 "matched_context: >\n  x\n---\n## ROLE\n")
    proc = env.run("run-pass", "--plan", env.plan)
    record("rule data: frontmatter id / filename mismatch fails loudly",
           proc.returncode == 1 and "does not match filename" in proc.stderr)
    os.remove(bad)

    # A body line that LOOKS like an id declaration must not satisfy the
    # drift check — id comes from the frontmatter block only.
    bad = os.path.join(lens_dir, "bodyid.md")
    with open(bad, "w") as fh:
        fh.write("---\nskill: iterate-plan\nrole: t\n"
                 "selection:\n  always: true\n  requires_sections: []\n"
                 "matched_context: >\n  x\n---\n## ROLE\nid: bodyid\n")
    proc = env.run("run-pass", "--plan", env.plan)
    record("rule data: missing frontmatter id not satisfied by a body line",
           proc.returncode == 1 and "does not match filename" in proc.stderr)
    os.remove(bad)


# ---------------------------------------------------------------------------
# Exit contracts, boundaries, wiring (subprocess, fake codex)
# ---------------------------------------------------------------------------

def test_contracts(env: Env) -> None:
    # run-pass happy path: summary published, exit 0, both lenses ok,
    # log_path echoes the plan path, scope keyed by sha1(realpath(plan)).
    env.set_mode("ok")
    proc = env.run("run-pass", "--plan", env.plan)
    summary = json.loads(proc.stdout) if proc.returncode == 0 else {}
    lenses = summary.get("lenses", {})
    record("run-pass: exit 0 and summary on stdout",
           proc.returncode == 0 and summary.get("complete") is True,
           proc.stderr.strip())
    record("run-pass: both lenses ran ok with selection reasons",
           sorted(lenses) == ["architect", "product-manager"]
           and all(v["status"] == "ok" for v in lenses.values())
           and all(v["selection_reasons"] == ["always selected per lenses/README.md"]
                   for v in lenses.values()))
    record("run-pass: log_path echoes the plan path",
           summary.get("log_path") == os.path.realpath(env.plan))
    record("run-pass: scope hash is sha1 of the plan's real path",
           summary.get("scope_hash") == env.scope_hash())
    state_dir = env.state_dir()
    record("run-pass: composed inputs published as pass-1 artifacts",
           os.path.exists(os.path.join(state_dir, "pass-1.architect.input.txt"))
           and os.path.exists(os.path.join(state_dir, "pass-1.product-manager.input.txt")))
    composed = read(os.path.join(state_dir, "pass-1.architect.input.txt"))
    record("run-pass: composed input carries matched context + plan blocks",
           "=== MATCHED CONTEXT (sections for the architect lens) ===" in composed
           and "=== PLAN ===" in composed
           and "## Approach" in composed)
    record("run-pass: lock released on completion",
           not os.path.exists(os.path.join(state_dir, "run.lock")))

    # Immutability: explicit --pass-num colliding with published state.
    proc = env.run("run-pass", "--plan", env.plan, "--pass-num", "1")
    record("run-pass: colliding --pass-num refused",
           proc.returncode == 1 and "immutable" in proc.stderr)

    # Staged note appears in every lens input.
    proc = env.run("run-pass", "--plan", env.plan, "--note", env.note)
    summary = json.loads(proc.stdout)
    n = summary["pass"]
    with_note = all(
        "=== NOTE: HUMAN EDITS SINCE LAST PASS ===" in
        read(os.path.join(state_dir, f"pass-{n}.{lid}.input.txt"))
        for lid in ("architect", "product-manager"))
    record("run-pass: staged --note prepended to every lens input",
           proc.returncode == 0 and with_note)

    # --lenses override wiring.
    proc = env.run("run-pass", "--plan", env.plan, "--lenses", "architect")
    summary = json.loads(proc.stdout)
    record("run-pass: --lenses override runs exactly the forced set",
           proc.returncode == 0 and sorted(summary["lenses"]) == ["architect"]
           and summary["lenses"]["architect"]["selection_reasons"]
           == ["forced via --lenses"])


def test_boundaries(env: Env) -> None:
    env.set_mode("ok")
    outside = os.path.join(env.root, "outside.md")
    with open(outside, "w") as fh:
        fh.write(PLAN_TEXT)
    proc = env.run("run-pass", "--plan", outside)
    record("boundary: --plan outside the repo root refused",
           proc.returncode == 1 and "trusted boundaries" in proc.stderr)

    dotenv = os.path.join(env.repo, ".env")
    with open(dotenv, "w") as fh:
        fh.write("SECRET=1\n")
    proc = env.run("run-pass", "--plan", dotenv)
    record("boundary: in-repo non-.md refused (.env)",
           proc.returncode == 1 and "must be a .md" in proc.stderr)

    # A symlinked "plan" pointing outside the repo is refused by realpath.
    link = os.path.join(env.repo, "docs", "linked.md")
    os.symlink(outside, link)
    proc = env.run("run-pass", "--plan", link)
    record("boundary: symlink escaping the repo root refused",
           proc.returncode == 1 and "trusted boundaries" in proc.stderr)
    os.remove(link)

    # Notes must come from the handoff dir — an in-repo file elsewhere is
    # refused even though it is inside the repo root.
    # A FIFO staged at a note name must refuse (regular files only), and
    # must do so without hanging on the open.
    fifo = os.path.join(env.handoff, "fifo-note")
    os.mkfifo(fifo)
    proc = env.run("run-pass", "--plan", env.plan, "--note", fifo)
    record("boundary: FIFO staged as --note refused without hanging",
           proc.returncode == 1 and "not a regular file" in proc.stderr)
    os.remove(fifo)

    stray = os.path.join(env.repo, "docs", "stray-note.txt")
    with open(stray, "w") as fh:
        fh.write("note\n")
    proc = env.run("run-pass", "--plan", env.plan, "--note", stray)
    record("boundary: --note outside the handoff dir refused",
           proc.returncode == 1 and "trusted boundaries" in proc.stderr)
    proc = env.run("run-lens", "--plan", env.plan, "--lens", "architect",
                   "--note", stray)
    record("boundary: run-lens --note outside the handoff dir refused",
           proc.returncode == 1 and "trusted boundaries" in proc.stderr)
    os.remove(stray)

    empty = os.path.join(env.repo, "docs", "empty.md")
    with open(empty, "w") as fh:
        fh.write("\n")
    proc = env.run("run-pass", "--plan", empty)
    record("run-pass: empty plan refused",
           proc.returncode == 1 and "empty" in proc.stderr)
    proc = env.run("run-lens", "--plan", empty, "--lens", "architect")
    record("run-lens: empty plan refused (same contract as run-pass)",
           proc.returncode == 1 and "empty" in proc.stderr)
    os.remove(empty)

    proc = env.run("run-lens", "--plan", env.plan, "--lens", "nope")
    record("run-lens: unknown lens id refused",
           proc.returncode == 1 and "unknown lens id" in proc.stderr)

    # Orchestration failure at the standalone boundary: codex missing from
    # PATH must produce a concise run-lens diagnostic, never a traceback.
    # PATH is a shim dir holding ONLY python3 + git — simply removing the
    # fake codex would fall through to the REAL codex on the machine's PATH.
    proc = run_without_codex(env, "run-lens", "--plan", env.plan,
                             "--lens", "architect")
    record("run-lens: codex missing -> exit 1 diagnostic, no traceback",
           proc.returncode == 1 and "run-lens:" in proc.stderr
           and "Traceback" not in proc.stderr)


def test_codex_invocation_contract(env: Env) -> None:
    """The -C contract: codex's working root is the PLAN's directory, placed
    right after `exec` per the SKILL.md invocation shape — asserted from the
    fake codex's recorded argv, for both command boundaries."""
    env.set_mode("ok")
    plan_dir = os.path.dirname(os.path.realpath(env.plan))

    def c_ok(rec):
        argv = rec["argv"]
        return ("exec" in argv
                and argv[argv.index("exec") + 1] == "-C"
                and argv[argv.index("exec") + 2] == plan_dir)

    env.clear_argv_records()
    proc = env.run("run-pass", "--plan", env.plan)
    recs = env.argv_records()
    record("codex argv: run-pass passes -C <plan-dir> right after exec",
           proc.returncode == 0 and len(recs) == 2
           and all(c_ok(r) for r in recs))

    env.clear_argv_records()
    proc = env.run("run-lens", "--plan", env.plan, "--lens", "architect")
    recs = env.argv_records()
    record("codex argv: run-lens passes -C <plan-dir> right after exec",
           proc.returncode == 0 and len(recs) == 1 and c_ok(recs[0]))
    env.clear_argv_records()


def test_failure_modes(env: Env) -> None:
    state_dir = env.state_dir()

    # Codex crash: per-lens data in the summary, run-pass still exits 0.
    env.set_mode("fail")
    proc = env.run("run-pass", "--plan", env.plan)
    summary = json.loads(proc.stdout)
    record("failure: codex crash is per-lens data, summary still published",
           proc.returncode == 0
           and all(v["status"] == "failed" and v["exit_code"] == 3
                   for v in summary["lenses"].values()))

    # Structural failure: missing required keys → rejected.
    env.set_mode("structural")
    proc = env.run("run-pass", "--plan", env.plan)
    summary = json.loads(proc.stdout)
    record("failure: off-schema response rejected with reasons",
           proc.returncode == 0
           and all(v["status"] == "rejected"
                   and any("missing required key" in r
                           for r in v["reject_reasons"])
                   for v in summary["lenses"].values()))

    # Patch markers: rejected at both command boundaries.
    env.set_mode("patchmarkers")
    proc = env.run("run-pass", "--plan", env.plan)
    summary = json.loads(proc.stdout)
    record("failure: patch-marker response is status rejected in run-pass",
           proc.returncode == 0
           and all(v["status"] == "rejected"
                   and any("patch marker" in r for r in v["reject_reasons"])
                   for v in summary["lenses"].values()))
    proc = env.run("run-lens", "--plan", env.plan, "--lens", "architect")
    result = json.loads(proc.stdout)
    record("failure: standalone run-lens patch marker exits 2",
           proc.returncode == 2 and result["status"] == "rejected")

    # Standalone run-lens writes ONLY to debug/, never pass-N.*.
    env.set_mode("ok")
    before = set(os.listdir(state_dir))
    proc = env.run("run-lens", "--plan", env.plan, "--lens", "architect")
    result = json.loads(proc.stdout)
    after = set(os.listdir(state_dir))
    record("run-lens: standalone artifacts land in debug/ only",
           proc.returncode == 0
           and after - before <= {"debug"}
           and "/debug/" in result["input_path"]
           and os.path.exists(result["response_path"]))
    record("run-lens: standalone takes no lock",
           not os.path.exists(os.path.join(state_dir, "run.lock")))


def test_concurrency(env: Env) -> None:
    env.clear_sleep_markers()
    env.set_mode("sleep3")
    first = env.popen("run-pass", "--plan", env.plan)
    try:
        record("concurrency: sleeper started", env.wait_sleeper())
        proc = env.run("run-pass", "--plan", env.plan)
        record("concurrency: second same-scope run-pass fails fast",
               proc.returncode == 1 and "locked by a live run" in proc.stderr)
    finally:
        out, err = first.communicate(timeout=60)
    record("concurrency: first run still completes (exit 0, summary)",
           first.returncode == 0 and '"complete": true' in out, err.strip())
    env.set_mode("ok")
    env.clear_sleep_markers()


def test_prune_smoke(env: Env) -> None:
    """Wiring smoke only — prune-state is a byte-identical copy whose deep
    behavior is pinned by tools/check-runners.py. This proves the copy
    resolves ITS OWN skill root (iterate-plan/state/) and that the model's
    state/<hash>.json records survive a scope prune."""
    shash = env.scope_hash()
    state_dir = env.state_dir()
    model_state = os.path.join(env.skill, "state", f"{shash}.json")
    with open(model_state, "w") as fh:
        json.dump({"pass_count": 3}, fh)

    proc = env.run("prune-state")
    record("prune: overview lists the iterate-plan scope",
           proc.returncode == 0 and shash in proc.stdout)

    proc = env.run("prune-state", "--scope", shash)
    record("prune: dry run deletes nothing",
           proc.returncode == 0 and "dry run" in proc.stdout
           and os.path.isdir(state_dir))

    proc = env.run("prune-state", "--scope", shash, "--yes")
    record("prune: converge prune removes the scope dir",
           proc.returncode == 0 and not os.path.exists(state_dir))
    record("prune: model state/<hash>.json survives",
           os.path.exists(model_state))


def test_register_integration(env: Env) -> None:
    """End-to-end: run-pass's register resolution + composition + the
    malformed-source abort, against the real CLI (Trinity v2.4 Phase 1,
    Q5) -- resolve_register()'s pure-function behavior is covered by
    test_register_resolution above; this proves run-pass actually wires it
    in the way SKILL.md step 5 promises. Placed LAST in the Env-based
    sequence: it commits to env.repo's git history (no test after it
    depends on the prior confirmed-absent state), and test_prune_smoke
    already wiped this scope's state dir, so pass numbering below starts
    clean regardless of how many passes earlier tests consumed."""
    env.set_mode("ok")
    state_dir = env.state_dir()

    # loaded: run-pass composes the register block into every lens's input.
    env.commit_register(
        "## Accepted risks\n\n"
        "- **RR-2026-08-06-seq-poison** — integration-fixture behavior; "
        "bound: n/a; recovery: n/a.\n")
    proc = env.run("run-pass", "--plan", env.plan)
    record("register integration: loaded register composes end to end",
           proc.returncode == 0, proc.stderr.strip())
    composed = read(os.path.join(state_dir, "pass-1.architect.input.txt"))
    record("register integration: composed input carries the register block",
           "=== ACCEPTED RISKS ===" in composed
           and "RR-2026-08-06-seq-poison" in composed)

    # malformed: run-pass aborts before any lens ever runs -- no new
    # summary, no lock left behind, a clear stderr reason naming the
    # offending id.
    summaries_before = set(
        glob.glob(os.path.join(state_dir, "pass-*.summary.json")))
    env.commit_register(
        "## Accepted risks\n\n"
        "- **RR-2026-08-06-dup** — first; bound: n/a; recovery: n/a.\n\n"
        "- **RR-2026-08-06-dup** — duplicate id, second bullet; "
        "bound: n/a; recovery: n/a.\n")
    proc = env.run("run-pass", "--plan", env.plan)
    record("register integration: malformed register aborts before fan-out",
           proc.returncode != 0
           and "register malformed" in proc.stderr
           and "RR-2026-08-06-dup" in proc.stderr)
    summaries_after = set(
        glob.glob(os.path.join(state_dir, "pass-*.summary.json")))
    record("register integration: malformed abort published no new summary",
           summaries_after == summaries_before)
    record("register integration: malformed abort took no run lock",
           not os.path.exists(os.path.join(state_dir, "run.lock")))

    # --ignore-register: the ONE human-directed way past a malformed/
    # operational_failure abort (SKILL.md step 5/8's "proceed with no
    # register" card outcome) -- the SAME malformed register from above is
    # still committed at HEAD; --ignore-register must still succeed and
    # compose with an explicitly empty register, never reading the broken
    # source at all.
    proc = env.run("run-pass", "--plan", env.plan, "--ignore-register")
    record("register integration: --ignore-register succeeds past a "
           "malformed register",
           proc.returncode == 0, proc.stderr.strip())
    if proc.returncode == 0:
        passnum = json.loads(proc.stdout)["pass"]
        composed = read(os.path.join(
            state_dir, f"pass-{passnum}.architect.input.txt"))
        real_header = "=== MATCHED CONTEXT (sections for the architect lens) ==="
        after_real_header = composed.split(real_header, 1)[-1]
        record("register integration: --ignore-register composes with no "
               "register block, never reading the malformed source",
               real_header in composed
               and "=== ACCEPTED RISKS ===" not in after_real_header
               and "RR-2026-08-06-dup" not in composed)

    # dirty worktree: an UNCOMMITTED edit to docs/risk-posture.md must never
    # reach a lens input -- composition and the register-match provenance
    # gate share HEAD as their one trusted source (Q5). Revert to the
    # well-formed committed register from above, then dirty the working
    # tree with a DIFFERENT id that was never committed.
    env.commit_register(
        "## Accepted risks\n\n"
        "- **RR-2026-08-06-seq-poison** — integration-fixture behavior; "
        "bound: n/a; recovery: n/a.\n")
    dirty_path = os.path.join(env.repo, "docs", "risk-posture.md")
    with open(dirty_path, "w") as fh:
        fh.write(
            "## Accepted risks\n\n"
            "- **RR-2026-08-06-seq-poison** — integration-fixture behavior; "
            "bound: n/a; recovery: n/a.\n\n"
            "- **RR-2026-08-21-uncommitted** — this entry was never "
            "committed; bound: n/a; recovery: n/a.\n")
    try:
        proc = env.run("run-pass", "--plan", env.plan)
        record("register integration: dirty-worktree run-pass still succeeds "
               "(composes from HEAD, not the dirty file)",
               proc.returncode == 0, proc.stderr.strip())
        composed = read(os.path.join(
            state_dir,
            f"pass-{json.loads(proc.stdout)['pass']}.architect.input.txt"
        )) if proc.returncode == 0 else ""
        record("register integration: dirty-worktree edit never reaches a "
               "lens input",
               "RR-2026-08-06-seq-poison" in composed
               and "RR-2026-08-21-uncommitted" not in composed)
    finally:
        # Leave the working tree clean for anything that might run after.
        env._git("checkout", "--", "docs/risk-posture.md")

    # confirmed_absent end to end, the freshly-seeded create-plan case:
    # HEAD has no register at all, and an UNTRACKED, never-committed
    # docs/risk-posture.md exists in the working tree. This is the exact
    # boundary iterate-review's own code review (pass 6) found
    # misclassified as operational_failure before plan_runner.py's fix
    # above -- confirm the fixed behavior end to end, not just at the
    # resolve_register() unit level.
    register_path = os.path.join(env.repo, "docs", "risk-posture.md")
    os.remove(register_path)
    env._git("add", "-A")
    env._git("commit", "-q", "-m", "remove committed register")
    with open(register_path, "w") as fh:
        fh.write("## Accepted risks\n\n- **RR-2026-08-21-uncommitted** — "
                 "never committed; bound: n/a; recovery: n/a.\n")
    try:
        proc = env.run("run-pass", "--plan", env.plan)
        record("register integration: untracked never-committed register "
               "still succeeds (confirmed_absent, not operational_failure)",
               proc.returncode == 0, proc.stderr.strip())
        composed = read(os.path.join(
            state_dir, f"pass-{json.loads(proc.stdout)['pass']}.architect.input.txt"
        )) if proc.returncode == 0 else ""
        # Check only the part AFTER the REAL matched-context header for
        # THIS lens -- reviewer-prompt.md's own ON RISK POSTURE prose
        # documents both the `=== ACCEPTED RISKS ===` marker AND a
        # generic "=== MATCHED CONTEXT (sections for the <lens-id> lens)
        # ===" template line (with a literal, never-substituted
        # `<lens-id>` placeholder) as part of its own footer example --
        # either would false-positive a naive absence check against the
        # whole composed input. The header for THIS lens always names the
        # real id ("architect"), never the placeholder, so splitting on
        # that exact substring reliably lands after the prompt's own
        # documentation and at the start of this pass's real assembly.
        real_header = "=== MATCHED CONTEXT (sections for the architect lens) ==="
        after_real_header = composed.split(real_header, 1)[-1]
        record("register integration: untracked register composes as "
               "absent (no block) and never reaches a lens",
               real_header in composed
               and "=== ACCEPTED RISKS ===" not in after_real_header
               and "RR-2026-08-21-uncommitted" not in composed)
    finally:
        os.remove(register_path)

    # operational_failure end to end: a repo with no HEAD yet (fresh git
    # init, zero commits) must abort run-pass exactly like the malformed
    # case above -- same before-any-lens contract, different upstream
    # register state. Its own scope (a different plan path) has never had
    # a pass, so no summaries-before/after comparison is needed.
    nohead_root = os.path.join(env.root, "nohead-repo")
    os.makedirs(os.path.join(nohead_root, "docs"))
    subprocess.run(["git", "init", "-q", nohead_root], check=True,
                   stdout=subprocess.DEVNULL)
    nohead_plan = os.path.join(nohead_root, "docs", "plan.md")
    with open(nohead_plan, "w") as fh:
        fh.write(PLAN_TEXT)
    proc = env.run("run-pass", "--plan", nohead_plan, cwd=nohead_root)
    record("register integration: operational_failure (no HEAD yet) aborts "
           "before fan-out",
           proc.returncode != 0 and "register unavailable" in proc.stderr)
    nohead_shash = hashlib.sha1(
        os.path.realpath(nohead_plan).encode("utf-8")).hexdigest()
    record("register integration: no-HEAD abort published no summary at all",
           not os.path.exists(os.path.join(
               env.skill, "state", nohead_shash, "pass-1.summary.json")))

    # run-lens gets its OWN --ignore-register coverage (qa's pass-7
    # finding): run-pass and run-lens are two separate CLIs that each add
    # their own control-flow path around resolve_register(), so a
    # regression in run-lens's copy could stay invisible to every run-pass
    # assertion above while the documented standalone-retry path silently
    # breaks. Same malformed register as the run-pass cases; debug/
    # artifacts are glob-compared before/after since debug_paths() names
    # them with a timestamp, not a predictable pass number.
    env.commit_register(
        "## Accepted risks\n\n"
        "- **RR-2026-08-06-dup** — first; bound: n/a; recovery: n/a.\n\n"
        "- **RR-2026-08-06-dup** — duplicate id, second bullet; "
        "bound: n/a; recovery: n/a.\n")
    debug_dir = os.path.join(state_dir, "debug")
    before = set(glob.glob(os.path.join(debug_dir, "*")))
    proc = env.run("run-lens", "--plan", env.plan, "--lens", "architect")
    record("register integration: run-lens without the flag aborts on a "
           "malformed register before invoking Codex",
           proc.returncode != 0 and "register malformed" in proc.stderr)
    after = set(glob.glob(os.path.join(debug_dir, "*")))
    record("register integration: run-lens's malformed abort wrote no "
           "debug artifacts either",
           after == before)

    proc = env.run("run-lens", "--plan", env.plan, "--lens", "architect",
                    "--ignore-register")
    record("register integration: run-lens --ignore-register succeeds past "
           "the same malformed register",
           proc.returncode == 0, proc.stderr.strip())
    if proc.returncode == 0:
        input_path = json.loads(proc.stdout)["input_path"]
        composed = read(input_path)
        real_header = "=== MATCHED CONTEXT (sections for the architect lens) ==="
        after_real_header = composed.split(real_header, 1)[-1]
        record("register integration: run-lens --ignore-register composes "
               "with no register block and never reads the malformed entry",
               real_header in composed
               and "=== ACCEPTED RISKS ===" not in after_real_header
               and "RR-2026-08-06-dup" not in composed)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> int:
    try:
        pr = load(os.path.join(SKILL, "bin", "plan_runner.py"), "pr_check")
    except Exception as exc:  # noqa: BLE001
        print(f"setup error loading runner modules: {exc}", file=sys.stderr)
        return 2

    tmp = tempfile.mkdtemp(prefix="check-plan-runners-")
    try:
        env = Env(tmp)
        test_composition(pr)
        test_register_resolution(pr)
        test_extraction(pr)
        test_trusted_read(pr)
        test_selection(pr)
        test_rule_data_drift(env)
        test_contracts(env)
        test_codex_invocation_contract(env)
        test_boundaries(env)
        test_failure_modes(env)
        test_concurrency(env)
        test_prune_smoke(env)
        test_register_integration(env)
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
