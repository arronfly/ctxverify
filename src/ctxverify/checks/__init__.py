"""Check registry and runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import time
from typing import Any, Callable, Iterable

from ..model import Pack
from ..report import Finding, Report, sort_findings
from ..resolve import LinkIndex, build_index
from ..rules import ERROR, RULES_BY_ID, RULE_GROUPS

CheckFn = Callable[[Pack, "CheckContext"], Iterable[Finding]]


@dataclass
class CheckContext:
    """Everything a check may need beyond the pack itself."""

    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    options: dict[str, Any] = field(default_factory=dict)
    index: LinkIndex | None = None
    entities: dict[str, str] = field(default_factory=dict)

    def option(self, key: str, default: Any = None) -> Any:
        return self.options.get(key, default)

    def resolve_entity(self, name: str) -> str | None:
        """Resolve an entity name or alias to an entity id."""
        return self.entities.get(name) or self.entities.get(name.strip().lower())


_CHECKS: list[tuple[str, CheckFn]] = []


def register(name: str) -> Callable[[CheckFn], CheckFn]:
    def decorator(fn: CheckFn) -> CheckFn:
        _CHECKS.append((name, fn))
        return fn

    return decorator


def check_names() -> list[str]:
    return [name for name, _ in _CHECKS]


def run_checks(pack: Pack, options: dict[str, Any] | None = None) -> Report:
    """Run every registered check against ``pack`` and return the report."""
    options = dict(options or {})
    now = options.pop("now", None) or datetime.now(timezone.utc)
    started = time.perf_counter()

    # Entity names and aliases are a separate namespace from file paths.
    # They resolve entity references, not links to files, so they must not
    # make a link to a missing file look resolvable.
    entity_alias_map: dict[str, str] = {}
    for entity in pack.entities:
        if entity.name:
            entity_alias_map.setdefault(entity.name, entity.id)
            entity_alias_map.setdefault(entity.id, entity.id)
        for alias in entity.aliases:
            entity_alias_map.setdefault(alias, entity.id)

    # File aliases live on the source record: a note can be linked by a name
    # other than its path, exactly as Obsidian resolves an alias.
    file_aliases: dict[str, str] = {}
    for source in pack.manifest.sources:
        for alias in source.extra.get("aliases") or []:
            alias = str(alias).strip()
            if alias:
                file_aliases.setdefault(alias, source.path)

    index = build_index([s.path for s in pack.manifest.sources], file_aliases)

    ctx = CheckContext(now=now, options=options, index=index, entities=entity_alias_map)
    ctx.options["invalid_ttls"] = set(getattr(pack, "invalid_ttls", set()) or set())

    findings: list[Finding] = list(getattr(pack, "load_findings", []) or [])
    enabled_groups, enabled_rule_ids = _resolve_selection(options.get("rules"))
    disabled_groups = _explicit_groups(options.get("exclude_rules"))
    _, disabled_rule_ids = _resolve_selection(options.get("exclude_rules"))
    for name, fn in _CHECKS:
        if enabled_groups is not None and name not in enabled_groups:
            continue
        if name in disabled_groups:
            continue
        try:
            findings.extend(fn(pack, ctx))
        except Exception as exc:  # a broken check must not hide the rest
            # This is a bug in ctxverify, not a defect in the pack. It gets
            # its own rule id so that the two are never confused, and it is
            # never filtered away: a tool that crashed still has to say so.
            findings.append(
                Finding(
                    rule="ctxverify.internal",
                    severity=ERROR,
                    message=(
                        f"internal error while running check {name}: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                    location=pack.root,
                    hint="this is a bug in ctxverify, not a problem with the pack; please report it",
                )
            )

    # A selection may name a single rule id. Selecting `ids.duplicate` must
    # report `ids.duplicate` and not its neighbour `ids.collision`.
    # Structural findings are never filtered away: a pack that cannot be
    # judged cannot be judged "clean" by narrowing the run.
    if enabled_rule_ids:
        findings = [
            f
            for f in findings
            if f.rule in enabled_rule_ids
            or f.rule in ("pack.structure", "ctxverify.internal")
        ]
    if disabled_rule_ids:
        findings = [f for f in findings if f.rule not in disabled_rule_ids]

    findings = sort_findings(findings)
    report = Report(
        pack=pack.root,
        findings=findings,
        stats=pack_stats(pack),
        checked_at=now.astimezone(timezone.utc).isoformat(timespec="seconds"),
        duration_ms=int((time.perf_counter() - started) * 1000),
        tool_version=tool_version(),
    )
    return report


def _resolve_selection(selection: Any) -> tuple[set[str] | None, set[str]]:
    """Turn a user's selection into check groups and rule ids.

    A selection may name a check group (``identity``) or a rule id
    (``ids.duplicate``). A rule id resolves to the group that implements it,
    so the check still runs; the rule ids are returned separately so that the
    findings can be narrowed to exactly the rules that were named.
    """
    if not selection:
        return None, set()
    groups: set[str] = set()
    rule_ids: set[str] = set()
    for item in selection:
        key = str(item).strip()
        if not key:
            continue
        if key in RULES_BY_ID:
            groups.add(RULE_GROUPS.get(key, key))
            rule_ids.add(key)
            continue
        groups.add(key)
    return (groups or None), rule_ids


def _explicit_groups(selection: Any) -> set[str]:
    """The check groups named directly, ignoring rule ids.

    Excluding a group silences every rule in it. Excluding a single rule id
    must not: the check still runs and the other rules it produces are still
    reported.
    """
    if not selection:
        return set()
    groups: set[str] = set()
    for item in selection:
        key = str(item).strip()
        if key and key not in RULES_BY_ID:
            groups.add(key)
    return groups


def pack_stats(pack: Pack) -> dict[str, Any]:
    return {
        "claims": len(pack.claims),
        "evidence": len(pack.evidence),
        "entities": len(pack.entities),
        "relations": len(pack.relations),
        "contradictions": len(pack.contradictions),
        "sources": len(pack.manifest.sources),
        "freshness_entries": len(pack.freshness),
    }


def tool_version() -> str:
    from ..version import __version__

    return __version__


# Importing the modules registers their checks.
from . import actions as _actions  # noqa: E402,F401
from . import consistency as _consistency  # noqa: E402,F401
from . import duplicates as _duplicates  # noqa: E402,F401
from . import freshness as _freshness  # noqa: E402,F401
from . import hygiene as _hygiene  # noqa: E402,F401
from . import identity as _identity  # noqa: E402,F401
from . import links as _links  # noqa: E402,F401
from . import orphans as _orphans  # noqa: E402,F401
from . import provenance as _provenance  # noqa: E402,F401
