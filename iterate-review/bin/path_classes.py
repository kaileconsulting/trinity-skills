"""The production / non-production path heuristic — iterate-review's §3
diff-scope classifier (`iterate-review/SKILL.md` Setup step 3) — in ONE
implementation.

Two consumers: the editor's scope classification (loop control; the
runner never decides it — `classify()` is exercised by
tools/check-scope-classification.py through the tools/scope_classifier.py
shim), and the runner's `--exclude` refusals (docs/review-diff-
exclusions-2026-09-29.md §2: `docs` and `governing-plan` may never take a
production path out of review). It lives in bin/ because a copied install
has no tools/, and tools/ imports it from here, so the two cannot drift.
SKILL.md Setup step 3 states the same heuristic in prose; change both in
the same commit (tools/check-scope-classification.py checks the prose
names every segment and root doc name listed here).
"""

from __future__ import annotations

import re

NON_PRODUCTION_SEGMENTS = {
    "test", "tests", "spec", "specs",
    "fixture", "fixtures", "golden", "goldens",
    "example", "examples", "docs",
}

_TEST_FILENAME_PATTERNS = [
    re.compile(r"^test_.+\..+$", re.IGNORECASE),
    re.compile(r"^.+_test\..+$", re.IGNORECASE),
    re.compile(r"^.+\.test\..+$", re.IGNORECASE),
    re.compile(r"^.+\.spec\..+$", re.IGNORECASE),
]

# Well-known root-level documentation filenames (the GitHub community-file
# conventions) count as non-production regardless of extension or absence
# of one -- a diff touching only README.md doesn't gain a `docs/` segment
# just because it's obviously documentation. Matched by basename with any
# extension stripped, case-insensitive.
_ROOT_DOC_BASENAMES = {
    "readme", "changelog", "contributing", "license", "licence",
    "code_of_conduct", "security", "authors", "notice", "governance",
}


def is_non_production(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    segments, filename = parts[:-1], parts[-1] if parts else ""
    if any(seg.lower() in NON_PRODUCTION_SEGMENTS for seg in segments):
        return True
    if any(p.match(filename) for p in _TEST_FILENAME_PATTERNS):
        return True
    if not segments:  # root-level exception only applies with NO directory
        # Split on the FIRST dot, not the last -- "any extension" must cover
        # multi-suffix variants like README.en.md or CHANGELOG.generated.md,
        # not just a single trailing extension.
        basename = filename.split(".", 1)[0]
        if basename.lower() in _ROOT_DOC_BASENAMES:
            return True
    return False


def classify(paths) -> str:
    """`paths`: iterable of touched file paths. Returns 'production' or
    'non-production'. Every touched path must match the non-production
    heuristic for the whole diff to classify non-production; one
    production-looking path is enough to classify the whole diff
    production. An empty path list (nothing touched) is the degenerate
    ambiguous case and classifies production, same as any other
    ambiguity -- biases toward the full budget."""
    paths = list(paths)
    if not paths:
        return "production"
    if all(is_non_production(p) for p in paths):
        return "non-production"
    return "production"
