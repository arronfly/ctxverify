"""Verify that the actions an agent reported actually happened.

This is the check no knowledge tool performs, and it comes from a real
incident: eight agents each reported "已归档" (archived) for the same files,
and not one of them had moved anything. The report was the only thing that
was wrong — the filesystem was the truth, and nobody looked.

An action record looks like this::

    {"id": "a-1", "action": "archived", "path": "notes/C-001.md"}
    {"id": "a-2", "action": "moved", "path": "new/C-001.md", "from": "old/C-001.md"}
    {"id": "a-3", "action": "wrote", "path": "out.md", "sha256": "..."}
    {"id": "a-4", "action": "archived", "paths": ["a.md", "b.md"], "count": 2}

The verifier reads the filesystem and says which claims are false.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from ..model import Pack, sha256_bytes
from ..report import Finding
from . import CheckContext, register

ACTIONS = ("archived", "moved", "deleted", "wrote", "exists")


def load_actions(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSONL file of action records."""
    records: list[dict[str, Any]] = []
    text = Path(path).read_text(encoding="utf-8")
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number} is not valid JSON: {exc}") from exc
        if isinstance(row, dict):
            row.setdefault("id", f"line-{number}")
            records.append(row)
    return records


def verify_actions(records: Iterable[dict[str, Any]], root: str | Path) -> list[Finding]:
    """Check every action record against the filesystem under ``root``."""
    base = Path(root).expanduser().resolve()
    findings: list[Finding] = []

    for record in records:
        action = str(record.get("action", "")).strip()
        action_id = str(record.get("id", "?"))
        location = f"actions.jsonl#{action_id}"

        if action not in ACTIONS:
            findings.append(
                Finding(
                    rule="action.unverified",
                    severity="error",
                    message=f"action {action_id} has unknown action {action!r}",
                    location=location,
                    hint=f"expected one of {', '.join(ACTIONS)}",
                )
            )
            continue

        paths = record.get("paths")
        if paths is None:
            single = record.get("path")
            paths = [single] if single else []
        if not paths:
            findings.append(
                Finding(
                    rule="action.unverified",
                    severity="error",
                    message=f"action {action_id} names no path to check",
                    location=location,
                )
            )
            continue

        declared_count = record.get("count")
        if declared_count is not None and int(declared_count) != len(paths):
            findings.append(
                Finding(
                    rule="action.unverified",
                    severity="error",
                    message=(
                        f"action {action_id} claims {declared_count} file(s) "
                        f"but lists {len(paths)}"
                    ),
                    location=location,
                    hint="the count and the list must agree before anyone believes the report",
                )
            )

        for raw in paths:
            target = base / str(raw)
            label = str(raw)
            if action in ("archived", "exists", "wrote"):
                if not target.exists():
                    findings.append(
                        Finding(
                            rule="action.unverified",
                            severity="error",
                            message=f"action {action_id} reports {label!r} as {action}, but it does not exist",
                            location=location,
                        )
                    )
            elif action == "deleted":
                if target.exists():
                    findings.append(
                        Finding(
                            rule="action.unverified",
                            severity="error",
                            message=f"action {action_id} reports {label!r} as deleted, but it still exists",
                            location=location,
                        )
                    )
            elif action == "moved":
                origin = record.get("from")
                if not target.exists():
                    findings.append(
                        Finding(
                            rule="action.unverified",
                            severity="error",
                            message=f"action {action_id} reports {label!r} as moved, but the new path is missing",
                            location=location,
                        )
                    )
                if origin and (base / str(origin)).exists():
                    findings.append(
                        Finding(
                            rule="action.unverified",
                            severity="error",
                            message=(
                                f"action {action_id} reports {label!r} as moved, "
                                f"but {str(origin)!r} still exists"
                            ),
                            location=location,
                        )
                    )

            expected_hash = record.get("sha256")
            if expected_hash and target.exists() and target.is_file():
                actual = sha256_bytes(target.read_bytes())
                if actual != expected_hash:
                    findings.append(
                        Finding(
                            rule="action.unverified",
                            severity="error",
                            message=(
                                f"action {action_id} reports content hash "
                                f"{str(expected_hash)[:12]}… for {label!r}, actual {actual[:12]}…"
                            ),
                            location=location,
                        )
                    )
    return findings


@register("actions")
def check_actions(pack: Pack, ctx: CheckContext) -> list[Finding]:
    """Run the action verifier when the caller supplied an actions file."""
    actions_file = ctx.option("actions_file")
    if not actions_file:
        return []
    root = ctx.option("actions_root") or pack.root
    try:
        records = load_actions(actions_file)
    except (OSError, ValueError) as exc:
        return [
            Finding(
                rule="action.unverified",
                severity="error",
                message=f"actions file could not be read: {exc}",
                location=str(actions_file),
            )
        ]
    return verify_actions(records, root)


def hash_file(path: str | Path) -> str:
    """sha256 of a file, hex."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
