"""Adapters: build a pack from a corpus that already exists.

An adapter is deliberately conservative. It reads what is on disk, records
where every piece came from, and does not try to repair anything. The linter
then judges the result — that separation is the point of the format.
"""

from __future__ import annotations

from .generic import export_markdown
from .llmwiki import export_llmwiki
from .obsidian import export_obsidian

__all__ = ["export_llmwiki", "export_markdown", "export_obsidian"]
