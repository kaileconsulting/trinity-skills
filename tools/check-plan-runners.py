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
    os.remove(empty)

    proc = env.run("run-lens", "--plan", env.plan, "--lens", "nope")
    record("run-lens: unknown lens id refused",
           proc.returncode == 1 and "unknown lens id" in proc.stderr)


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
        test_extraction(pr)
        test_selection(pr)
        test_rule_data_drift(env)
        test_contracts(env)
        test_boundaries(env)
        test_failure_modes(env)
        test_concurrency(env)
        test_prune_smoke(env)
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
