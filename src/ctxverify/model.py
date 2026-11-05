"""Data model for the Context Pack Format (CPF).

The format is specified in SPEC.md. This module holds the normative constants
and the dataclasses that represent each file of a pack.

Design rules that the rest of the code depends on:

* Every identifier is a string. Prefixes are conventional, not enforced:
  ``clm-`` claims, ``ev-`` evidence, ``ent-`` entities, ``rel-`` relations,
  ``con-`` contradictions, ``src-`` sources.
* Unknown keys are preserved, never rejected. A pack written by a newer
  compiler must still be checkable by an older linter; that is the whole point
  of a versioned format.
* Nothing here reads the filesystem. Loading is the job of :mod:`ctxverify.loader`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

#: Version of the Context Pack Format implemented by this module.
FORMAT_VERSION = "0.1"

#: Format versions this build of ctxverify can check.
SUPPORTED_FORMAT_VERSIONS = frozenset({"0.1"})

#: The eight files that make up a pack.
REQUIRED_FILES = (
    "manifest.json",
    "claims.jsonl",
    "evidence.jsonl",
    "entities.json",
    "relations.json",
    "contradictions.json",
    "freshness.json",
    "README.md",
)

#: Files a pack may contain in addition to the required eight. A checker
#: ignores files it does not recognise.
OPTIONAL_FILES = ("verification.json", "LICENSE", "LICENSE-SPEC", "NOTICE")

#: Epistemic status of a claim, ordered from weakest to strongest evidence.
CLAIM_STATUSES = ("asserted", "verified", "inferred", "disputed", "refuted")

#: Statuses that must be backed by at least one evidence record.
STATUSES_REQUIRING_EVIDENCE = ("verified",)

#: Statuses that are legal without evidence but produce a warning.
STATUSES_ADVISING_EVIDENCE = ("asserted",)

#: Statuses that must be referenced by a contradiction entry.
STATUSES_REQUIRING_CONTRADICTION = ("disputed", "refuted")

#: Statuses that must carry a written rationale in ``notes``.
STATUSES_REQUIRING_NOTES = ("inferred",)


def sha256_text(text: str) -> str:
    """Return the lowercase hex sha256 of ``text`` encoded as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Return the lowercase hex sha256 of ``data``."""
    return hashlib.sha256(data).hexdigest()


def as_dict(value: Any) -> dict[str, Any]:
    """Coerce a value to a dictionary. A wrong type becomes an empty dict.

    A pack is written by other tools. A field that should be an object and
    is a string is a defect in the pack, not a reason to crash the checker.
    """
    return dict(value) if isinstance(value, dict) else {}


def as_dict_list(value: Any) -> list[Any]:
    """Coerce a value to a list. A wrong type becomes an empty list."""
    return list(value) if isinstance(value, list) else []


def as_str_list(value: Any) -> list[str]:
    """Coerce a value to a list of strings.

    A string where a list belongs is a pack defect; expanding it into its
    characters would turn one mistake into a shower of confusing findings.
    """
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [str(value)]
    return []


@dataclass
class Source:
    """A file, URL or document that claims were compiled from."""

    id: str
    path: str
    title: str | None = None
    kind: str = "file"
    sha256: str | None = None
    url: str | None = None
    modified_at: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Source":
        known = {"id", "path", "title", "kind", "sha256", "url", "modified_at"}
        return cls(
            id=str(data.get("id", "")),
            path=str(data.get("path", "") if isinstance(data.get("path"), str) else ""),
            title=data.get("title"),
            kind=str(data.get("kind", "file")),
            sha256=data.get("sha256"),
            url=data.get("url"),
            modified_at=data.get("modified_at"),
            extra={k: v for k, v in data.items() if k not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        out = {
            "id": self.id,
            "path": self.path,
            "kind": self.kind,
        }
        if self.title:
            out["title"] = self.title
        if self.sha256:
            out["sha256"] = self.sha256
        if self.url:
            out["url"] = self.url
        if self.modified_at:
            out["modified_at"] = self.modified_at
        # Extra keys are appended, never allowed to overwrite a core field.
        for key, value in self.extra.items():
            if key not in out:
                out[key] = value
        return out


@dataclass
class Evidence:
    """A pointer from a claim back to a concrete location in a source."""

    id: str
    claim_id: str
    source_id: str
    quote: str = ""
    locator: dict[str, Any] = field(default_factory=dict)
    quote_sha256: str | None = None
    retrieved_at: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Evidence":
        known = {
            "id",
            "claim_id",
            "source_id",
            "quote",
            "locator",
            "quote_sha256",
            "retrieved_at",
        }
        return cls(
            id=str(data.get("id", "")),
            claim_id=str(data.get("claim_id", "")),
            source_id=str(data.get("source_id", "")),
            quote=str(data.get("quote", "") or ""),
            locator=as_dict(data.get("locator")),
            quote_sha256=data.get("quote_sha256"),
            retrieved_at=data.get("retrieved_at"),
            extra={k: v for k, v in data.items() if k not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "claim_id": self.claim_id,
            "source_id": self.source_id,
            "quote": self.quote,
        }
        if self.locator:
            out["locator"] = self.locator
        if self.quote_sha256:
            out["quote_sha256"] = self.quote_sha256
        if self.retrieved_at:
            out["retrieved_at"] = self.retrieved_at
        for key, value in self.extra.items():
            if key not in out:
                out[key] = value
        return out


@dataclass
class Claim:
    """One atomic assertion, with its epistemic status and its evidence."""

    id: str
    text: str = ""
    status: str = "asserted"
    confidence: float | None = None
    evidence: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    links: list[dict[str, Any]] = field(default_factory=list)
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Claim":
        known = {
            "id",
            "text",
            "status",
            "confidence",
            "evidence",
            "entities",
            "topics",
            "links",
            "notes",
            "created_at",
            "updated_at",
        }
        links = data.get("links") or []
        normalised_links = []
        for link in links:
            if isinstance(link, str):
                normalised_links.append({"target": link, "resolved": None})
            elif isinstance(link, dict):
                normalised_links.append(dict(link))
        return cls(
            id=str(data.get("id", "")),
            text=str(data.get("text", "") or ""),
            status=str(data.get("status", "asserted") or "asserted"),
            confidence=_maybe_float(data.get("confidence")),
            evidence=as_str_list(data.get("evidence")),
            entities=as_str_list(data.get("entities")),
            topics=as_str_list(data.get("topics")),
            links=normalised_links,
            notes=data.get("notes"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            extra={k: v for k, v in data.items() if k not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "text": self.text, "status": self.status}
        if self.confidence is not None:
            out["confidence"] = self.confidence
        if self.evidence:
            out["evidence"] = list(self.evidence)
        if self.entities:
            out["entities"] = list(self.entities)
        if self.topics:
            out["topics"] = list(self.topics)
        if self.links:
            out["links"] = list(self.links)
        if self.notes:
            out["notes"] = self.notes
        if self.created_at:
            out["created_at"] = self.created_at
        if self.updated_at:
            out["updated_at"] = self.updated_at
        for key, value in self.extra.items():
            if key not in out:
                out[key] = value
        return out


@dataclass
class Entity:
    """A named thing a claim is about, with the aliases it is written under."""

    id: str
    name: str = ""
    type: str | None = None
    aliases: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Entity":
        known = {"id", "name", "type", "aliases", "properties"}
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "") or ""),
            type=data.get("type"),
            aliases=as_str_list(data.get("aliases")),
            properties=as_dict(data.get("properties")),
            extra={k: v for k, v in data.items() if k not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "name": self.name}
        if self.type:
            out["type"] = self.type
        if self.aliases:
            out["aliases"] = list(self.aliases)
        if self.properties:
            out["properties"] = self.properties
        for key, value in self.extra.items():
            if key not in out:
                out[key] = value
        return out


@dataclass
class Relation:
    """A typed edge between two entities."""

    id: str
    from_id: str
    to_id: str
    type: str = "related_to"
    evidence: list[str] = field(default_factory=list)
    claim_id: str | None = None
    note: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Relation":
        known = {"id", "from", "to", "from_id", "to_id", "type", "evidence", "claim_id", "note"}
        return cls(
            id=str(data.get("id", "")),
            from_id=str(data.get("from", data.get("from_id", ""))),
            to_id=str(data.get("to", data.get("to_id", ""))),
            type=str(data.get("type", "") or ""),
            evidence=as_str_list(data.get("evidence")),
            claim_id=data.get("claim_id"),
            note=data.get("note"),
            extra={k: v for k, v in data.items() if k not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "from": self.from_id,
            "to": self.to_id,
            "type": self.type,
        }
        if self.evidence:
            out["evidence"] = list(self.evidence)
        if self.claim_id:
            out["claim_id"] = self.claim_id
        if self.note:
            out["note"] = self.note
        for key, value in self.extra.items():
            if key not in out:
                out[key] = value
        return out


@dataclass
class Contradiction:
    """Two claims that cannot both be true, with their supporting evidence."""

    id: str
    claims: list[str] = field(default_factory=list)
    description: str = ""
    status: str = "open"
    resolution: str | None = None
    detected_at: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Contradiction":
        known = {"id", "claims", "description", "status", "resolution", "detected_at"}
        return cls(
            id=str(data.get("id", "")),
            claims=as_str_list(data.get("claims")),
            description=str(data.get("description", "") or ""),
            status=str(data.get("status", "open") or "open"),
            resolution=data.get("resolution"),
            detected_at=data.get("detected_at"),
            extra={k: v for k, v in data.items() if k not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "claims": list(self.claims),
            "description": self.description,
            "status": self.status,
        }
        if self.resolution:
            out["resolution"] = self.resolution
        if self.detected_at:
            out["detected_at"] = self.detected_at
        for key, value in self.extra.items():
            if key not in out:
                out[key] = value
        return out


@dataclass
class FreshnessEntry:
    """The review state of a single claim."""

    claim_id: str
    source_date: str | None = None
    reviewed_at: str | None = None
    expires_at: str | None = None
    decay: str | None = None
    last_verified: str | None = None

    @classmethod
    def from_dict(cls, claim_id: str, data: dict[str, Any]) -> "FreshnessEntry":
        return cls(
            claim_id=claim_id,
            source_date=data.get("source_date"),
            reviewed_at=data.get("reviewed_at"),
            expires_at=data.get("expires_at"),
            decay=data.get("decay"),
            last_verified=data.get("last_verified"),
        )


@dataclass
class Manifest:
    """The pack's front door: identity, provenance and inventory."""

    format_version: str = FORMAT_VERSION
    pack_id: str = ""
    title: str | None = None
    description: str | None = None
    generated_at: str | None = None
    generator: dict[str, Any] = field(default_factory=dict)
    sources: list[Source] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    verification: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Manifest":
        known = {
            "format_version",
            "pack_id",
            "title",
            "description",
            "generated_at",
            "generator",
            "sources",
            "stats",
            "verification",
        }
        return cls(
            format_version=str(data.get("format_version", FORMAT_VERSION) or FORMAT_VERSION),
            pack_id=str(data.get("pack_id", "") or ""),
            title=data.get("title"),
            description=data.get("description"),
            generated_at=data.get("generated_at"),
            generator=as_dict(data.get("generator")),
            sources=[Source.from_dict(s) for s in as_dict_list(data.get("sources")) if isinstance(s, dict)],
            stats=as_dict(data.get("stats")),
            verification=as_dict(data.get("verification")),
            extra={k: v for k, v in data.items() if k not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "format_version": self.format_version,
            "pack_id": self.pack_id,
        }
        if self.title:
            out["title"] = self.title
        if self.description:
            out["description"] = self.description
        if self.generated_at:
            out["generated_at"] = self.generated_at
        if self.generator:
            out["generator"] = self.generator
        out["sources"] = [s.to_dict() for s in self.sources]
        if self.stats:
            out["stats"] = self.stats
        if self.verification:
            out["verification"] = self.verification
        for key, value in self.extra.items():
            if key not in out:
                out[key] = value
        return out


@dataclass
class Pack:
    """A loaded context pack."""

    root: str
    manifest: Manifest
    claims: list[Claim] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
    freshness: dict[str, FreshnessEntry] = field(default_factory=dict)
    freshness_policy: dict[str, Any] = field(default_factory=dict)
    readme: str = ""
    errors: list[str] = field(default_factory=list)

    # -- convenience lookups -------------------------------------------------
    def claims_by_id(self) -> dict[str, Claim]:
        return {c.id: c for c in self.claims}

    def evidence_by_id(self) -> dict[str, Evidence]:
        return {e.id: e for e in self.evidence}

    def sources_by_id(self) -> dict[str, Source]:
        return {s.id: s for s in self.manifest.sources}

    def entities_by_id(self) -> dict[str, Entity]:
        return {e.id: e for e in self.entities}


def _maybe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None
