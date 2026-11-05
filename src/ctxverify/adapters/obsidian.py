"""Export an Obsidian-style vault into a context pack.

The mapping is intentionally flat: one note becomes one claim, with the note
itself as the evidence. That is not as rich as a compiled pack, but it is
honest, and it means a vault can be checked on day one instead of after a
compiler is written.

What the adapter does preserve is the part that is expensive to get right:
the link structure of the vault, resolved the way Obsidian resolves it.
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

SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules", ".venv", "__pycache__"}

HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
WIKILINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")
CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
#: A note id that looks like a card number: "C-001", "P-012".
NUMBER_LIKE = re.compile(r"^[A-Za-z]{1,6}-\d{1,6}$")


def _iter_notes(vault: Path):
    for path in sorted(vault.rglob("*.md")):
        parts = set(path.relative_to(vault).parts[:-1])
        if parts & SKIP_DIRS:
            continue
        if any(part.startswith(".") for part in parts):
            continue
        yield path


def _slug(path: Path) -> str:
    stem = path.stem
    cleaned = re.sub(r"[^\w\-一-鿿]+", "-", stem).strip("-")
    return cleaned or "note"


def _first_paragraph(body: str) -> str:
    text = CODE_FENCE_RE.sub("", body)
    for block in re.split(r"\n\s*\n", text):
        stripped = block.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            heading = HEADING_RE.search(stripped)
            if heading:
                return heading.group(1).strip()
            continue
        if stripped.startswith(("```", "|", "-", "*", ">", "<!--")):
            continue
        return re.sub(r"\s+", " ", stripped)[:600]
    return ""


def export_obsidian(
    vault: str | Path,
    pack_id: str | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> Pack:
    """Read ``vault`` and return a :class:`Pack`."""
    root = Path(vault).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"vault not found: {root}")

    include = include or []
    exclude = exclude or []

    notes = []
    for path in _iter_notes(root):
        rel = path.relative_to(root).as_posix()
        if include and not any(pattern in rel for pattern in include):
            continue
        if exclude and any(pattern in rel for pattern in exclude):
            continue
        notes.append((path, rel))

    # Obsidian resolves a link to a note's alias as well as to its filename.
    # Reading them is the difference between reporting a real broken link and
    # reporting 1,254 false ones.
    aliases: dict[str, str] = {}
    note_frontmatter: dict[str, dict] = {}
    for path, rel in notes:
        text = path.read_text(encoding="utf-8", errors="replace")
        front = parse_frontmatter(text)
        note_frontmatter[rel] = front
        for alias in as_list(front.get("aliases")) + as_list(front.get("alias")):
            alias = alias.strip()
            if alias:
                aliases.setdefault(alias, rel)
                aliases.setdefault(alias.lower(), rel)

    index = LinkIndex(paths=[rel for _, rel in notes], aliases=aliases)

    claims: list[Claim] = []
    evidence: list[Evidence] = []
    entities: list[Entity] = []
    sources: list[Source] = []
    entity_ids: dict[str, str] = {}

    for number, (path, rel) in enumerate(notes, start=1):
        text = path.read_text(encoding="utf-8", errors="replace")
        front = note_frontmatter.get(rel) or parse_frontmatter(text)
        _, body = split_frontmatter(text)

        source_id = f"src-{number:03d}"
        claim_id = f"clm-{number:03d}"
        evidence_id = f"ev-{number:03d}"

        title = as_text(front.get("title")).strip() or path.stem
        summary = (
            as_text(front.get("summary")).strip()
            or as_text(front.get("description")).strip()
            or as_text(front.get("abstract")).strip()
            or _first_paragraph(body)
        )

        raw_status = as_text(front.get("status")).strip().lower()
        status = raw_status if raw_status in CLAIM_STATUSES else "asserted"

        confidence = front.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            confidence = None

        topics = as_list(front.get("topics")) or as_list(front.get("domain")) or as_list(
            front.get("tags")
        )

        links = []
        for raw in WIKILINK_RE.findall(body):
            target = strip_wikilink(raw)
            if not target:
                continue
            resolved = index.resolve(raw)
            links.append({"target": raw, "resolved": resolved})

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

        created = (
            as_text(front.get("created")).strip()
            or as_text(front.get("createdAt")).strip()
            or as_text(front.get("date")).strip()
            or None
        )
        updated = (
            as_text(front.get("updated")).strip()
            or as_text(front.get("updatedAt")).strip()
            or as_text(front.get("modified")).strip()
            or None
        )

        claims.append(
            Claim(
                id=claim_id,
                text=summary or title,
                status=status,
                confidence=float(confidence) if confidence is not None else None,
                evidence=[evidence_id],
                entities=claim_entities,
                topics=topics,
                links=links,
                created_at=created,
                updated_at=updated,
            )
        )

        quote = summary or title
        record = evidence_record(
            evidence_id,
            claim_id,
            source_id,
            quote,
            locator={"path": rel, "line_start": 1, "line_end": 1},
            retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        evidence.append(Evidence.from_dict(record))

        # A corpus that keeps several numbering spaces side by side declares
        # them: a source in namespace "billing" may carry C-001 without
        # colliding with the global C-001.
        extra: dict = {}
        aliases = as_list(front.get("aliases"))
        if aliases:
            extra["aliases"] = aliases
        namespace = as_text(front.get("namespace")).strip() or as_text(
            front.get("编号空间")
        ).strip()
        if namespace:
            extra["namespace"] = namespace
        # A note's own number. It is kept under a distinct key so that it can
        # never be mistaken for the pack's source id.
        number = as_text(front.get("number")).strip() or as_text(front.get("编号")).strip()
        if not number:
            note_id = as_text(front.get("id")).strip()
            if note_id and NUMBER_LIKE.match(note_id):
                number = note_id
        if number:
            extra["number"] = number

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
                extra=extra,
            )
        )

    manifest = Manifest(
        pack_id=pack_id or root.name,
        title=f"{root.name} (Obsidian export)",
        description=f"Context pack exported from the Obsidian vault at {root}.",
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        generator={"name": "ctxverify-adapter-obsidian", "version": "0.1.0"},
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
