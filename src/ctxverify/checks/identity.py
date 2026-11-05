"""Identity checks: unique ids, and numbering schemes that do not collide."""

from __future__ import annotations

import posixpath
import re
from collections import defaultdict

from ..model import Pack
from ..report import Finding
from . import CheckContext, register

#: "C-001", "P-12", "KB-007" — a prefix, a dash, digits.
NUMBER_RE = re.compile(r"^([A-Za-z]{1,6})-(\d{1,6})$")
#: The same shape at the start of a filename: "C-001_Context_Packs.md".
#:
#: The separator must be an underscore. A hyphen would sweep in document ids
#: that merely happen to start with one ("acme-1077-transmission-pricing.md"
#: is a filing, not a card numbered 1077).
FILENAME_NUMBER_RE = re.compile(r"^([A-Za-z]{1,6}-\d{1,6})(?=_|$)")


@register("identity")
def check_identity(pack: Pack, ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []

    groups = {
        "claims": [c.id for c in pack.claims],
        "evidence": [e.id for e in pack.evidence],
        "entities": [e.id for e in pack.entities],
        "relations": [r.id for r in pack.relations],
        "contradictions": [c.id for c in pack.contradictions],
        "sources": [s.id for s in pack.manifest.sources],
    }

    for kind, ids in groups.items():
        by_id: dict[str, int] = defaultdict(int)
        for item_id in ids:
            by_id[item_id] += 1
        for item_id, count in sorted(by_id.items()):
            if count > 1:
                findings.append(
                    Finding(
                        rule="ids.duplicate",
                        severity="error",
                        message=f"{kind}: id {item_id!r} is used {count} times",
                        location=f"{kind}.jsonl#{item_id}" if kind else None,
                        hint="every consumer that keys on this id will keep only the last one",
                    )
                )

        empty = [i for i in ids if not i.strip()]
        if empty:
            findings.append(
                Finding(
                    rule="ids.duplicate",
                    severity="error",
                    message=f"{kind}: {len(empty)} record(s) have an empty id",
                    location=kind,
                )
            )

    findings.extend(_number_collisions(pack))
    return findings


def _number_collisions(pack: Pack) -> list[Finding]:
    """A numbering scheme must identify exactly one file.

    ``C-001_Context_Packs.md`` and ``C-001_Evidence.md`` are two
    files claiming the same number. Any reference to "C-001" is then
    ambiguous, and the compiler that produced them was working from a
    numbering scheme that had already drifted.

    Some corpora deliberately keep several numbering spaces side by side: a
    global ``C-001`` and a domain-local ``C-001`` in a sub-directory. That is
    legitimate, but it has to be declared rather than inferred from where the
    file happens to sit: a source may carry a ``namespace`` field, and numbers
    are then compared within a namespace. A source without one belongs to the
    default namespace, where a collision with any other default-namespace file
    is still an error.

    The tool cannot tell a deliberate second space from a file that was
    copied and never cleaned up, so it reports both and says which is which.
    """
    owners: dict[tuple[str, str], set[str]] = defaultdict(set)
    for source in pack.manifest.sources:
        candidates: set[str] = set()
        for key in ("id", "number", "编号"):
            value = source.extra.get(key)
            if isinstance(value, str) and NUMBER_RE.match(value.strip()):
                candidates.add(value.strip())
        basename = posixpath.basename(source.path)
        match = FILENAME_NUMBER_RE.match(basename)
        if match:
            candidates.add(match.group(1))
        namespace = str(source.extra.get("namespace") or "").strip()
        for candidate in candidates:
            owners[(namespace, candidate)].add(source.path)

    findings: list[Finding] = []
    for (namespace, number), paths in sorted(owners.items()):
        if len(paths) > 1:
            listing = ", ".join(sorted(paths))
            scope = f" in namespace {namespace!r}" if namespace else ""
            directories = {posixpath.dirname(path) for path in paths}
            if len(directories) > 1:
                hint = (
                    "these files sit in different directories, which often means two "
                    "numbering spaces; give each source a 'namespace' to say so, or renumber "
                    "if it is an accident"
                )
            else:
                hint = "one numbering scheme must map to one file; renumber one of them"
            findings.append(
                Finding(
                    rule="ids.collision",
                    severity="error",
                    message=(
                        f"number {number!r} is claimed by {len(paths)} files{scope}: {listing}"
                    ),
                    location=f"manifest.json#{number}",
                    hint=hint,
                )
            )
    return findings
