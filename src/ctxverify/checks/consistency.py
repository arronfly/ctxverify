"""Consistency checks: does a claim's status match what the pack knows?"""

from __future__ import annotations

from ..model import (
    CLAIM_STATUSES,
    STATUSES_REQUIRING_CONTRADICTION,
    STATUSES_REQUIRING_NOTES,
    Pack,
)
from ..report import Finding
from . import CheckContext, register


@register("consistency")
def check_consistency(pack: Pack, ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    claims = pack.claims_by_id()
    evidence = pack.evidence_by_id()

    contradicted_claims: set[str] = set()
    for contradiction in pack.contradictions:
        for claim_id in contradiction.claims:
            if claim_id in claims:
                contradicted_claims.add(claim_id)
            else:
                findings.append(
                    Finding(
                        rule="contradiction.unresolved",
                        severity="error",
                        message=(
                            f"contradiction {contradiction.id} references unknown claim {claim_id}"
                        ),
                        location=f"contradictions.json#{contradiction.id}",
                    )
                )
        if contradiction.status == "open":
            findings.append(
                Finding(
                    rule="contradiction.unresolved",
                    severity="warning",
                    message=(
                        f"contradiction {contradiction.id} is still open: "
                        f"{contradiction.description or 'no description'}"
                    ),
                    location=f"contradictions.json#{contradiction.id}",
                    hint="an open contradiction means the pack holds two incompatible statements",
                )
            )
        if contradiction.status == "resolved" and not (contradiction.resolution or "").strip():
            findings.append(
                Finding(
                    rule="contradiction.unresolved",
                    severity="warning",
                    message=(
                        f"contradiction {contradiction.id} is marked resolved but records no resolution"
                    ),
                    location=f"contradictions.json#{contradiction.id}",
                )
            )
        if len(contradiction.claims) < 2:
            findings.append(
                Finding(
                    rule="contradiction.unresolved",
                    severity="warning",
                    message=(
                        f"contradiction {contradiction.id} names {len(contradiction.claims)} claim(s); "
                        "a contradiction needs at least two"
                    ),
                    location=f"contradictions.json#{contradiction.id}",
                )
            )

    for claim in pack.claims:
        if claim.status not in CLAIM_STATUSES:
            findings.append(
                Finding(
                    rule="status.inconsistent",
                    severity="error",
                    message=(
                        f"claim {claim.id} has unknown status {claim.status!r}; "
                        f"expected one of {', '.join(CLAIM_STATUSES)}"
                    ),
                    location=f"claims.jsonl#{claim.id}",
                )
            )
            continue

        if not claim.text.strip():
            findings.append(
                Finding(
                    rule="status.inconsistent",
                    severity="error",
                    message=f"claim {claim.id} has no text",
                    location=f"claims.jsonl#{claim.id}",
                )
            )

        if claim.status in STATUSES_REQUIRING_NOTES and not (claim.notes or "").strip():
            findings.append(
                Finding(
                    rule="status.inconsistent",
                    severity="warning",
                    message=(
                        f"claim {claim.id} is marked 'inferred' but records no reasoning in 'notes'"
                    ),
                    location=f"claims.jsonl#{claim.id}",
                    hint="an inference without a stated chain is indistinguishable from a guess",
                )
            )

        if claim.status in STATUSES_REQUIRING_CONTRADICTION and claim.id not in contradicted_claims:
            findings.append(
                Finding(
                    rule="status.inconsistent",
                    severity="warning",
                    message=(
                        f"claim {claim.id} is marked {claim.status!r} but no contradiction entry "
                        "references it"
                    ),
                    location=f"claims.jsonl#{claim.id}",
                    hint="a disputed claim needs the contradiction it takes part in",
                )
            )

        for evidence_id in claim.evidence:
            ev = evidence.get(evidence_id)
            if ev is not None and ev.claim_id and ev.claim_id != claim.id:
                findings.append(
                    Finding(
                        rule="status.inconsistent",
                        severity="error",
                        message=(
                            f"claim {claim.id} lists evidence {evidence_id}, "
                            f"but that evidence points at claim {ev.claim_id}"
                        ),
                        location=f"claims.jsonl#{claim.id}",
                    )
                )

        for entity_id in claim.entities:
            if entity_id not in pack.entities_by_id():
                findings.append(
                    Finding(
                        rule="status.inconsistent",
                        severity="error",
                        message=f"claim {claim.id} references unknown entity {entity_id}",
                        location=f"claims.jsonl#{claim.id}",
                    )
                )

    for relation in pack.relations:
        entities = pack.entities_by_id()
        if not relation.type.strip():
            findings.append(
                Finding(
                    rule="status.inconsistent",
                    severity="error",
                    message=f"relation {relation.id} has no type",
                    location=f"relations.json#{relation.id}",
                    hint="the type says how the two entities relate; without it the edge says nothing",
                )
            )
        if relation.from_id not in entities:
            findings.append(
                Finding(
                    rule="status.inconsistent",
                    severity="error",
                    message=f"relation {relation.id} starts at unknown entity {relation.from_id}",
                    location=f"relations.json#{relation.id}",
                )
            )
        if relation.to_id not in entities:
            findings.append(
                Finding(
                    rule="status.inconsistent",
                    severity="error",
                    message=f"relation {relation.id} ends at unknown entity {relation.to_id}",
                    location=f"relations.json#{relation.id}",
                )
            )
        if relation.claim_id and relation.claim_id not in claims:
            findings.append(
                Finding(
                    rule="status.inconsistent",
                    severity="error",
                    message=f"relation {relation.id} references unknown claim {relation.claim_id}",
                    location=f"relations.json#{relation.id}",
                )
            )
        for evidence_id in relation.evidence:
            if evidence_id not in evidence:
                findings.append(
                    Finding(
                        rule="status.inconsistent",
                        severity="error",
                        message=f"relation {relation.id} references unknown evidence {evidence_id}",
                        location=f"relations.json#{relation.id}",
                    )
                )

    return findings
