"""Freshness checks: is this claim still worth believing?"""

from __future__ import annotations

from datetime import date, datetime, timezone

from ..model import Pack
from ..report import Finding
from . import CheckContext, register


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.combine(date.fromisoformat(text), datetime.min.time())
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@register("freshness")
def check_freshness(pack: Pack, ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    now = ctx.now
    policy = pack.freshness_policy or {}
    default_ttl = policy.get("default_ttl_days")
    per_topic = policy.get("per_topic") or {}

    # A policy whose TTL is nonsense is a broken policy, not a strict one.
    for label, value in [("default_ttl_days", default_ttl)] + [
        (f"per_topic.{topic}", ttl) for topic, ttl in (per_topic or {}).items()
    ]:
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            findings.append(
                Finding(
                    rule="pack.structure",
                    severity="error",
                    message=f"freshness policy {label} must be a number, got {value!r}",
                    location="freshness.json",
                )
            )
        elif value < 0:
            findings.append(
                Finding(
                    rule="pack.structure",
                    severity="error",
                    message=f"freshness policy {label} must not be negative, got {value!r}",
                    location="freshness.json",
                )
            )

    for claim in pack.claims:
        entry = pack.freshness.get(claim.id)
        if entry is not None and entry.expires_at:
            expires = _parse_dt(entry.expires_at)
            if expires and expires < now:
                days = (now - expires).days
                findings.append(
                    Finding(
                        rule="freshness.stale",
                        severity="warning",
                        message=(
                            f"claim {claim.id} expired {days} day(s) ago "
                            f"(expires_at {entry.expires_at})"
                        ),
                        location=f"freshness.json#{claim.id}",
                        hint="review the claim and extend the window, or drop it",
                    )
                )

        ttl = None
        for topic in claim.topics:
            if topic in per_topic:
                ttl = per_topic[topic]
                break
        if ttl is None:
            ttl = default_ttl
        if ttl is None:
            continue

        reviewed = _parse_dt(entry.reviewed_at) if entry else None
        if reviewed is not None:
            continue

        source_date = _parse_dt(entry.source_date) if entry else None
        if source_date is None:
            source_date = _parse_dt(claim.updated_at) or _parse_dt(claim.created_at)
        if source_date is None:
            continue

        age_days = (now - source_date).days
        if age_days > int(ttl):
            findings.append(
                Finding(
                    rule="freshness.stale",
                    severity="warning",
                    message=(
                        f"claim {claim.id} has not been reviewed for {age_days} day(s) "
                        f"(policy TTL {ttl} days)"
                    ),
                    location=f"claims.jsonl#{claim.id}",
                    hint="record a review in freshness.json, or shorten the TTL if it does not apply",
                )
            )
    return findings
