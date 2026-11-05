"""Load a context pack from disk.

Loading never raises on bad content: a pack that cannot be parsed produces
findings instead, because "this pack is broken" is exactly the kind of thing
ctxverify exists to say out loud.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .model import (
    FORMAT_VERSION,
    REQUIRED_FILES,
    SUPPORTED_FORMAT_VERSIONS,
    Claim,
    Contradiction,
    Entity,
    Evidence,
    FreshnessEntry,
    Manifest,
    Pack,
    Relation,
)
from .report import Finding


class PackLoadError(Exception):
    """Raised when a pack cannot be opened at all."""


def load_pack(root: str | os.PathLike[str]) -> Pack:
    """Read the pack at ``root`` into a :class:`Pack`.

    Structural problems are recorded in ``pack.errors`` as human-readable
    strings and as ``pack.structure`` findings by the caller.
    """
    path = Path(root).expanduser()
    if not path.exists():
        raise PackLoadError(f"pack not found: {path}")
    if not path.is_dir():
        raise PackLoadError(f"pack is not a directory: {path}")

    errors: list[str] = []
    findings: list[Finding] = []

    missing = [name for name in REQUIRED_FILES if not (path / name).exists()]
    if missing:
        message = f"pack is missing {len(missing)} required file(s): {', '.join(missing)}"
        errors.append(message)
        findings.append(
            Finding(
                rule="pack.structure",
                severity="error",
                message=message,
                location=str(path),
                hint="run `ctxv init <dir>` to scaffold a conforming pack",
            )
        )

    manifest = Manifest()
    manifest_path = path / "manifest.json"
    if manifest_path.exists():
        data = _read_json(manifest_path, errors, findings)
        if data is not None:
            if not isinstance(data, dict):
                message = "manifest.json must contain a JSON object"
                errors.append(message)
                findings.append(
                    Finding(
                        rule="pack.structure",
                        severity="error",
                        message=message,
                        location=str(manifest_path),
                    )
                )
            else:
                manifest = Manifest.from_dict(data)
                for source in manifest.sources:
                    findings.extend(_source_path_findings(source, manifest_path))
                if not _version_supported(manifest.format_version):
                    message = (
                        f"unsupported format_version {manifest.format_version!r}; "
                        f"this build supports {', '.join(sorted(SUPPORTED_FORMAT_VERSIONS))}"
                    )
                    errors.append(message)
                    findings.append(
                        Finding(
                            rule="pack.structure",
                            severity="error",
                            message=message,
                            location=str(manifest_path),
                            hint="upgrade ctxverify, or pin the pack to a supported version",
                        )
                    )
                elif manifest.format_version not in SUPPORTED_FORMAT_VERSIONS:
                    # Same major, newer minor: compatible, but worth saying so.
                    findings.append(
                        Finding(
                            rule="pack.structure",
                            severity="info",
                            message=(
                                f"pack declares format_version {manifest.format_version!r}; "
                                f"this build implements {FORMAT_VERSION} and read it anyway"
                            ),
                            location=str(manifest_path),
                            hint="upgrade ctxverify to check the newest fields",
                        )
                    )

    # A pack may carry the result of a previous check. It is informational:
    # the manifest's own `verification` object takes precedence, and this
    # never affects the verdict of the current run.
    verification_path = path / "verification.json"
    if verification_path.exists():
        verification = _read_json(verification_path, errors, findings, default={})
        if isinstance(verification, dict):
            manifest.verification = {**verification, **manifest.verification}

    claims = _read_jsonl(path / "claims.jsonl", errors, findings)
    evidence = _read_jsonl(path / "evidence.jsonl", errors, findings)

    collections: dict[str, Any] = {}
    for name, key in (
        ("entities.json", "entities"),
        ("relations.json", "relations"),
        ("contradictions.json", "contradictions"),
    ):
        raw = _read_json(path / name, errors, findings, default=None)
        if raw is None:
            collections[key] = []
            continue
        if not isinstance(raw, dict) or not isinstance(raw.get(key), list):
            message = f"{name} must be an object with a '{key}' array"
            errors.append(message)
            findings.append(
                Finding(
                    rule="pack.structure",
                    severity="error",
                    message=message,
                    location=str(path / name),
                    hint=f'write {{"{key}": [...]}}',
                )
            )
            collections[key] = []
            continue
        collections[key] = raw[key]

    entities_raw = collections["entities"]
    relations_raw = collections["relations"]
    contradictions_raw = collections["contradictions"]

    freshness_raw = _read_json(path / "freshness.json", errors, findings, default=None)
    if freshness_raw is None:
        freshness_raw = {}
    elif not isinstance(freshness_raw, dict):
        message = "freshness.json must be a JSON object"
        errors.append(message)
        findings.append(
            Finding(
                rule="pack.structure",
                severity="error",
                message=message,
                location=str(path / "freshness.json"),
                hint='write {"policy": {...}, "claims": {...}}',
            )
        )
        freshness_raw = {}

    claims_models = [Claim.from_dict(row) for row in claims]
    evidence_models = [Evidence.from_dict(row) for row in evidence]
    entities = [Entity.from_dict(row) for row in entities_raw if isinstance(row, dict)]
    relations = [Relation.from_dict(row) for row in relations_raw if isinstance(row, dict)]
    contradictions = [
        Contradiction.from_dict(row) for row in contradictions_raw if isinstance(row, dict)
    ]

    freshness: dict[str, FreshnessEntry] = {}
    policy: dict[str, Any] = {}
    if isinstance(freshness_raw, dict):
        policy = dict(freshness_raw.get("policy") or {})
        claims_fresh = freshness_raw.get("claims") or {}
        if isinstance(claims_fresh, dict):
            for claim_id, entry in claims_fresh.items():
                if isinstance(entry, dict):
                    freshness[str(claim_id)] = FreshnessEntry.from_dict(str(claim_id), entry)

    readme = ""
    readme_path = path / "README.md"
    if readme_path.exists():
        try:
            readme = readme_path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"README.md could not be read: {exc}")

    # Anything that went wrong while loading and did not already produce a
    # finding of its own becomes a structural finding now. A silent failure
    # to read a file is exactly the kind of thing this tool exists to catch.
    already = {finding.message for finding in findings}
    for message in errors:
        if message in already:
            continue
        findings.append(
            Finding(
                rule="pack.structure",
                severity="error",
                message=message,
                location=str(path),
            )
        )

    pack = Pack(
        root=str(path),
        manifest=manifest,
        claims=claims_models,
        evidence=evidence_models,
        entities=entities,
        relations=relations,
        contradictions=contradictions,
        freshness=freshness,
        freshness_policy=policy,
        readme=readme,
        errors=errors,
    )
    pack.load_findings = findings  # type: ignore[attr-defined]
    return pack


def _source_path_findings(source, manifest_path: Path) -> list[Finding]:
    """A source path must be inside the pack.

    Paths are relative to the pack root by rule. A path that points outside
    it is either a mistake or a leak: either way, the pack is describing
    something the reader cannot open.
    """
    findings: list[Finding] = []
    path = source.path
    if not path:
        findings.append(
            Finding(
                rule="pack.structure",
                severity="error",
                message=f"source {source.id} has no path",
                location=str(manifest_path),
            )
        )
        return findings

    normalised = path.replace("\\", "/")
    outside = (
        normalised.startswith("/")
        or normalised.startswith("~")
        or ".." in normalised.split("/")
    )
    if outside:
        findings.append(
            Finding(
                rule="pack.structure",
                severity="error",
                message=f"source {source.id} has a path outside the pack: {path!r}",
                location=str(manifest_path),
                hint="source paths are relative to the pack root",
            )
        )
    return findings


def _version_supported(version: str) -> bool:
    """A pack is supported when this build implements the same MAJOR version.

    Minor versions are additive by rule (SPEC.md §13), so a pack written by a
    newer minor of the same major is still readable. A different major is not:
    interpreting it would be guesswork.
    """
    if version in SUPPORTED_FORMAT_VERSIONS:
        return True
    parts = version.split(".")
    current = FORMAT_VERSION.split(".")
    if len(parts) >= 1 and len(current) >= 1 and parts[0] == current[0]:
        return True
    return False


def _read_json(
    path: Path,
    errors: list[str],
    findings: list[Finding],
    default: Any = None,
) -> Any:
    if not path.exists():
        return default
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{path.name} could not be read: {exc}")
        return default
    if not text.strip():
        message = f"{path.name} is empty"
        errors.append(message)
        findings.append(
            Finding(
                rule="pack.structure",
                severity="error",
                message=message,
                location=str(path),
            )
        )
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        message = f"{path.name} is not valid JSON: {exc}"
        errors.append(message)
        findings.append(
            Finding(
                rule="pack.structure",
                severity="error",
                message=message,
                location=str(path),
            )
        )
        return default


def _read_jsonl(path: Path, errors: list[str], findings: list[Finding]) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{path.name} could not be read: {exc}")
        return rows
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            message = f"line {number} is not valid JSON: {exc}"
            errors.append(message)
            findings.append(
                Finding(
                    rule="pack.structure",
                    severity="error",
                    message=message,
                    location=f"{path.name}:{number}",
                )
            )
            continue
        if not isinstance(row, dict):
            message = f"line {number} is not a JSON object"
            errors.append(message)
            findings.append(
                Finding(
                    rule="pack.structure",
                    severity="error",
                    message=message,
                    location=f"{path.name}:{number}",
                )
            )
            continue
        rows.append(row)
    return rows


def _as_list(value: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        inner = value.get(key)
        if isinstance(inner, list):
            return [row for row in inner if isinstance(row, dict)]
    return []
