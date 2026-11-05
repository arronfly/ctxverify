"""A deliberately small YAML frontmatter reader.

Vendors differ in what they write into frontmatter: lists inline or as
blocks, dates as strings or dates, nested maps one or two levels deep. A full
YAML parser is a dependency this project does not want, and a parser that
raises is worse than one that is merely tolerant.

This reader handles the shapes that actually occur in frontmatter and returns
plain Python values. Anything it cannot read is skipped, never fatal.
"""

from __future__ import annotations

import re
from typing import Any

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)


def split_frontmatter(text: str) -> tuple[str, str]:
    """Return ``(frontmatter_text, body)``."""
    match = FRONTMATTER_RE.match(text or "")
    if not match:
        return "", text or ""
    return match.group(1), (text or "")[match.end() :]


def _scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value[0:1] in {'"', "'"} and value[-1:] == value[0:1] and len(value) >= 2:
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_scalar(part) for part in inner.split(",")]
    lowered = value.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if lowered in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value
    if re.fullmatch(r"-?\d*\.\d+", value):
        try:
            return float(value)
        except ValueError:
            return value
    return value


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse a YAML-ish frontmatter block into a dictionary."""
    raw, _ = split_frontmatter(text)
    if not raw.strip():
        return {}

    data: dict[str, Any] = {}

    # A single pass, because a second pass cannot tell which indented lines
    # belong to which key: a nested map must end where the next top-level
    # key begins, or its entries bleed into each other.
    pending_key: str | None = None
    pending_list: list[Any] | None = None
    pending_map: dict[str, Any] | None = None

    for line in raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        stripped = line.strip()

        if stripped.startswith("- ") or stripped == "-":
            if pending_key is not None and pending_list is not None:
                pending_list.append(_scalar(stripped[2:] if len(stripped) > 1 else ""))
            continue

        if line[:1] in (" ", "\t"):
            # Nested content under the pending key.
            if pending_map is not None:
                sub_key, sep, sub_value = stripped.partition(":")
                if sep:
                    pending_map[sub_key.strip()] = _scalar(sub_value)
            continue

        # A new top-level key ends whatever was pending.
        key, sep, value = stripped.partition(":")
        if not sep:
            pending_key = None
            pending_list = None
            pending_map = None
            continue
        key = key.strip()
        value = value.strip()

        if pending_key is not None:
            if pending_map and pending_map:
                data[pending_key] = pending_map
            elif pending_list:
                data[pending_key] = pending_list
            else:
                data[pending_key] = {}

        if value == "":
            # Could be a block list or a nested map; decide as the lines come.
            pending_key = key
            pending_list = []
            pending_map = {}
            data[key] = pending_list
            continue

        data[key] = _scalar(value)
        pending_key = None
        pending_list = None
        pending_map = None

    if pending_key is not None:
        if pending_map and pending_map:
            data[pending_key] = pending_map
        elif pending_list:
            data[pending_key] = pending_list

    return data


def as_list(value: Any) -> list[str]:
    """Coerce a frontmatter value into a list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, (str, int, float)):
        text = str(value).strip()
        return [text] if text else []
    return []


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)
