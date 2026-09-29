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

# Simplification-gate recipe fixtures (schema 2 cards, schema-1 mixing).
FIXTURES = os.path.join(REPO, "tools", "fixtures", "provenance")
SCHEMA1 = os.path.join(FIXTURES, "schema1-run.json")
TWO_CARDS = os.path.join(FIXTURES, "two-cards.json")
PENDING = os.path.join(FIXTURES, "pending-card.json")
ABORTED_CARD = os.path.join(FIXTURES, "aborted-card.json")


def run_recipe(*state_files: str, n: int | None = None) -> dict:
    if shutil.which("jq") is None:
        raise RuntimeError(
            "jq not found on PATH -- this checker runs the real "
            "tools/provenance-recipe.jq through the jq binary rather than "
            "reimplementing it, so jq is a prerequisite for this one check "
            "(not for the skills themselves). Install jq and re-run."
        )
    arg = ["--arg", "n", str(n)] if n is not None else []
    result = subprocess.run(
        ["jq", "-s", *arg, "-f", RECIPE, *state_files],
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
    for f in (PLAN_CONVERGED, PLAN_ABORTED, REVIEW_CONVERGED, REVIEW_ABORTED,
              SCHEMA1, TWO_CARDS, PENDING, ABORTED_CARD):
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

    # -- Phase-0-only: schema-2 examples with no cards read as empty ---------
    failures += check("phase-0-only (examples, no cards)", combined, {
        "cluster_threshold": None,
        "cluster_hits": [],
        "card_outcome_mix": {},
        "card_false_positive": {"resolved": 0, "premature": 0},
        "card_run_pass_counts": [],
    })

    # -- mixed schema: a schema-1 file still counts, with no cards ------------
    mixed = run_recipe(SCHEMA1, REVIEW_CONVERGED, REVIEW_ABORTED, n=3)
    failures += check("mixed schema-1/schema-2", mixed, {
        "runs": 3,
        "pass_count": 7,          # 2 (schema-1) + 2 + 3
        "findings_total": 19,     # 7 + 7 + 5
        "fold_caused_total": 3,   # 1 + 1 + 1
        "cluster_hits": [],
        "cluster_threshold": 3,
    })

    # -- cards: two on one pass, a pending one, an aborted one ----------------
    cards = run_recipe(TWO_CARDS, PENDING, ABORTED_CARD, n=3)
    hits = {(h["component"], h["pass"]): h for h in cards["cluster_hits"]}
    failures += check("cards (two-cards + pending + aborted)", cards, {
        "runs": 3,
        "card_outcome_mix": {"remove": 1, "fold-once-more": 1,
                             "pending": 1, "aborted": 1},
        # pending and aborted rows are excluded from the denominator
        "card_false_positive": {"resolved": 2, "premature": 1},
        "card_run_pass_counts": [5, 3, 4],
    })
    want_hits = {
        # removed label: the next observed pass is quiet on it -> null
        ("sql-classifier", 3): {"chosen": "remove", "next": None,
                                "recurrence": False},
        # the join skips pass 4 (observation false) and lands on pass 5
        ("grant-toggle", 3): {"chosen": "fold-once-more", "reason": "premature",
                              "next": {"worst_severity": "LOW", "findings": 1,
                                       "fold_caused": 0},
                              "recurrence": False},
        # no later completed pass -> unknown, never guessed
        ("cache-key", 3): {"chosen": "pending", "next": "unknown"},
        ("retry-loop", 4): {"chosen": "aborted", "next": "unknown"},
    }
    for key, want in want_hits.items():
        failures += check(f"cluster_hits {key}", hits.get(key, {}), want)

    # without --arg n the recipe never assumes a threshold
    no_n = run_recipe(TWO_CARDS)
    failures += check("cards without --arg n", no_n, {"cluster_threshold": None})
    failures += [f"cards without --arg n: recurrence {h['recurrence']!r}, want None"
                 for h in no_n["cluster_hits"] if h["recurrence"] is not None]

    if failures:
        print("provenance recipe: FAILED")
        for f in failures:
            print(f"  {f}")
        return 1

    print("provenance recipe: iterate-plan (converge+abort) OK")
    print("provenance recipe: iterate-review (converge+abort) OK")
    print("provenance recipe: combined cross-skill invocation OK")
    print("provenance recipe: phase-0-only, mixed-schema, card fixtures OK")
    print("7/7 recipe invocations verified against tracked sample and fixture state files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
