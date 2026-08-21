"""Reference implementation of iterate-review's §3 diff-scope classifier
(Trinity v2.4 Phase 0, `iterate-review/SKILL.md` Setup step 3).

Classification is **editor-side, deliberate loop-control judgment** — the
runner never decides it, and nothing in `bin/` calls this module at
runtime. It exists purely so the written path heuristic has an
executable, fixture-pinned form instead of living only in prose; see
`check-scope-classification.py`. If you change the heuristic here,
update `iterate-review/SKILL.md`'s Setup step 3 in the same commit (and
vice versa) — this module is a mirror of that prose, not its source of
truth.
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


def _path_is_non_production(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    segments, filename = parts[:-1], parts[-1] if parts else ""
    if any(seg.lower() in NON_PRODUCTION_SEGMENTS for seg in segments):
        return True
    if any(p.match(filename) for p in _TEST_FILENAME_PATTERNS):
        return True
    basename = filename.rsplit(".", 1)[0] if "." in filename else filename
    return basename.lower() in _ROOT_DOC_BASENAMES


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
    if all(_path_is_non_production(p) for p in paths):
        return "non-production"
    return "production"
