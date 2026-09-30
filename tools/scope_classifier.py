"""Shim: the §3 path heuristic lives in iterate-review/bin/path_classes.py
(one implementation, shared with the runner's --exclude refusals). Kept so
tools/ keeps its historical import path."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "iterate-review", "bin"))

from path_classes import (  # noqa: E402,F401
    NON_PRODUCTION_SEGMENTS, classify, is_non_production)
from path_classes import _ROOT_DOC_BASENAMES  # noqa: E402,F401
