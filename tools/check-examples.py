#!/usr/bin/env python3
"""Validate every example reviewer response against its owning skill's schema.

Walks `<skill>/examples/**` for each skill that ships a reviewer schema and
checks every `*.json` against `<skill>/reviewer-output.schema.json`.

Also asserts the inverse: any `*.json.malformed` fixture must **fail** to parse.
Those files represent a lens that failed after retry, and the FAILED-lens
scenario in `iterate-review/examples/merge/02-...` is fiction if the file it
points at is quietly valid.

Requires the `jsonschema` package. It fails loudly if absent rather than
skipping — a check that silently passes when it cannot run is worse than no
check.

Usage:
    tools/check-examples.py
"""

from __future__ import annotations

import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = ("iterate-plan", "iterate-review")

# The patch-shaped-output markers iterate-review/SKILL.md step 11 scans for.
PATCH_MARKERS = (
    re.compile(r"\*\*\* Begin Patch"),
    re.compile(r"^--- a/", re.MULTILINE),
    re.compile(r"^\+\+\+ b/", re.MULTILINE),
    re.compile(r"@@ -\d"),
    re.compile(r"<{7}|={7}|>{7}"),
)


def find_patch_markers(doc: dict) -> list[str]:
    """Return the patch markers present anywhere in a response document.

    Serialising with ensure_ascii=False and decoding escapes matters: the
    markers live inside JSON string values, where a newline is written as \\n.
    """
    text = json.dumps(doc, ensure_ascii=False)
    text = text.replace("\\n", "\n")
    return [p.pattern for p in PATCH_MARKERS if p.search(text)]


def main() -> int:
    try:
        import jsonschema
    except ImportError:
        print(
            "error: this checker requires the `jsonschema` package.\n"
            "       install it with:  pip install jsonschema",
            file=sys.stderr,
        )
        return 2

    checked = 0
    failures: list[str] = []

    for skill in SKILLS:
        schema_path = os.path.join(REPO, skill, "reviewer-output.schema.json")
        examples_dir = os.path.join(REPO, skill, "examples")
        if not os.path.exists(schema_path):
            failures.append(f"{skill}: no reviewer-output.schema.json")
            continue
        if not os.path.isdir(examples_dir):
            print(f"{skill}: no examples/ directory — skipped")
            continue

        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)
        validator = jsonschema.Draft202012Validator(schema)

        print(f"{skill}/examples  (schema: {os.path.basename(schema_path)})")

        for root, _dirs, files in os.walk(examples_dir):
            for name in sorted(files):
                path = os.path.join(root, name)
                rel = os.path.relpath(path, REPO)

                if name.endswith(".json.malformed"):
                    checked += 1
                    try:
                        with open(path, encoding="utf-8") as fh:
                            json.load(fh)
                    except json.JSONDecodeError:
                        print(f"  ok    {rel}  (invalid JSON, as intended)")
                    else:
                        print(f"  FAIL  {rel}  parses as valid JSON but is "
                              f"supposed to represent a failed lens")
                        failures.append(rel)
                    continue

                if not name.endswith(".json"):
                    continue

                checked += 1
                try:
                    with open(path, encoding="utf-8") as fh:
                        doc = json.load(fh)
                except json.JSONDecodeError as exc:
                    print(f"  FAIL  {rel}  not valid JSON: {exc}")
                    failures.append(rel)
                    continue

                errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
                if errors:
                    print(f"  FAIL  {rel}")
                    for err in errors:
                        loc = "/".join(str(p) for p in err.path) or "(root)"
                        print(f"          {loc}: {err.message}")
                    failures.append(rel)
                    continue

                # A fixture whose name claims it violates the patch-marker rule
                # must actually contain markers, or the regression check it
                # backs is vacuous. Every other fixture must be free of them.
                markers = find_patch_markers(doc)
                wants_markers = "patch-marker-violation" in name
                if wants_markers and not markers:
                    print(f"  FAIL  {rel}  claims to violate the patch-marker "
                          f"rule but contains no patch markers")
                    failures.append(rel)
                elif markers and not wants_markers:
                    print(f"  FAIL  {rel}  contains patch markers "
                          f"({', '.join(markers)}) but is not named as a "
                          f"patch-marker-violation fixture")
                    failures.append(rel)
                elif wants_markers:
                    print(f"  ok    {rel}  (schema-valid; carries "
                          f"{len(markers)} patch marker kind(s), as intended)")
                else:
                    print(f"  ok    {rel}")
        print()

    if failures:
        print(f"{checked - len(failures)}/{checked} example fixtures OK "
              f"-- FAILED: {', '.join(failures)}")
        return 1
    print(f"{checked}/{checked} example fixtures OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
