"""Command line interface.

    ctxv check ./pack          # judge a pack
    ctxv init ./pack           # scaffold a conforming pack
    ctxv export obsidian VAULT # build a pack from an Obsidian vault
    ctxv export llmwiki WIKI   # build a pack from an llmwiki project
    ctxv verify-actions a.jsonl # check an agent's report against the disk
    ctxv rules                 # list the rule catalogue
    ctxv mcp                   # run the MCP server on stdio
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .checks import check_names
from .checks.actions import load_actions, verify_actions
from .loader import PackLoadError, load_pack
from .report import Report, sort_findings
from .rules import RULES, RULES_BY_ID
from .version import __version__

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_UNUSABLE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ctxv",
        description="Check that a context pack can be trusted: provenance, links, ids, freshness, hygiene.",
    )
    parser.add_argument("--version", action="version", version=f"ctxverify {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="check a context pack")
    check.add_argument("pack", nargs="?", default=".", help="path to the pack directory")
    check.add_argument(
        "--format",
        choices=("text", "json", "sarif"),
        default="text",
        help="output format (default: text)",
    )
    check.add_argument("--strict", action="store_true", help="treat warnings as failures")
    check.add_argument("--rule", action="append", default=[], help="only run this rule id (repeatable)")
    check.add_argument(
        "--exclude-rule", action="append", default=[], help="skip this rule id (repeatable)"
    )
    check.add_argument(
        "--min-severity",
        choices=("error", "warning", "info"),
        default="info",
        help="only report findings at or above this severity",
    )
    check.add_argument("--no-pii", action="store_true", help="skip the personal-detail check")
    check.add_argument(
        "--scan-text-links",
        action="store_true",
        help="also resolve [[wikilinks]] found inside claim text",
    )
    check.add_argument(
        "--actions",
        help="also verify an agent's reported actions (JSONL) against the filesystem",
    )
    check.add_argument(
        "--actions-root",
        help="root directory the action paths are relative to (default: the pack directory)",
    )
    check.add_argument("--color", action="store_true", help="colourise the text report")
    check.add_argument("--quiet", action="store_true", help="print nothing; rely on the exit code")

    init = sub.add_parser("init", help="scaffold an empty conforming pack")
    init.add_argument("directory")
    init.add_argument("--id", default="my-pack", help="pack id")
    init.add_argument("--title", default=None, help="human title")
    init.add_argument("--force", action="store_true", help="overwrite an existing pack")

    export = sub.add_parser("export", help="build a pack from an existing corpus")
    export_sub = export.add_subparsers(dest="target", required=True)
    obsidian = export_sub.add_parser("obsidian", help="export an Obsidian-style vault")
    obsidian.add_argument("vault")
    obsidian.add_argument("--out", required=True, help="output pack directory")
    obsidian.add_argument("--id", default=None, help="pack id (defaults to the folder name)")
    obsidian.add_argument(
        "--include",
        action="append",
        default=[],
        help="only include notes whose path matches this substring (repeatable)",
    )
    obsidian.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="skip notes whose path matches this substring (repeatable)",
    )
    llmwiki = export_sub.add_parser("llmwiki", help="export an llmwiki project")
    llmwiki.add_argument("project")
    llmwiki.add_argument("--out", required=True, help="output pack directory")

    markdown = export_sub.add_parser("markdown", help="export a plain markdown directory")
    markdown.add_argument("corpus")
    markdown.add_argument("--out", required=True, help="output pack directory")
    markdown.add_argument("--id", default=None, help="pack id (defaults to the folder name)")
    markdown.add_argument(
        "--include",
        action="append",
        default=[],
        help="only include files whose path matches this substring (repeatable)",
    )
    markdown.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="skip files whose path matches this substring (repeatable)",
    )

    actions = sub.add_parser("verify-actions", help="check an agent's reported actions")
    actions.add_argument("actions", help="JSONL file of action records")
    actions.add_argument("--root", required=True, help="root directory the paths are relative to")
    actions.add_argument("--format", choices=("text", "json"), default="text")

    sub.add_parser("rules", help="list the rule catalogue")

    mcp = sub.add_parser("mcp", help="run the MCP server on stdio")
    mcp.add_argument("--root", default=None, help="default pack directory")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "check":
        return cmd_check(args)
    if args.command == "init":
        return cmd_init(args)
    if args.command == "export":
        return cmd_export(args)
    if args.command == "verify-actions":
        return cmd_verify_actions(args)
    if args.command == "rules":
        return cmd_rules(args)
    if args.command == "mcp":
        return cmd_mcp(args)
    parser.print_help()
    return EXIT_UNUSABLE


def cmd_check(args: argparse.Namespace) -> int:
    from .checks import run_checks
    from .rules import RULES_BY_ID

    unknown = [
        token
        for token in list(args.rule) + list(args.exclude_rule)
        if token not in RULES_BY_ID and token not in check_names()
    ]
    if unknown:
        # A misspelt rule would otherwise select nothing and turn a failing
        # pack into a PASS. That is the worst possible failure for a gate.
        print(
            f"ctxverify: unknown rule or check group: {', '.join(sorted(set(unknown)))}",
            file=sys.stderr,
        )
        print(
            "  known groups: " + ", ".join(check_names()),
            file=sys.stderr,
        )
        return EXIT_UNUSABLE

    try:
        pack = load_pack(args.pack)
    except PackLoadError as exc:
        print(f"ctxverify: {exc}", file=sys.stderr)
        return EXIT_UNUSABLE

    if args.actions:
        try:
            load_actions(args.actions)
        except (OSError, ValueError) as exc:
            print(f"ctxverify: {exc}", file=sys.stderr)
            return EXIT_UNUSABLE

    options: dict = {
        "rules": set(args.rule) if args.rule else None,
        "exclude_rules": set(args.exclude_rule),
        "pii": not args.no_pii,
        "scan_text_links": args.scan_text_links,
    }
    if args.actions:
        options["actions_file"] = args.actions
        options["actions_root"] = args.actions_root or pack.root

    report = run_checks(pack, options)
    report.strict = args.strict
    exit_code = report.exit_code()

    # The severity filter is a display filter. The exit code and the header
    # counts always reflect the full set of findings, so a CI gate never
    # silently stops failing and a filtered view never reads as clean.
    if not args.quiet:
        shown = [
            f
            for f in report.findings
            if _severity_rank(f.severity) <= _severity_rank(args.min_severity)
        ]
        if args.format == "json":
            payload = report.to_dict()
            payload["findings"] = [f.to_dict() for f in shown]
            payload["counts"] = _counts_of(shown)
            payload["reported"] = len(shown)
            payload["total_findings"] = len(report.findings)
            payload["total_counts"] = report.counts()
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif args.format == "sarif":
            print(_sarif_within(report, shown))
        else:
            print(report.to_text(color=args.color, findings=shown))
    return exit_code


def _counts_of(findings) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return counts


def _sarif_within(report: Report, findings) -> str:
    trimmed = Report(
        pack=report.pack,
        findings=findings,
        stats=report.stats,
        checked_at=report.checked_at,
        duration_ms=report.duration_ms,
        tool_version=report.tool_version,
        strict=report.strict,
    )
    return trimmed.to_sarif()


def cmd_init(args: argparse.Namespace) -> int:
    from .scaffold import scaffold_pack

    target = Path(args.directory)
    if target.exists() and not target.is_dir():
        print(f"ctxverify: {target} is not a directory", file=sys.stderr)
        return EXIT_UNUSABLE
    if target.exists() and any(target.iterdir()) and not args.force:
        print(
            f"ctxverify: {target} already exists and is not empty; pass --force to overwrite",
            file=sys.stderr,
        )
        return EXIT_UNUSABLE
    try:
        scaffold_pack(target, pack_id=args.id, title=args.title)
    except OSError as exc:
        print(f"ctxverify: could not create {target}: {exc}", file=sys.stderr)
        return EXIT_UNUSABLE
    print(f"ctxverify: created pack at {target}")
    print(f"  next: ctxv check {target}")
    return EXIT_CLEAN


def cmd_export(args: argparse.Namespace) -> int:
    from .adapters.generic import export_markdown
    from .adapters.llmwiki import export_llmwiki
    from .adapters.obsidian import export_obsidian

    try:
        if args.target == "obsidian":
            pack = export_obsidian(
                args.vault,
                pack_id=args.id,
                include=args.include,
                exclude=args.exclude,
            )
        elif args.target == "llmwiki":
            pack = export_llmwiki(args.project)
        elif args.target == "markdown":
            pack = export_markdown(
                args.corpus,
                pack_id=args.id,
                include=args.include,
                exclude=args.exclude,
            )
        else:  # pragma: no cover - argparse enforces this
            return EXIT_UNUSABLE
    except FileNotFoundError as exc:
        print(f"ctxverify: {exc}", file=sys.stderr)
        return EXIT_UNUSABLE
    except NotADirectoryError as exc:
        print(f"ctxverify: {exc}", file=sys.stderr)
        return EXIT_UNUSABLE
    except OSError as exc:
        print(f"ctxverify: {exc}", file=sys.stderr)
        return EXIT_UNUSABLE

    out = Path(args.out)

    from .writer import write_pack

    write_pack(pack, out)
    print(f"ctxverify: wrote pack with {len(pack.claims)} claims to {out}")
    print(f"  next: ctxv check {out}")
    return EXIT_CLEAN


def cmd_verify_actions(args: argparse.Namespace) -> int:
    try:
        records = load_actions(args.actions)
    except (OSError, ValueError) as exc:
        print(f"ctxverify: {exc}", file=sys.stderr)
        return EXIT_UNUSABLE

    findings = sort_findings(verify_actions(records, args.root))
    report = Report(pack=str(args.root), findings=findings, tool_version=__version__)
    if args.format == "json":
        print(report.to_json())
    else:
        print(report.to_text())
    return report.exit_code()


def cmd_rules(args: argparse.Namespace) -> int:
    from .rules import GROUP_RULES, RULE_GROUPS

    print(f"ctxverify {__version__} — {len(RULES)} rules\n")
    for rule in RULES:
        group = RULE_GROUPS.get(rule.id, "")
        suffix = f"  [{group}]" if group else ""
        print(f"{rule.severity.upper():7} {rule.id:26} {rule.title}{suffix}")
        print(f"        {rule.description}\n")
    print("check groups: " + ", ".join(check_names()))
    print("groups and their rules:")
    for group in check_names():
        print(f"  {group}: {', '.join(GROUP_RULES.get(group, ()))}")
    return EXIT_CLEAN


def cmd_mcp(args: argparse.Namespace) -> int:
    from .mcp.server import serve

    serve(default_root=args.root)
    return EXIT_CLEAN


def _severity_rank(severity: str) -> int:
    return {"error": 0, "warning": 1, "info": 2}.get(severity, 3)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
