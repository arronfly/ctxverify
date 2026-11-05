"""Hygiene checks: a pack travels. Credentials and phone numbers should not."""

from __future__ import annotations

import re
from typing import Iterator

from ..model import Pack
from ..report import Finding
from . import CheckContext, register

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("github fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}")),
    ("anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{24,}")),
    ("openai-style key", re.compile(r"\bsk-[A-Za-z0-9]{20,}")),
    ("aws access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    (
        "assigned credential",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|password|passwd)"
            r"\s*[:=]\s*[\"']?[A-Za-z0-9\-_./+=]{16,}"
        ),
    ),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{5,}")),
)

PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    (
        "phone number",
        re.compile(
            r"(?i)(?:电话|手机|联系电话|phone|mobile|tel)\s*[:：]?\s*(\+?\d[\d\s\-]{6,}\d)"
        ),
    ),
    ("mainland mobile number", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("national id number", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
)


def _pack_texts(pack: Pack) -> Iterator[tuple[str, str]]:
    """Every string in the pack that a human would read.

    A credential does not only hide in a claim's text. It hides in a source's
    title, in a free-form properties blob, in the link a claim carries. The
    secret scan therefore walks the whole pack; the personal-detail scan
    stays on the narrower list, because contact details are sometimes the
    point of a record.
    """
    for claim in pack.claims:
        yield f"claims.jsonl#{claim.id}", claim.text
        if claim.notes:
            yield f"claims.jsonl#{claim.id}", claim.notes
        for link in claim.links:
            target = link.get("target")
            if isinstance(target, str):
                yield f"claims.jsonl#{claim.id}", target
    for ev in pack.evidence:
        if ev.quote:
            yield f"evidence.jsonl#{ev.id}", ev.quote
    for entity in pack.entities:
        yield f"entities.json#{entity.id}", entity.name
        for value in entity.properties.values():
            if isinstance(value, str):
                yield f"entities.json#{entity.id}", value
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        yield f"entities.json#{entity.id}", item
    for relation in pack.relations:
        if relation.note:
            yield f"relations.json#{relation.id}", relation.note
    for contradiction in pack.contradictions:
        yield f"contradictions.json#{contradiction.id}", contradiction.description
    for source in pack.manifest.sources:
        for value in (source.title, source.path, source.url):
            if value:
                yield f"manifest.json#{source.id}", str(value)
    for value in (pack.manifest.title, pack.manifest.description):
        if value:
            yield "manifest.json", str(value)
    for value in pack.manifest.generator.values():
        if isinstance(value, str):
            yield "manifest.json", value
    if pack.readme:
        yield "README.md", pack.readme


def _narrow_texts(pack: Pack) -> Iterator[tuple[str, str]]:
    """The strings where contact details are worth reporting."""
    for claim in pack.claims:
        yield f"claims.jsonl#{claim.id}", claim.text
        if claim.notes:
            yield f"claims.jsonl#{claim.id}", claim.notes
    for ev in pack.evidence:
        if ev.quote:
            yield f"evidence.jsonl#{ev.id}", ev.quote
    for entity in pack.entities:
        yield f"entities.json#{entity.id}", entity.name
    for relation in pack.relations:
        if relation.note:
            yield f"relations.json#{relation.id}", relation.note
    for contradiction in pack.contradictions:
        yield f"contradictions.json#{contradiction.id}", contradiction.description
    if pack.readme:
        yield "README.md", pack.readme


@register("hygiene")
def check_hygiene(pack: Pack, ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    scan_pii = ctx.option("pii", True)

    for location, text in _pack_texts(pack):
        for label, pattern in SECRET_PATTERNS:
            match = pattern.search(text)
            if match:
                findings.append(
                    Finding(
                        rule="hygiene.secret",
                        severity="error",
                        message=f"possible {label} in {location}",
                        location=location,
                        hint="remove the value before sharing the pack; rotate it if it was real",
                    )
                )

    if not scan_pii:
        return findings

    for location, text in _narrow_texts(pack):
        for label, pattern in PII_PATTERNS:
            match = pattern.search(text)
            if match:
                findings.append(
                    Finding(
                        rule="hygiene.pii",
                        severity="warning",
                        message=f"possible {label} in {location}",
                        location=location,
                        hint="packs often travel between tools; contact details rarely need to travel",
                    )
                )
    return findings
