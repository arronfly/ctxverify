"""Write a pack to disk.

The writer is the other half of the loader: adapters build a :class:`Pack`
in memory and this module lays it out as the eight files of the format.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .model import FORMAT_VERSION, Pack, sha256_text


def write_pack(pack: Pack, root: str | os.PathLike[str], readme: str | None = None) -> Path:
    """Write ``pack`` to ``root``, creating the directory if needed."""
    target = Path(root).expanduser()
    target.mkdir(parents=True, exist_ok=True)

    manifest = pack.manifest.to_dict()
    manifest.setdefault("format_version", FORMAT_VERSION)
    manifest["sources"] = [source.to_dict() for source in pack.manifest.sources]
    manifest["stats"] = {
        "claims": len(pack.claims),
        "evidence": len(pack.evidence),
        "entities": len(pack.entities),
        "relations": len(pack.relations),
        "contradictions": len(pack.contradictions),
        "sources": len(pack.manifest.sources),
    }

    _write_json(target / "manifest.json", manifest)
    _write_jsonl(target / "claims.jsonl", [claim.to_dict() for claim in pack.claims])
    _write_jsonl(target / "evidence.jsonl", [ev.to_dict() for ev in pack.evidence])
    _write_json(target / "entities.json", {"entities": [e.to_dict() for e in pack.entities]})
    _write_json(target / "relations.json", {"relations": [r.to_dict() for r in pack.relations]})
    _write_json(
        target / "contradictions.json",
        {"contradictions": [c.to_dict() for c in pack.contradictions]},
    )
    freshness = {
        "policy": pack.freshness_policy or {"default_ttl_days": 180},
        "claims": {
            claim_id: {
                key: value
                for key, value in (
                    ("source_date", entry.source_date),
                    ("reviewed_at", entry.reviewed_at),
                    ("expires_at", entry.expires_at),
                    ("decay", entry.decay),
                    ("last_verified", entry.last_verified),
                )
                if value
            }
            for claim_id, entry in pack.freshness.items()
        },
    }
    _write_json(target / "freshness.json", freshness)

    readme_text = readme if readme is not None else _default_readme(pack)
    (target / "README.md").write_text(readme_text, encoding="utf-8")
    return target


def _default_readme(pack: Pack) -> str:
    title = pack.manifest.title or pack.manifest.pack_id or "Context Pack"
    lines = [
        f"# {title}",
        "",
        pack.manifest.description or "_A portable context pack. See SPEC.md for the format._",
        "",
        "## Contents",
        "",
        f"- Claims: {len(pack.claims)}",
        f"- Evidence records: {len(pack.evidence)}",
        f"- Entities: {len(pack.entities)}",
        f"- Relations: {len(pack.relations)}",
        f"- Contradictions: {len(pack.contradictions)}",
        f"- Sources: {len(pack.manifest.sources)}",
        "",
        "## Checking this pack",
        "",
        "```bash",
        "ctxv check .",
        "```",
        "",
    ]
    return "\n".join(lines)


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows) -> None:
    body = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(body, encoding="utf-8")


def evidence_record(
    evidence_id: str,
    claim_id: str,
    source_id: str,
    quote: str,
    locator: dict | None = None,
    retrieved_at: str | None = None,
) -> dict:
    """Build an evidence record with its quote hash already computed."""
    return {
        "id": evidence_id,
        "claim_id": claim_id,
        "source_id": source_id,
        "quote": quote,
        "locator": locator or {},
        "quote_sha256": sha256_text(quote),
        "retrieved_at": retrieved_at,
    }
