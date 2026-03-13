"""Shared HTTP contract validation constants."""

from __future__ import annotations

import re

SEMVER_CORE = (
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)
SEMVER_PATTERN = rf"^{SEMVER_CORE}$"
SLUG_PATTERN = r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,127})$"
VERSION_CONSTRAINT_PATTERN = re.compile(
    rf"^\s*(?:==|=|!=|>=|<=|>|<)\s*{SEMVER_CORE}\s*"
    rf"(?:,\s*(?:==|=|!=|>=|<=|>|<)\s*{SEMVER_CORE}\s*)*$"
)
MARKER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
MAX_BATCH_ITEMS = 100
