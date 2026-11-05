"""Scaffold a conforming, empty pack."""

from __future__ import annotations

from pathlib import Path

from .model import (
    FORMAT_VERSION,
    Claim,
    Entity,
    Evidence,
    Manifest,
    Pack,
    Relation,
)
from .writer import write_pack

EXAMPLE_CLAIM = "The Context Pack Format is versioned, and readers ignore unknown fields."
EXAMPLE_QUOTE = (
    "Unknown keys are preserved, never rejected. A pack written by a newer compiler "
    "must still be checkable by an older linter."
)


def scaffold_pack(directory: str | Path, pack_id: str = "my-pack", title: str | None = None) -> Pack:
    """Write a minimal pack that passes ``ctxv check``."""
    target = Path(directory).expanduser()
    target.mkdir(parents=True, exist_ok=True)

    source = {
        "id": "src-001",
        "path": "sources/example.md",
        "title": "Example source",
        "kind": "file",
        "sha256": None,
    }
    manifest = Manifest(
        format_version=FORMAT_VERSION,
        pack_id=pack_id,
        title=title or "My Context Pack",
        description="A context pack. Check it with `ctxv check`.",
        generator={"name": "ctxverify", "version": "0.1.0"},
        sources=[],
    )
    manifest.sources = []
    from .model import Source

    manifest.sources = [Source.from_dict(source)]

    claim = Claim(
        id="clm-001",
        text=EXAMPLE_CLAIM,
        status="verified",
        confidence=1.0,
        evidence=["ev-001"],
        entities=["ent-001"],
        topics=["example"],
    )
    evidence = Evidence(
        id="ev-001",
        claim_id="clm-001",
        source_id="src-001",
        quote=EXAMPLE_QUOTE,
        locator={"path": "sources/example.md", "line_start": 1, "line_end": 1},
        quote_sha256=None,
    )
    from .model import sha256_text

    evidence.quote_sha256 = sha256_text(EXAMPLE_QUOTE)

    entity = Entity(id="ent-001", name="Context Pack Format", type="concept")

    pack = Pack(
        root=str(target),
        manifest=manifest,
        claims=[claim],
        evidence=[evidence],
        entities=[entity],
        relations=[],
        contradictions=[],
        freshness={},
        freshness_policy={"default_ttl_days": 180},
    )
    write_pack(pack, target)
    return pack
