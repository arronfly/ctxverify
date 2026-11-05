"""Duplicate detection: the same fact stated twice."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

from ..model import Pack
from ..report import Finding
from . import CheckContext, register

_PUNCT = re.compile(r"[\s　。！？!?.,，、；;：:“”\"'‘’（）()\[\]【】<>《》\-—_/\\|]+")


def normalise(text: str) -> str:
    """Fold a claim's text to a comparable form: no punctuation, no case."""
    folded = unicodedata.normalize("NFKC", text or "").strip().lower()
    return _PUNCT.sub("", folded)


@register("duplicates")
def check_duplicates(pack: Pack, ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    groups: dict[str, list[str]] = defaultdict(list)
    for claim in pack.claims:
        key = normalise(claim.text)
        if key:
            groups[key].append(claim.id)

    for key, ids in sorted(groups.items()):
        if len(ids) > 1:
            listing = ", ".join(ids)
            findings.append(
                Finding(
                    rule="duplicate.claim",
                    severity="warning",
                    message=f"{len(ids)} claims state the same thing: {listing}",
                    location=f"claims.jsonl#{ids[0]}",
                    hint="a recompile that appends instead of reconciles produces these",
                )
            )
    return findings
