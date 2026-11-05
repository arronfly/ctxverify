"""Link resolution.

Vaults resolve links the way Obsidian does, not the way a filesystem does:
``[[note]]`` may point at ``notes/sub/dir/note.md``, at a file whose basename
matches in another folder, or at an alias declared in frontmatter. A linter
that resolves links naively reports broken links that are perfectly fine, and
people stop reading the report.

This module implements Obsidian-style resolution over an index of known paths
and known aliases.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field
from typing import Iterable

WIKILINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")


def strip_wikilink(target: str) -> str:
    """Return the bare target of a wikilink: no brackets, no alias, no heading."""
    text = target.strip()
    if text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2]
    text = text.split("|", 1)[0]
    text = text.split("#", 1)[0]
    return text.strip()


def normalise_path(path: str) -> str:
    """Normalise a path for comparison: forward slashes, no leading ``./``."""
    text = str(path).strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


@dataclass
class LinkIndex:
    """Everything a link may legitimately point at."""

    paths: list[str] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._by_path: dict[str, str] = {}
        self._by_lower_path: dict[str, str] = {}
        self._by_basename: dict[str, str] = {}
        self._by_lower_basename: dict[str, str] = {}
        self._by_suffix: dict[str, str] = {}
        for path in self.paths:
            norm = normalise_path(path)
            self._by_path.setdefault(norm, path)
            self._by_lower_path.setdefault(norm.lower(), path)
            base = posixpath.basename(norm)
            stem = base[:-3] if base.endswith(".md") else base
            self._by_basename.setdefault(stem, path)
            self._by_lower_basename.setdefault(stem.lower(), path)
            parts = norm.split("/")
            for depth in range(1, len(parts)):
                suffix = "/".join(parts[-depth:])
                self._by_suffix.setdefault(suffix, path)

    def resolve(self, target: str) -> str | None:
        """Resolve ``target`` to a known path, or return ``None``.

        The order mirrors Obsidian: exact path, path with ``.md``, path
        suffix, basename, then alias.
        """
        bare = strip_wikilink(target)
        if not bare:
            return None

        if bare in self.aliases:
            return self.aliases[bare]

        norm = normalise_path(bare)
        if norm in self._by_path:
            return self._by_path[norm]
        if norm + ".md" in self._by_path:
            return self._by_path[norm + ".md"]
        if norm.lower() in self._by_lower_path:
            return self._by_lower_path[norm.lower()]

        # Path suffix: "concepts/C-001" should find "wiki/concepts/C-001.md"
        if "/" in norm:
            if norm + ".md" in self._by_suffix:
                return self._by_suffix[norm + ".md"]
            if norm in self._by_suffix:
                return self._by_suffix[norm]
            lowered = norm.lower()
            for suffix, path in self._by_suffix.items():
                if suffix.lower() == lowered or suffix.lower() == lowered + ".md":
                    return path

        base = posixpath.basename(norm)
        stem = base[:-3] if base.endswith(".md") else base
        if stem in self._by_basename:
            return self._by_basename[stem]
        if stem.lower() in self._by_lower_basename:
            return self._by_lower_basename[stem.lower()]

        # A full path that matches a suffix of a known path (Obsidian's
        # "shortest path when possible" behaviour).
        for suffix, path in self._by_suffix.items():
            if suffix.lower() == (stem + ".md").lower():
                return path
        return None

    def find_wikilinks(self, text: str) -> list[str]:
        return [match.group(1) for match in WIKILINK_RE.finditer(text or "")]


def build_index(paths: Iterable[str], aliases: dict[str, str] | None = None) -> LinkIndex:
    return LinkIndex(paths=list(paths), aliases=dict(aliases or {}))
