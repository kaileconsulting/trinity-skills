#!/usr/bin/env bash
# Run every fixture/parity check in this repo. Exits non-zero if any fails.
#
#   tools/check-all.sh
#
# Requires python3 and the `jsonschema` package (pip install jsonschema).
# Requires the `jq` binary on PATH (only for check-provenance-recipe.py,
# which runs the real tools/provenance-recipe.jq rather than
# reimplementing it -- that checker reports a clear error, not a
# traceback, if jq is missing).

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

failed=()

run() {
  local label="$1"; shift
  echo "=============================================================="
  echo "  $label"
  echo "=============================================================="
  if "$@"; then
    echo
  else
    echo
    failed+=("$label")
  fi
}

run "selection routing (iterate-review)" \
    python3 iterate-review/examples/selection/check-selection.py
run "runner scripts (iterate-review bin/)" \
    python3 tools/check-runners.py
run "runner scripts (iterate-plan bin/)" \
    python3 tools/check-plan-runners.py
run "example fixtures vs. schemas" \
    python3 tools/check-examples.py
run "shared-machinery parity" \
    python3 tools/check-parity.py
run "provenance analytics recipe" \
    python3 tools/check-provenance-recipe.py
run "scope classification (iterate-review §3)" \
    python3 tools/check-scope-classification.py
run "open-question freeze counting (iterate-plan §4)" \
    python3 tools/check-question-freeze.py
run "checker self-tests" \
    python3 tools/test-checkers.py

echo "=============================================================="
if [ ${#failed[@]} -eq 0 ]; then
  echo "  all checks passed"
  exit 0
fi
echo "  FAILED: ${failed[*]}"
exit 1
