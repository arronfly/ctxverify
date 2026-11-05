"""Provenance checks: does every claim actually trace back to something?"""

from __future__ import annotations

from ..model import (
    STATUSES_ADVISING_EVIDENCE,
    STATUSES_REQUIRING_EVIDENCE,
    Pack,
    sha256_text,
)
from ..report import Finding
from . import CheckContext, register


@register("provenance")
def check_provenance(pack: Pack, ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    claims = pack.claims_by_id()
    evidence = pack.evidence_by_id()
    sources = pack.sources_by_id()

    # Evidence must point at a claim and a source that exist.
    for ev in pack.evidence:
        if ev.claim_id and ev.claim_id not in claims:
            findings.append(
                Finding(
                    rule="provenance.dangling",
                    severity="error",
                    message=f"evidence {ev.id} references unknown claim {ev.claim_id}",
                    location=f"evidence.jsonl#{ev.id}",
                )
            )
        if ev.source_id and ev.source_id not in sources:
            findings.append(
                Finding(
                    rule="provenance.dangling",
                    severity="error",
                    message=f"evidence {ev.id} references unknown source {ev.source_id}",
                    location=f"evidence.jsonl#{ev.id}",
                )
            )
        if not ev.quote.strip():
            findings.append(
                Finding(
                    rule="provenance.quote",
                    severity="error",
                    message=f"evidence {ev.id} has an empty quote",
                    location=f"evidence.jsonl#{ev.id}",
                    hint="an evidence record without a quote cannot be checked by a human",
                )
            )
        elif ev.quote_sha256:
            expected = sha256_text(ev.quote)
            # Hex digests are case-insensitive. A pack written by a tool that
            # uppercases them is not tampered with.
            if expected.lower() != str(ev.quote_sha256).strip().lower():
                findings.append(
                    Finding(
                        rule="provenance.quote",
                        severity="error",
                        message=(
                            f"evidence {ev.id} quote hash mismatch: recorded "
                            f"{ev.quote_sha256[:12]}…, actual {expected[:12]}…"
                        ),
                        location=f"evidence.jsonl#{ev.id}",
                        hint="the quote was edited after the hash was recorded",
                    )
                )

    # Claims must be backed by evidence where their status promises it.
    for claim in pack.claims:
        referenced = [e for e in claim.evidence if e in evidence]
        missing = [e for e in claim.evidence if e not in evidence]
        for evidence_id in missing:
            findings.append(
                Finding(
                    rule="provenance.dangling",
                    severity="error",
                    message=f"claim {claim.id} references unknown evidence {evidence_id}",
                    location=f"claims.jsonl#{claim.id}",
                )
            )
        if claim.status in STATUSES_REQUIRING_EVIDENCE and not referenced:
            findings.append(
                Finding(
                    rule="provenance.missing",
                    severity="error",
                    message=f"claim {claim.id} is marked 'verified' but has no evidence",
                    location=f"claims.jsonl#{claim.id}",
                    hint="downgrade the status, or attach the evidence that verifies it",
                )
            )
        elif claim.status in STATUSES_ADVISING_EVIDENCE and not referenced:
            findings.append(
                Finding(
                    rule="provenance.missing",
                    severity="warning",
                    message=f"claim {claim.id} is marked 'asserted' but has no evidence",
                    location=f"claims.jsonl#{claim.id}",
                )
            )
        if claim.status not in STATUSES_REQUIRING_EVIDENCE and not referenced:
            continue
    return findings
