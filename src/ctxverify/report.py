"""Findings and the check report."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from .rules import ERROR, INFO, WARNING, RULES_BY_ID


@dataclass
class Finding:
    """One rule violation, anchored to a place in the pack."""

    rule: str
    severity: str
    message: str
    location: str | None = None
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
        }
        if self.location:
            out["location"] = self.location
        if self.hint:
            out["hint"] = self.hint
        return out


@dataclass
class Report:
    """The result of checking one pack."""

    pack: str
    findings: list[Finding] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    checked_at: str | None = None
    duration_ms: int | None = None
    tool_version: str = ""
    strict: bool = False

    # -- aggregation ---------------------------------------------------------
    def counts(self) -> dict[str, int]:
        counts = {ERROR: 0, WARNING: 0, INFO: 0}
        for finding in self.findings:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        return counts

    def by_severity(self, severity: str) -> list[Finding]:
        return [f for f in self.findings if f.severity == severity]

    def by_rule(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.rule] = counts.get(finding.rule, 0) + 1
        return dict(sorted(counts.items()))

    def exit_code(self, strict: bool | None = None) -> int:
        """0 = clean, 1 = findings that block, 2 = the pack could not be read."""
        if strict is None:
            strict = self.strict
        counts = self.counts()
        if counts.get(ERROR, 0):
            return 1
        if strict and (counts.get(WARNING, 0) or counts.get(INFO, 0)):
            return 1
        return 0

    # -- rendering -----------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        counts = self.counts()
        return {
            "tool": "ctxverify",
            "tool_version": self.tool_version,
            "pack": self.pack,
            "checked_at": self.checked_at,
            "duration_ms": self.duration_ms,
            "strict": self.strict,
            "status": "fail" if self.exit_code() else "pass",
            "counts": counts,
            "stats": self.stats,
            "findings": [f.to_dict() for f in self.findings],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def to_text(
        self,
        color: bool = False,
        status_code: int | None = None,
        findings: list[Finding] | None = None,
    ) -> str:
        """Human-readable report. Colors are ANSI and only used when asked.

        ``status_code`` overrides the verdict shown in the header. ``findings``
        limits which findings are listed while the header keeps describing
        the whole pack. The caller uses both when a severity filter is in
        play: the verdict and the counts must always reflect every finding
        the run produced, otherwise a filtered view reads as clean while the
        process exits non-zero.
        """
        counts = self.counts()
        listed = self.findings if findings is None else findings
        lines: list[str] = []
        code = self.exit_code() if status_code is None else status_code
        status = "FAIL" if code else "PASS"
        lines.append(f"ctxverify {self.tool_version} — {self.pack}")
        lines.append(
            "  {status}  {err} error(s), {warn} warning(s), {info} info".format(
                status=status,
                err=counts.get(ERROR, 0),
                warn=counts.get(WARNING, 0),
                info=counts.get(INFO, 0),
            )
        )
        if self.stats:
            summary = ", ".join(f"{k}={v}" for k, v in self.stats.items())
            lines.append(f"  pack: {summary}")
        if listed:
            lines.append("")
            current = None
            for finding in listed:
                if finding.rule != current:
                    current = finding.rule
                    rule = RULES_BY_ID.get(finding.rule)
                    title = rule.title if rule else finding.rule
                    lines.append(f"{_paint(finding.severity, color)} {finding.rule} — {title}")
                location = f"  {finding.location}" if finding.location else ""
                lines.append(f"    - {finding.message}{location}")
                if finding.hint:
                    lines.append(f"      hint: {finding.hint}")
        return "\n".join(lines)

    def to_sarif(self) -> str:
        """SARIF 2.1.0 output, for GitHub code scanning.

        Artifact locations are relative to the working directory, so that
        code scanning can find the file. An absolute path outside the
        repository is not a valid SARIF URI and is reported against the
        pack directory instead.
        """
        rules = []
        seen = set()
        for finding in self.findings:
            if finding.rule in seen:
                continue
            seen.add(finding.rule)
            rule = RULES_BY_ID.get(finding.rule)
            rules.append(
                {
                    "id": finding.rule,
                    "name": finding.rule.replace(".", "_"),
                    "shortDescription": {"text": rule.title if rule else finding.rule},
                    "fullDescription": {"text": rule.description if rule else ""},
                    "defaultConfiguration": {"level": _sarif_level(finding.severity)},
                    "properties": {"category": rule.category if rule else "unknown"},
                }
            )
        results = []
        for finding in self.findings:
            region = {"startLine": 1}
            location = finding.location or ""
            if ":" in location:
                tail = location.rsplit(":", 1)[-1]
                if tail.isdigit():
                    region["startLine"] = int(tail)
            results.append(
                {
                    "ruleId": finding.rule,
                    "level": _sarif_level(finding.severity),
                    "message": {"text": finding.message},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {
                                    "uri": _sarif_uri(location, self.pack)
                                },
                                "region": region,
                            }
                        }
                    ],
                }
            )
        document = {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "ctxverify",
                            "version": self.tool_version,
                            "informationUri": "https://github.com/arronfly/ctxverify",
                            "rules": rules,
                        }
                    },
                    "results": results,
                }
            ],
        }
        return json.dumps(document, ensure_ascii=False, indent=2)


def _sarif_level(severity: str) -> str:
    return {ERROR: "error", WARNING: "warning", INFO: "note"}.get(severity, "note")


def _sarif_uri(location: str, pack_root: str) -> str:
    """A repository-relative URI for a finding's location.

    A location like ``claims.jsonl#clm-001`` is relative to the pack. A
    location like ``/abs/path/claims.jsonl:12`` is absolute, and code
    scanning cannot use it; it is rewritten relative to the working
    directory when that works, and dropped to the pack directory when it
    does not.
    """
    import os

    text = location.split("#", 1)[0]
    if not text:
        return pack_root

    if os.path.isabs(text):
        try:
            relative = os.path.relpath(text, os.getcwd())
        except ValueError:
            return pack_root
        if relative.startswith(".."):
            return pack_root
        return relative
    return text


_COLORS = {ERROR: "\033[31m", WARNING: "\033[33m", INFO: "\033[36m"}


def _paint(severity: str, color: bool) -> str:
    label = severity.upper().ljust(7)
    if not color:
        return label
    return f"{_COLORS.get(severity, '')}{label}\033[0m"


def sort_findings(findings: Iterable[Finding]) -> list[Finding]:
    order = {ERROR: 0, WARNING: 1, INFO: 2}
    return sorted(findings, key=lambda f: (order.get(f.severity, 3), f.rule, f.location or ""))
