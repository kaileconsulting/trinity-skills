#!/usr/bin/env python3
"""Fixture-pin the shared provenance analytics recipe (Trinity v2.4 Phase 0 §5).

Runs `tools/provenance-recipe.jq` — via the actual `jq` binary, not a
reimplementation — against the four tracked example state files (one
Converge-path and one Abort-path sample per skill) and asserts the exact
tallies. This is the "runs against those samples" half of Phase 0's §5
acceptance criterion; the other half (schema shape, field names) is
inspectable directly in the example files themselves.

Also exercises each skill's samples in isolation, so a real user running
the recipe against only one skill's state/ directory (the common case)
is covered too, not just the combined cross-skill invocation.

Prerequisite: the `jq` binary on PATH (this checker runs the real
recipe through it, deliberately, rather than reimplementing the query
in Python — see the module docstring above). `tools/check-all.sh`
documents this same prerequisite; see the checker there.

Usage:
    tools/check-provenance-recipe.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECIPE = os.path.join(REPO, "tools", "provenance-recipe.jq")

PLAN_CONVERGED = os.path.join(REPO, "iterate-plan", "state", "example.json")
PLAN_ABORTED = os.path.join(REPO, "iterate-plan", "state", "example-aborted.json")
REVIEW_CONVERGED = os.path.join(REPO, "iterate-review", "state", "example.json")
REVIEW_ABORTED = os.path.join(REPO, "iterate-review", "state", "example-aborted.json")


def run_recipe(*state_files: str) -> dict:
    if shutil.which("jq") is None:
        raise RuntimeError(
            "jq not found on PATH -- this checker runs the real "
            "tools/provenance-recipe.jq through the jq binary rather than "
            "reimplementing it, so jq is a prerequisite for this one check "
            "(not for the skills themselves). Install jq and re-run."
        )
    result = subprocess.run(
        ["jq", "-s", "-f", RECIPE, *state_files],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"jq failed: {result.stderr}")
    return json.loads(result.stdout)


def check(label: str, got: dict, want: dict) -> list[str]:
    failures = []
    for key, expected in want.items():
        actual = got.get(key)
        if isinstance(expected, float):
            ok = actual is not None and abs(actual - expected) < 1e-9
        else:
            ok = actual == expected
        if not ok:
            failures.append(f"{label}: {key} = {actual!r}, want {expected!r}")
    return failures


def main() -> int:
    if shutil.which("jq") is None:
        print("error: jq not found on PATH -- required to run this checker "
              "(not required to use iterate-plan/iterate-review themselves). "
              "Install jq and re-run.", file=sys.stderr)
        return 2
    if not os.path.exists(RECIPE):
        print(f"error: {RECIPE} not found", file=sys.stderr)
        return 2
    for f in (PLAN_CONVERGED, PLAN_ABORTED, REVIEW_CONVERGED, REVIEW_ABORTED):
        if not os.path.exists(f):
            print(f"error: sample state file not found: {f}", file=sys.stderr)
            return 2

    failures: list[str] = []

    # -- iterate-plan alone: Converge + Abort samples ------------------------
    plan_all = run_recipe(PLAN_CONVERGED, PLAN_ABORTED)
    failures += check("iterate-plan (converge+abort)", plan_all, {
        "runs": 2,
        "pass_count": 4,          # 3 (converged) + 1 (aborted)
        "findings_total": 11,     # 7 + 4
        "fold_caused_total": 1,   # 1 + 0
        "fold_caused_share": 1 / 11,
        "disposition_mix": {
            "incorporated": 6,     # 4 (pass 1 + pass 3) + 2 (aborted)
            "skipped": 3,          # 2 + 1
            "disputed": 1,         # 0 + 1
            "accepted-risk": 1,    # 1 (pass 2, Phase 1 example) + 0
            "register-match": 0,
        },
        # scope_class is null for every iterate-plan run -- never a match.
        "non_production_rollback_hits": 0,
    })

    # -- iterate-review alone: Converge (production) + Abort (non-production)
    review_all = run_recipe(REVIEW_CONVERGED, REVIEW_ABORTED)
    failures += check("iterate-review (converge+abort)", review_all, {
        "runs": 2,
        "pass_count": 5,          # 2 (converged) + 3 (aborted)
        "findings_total": 12,     # 7 + 5
        "fold_caused_total": 2,   # 1 + 1
        "fold_caused_share": 2 / 12,
        "disposition_mix": {
            "incorporated": 6,     # 3 (pass 1) + 3 (aborted passes 1-3)
            "skipped": 3,          # 2 (pass 1+2) + 1 (aborted pass 1)
            "disputed": 1,         # 0 + 1 (aborted pass 3)
            "accepted-risk": 1,    # 1 + 0
            "register-match": 1,   # 1 + 0
        },
        # only example-aborted.json is non-production; its pass 3 (pass > 2)
        # carries high_medium_count = 2 -- the §3 rollback condition firing.
        "non_production_rollback_hits": 2,
    })

    # -- cross-skill: the whole point of a shared row schema -----------------
    combined = run_recipe(PLAN_CONVERGED, PLAN_ABORTED, REVIEW_CONVERGED, REVIEW_ABORTED)
    failures += check("combined (both skills)", combined, {
        "runs": 4,
        "pass_count": 9,
        "findings_total": 23,
        "fold_caused_total": 3,
        "fold_caused_share": 3 / 23,
        "disposition_mix": {
            "incorporated": 12,    # 6 (iterate-plan) + 6 (iterate-review)
            "skipped": 6,
            "disputed": 2,
            "accepted-risk": 2,    # 1 (iterate-plan) + 1 (iterate-review)
            "register-match": 1,
        },
        "non_production_rollback_hits": 2,
    })

    if failures:
        print("provenance recipe: FAILED")
        for f in failures:
            print(f"  {f}")
        return 1

    print("provenance recipe: iterate-plan (converge+abort) OK")
    print("provenance recipe: iterate-review (converge+abort) OK")
    print("provenance recipe: combined cross-skill invocation OK")
    print("3/3 recipe invocations verified against tracked sample state files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
