"""Export an llmwiki project into a context pack.

llmwiki (https://github.com/atomicstrata/llm-wiki-compiler) compiles raw
sources into a markdown wiki with citation markers such as
``^[source.md:42-58]`` and ``[[wikilinks]]`` between concept pages.

This adapter reads that wiki as it stands. It does not import, does not
refresh, does not ask for API keys and does not need an LLM: it turns the
existing artifact into a pack so that any linter — this one included — can
judge it on the same terms as every other compiler's output.

The result is deliberately conservative. A page whose citation markers point
at a file that is not in ``sources/`` still produces an evidence record: the
claim is reported as uncited rather than the citation being quietly dropped,
because a missing citation and a silently dropped one look the same to a
reader and mean different things to whoever owns the pack.
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

CITATION_RE = re.compile(r"\^\[([^\]]+)\]")
WIKILINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")
LINE_RANGE_RE = re.compile(r"^(?P<file>[^:]+):(?P<start>\d+)(?:-(?P<end>\d+))?$")

WIKI_DIRS = ("wiki/concepts", "wiki/queries", "wiki")


def _iter_pages(root: Path):
    seen: set[Path] = set()
    for sub in WIKI_DIRS:
        directory = root / sub
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.md")):
            if path in seen:
                continue
            seen.add(path)
            yield path


def _paragraphs(body: str) -> list[str]:
    chunks = re.split(r"\n\s*\n", body)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def export_llmwiki(project: str | Path) -> Pack:
    """Read an llmwiki project and return a :class:`Pack`."""
    root = Path(project).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"llmwiki project not found: {root}")

    pages = list(_iter_pages(root))
    page_paths = [path.relative_to(root).as_posix() for path in pages]
    index = LinkIndex(paths=page_paths)

    claims: list[Claim] = []
    evidence: list[Evidence] = []
    entities: list[Entity] = []
    sources: list[Source] = []
    source_ids: dict[str, str] = {}
    entity_ids: dict[str, str] = {}
    evidence_counter = 0

    def source_id_for(filename: str) -> str:
        key = filename.strip()
        if key not in source_ids:
            source_ids[key] = f"src-{len(source_ids) + 1:03d}"
            sources.append(
                Source(
                    id=source_ids[key],
                    path=f"sources/{key}",
                    title=key,
                    kind="file",
                    sha256=None,
                )
            )
        return source_ids[key]

    for number, path in enumerate(pages, start=1):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        front = parse_frontmatter(text)
        _, body = split_frontmatter(text)

        claim_id = f"clm-{number:03d}"
        title = as_text(front.get("title")).strip() or path.stem
        summary = as_text(front.get("summary")).strip()

        confidence = front.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            confidence = None

        raw_status = as_text(front.get("status")).strip().lower()
        status = raw_status if raw_status in CLAIM_STATUSES else "asserted"

        declared_sources = as_list(front.get("sources"))
        evidence_ids: list[str] = []

        for paragraph in _paragraphs(body):
            citations = CITATION_RE.findall(paragraph)
            if not citations:
                continue
            quote = CITATION_RE.sub("", paragraph).strip()
            quote = re.sub(r"\s+", " ", quote)[:1200]
            for citation in citations:
                match = LINE_RANGE_RE.match(citation.strip())
                filename = match.group("file") if match else citation.strip()
                line_start = int(match.group("start")) if match else None
                line_end = int(match.group("end")) if match and match.group("end") else line_start
                locator = {"path": f"sources/{filename.strip()}"}
                if line_start is not None:
                    locator["line_start"] = line_start
                    locator["line_end"] = line_end or line_start
                evidence_counter += 1
                evidence_id = f"ev-{evidence_counter:03d}"
                record = evidence_record(
                    evidence_id,
                    claim_id,
                    source_id_for(filename),
                    quote or title,
                    locator=locator,
                    retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                )
                evidence.append(Evidence.from_dict(record))
                evidence_ids.append(evidence_id)

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

        topics = as_list(front.get("topics")) or ([as_text(front.get("kind")).strip()] if front.get("kind") else [])

        claims.append(
            Claim(
                id=claim_id,
                text=summary or title,
                status=status,
                confidence=float(confidence) if confidence is not None else None,
                evidence=evidence_ids,
                entities=claim_entities,
                topics=topics,
                links=links,
                created_at=as_text(front.get("createdAt")).strip() or None,
                updated_at=as_text(front.get("updatedAt")).strip() or None,
            )
        )

        for filename in declared_sources:
            source_id_for(filename)

    manifest = Manifest(
        pack_id=root.name,
        title=f"{root.name} (llmwiki export)",
        description=f"Context pack exported from the llmwiki project at {root}.",
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        generator={"name": "ctxverify-adapter-llmwiki", "version": "0.1.0"},
        sources=sources,
    )

    for source in sources:
        candidate = root / source.path
        if candidate.exists():
            source.sha256 = hashlib.sha256(candidate.read_bytes()).hexdigest()

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
