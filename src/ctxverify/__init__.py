"""ctxverify — a linter and verifier for context packs.

A context pack is a portable container for the knowledge an agent is given:
atomic claims, the evidence behind each claim, the entities involved, the
relations between them, and the contradictions and freshness states that a
reader needs in order to decide how much to trust it.

Compilers produce packs. ctxverify judges them.

    from ctxverify import load_pack, run_checks

    pack = load_pack("./pack")
    report = run_checks(pack)
    print(report.to_text())
    raise SystemExit(report.exit_code())
"""

from __future__ import annotations

from .loader import PackLoadError, load_pack
from .model import FORMAT_VERSION, SUPPORTED_FORMAT_VERSIONS, Claim, Evidence, Pack
from .report import Finding, Report
from .rules import RULES, RULES_BY_ID, Rule
from .version import __version__

__all__ = [
    "Claim",
    "Evidence",
    "Finding",
    "FORMAT_VERSION",
    "Pack",
    "PackLoadError",
    "RULES",
    "RULES_BY_ID",
    "Report",
    "Rule",
    "SUPPORTED_FORMAT_VERSIONS",
    "__version__",
    "load_pack",
    "run_checks",
]


def run_checks(pack, options=None):  # re-exported lazily to avoid a cycle
    from .checks import run_checks as _run_checks

    return _run_checks(pack, options)
