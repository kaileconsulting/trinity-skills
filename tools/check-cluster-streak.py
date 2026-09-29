#!/usr/bin/env python3
"""Fixture-pin `tools/cluster_tracker.py` against the simplification gate's
counting semantics (simplification-gate plan §1/§2, both loop skills).

Tagging and same-mechanism judgments are editor fold-time calls, never
runner-owned code -- this checker exists so the streak arithmetic has an
executable, boundary-case-tested form instead of resting on prose alone,
the same pattern as `check-question-freeze.py`.

Usage:
    tools/check-cluster-streak.py
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cluster_tracker import (  # noqa: E402
    CLUSTER_N, advance, initial_state, observation, run,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = ("iterate-plan", "iterate-review")

FAILED = ("failed",)
QUIET = ("findings", {})

# Every place a SKILL.md states the threshold uses one of these phrasings,
# so the literal is findable; emphasis/backticks are stripped first.
THRESHOLD_RX = re.compile(r"(?<!one below )the cluster threshold, (\d+),")
BELOW_RX = re.compile(r"one below the cluster threshold, (\d+),")


def threshold_problems(skill_texts, n):
    """Return a list of problems with the threshold literals across
    `{skill: SKILL.md text}` against the development constant `n`: each
    file must state it at least once, every literal must equal `n` (and
    every "one below" literal `n - 1`), which also makes the files agree."""
    problems = []
    for skill, raw in skill_texts.items():
        text = re.sub(r"\s+", " ", raw.replace("*", "").replace("`", ""))
        found = [int(x) for x in THRESHOLD_RX.findall(text)]
        below = [int(x) for x in BELOW_RX.findall(text)]
        if not found:
            problems.append(f"{skill}: no 'the cluster threshold, <n>,' literal")
        problems += [f"{skill}: threshold literal {v} != CLUSTER_N {n}"
                     for v in found if v != n]
        problems += [f"{skill}: 'one below' literal {v} != CLUSTER_N-1 {n - 1}"
                     for v in below if v != n - 1]
    return problems


def f(**labels):
    """A completed pass: f(guard="HIGH", toast="LOW")."""
    return ("findings", {k.replace("_", "-"): v for k, v in labels.items()})


def seq(*passes):
    """Each item is a pass record, or `(record, [outcomes])`."""
    return [p if isinstance(p, tuple) and len(p) == 2 and isinstance(p[1], list)
            else (p, []) for p in passes]


def fired(passes):
    return run(seq(*passes))[0]


def streaks(passes):
    return run(seq(*passes))[1][0]


def retired(passes):
    return run(seq(*passes))[1][1]


def raises(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


def main() -> int:
    failures = []
    total = 0

    def check(label, got, want):
        nonlocal total
        total += 1
        status = "ok" if got == want else "FAIL"
        print(f"  {status:4}  {label:<74} -> {got!r}")
        if got != want:
            failures.append(f"{label}: got {got!r}, want {want!r}")

    check("CLUSTER_N is 3", CLUSTER_N, 3)

    # -- the deployed threshold: a literal in each SKILL.md ------------------
    texts = {}
    for skill in SKILLS:
        with open(os.path.join(REPO, skill, "SKILL.md"), encoding="utf-8") as fh:
            texts[skill] = fh.read()
    check("both SKILL.md threshold literals equal CLUSTER_N (and each other)",
          threshold_problems(texts, CLUSTER_N), [])
    # teeth: the assertion must fail on drift, not just pass on agreement
    check("teeth: a literal that disagrees with CLUSTER_N is reported",
          len(threshold_problems(
              {"a": "the cluster threshold, **3**,", "b": "the cluster threshold, 4,"},
              3)), 1)
    check("teeth: a file with no literal is reported",
          threshold_problems({"a": "no threshold here"}, 3),
          ["a: no 'the cluster threshold, <n>,' literal"])
    check("teeth: a wrong 'one below' literal is reported",
          len(threshold_problems(
              {"a": "the cluster threshold, 3, and one below the cluster threshold, 1,"},
              3)), 1)

    # -- basic counting ------------------------------------------------------
    check("first HIGH/MEDIUM pass counts as 1",
          streaks([f(guard="HIGH")]), {"guard": 1})
    check("three consecutive HIGH/MEDIUM passes fire on the 3rd",
          fired([f(guard="HIGH"), f(guard="MEDIUM"), f(guard="HIGH")]),
          [[], [], ["guard"]])
    check("two passes never fire",
          fired([f(guard="HIGH"), f(guard="HIGH")]), [[], []])
    check("a LOW-only pass resets the streak to 0",
          streaks([f(guard="HIGH"), f(guard="HIGH"), f(guard="LOW")]),
          {"guard": 0})
    check("a pass where the label is absent resets it (absence is only a reset)",
          (streaks([f(guard="HIGH"), f(guard="HIGH"), QUIET]),
           retired([f(guard="HIGH"), f(guard="HIGH"), QUIET])),
          ({"guard": 0}, frozenset()))
    check("LOW findings never count, however many passes",
          fired([f(guard="LOW")] * 5), [[]] * 5)

    # -- FAILED pass skips ----------------------------------------------------
    check("a FAILED pass neither counts nor resets (3 qualifying over 4 attempts)",
          fired([f(guard="HIGH"), FAILED, f(guard="HIGH"), f(guard="HIGH")]),
          [[], [], [], ["guard"]])
    check("FAILED passes alone never fire",
          fired([FAILED, FAILED, FAILED]), [[], [], []])
    check("an explicit retire on a FAILED pass still persists",
          retired([f(guard="HIGH"), (FAILED, [("retire", "guard")])]),
          frozenset({"guard"}))

    # -- independence and one-observation-per-pass ---------------------------
    check("two labels in one pass track independently",
          streaks([f(guard="HIGH", toast="MEDIUM"), f(guard="HIGH"),
                   f(guard="HIGH", toast="HIGH")]),
          {"guard": 3, "toast": 1})
    check("several findings on one label in one pass count once",
          observation([("guard", "MEDIUM"), ("guard", "HIGH"), ("guard", "LOW")]),
          ("findings", {"guard": "HIGH"}))
    one_pass = observation([("guard", "HIGH")] * 4)
    check("... and advance one streak step, not four",
          advance(initial_state(), one_pass)[0][0], {"guard": 1})

    # -- the three simplification outcomes -----------------------------------
    three = [f(guard="HIGH")] * 2
    check("remove retires the label",
          (streaks(three + [(f(guard="HIGH"), [("remove", "guard")])]),
           retired(three + [(f(guard="HIGH"), [("remove", "guard")])])),
          ({}, frozenset({"guard"})))
    rep = three + [(f(guard="HIGH"), [("replace", "guard", "recovery")])]
    check("replace retires the old label and starts the new one at 0",
          (streaks(rep), retired(rep)),
          ({"recovery": 0}, frozenset({"guard"})))
    check("... the replacement fires after N fresh passes, not sooner",
          fired(rep + [f(recovery="HIGH")] * 3)[-3:],
          [[], [], ["recovery"]])
    nar = three + [(f(guard="HIGH"), [("narrow", "guard")])]
    check("narrow retains the label at streak 0",
          (streaks(nar), retired(nar)), ({"guard": 0}, frozenset()))
    check("... and re-fires after N further passes on the narrowed mechanism",
          fired(nar + [f(guard="MEDIUM")] * 3)[-3:],
          [[], [], ["guard"]])

    # -- fold once more, accept the risk, split the plan ---------------------
    fom = three + [(f(guard="HIGH"), [("fold-once-more", "guard")])]
    check("fold-once-more keeps counting (streak stays at N)",
          streaks(fom), {"guard": 3})
    check("... and the card returns on the very next pass on that label",
          fired(fom + [f(guard="MEDIUM")])[-1], ["guard"])
    acc = three + [(f(guard="HIGH"), [("accept-risk", "guard")])]
    check("accept-risk retains the label at streak 0",
          (streaks(acc), retired(acc)), ({"guard": 0}, frozenset()))
    check("... and a later merged finding on it is an ordinary observation",
          streaks(acc + [f(guard="HIGH")]), {"guard": 1})
    # An AR-<n> rejected at a checkpoint changes ledger state only: that pass
    # is quiet on the label (not an observation); the re-report counts.
    check("a checkpoint AR rejection on a quiet pass is not an observation",
          streaks(acc + [QUIET]), {"guard": 0})
    check("... the finding's next re-report is",
          streaks(acc + [QUIET, f(guard="HIGH")]), {"guard": 1})
    spl = three + [(f(guard="HIGH"), [("split-plan", "guard")])]
    check("split-plan retires the label here",
          (streaks(spl), retired(spl)), ({}, frozenset({"guard"})))

    # -- retirement vs absence, and identity rules ---------------------------
    check("explicit retirement (no card) ends identity; absence would not",
          (retired([f(guard="HIGH"), (QUIET, [("retire", "guard")])]),
           retired([f(guard="HIGH"), QUIET])),
          (frozenset({"guard"}), frozenset()))
    check("a retired label may not be reused",
          raises(lambda: run(seq((f(guard="HIGH"), []),
                                 (QUIET, [("retire", "guard")]),
                                 f(guard="HIGH")))), True)
    check("a replacement label must be new",
          raises(lambda: run(seq(f(guard="HIGH", other="LOW"), f(guard="HIGH"),
                                 (f(guard="HIGH"),
                                  [("replace", "guard", "other")])))), True)
    check("a card outcome must answer a card presented that pass",
          raises(lambda: run(seq((f(guard="HIGH"), [("narrow", "guard")])))),
          True)
    check("a card cannot be answered on a FAILED pass",
          raises(lambda: run(seq(f(guard="HIGH"), f(guard="HIGH"),
                                 (FAILED, [("remove", "guard")])))), True)
    check("an unknown severity is rejected",
          raises(lambda: run(seq(f(guard="CRITICAL")))), True)

    # -- chunk boundaries (plan Q3): mechanism continuity carries a streak ---
    check("a streak carries across a chunk boundary when the mechanism continues",
          fired([f(picker="HIGH"), f(picker="HIGH"), f(picker="MEDIUM")])[-1],
          ["picker"])
    check("a component the next chunk drops is retired, not carried",
          streaks([f(picker="HIGH"), (f(toggle="HIGH"), [("retire", "picker")])]),
          {"toggle": 1})

    # -- worked example: impersonation-c1b (ResearchLogix_v2, 2026-09-15) ----
    # Passes 1-11 as recorded. Pass 2's HIGH is a different mechanism (the
    # account-resolution fallback). The reload-loop guard draws HIGH/MEDIUM
    # on passes 3-7; under this rule its card fires at pass 5, not pass 7.
    # The operator folds once more at 5 and 6 (the card returns each pass),
    # then chooses replace at pass 7: the in-memory recovery gets a new
    # label, draws HIGHs on passes 8-10, and its card fires at pass 10 --
    # the pass on which the real review did present a card. Kyle's answer
    # there (add compare-and-set to the recovery) kept the mechanism and
    # patched it, so it is recorded as fold-once-more; pass 11 is quiet.
    c1b = seq(
        QUIET,                                                   # 1
        f(account_fallback="HIGH"),                              # 2
        f(reload_guard="HIGH"),                                  # 3
        f(reload_guard="HIGH"),                                  # 4
        (f(reload_guard="MEDIUM"),
         [("fold-once-more", "reload-guard")]),                  # 5
        (f(reload_guard="MEDIUM"),
         [("fold-once-more", "reload-guard")]),                  # 6
        (f(reload_guard="MEDIUM"),
         [("replace", "reload-guard", "in-memory-recovery")]),   # 7
        f(in_memory_recovery="HIGH"),                            # 8
        f(in_memory_recovery="HIGH"),                            # 9
        (f(in_memory_recovery="HIGH"),
         [("fold-once-more", "in-memory-recovery")]),            # 10
        QUIET,                                                   # 11
    )
    c1b_fired, c1b_state = run(c1b)
    check("impersonation-c1b: cards fire at passes 5, 6, 7 and 10",
          [i + 1 for i, labels in enumerate(c1b_fired) if labels],
          [5, 6, 7, 10])
    check("impersonation-c1b: pass 5 card is for the reload guard",
          c1b_fired[4], ["reload-guard"])
    check("impersonation-c1b: pass 10 card is for the replacement",
          c1b_fired[9], ["in-memory-recovery"])
    check("impersonation-c1b: final state",
          c1b_state,
          ({"account-fallback": 0, "in-memory-recovery": 0},
           frozenset({"reload-guard"})))

    print()
    if failures:
        print(f"{total - len(failures)}/{total} passed")
        for msg in failures:
            print(f"  FAILED: {msg}")
        return 1
    print(f"{total}/{total} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
