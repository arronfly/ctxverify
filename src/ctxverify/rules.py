"""The rule registry.

Every check ctxverify performs is registered here with a stable id, a
severity and a one-line description. The ids are part of the public contract:
CI configurations select rules by id, so they must not be renamed lightly.
"""

from __future__ import annotations

from dataclasses import dataclass

ERROR = "error"
WARNING = "warning"
INFO = "info"

SEVERITIES = (ERROR, WARNING, INFO)


@dataclass(frozen=True)
class Rule:
    id: str
    severity: str
    category: str
    title: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "severity": self.severity,
            "category": self.category,
            "title": self.title,
            "description": self.description,
        }


RULES: tuple[Rule, ...] = (
    Rule(
        id="pack.structure",
        severity=ERROR,
        category="pack",
        title="Pack files are present and parseable",
        description=(
            "A pack must contain the eight files of the Context Pack Format and "
            "each must parse. An unreadable pack cannot be judged."
        ),
    ),
    Rule(
        id="provenance.missing",
        severity=ERROR,
        category="provenance",
        title="Claims are backed by evidence",
        description=(
            "Every claim marked 'verified' must cite at least one evidence "
            "record. A claim marked 'asserted' without evidence is reported as "
            "a warning: the compiler may not have found a locatable source."
        ),
    ),
    Rule(
        id="provenance.dangling",
        severity=ERROR,
        category="provenance",
        title="Evidence points at things that exist",
        description=(
            "Each evidence record must reference an existing claim and an "
            "existing source. Dangling references mean the pack was assembled "
            "from parts that no longer fit together."
        ),
    ),
    Rule(
        id="provenance.quote",
        severity=ERROR,
        category="provenance",
        title="Quotes are present and untampered",
        description=(
            "An evidence record must carry a non-empty quote. When a quote "
            "carries a sha256, it must match the hash of the quote text: a "
            "mismatch means the quote was edited after it was recorded."
        ),
    ),
    Rule(
        id="links.broken",
        severity=ERROR,
        category="links",
        title="Links resolve to real files",
        description=(
            "Every link recorded on a claim must resolve to a file listed in "
            "the manifest. Resolution follows Obsidian-style rules: exact "
            "path, path suffix, basename, or alias."
        ),
    ),
    Rule(
        id="ids.duplicate",
        severity=ERROR,
        category="identity",
        title="Identifiers are unique",
        description=(
            "Claim, evidence, entity, relation, contradiction and source ids "
            "must each be unique within the pack. A duplicate id silently "
            "overwrites one of the two records in any consumer."
        ),
    ),
    Rule(
        id="ids.collision",
        severity=ERROR,
        category="identity",
        title="Numbered files do not collide",
        description=(
            "A numbering scheme such as C-001 must identify exactly one file. "
            "Two different paths claiming the same number means one of them "
            "is wrong, and every reference to that number is ambiguous."
        ),
    ),
    Rule(
        id="status.inconsistent",
        severity=ERROR,
        category="consistency",
        title="Claim status matches its evidence",
        description=(
            "'verified' needs evidence, 'inferred' needs a written rationale, "
            "'disputed' and 'refuted' need a contradiction entry."
        ),
    ),
    Rule(
        id="contradiction.unresolved",
        severity=WARNING,
        category="consistency",
        title="Contradictions are tracked and closed",
        description=(
            "An open contradiction is a warning: the pack knows it holds two "
            "incompatible statements. A contradiction that references an "
            "unknown claim is an error."
        ),
    ),
    Rule(
        id="freshness.stale",
        severity=WARNING,
        category="freshness",
        title="Claims are still fresh",
        description=(
            "A claim whose review window has expired, or that has never been "
            "reviewed although its source is older than the policy TTL, is "
            "reported as stale."
        ),
    ),
    Rule(
        id="duplicate.claim",
        severity=WARNING,
        category="redundancy",
        title="The same fact is not stated twice",
        description=(
            "Two claims whose normalised text matches are duplicates. They "
            "usually mean a recompile appended instead of reconciled."
        ),
    ),
    Rule(
        id="orphan.source",
        severity=INFO,
        category="hygiene",
        title="Sources are used",
        description=(
            "A source that no evidence record points at contributed nothing "
            "to the pack. Informational: ingesting a source and then not "
            "using it is normal."
        ),
    ),
    Rule(
        id="orphan.entity",
        severity=INFO,
        category="hygiene",
        title="Entities are used",
        description="An entity that no claim or relation mentions is dead weight.",
    ),
    Rule(
        id="hygiene.secret",
        severity=ERROR,
        category="hygiene",
        title="No credentials in the pack",
        description=(
            "The pack contains a string that looks like a credential. A pack "
            "is meant to be shareable; credentials are not."
        ),
    ),
    Rule(
        id="hygiene.pii",
        severity=WARNING,
        category="hygiene",
        title="No personal contact details in the pack",
        description=(
            "The pack contains an email address or phone number. Context packs "
            "often travel between tools and people; contact details rarely "
            "need to travel with them."
        ),
    ),
    Rule(
        id="action.unverified",
        severity=ERROR,
        category="actions",
        title="Reported actions really happened",
        description=(
            "An agent reported an action (archived, moved, wrote, deleted). "
            "The verifier checks the filesystem: does the file exist, does the "
            "old path still exist, does the content hash match what was "
            "claimed? This is the one check no knowledge tool performs."
        ),
    ),
)

RULES_BY_ID = {rule.id: rule for rule in RULES}

#: Which check implements each rule. Rule ids are the public contract; this
#: maps them onto the internal check groups so that ``--rule ids.duplicate``
#: and ``--rule identity`` both work.
RULE_GROUPS: dict[str, str] = {
    "pack.structure": "pack",
    "provenance.missing": "provenance",
    "provenance.dangling": "provenance",
    "provenance.quote": "provenance",
    "links.broken": "links",
    "ids.duplicate": "identity",
    "ids.collision": "identity",
    "status.inconsistent": "consistency",
    "contradiction.unresolved": "consistency",
    "freshness.stale": "freshness",
    "duplicate.claim": "duplicates",
    "orphan.source": "orphans",
    "orphan.entity": "orphans",
    "hygiene.secret": "hygiene",
    "hygiene.pii": "hygiene",
    "action.unverified": "actions",
}

#: The rules each check group implements.
GROUP_RULES: dict[str, tuple[str, ...]] = {}
for _rule_id, _group in RULE_GROUPS.items():
    GROUP_RULES.setdefault(_group, ())
    GROUP_RULES[_group] = GROUP_RULES[_group] + (_rule_id,)


def get_rule(rule_id: str) -> Rule | None:
    return RULES_BY_ID.get(rule_id)


def severity_of(rule_id: str, default: str = ERROR) -> str:
    rule = RULES_BY_ID.get(rule_id)
    return rule.severity if rule else default
