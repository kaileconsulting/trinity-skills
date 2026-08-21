#!/usr/bin/env python3
"""Fixture-pin `tools/scope_classifier.py` against §3's worked examples
(Trinity v2.4 Phase 0, iterate-review's diff-scope classifier).

The classifier itself is editor-side judgment, never runner-owned code --
this checker exists so the written heuristic in iterate-review/SKILL.md
Setup step 3 has an executable, boundary-case-tested form instead of
resting on prose examples alone (qa lens finding, Phase 0 pass 1).

Usage:
    tools/check-scope-classification.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scope_classifier import classify  # noqa: E402

CASES: list[tuple[str, list[str], str]] = [
    ("tests+docs-only diff (SKILL.md worked example 1)",
     ["tests/test_foo.py", "docs/README.md"], "non-production"),
    ("mixed diff -- one production path is enough (worked example 2)",
     ["src/foo.py", "tests/test_foo.py"], "production"),
    ("ambiguous path biases toward the full budget (worked example 3)",
     [".github/workflows/ci.yml"], "production"),
    ("golden/example-only diff",
     ["iterate-review/examples/composition/golden-plain.txt"], "non-production"),
    ("a real production path from this very review's own diff",
     ["iterate-plan/SKILL.md"], "production"),
    ("no paths touched -- degenerate/ambiguous, biases production",
     [], "production"),
    ("bare test-file-convention filename, no directory segment at all",
     ["test_foo.py"], "non-production"),
    ("suffix test-file convention",
     ["foo_test.py"], "non-production"),
    (".spec. filename convention",
     ["foo.spec.js"], "non-production"),
    ("non-production path segment matching is case-insensitive",
     ["Tests/Foo.cs"], "non-production"),
    ("fixtures directory",
     ["iterate-review/examples/merge/01-dedupe-and-worst-of/pass-1.qa.response.json"],
     "non-production"),
    ("one non-matching path among several non-production ones is still production",
     ["docs/README.md", "tools/check-all.sh", "tests/test_foo.py"], "production"),
    ("root-level README with no docs/ segment at all",
     ["README.md"], "non-production"),
    ("root-level CHANGELOG, no extension",
     ["CHANGELOG"], "non-production"),
    ("root-level LICENSE and CONTRIBUTING together",
     ["LICENSE", "CONTRIBUTING.md"], "non-production"),
    ("root-level doc filename matching is case-insensitive",
     ["readme.MD"], "non-production"),
    ("a root-level doc-only diff from this very repo (dogfooding check)",
     [".gitignore", "README.md", "CHANGELOG.md"], "production"),  # .gitignore isn't a doc file
]


def main() -> int:
    failures = []
    for label, paths, want in CASES:
        got = classify(paths)
        status = "ok" if got == want else "FAIL"
        print(f"  {status:4}  {label:<70} -> {got}")
        if got != want:
            failures.append(f"{label}: got {got!r}, want {want!r} (paths={paths})")

    print()
    if failures:
        print(f"{len(CASES) - len(failures)}/{len(CASES)} passed")
        for f in failures:
            print(f"  FAILED: {f}")
        return 1
    print(f"{len(CASES)}/{len(CASES)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
