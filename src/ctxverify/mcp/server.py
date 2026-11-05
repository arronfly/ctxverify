"""A minimal MCP server over stdio.

MCP over stdio is newline-delimited JSON-RPC 2.0. This implementation covers
what an agent actually needs from a linter: ``initialize``, ``tools/list`` and
``tools/call``. It has no dependencies, which matters because the whole point
of this tool is to be installed next to an agent without a second package
manager in the loop.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from ..checks import run_checks
from ..checks.actions import load_actions, verify_actions
from ..loader import PackLoadError, load_pack
from ..version import __version__

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "ctxverify", "version": __version__}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "check_pack",
        "description": (
            "Check a context pack for broken provenance, dangling references, duplicate ids, "
            "numbering collisions, unresolved contradictions, stale claims and leaked "
            "credentials. Returns findings with severities and an exit-code style verdict."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Pack directory. Defaults to the server root."},
                "strict": {"type": "boolean", "description": "Treat warnings as failures."},
                "min_severity": {
                    "type": "string",
                    "enum": ["error", "warning", "info"],
                    "description": "Only report findings at or above this severity.",
                },
                "exclude_rules": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Rule ids to skip.",
                },
            },
        },
    },
    {
        "name": "list_claims",
        "description": "List the claims in a pack with their status, confidence and evidence count.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "status": {"type": "string", "description": "Filter by claim status."},
                "topic": {"type": "string", "description": "Filter by topic."},
                "limit": {"type": "integer", "description": "Maximum number of claims to return."},
            },
        },
    },
    {
        "name": "get_claim",
        "description": "Return one claim with its evidence records and their source locations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "claim_id": {"type": "string"},
            },
            "required": ["claim_id"],
        },
    },
    {
        "name": "verify_actions",
        "description": (
            "Verify that actions an agent reported actually happened. Each record needs an "
            "action (archived, moved, deleted, wrote, exists) and a path relative to root. "
            "This is the check that catches a report of work that was never done."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Action records, e.g. {\"action\": \"archived\", \"path\": \"a.md\"}.",
                },
                "root": {"type": "string", "description": "Directory the paths are relative to."},
            },
            "required": ["actions"],
        },
    },
]


def serve(default_root: str | None = None) -> None:
    """Run the server until stdin closes."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle(message, default_root)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


def handle(message: dict[str, Any], default_root: str | None) -> dict[str, Any] | None:
    method = message.get("method")
    message_id = message.get("id")
    params = message.get("params") or {}

    if method is None:
        return None
    if method.startswith("notifications/"):
        return None

    if method == "initialize":
        return _ok(
            message_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": (
                    "Check a context pack after writing it. Use check_pack on the pack you "
                    "just produced; fix what it reports before you report the work as done."
                ),
            },
        )

    if method == "ping":
        return _ok(message_id, {})

    if method == "tools/list":
        return _ok(message_id, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            payload = call_tool(name, arguments, default_root)
        except Exception as exc:  # tool errors are reported, not crashed
            return _ok(
                message_id,
                {
                    "isError": True,
                    "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
                },
            )
        return _ok(
            message_id,
            {
                "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
                "isError": False,
            },
        )

    if method == "shutdown":
        return _ok(message_id, {})

    return _error(message_id, -32601, f"method not found: {method}")


def call_tool(name: str, arguments: dict[str, Any], default_root: str | None) -> Any:
    root = arguments.get("path") or default_root or "."

    if name == "check_pack":
        pack = load_pack(root)
        options: dict[str, Any] = {
            "pii": arguments.get("pii", True),
            "exclude_rules": set(arguments.get("exclude_rules") or []),
        }
        report = run_checks(pack, options)
        report.strict = bool(arguments.get("strict"))

        # The severity filter decides what is listed. The verdict and the
        # total counts describe the whole pack, so a filtered response can
        # never read as clean while the pack is not.
        minimum = arguments.get("min_severity")
        shown = report.findings
        if minimum:
            order = {"error": 0, "warning": 1, "info": 2}
            shown = [
                f for f in report.findings if order.get(f.severity, 3) <= order.get(minimum, 2)
            ]

        payload = report.to_dict()
        payload["findings"] = [f.to_dict() for f in shown]
        payload["counts"] = _counts_of(shown)
        payload["reported"] = len(shown)
        payload["total_findings"] = len(report.findings)
        payload["total_counts"] = report.counts()
        payload["verdict"] = "fail" if report.exit_code() else "pass"
        return payload

    if name == "list_claims":
        pack = load_pack(root)
        status = arguments.get("status")
        topic = arguments.get("topic")
        limit = arguments.get("limit")
        limit = 100 if limit is None else max(0, int(limit))
        rows = []
        for claim in pack.claims:
            if len(rows) >= limit:
                break
            if status and claim.status != status:
                continue
            if topic and topic not in claim.topics:
                continue
            rows.append(
                {
                    "id": claim.id,
                    "text": claim.text[:400],
                    "status": claim.status,
                    "confidence": claim.confidence,
                    "evidence": len(claim.evidence),
                    "topics": claim.topics,
                }
            )
        return {"claims": rows, "total": len(pack.claims)}

    if name == "get_claim":
        pack = load_pack(root)
        claim_id = arguments.get("claim_id")
        claim = pack.claims_by_id().get(str(claim_id))
        if claim is None:
            raise KeyError(f"claim not found: {claim_id}")
        evidence = pack.evidence_by_id()
        sources = pack.sources_by_id()
        records = []
        for evidence_id in claim.evidence:
            record = evidence.get(evidence_id)
            if record is None:
                continue
            source = sources.get(record.source_id)
            records.append(
                {
                    "id": record.id,
                    "source_id": record.source_id,
                    "source_path": source.path if source else None,
                    "locator": record.locator,
                    "quote": record.quote[:400],
                }
            )
        return {"claim": claim.to_dict(), "evidence": records}

    if name == "verify_actions":
        records = arguments.get("actions") or []
        root_dir = arguments.get("root") or default_root or "."
        findings = verify_actions(records, root_dir)
        return {
            "verified": not findings,
            "findings": [f.to_dict() for f in findings],
        }

    raise ValueError(f"unknown tool: {name}")


def _ok(message_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def _counts_of(findings) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return counts


def _error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}
