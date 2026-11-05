"""Orphan checks: what in the pack is not being used?"""

from __future__ import annotations

from ..model import Pack
from ..report import Finding
from . import CheckContext, register


@register("orphans")
def check_orphans(pack: Pack, ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []

    used_sources = {ev.source_id for ev in pack.evidence if ev.source_id}
    for source in pack.manifest.sources:
        if source.id not in used_sources:
            findings.append(
                Finding(
                    rule="orphan.source",
                    severity="info",
                    message=f"source {source.id} ({source.path}) is not cited by any evidence",
                    location=f"manifest.json#{source.id}",
                )
            )

    used_entities: set[str] = set()
    for claim in pack.claims:
        used_entities.update(claim.entities)
    for relation in pack.relations:
        used_entities.add(relation.from_id)
        used_entities.add(relation.to_id)

    for entity in pack.entities:
        if entity.id not in used_entities:
            findings.append(
                Finding(
                    rule="orphan.entity",
                    severity="info",
                    message=f"entity {entity.id} ({entity.name}) is not referenced by any claim or relation",
                    location=f"entities.json#{entity.id}",
                )
            )
    return findings
