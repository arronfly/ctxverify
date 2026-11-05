"""Export a plain markdown directory into a context pack.

Not every knowledge base is an Obsidian vault. Karpathy's LLM Wiki pattern
— a directory of markdown pages compiled from raw sources — has no
frontmatter, no aliases and no wikilinks by convention, and a tool that only
reads Obsidian vaults would not touch it.

This adapter reads any directory of markdown files: frontmatter if it is
there, the first heading and first paragraph if it is not. It is the
lowest-common-denominator adapter, and it is the one to start from when
writing an adapter for your own corpus.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from ..frontmatter import as_list, as_text, parse_frontmatter, split_frontmatter
from ..model import CLAIM_STATUSES, Claim, Entity, Evidence, Manifest, Pack, Source
from ..resolve import LinkIndex, strip_wikilink
from ..writer import evidence_record

SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules", ".venv", "__pycache__", "dist", "build"}

HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
WIKILINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")
CODE_FENCE_RE = re.compile(r"```.*?```")


def _iter_markdown(root: Path):
    for path in sorted(root.rglob("*.md")):
        parts = set(path.relative_to(root).parts[:-1])
        if parts & SKIP_DIRS:
            continue
        if any(part.startswith(".") for part in parts):
            continue
        yield path


def _first_heading(body: str) -> str:
    match = HEADING_RE.search(body)
    return match.group(1).strip() if match else ""


def _first_paragraph(body: str) -> str:
    text = CODE_FENCE_RE.sub("", body)
    for block in re.split(r"\n\s*\n", text):
        stripped = block.strip()
        if not stripped or stripped.startswith(("#", "```", "|", "-", "*", ">", "<!--")):
            continue
        return re.sub(r"\s+", " ", stripped)[:600]
    return ""


def export_markdown(
    corpus: str | Path,
    pack_id: str | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> Pack:
    """Read a markdown corpus and return a :class:`Pack`."""
    root = Path(corpus).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"corpus not found: {root}")

    include = include or []
    exclude = exclude or []

    pages: list[tuple[Path, str]] = []
    for path in _iter_markdown(root):
        rel = path.relative_to(root).as_posix()
        if include and not any(pattern in rel for pattern in include):
            continue
        if exclude and any(pattern in rel for pattern in exclude):
            continue
        pages.append((path, rel))

    index = LinkIndex(paths=[rel for _, rel in pages])

    claims: list[Claim] = []
    evidence: list[Evidence] = []
    entities: list[Entity] = []
    sources: list[Source] = []
    entity_ids: dict[str, str] = {}

    for number, (path, rel) in enumerate(pages, start=1):
        text = path.read_text(encoding="utf-8", errors="replace")
        front = parse_frontmatter(text)
        _, body = split_frontmatter(text)

        source_id = f"src-{number:03d}"
        claim_id = f"clm-{number:03d}"
        evidence_id = f"ev-{number:03d}"

        title = as_text(front.get("title")).strip() or _first_heading(body) or path.stem
        summary = (
            as_text(front.get("summary")).strip()
            or as_text(front.get("description")).strip()
            or _first_paragraph(body)
            or title
        )

        raw_status = as_text(front.get("status")).strip().lower()
        status = raw_status if raw_status in CLAIM_STATUSES else "asserted"

        confidence = front.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            confidence = None

        topics = as_list(front.get("topics")) or as_list(front.get("tags"))

        links = []
        for raw in WIKILINK_RE.findall(body):
            target = strip_wikilink(raw)
            if not target:
                continue
            links.append({"target": raw, "resolved": index.resolve(raw)})

        claim_entities: list[str] = []
        for name in as_list(front.get("entities")):
            key = name.strip().lower()
            if not key:
                continue
            if key not in entity_ids:
                entity_id = f"ent-{len(entity_ids) + 1:03d}"
                entity_ids[key] = entity_id
                entities.append(Entity(id=entity_id, name=name.strip()))
            claim_entities.append(entity_ids[key])

        claims.append(
            Claim(
                id=claim_id,
                text=summary,
                status=status,
                confidence=float(confidence) if confidence is not None else None,
                evidence=[evidence_id],
                entities=claim_entities,
                topics=topics,
                links=links,
                created_at=as_text(front.get("created")).strip() or None,
                updated_at=as_text(front.get("updated")).strip() or None,
            )
        )

        record = evidence_record(
            evidence_id,
            claim_id,
            source_id,
            summary,
            locator={"path": rel, "line_start": 1, "line_end": 1},
            retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        evidence.append(Evidence.from_dict(record))

        sources.append(
            Source(
                id=source_id,
                path=rel,
                title=title,
                kind="markdown",
                sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                modified_at=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(
                    timespec="seconds"
                ),
            )
        )

    manifest = Manifest(
        pack_id=pack_id or root.name,
        title=f"{root.name} (markdown export)",
        description=f"Context pack exported from the markdown corpus at {root}.",
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        generator={"name": "ctxverify-adapter-markdown", "version": "0.1.0"},
        sources=sources,
    )

    return Pack(
        root=str(root),
        manifest=manifest,
        claims=claims,
        evidence=evidence,
        entities=entities,
        relations=[],
        contradictions=[],
        freshness={},
        freshness_policy={"default_ttl_days": 180},
    )
