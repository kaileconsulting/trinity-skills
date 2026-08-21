#!/usr/bin/env python3
"""Fixture-pin `tools/freeze_tracker.py` against §4's counting semantics
(Trinity v2.4 Phase 0, iterate-plan's open-question freeze).

Freezing itself is an editor fold-time judgment, never runner-owned code
-- this checker exists so the counting algorithm has an executable,
boundary-case-tested form instead of resting on prose alone (qa lens
finding; the exact ambiguity this checker closes is senior-dev's Phase 0
pass 1 finding about where the streak starts counting).

Usage:
    tools/check-question-freeze.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from freeze_tracker import FREEZE_N, advance, run  # noqa: E402

FAILED = ("failed",)
DISAGREEMENT = ("disagreement",)


def answer(token):
    return ("answer", token)


def main() -> int:
    failures = []
    total = 0

    def check(label, got, want):
        nonlocal total
        total += 1
        status = "ok" if got == want else "FAIL"
        print(f"  {status:4}  {label:<70} -> {got!r}")
        if got != want:
            failures.append(f"{label}: got {got!r}, want {want!r}")

    # -- SKILL.md's own worked example: passes 4,5,6 identical -> frozen at
    # the pass corresponding to index 2 (the 3rd pass in the streak, i.e.
    # pass 6) -- this is the exact case senior-dev flagged as ambiguous:
    # the first answered pass (pass 4) trivially becomes counted-pass #1.
    check("three identical full-lens passes freeze at the 3rd (index 2)",
          run([answer("fixed"), answer("fixed"), answer("fixed")]), 2)

    check("N-1 identical passes never freeze",
          run([answer("fixed"), answer("fixed")]), None)

    check("a single answered pass never freezes on its own",
          run([answer("fixed")]), None)

    # -- FAILED-lens pass neither counts nor resets --------------------------
    check("a FAILED pass in the middle of a streak doesn't break it",
          run([answer("fixed"), FAILED, answer("fixed"), answer("fixed")]), 3)

    check("a FAILED pass alone never freezes",
          run([FAILED, FAILED, FAILED]), None)

    check("a FAILED pass before any answer doesn't count as a baseline",
          run([FAILED, answer("fixed"), answer("fixed"), answer("fixed")]), 3)

    # -- a differing answer resets the streak, starting a new one -----------
    check("a differing answer resets -- 2 identical, 1 different, 2 identical: needs a fresh 3",
          run([answer("fixed"), answer("fixed"), answer("configurable"),
               answer("configurable"), answer("configurable")]), 4)

    # -- an escalated cross-lane disagreement resets to NO baseline, unlike
    # a FAILED pass's neutral skip -- answers on either side of an unresolved
    # disagreement must never form one continuous streak.
    check("a disagreement between two equivalent answers breaks the streak entirely",
          run([answer("fixed"), answer("fixed"), DISAGREEMENT,
               answer("fixed"), answer("fixed")]), None)

    check("resolving after a disagreement starts a genuinely fresh streak",
          run([answer("fixed"), answer("fixed"), DISAGREEMENT,
               answer("fixed"), answer("fixed"), answer("fixed")]), 5)

    check("a disagreement alone never freezes",
          run([DISAGREEMENT, DISAGREEMENT, DISAGREEMENT]), None)

    check("advance() on a disagreement always returns state=None, frozen=False",
          advance((2, "fixed"), DISAGREEMENT), (None, False))

    check("alternating answers never freeze",
          run([answer("a"), answer("b"), answer("a"), answer("b")]), None)

    # -- reopening / unfreeze are both "reset state to None, resume" --------
    frozen_state, frozen = advance((2, "fixed"), answer("fixed"))
    check("advance() reaching N reports frozen=True on that exact call",
          frozen, True)
    check("frozen state carries the completed streak count",
          frozen_state, (FREEZE_N, "fixed"))

    reopened_state, reopened_frozen = advance(None, answer("configurable"))
    check("reopening (state reset to None) starts a fresh streak at 1, not frozen",
          (reopened_state, reopened_frozen), ((1, "configurable"), False))

    # keep-active has nothing to assert here by design: a keep-active
    # question is simply never passed through advance()/run() at all.

    print()
    if failures:
        print(f"{total - len(failures)}/{total} passed")
        for f in failures:
            print(f"  FAILED: {f}")
        return 1
    print(f"{total}/{total} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
