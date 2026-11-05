"""Link checks: do the references point at files that exist?"""

from __future__ import annotations

from ..model import Pack
from ..report import Finding
from ..resolve import LinkIndex, normalise_path, strip_wikilink
from . import CheckContext, register


@register("links")
def check_links(pack: Pack, ctx: CheckContext) -> list[Finding]:
    findings: list[Finding] = []
    index = ctx.index or LinkIndex()
    known = {normalise_path(path) for path in index.paths}

    for claim in pack.claims:
        for link in claim.links:
            target = str(link.get("target", "") or "")
            if not target.strip():
                continue
            resolved = link.get("resolved")
            if resolved:
                if normalise_path(str(resolved)) not in known:
                    findings.append(
                        Finding(
                            rule="links.broken",
                            severity="error",
                            message=(
                                f"claim {claim.id} links to {resolved!r}, "
                                "which is not in the manifest"
                            ),
                            location=f"claims.jsonl#{claim.id}",
                        )
                    )
                continue
            if index.resolve(target) is None:
                bare = strip_wikilink(target)
                hint = "the target file is missing, or the link needs its full path"
                if ctx.resolve_entity(bare):
                    hint = (
                        f"{bare!r} is an entity, not a file; reference it through the claim's "
                        "'entities' field instead"
                    )
                findings.append(
                    Finding(
                        rule="links.broken",
                        severity="error",
                        message=(
                            f"claim {claim.id} links to {bare!r}, which resolves to nothing"
                        ),
                        location=f"claims.jsonl#{claim.id}",
                        hint=hint,
                    )
                )

    if ctx.option("scan_text_links"):
        for claim in pack.claims:
            for target in index.find_wikilinks(claim.text):
                if index.resolve(target) is None:
                    findings.append(
                        Finding(
                            rule="links.broken",
                            severity="error",
                            message=(
                                f"claim {claim.id} text links to {strip_wikilink(target)!r}, "
                                "which resolves to nothing"
                            ),
                            location=f"claims.jsonl#{claim.id}",
                        )
                    )
    return findings
