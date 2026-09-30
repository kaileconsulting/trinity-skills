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
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scope_classifier import (  # noqa: E402
    NON_PRODUCTION_SEGMENTS, _ROOT_DOC_BASENAMES, classify)

SKILL_MD = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "iterate-review", "SKILL.md")


def prose_agreement() -> list:
    """Pins SKILL.md Setup step 3's prose to scope_classifier.py: the
    prose names, in backticks, exactly the segments and root doc names the
    code uses — both directions."""
    with open(SKILL_MD, encoding="utf-8") as fh:
        text = fh.read()
    start = text.index("**Classify the diff")
    step = text[start:text.index("**Worked examples:**", start)]
    problems = []
    named_segments = set(re.findall(r"`([a-z]+)`", step.split("a filename matching")[0]))
    if named_segments != NON_PRODUCTION_SEGMENTS:
        problems.append(f"segments: prose {sorted(named_segments)} vs code "
                        f"{sorted(NON_PRODUCTION_SEGMENTS)}")
    # The root doc list runs from "documentation filename" to its
    # "(case-insensitive" qualifier; names are backticked, upper-case, and
    # LICENSE/LICENCE is written `LICENSE`/`LICENCE`.
    lo = step.index("documentation filename")
    root_list = step[lo:step.index("(case-insensitive", lo)]
    named_roots = {n.lower() for n in re.findall(r"`([A-Z][A-Z_]*)`", root_list)}
    if named_roots != _ROOT_DOC_BASENAMES:
        problems.append(f"root doc names: prose {sorted(named_roots)} vs code "
                        f"{sorted(_ROOT_DOC_BASENAMES)}")
    return problems


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
    ("a nested file matching a doc basename is NOT the root-level exception",
     ["src/README.py"], "production"),
    ("nested SECURITY.md under a config dir is still production",
     ["config/SECURITY.md"], "production"),
    ("nested LICENSE.ts under lib/ is still production",
     ["lib/LICENSE.ts"], "production"),
    ("root-level doc file alongside a nested doc-named file is still production",
     ["README.md", "src/README.py"], "production"),
    ("multi-extension root doc filename (locale variant)",
     ["README.en.md"], "non-production"),
    ("multi-extension root doc filename (generated variant)",
     ["CHANGELOG.generated.md"], "non-production"),
    ("a literal backslash is a filename character, not a separator (git paths)",
     ["src\\docs\\billing.py"], "production"),
]


def main() -> int:
    failures = []
    for label, paths, want in CASES:
        got = classify(paths)
        status = "ok" if got == want else "FAIL"
        print(f"  {status:4}  {label:<70} -> {got}")
        if got != want:
            failures.append(f"{label}: got {got!r}, want {want!r} (paths={paths})")

    for problem in prose_agreement():
        failures.append(f"SKILL.md step 3 prose disagrees with scope_classifier.py — {problem}")
        print(f"  FAIL  prose agreement: {problem}")
    if not any("prose" in f for f in failures):
        print("  ok    SKILL.md step 3 prose names exactly the code's segments and root doc names")

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
