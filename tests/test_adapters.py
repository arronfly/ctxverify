"""Adapters and the frontmatter reader."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ctxverify.adapters.llmwiki import export_llmwiki
from ctxverify.adapters.obsidian import export_obsidian
from ctxverify.checks import run_checks
from ctxverify.frontmatter import parse_frontmatter

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class FrontmatterTests(unittest.TestCase):
    def test_scalars_lists_and_nested_maps(self) -> None:
        raw = """---
title: A Note
id: C-001
confidence: 0.9
draft: false
tags: [context, format]
aliases:
  - note
  - a note
meta:
  author: someone
---

# Body
"""
        data = parse_frontmatter(raw)
        self.assertEqual(data["title"], "A Note")
        self.assertEqual(data["id"], "C-001")
        self.assertEqual(data["confidence"], 0.9)
        self.assertIs(data["draft"], False)
        self.assertEqual(data["tags"], ["context", "format"])
        self.assertEqual(data["aliases"], ["note", "a note"])
        self.assertEqual(data["meta"], {"author": "someone"})

    def test_no_frontmatter(self) -> None:
        self.assertEqual(parse_frontmatter("# Just a heading\n"), {})


class ObsidianAdapterTests(unittest.TestCase):
    def test_export_finds_the_broken_link(self) -> None:
        pack = export_obsidian(EXAMPLES / "obsidian-vault")
        self.assertEqual(len(pack.claims), 3)
        report = run_checks(pack)
        rules = {finding.rule for finding in report.findings}
        self.assertIn("links.broken", rules)

    def test_include_filter(self) -> None:
        pack = export_obsidian(EXAMPLES / "obsidian-vault", include=["C-001"])
        self.assertEqual(len(pack.claims), 1)


class MarkdownAdapterTests(unittest.TestCase):
    def test_export_reads_a_plain_markdown_directory(self) -> None:
        from ctxverify.adapters.generic import export_markdown

        pack = export_markdown(EXAMPLES / "obsidian-vault")
        self.assertEqual(len(pack.claims), 3)
        self.assertEqual(len(pack.evidence), 3)
        # Every claim names its own file as the evidence.
        self.assertTrue(all(c.evidence for c in pack.claims))

    def test_export_finds_the_broken_link(self) -> None:
        from ctxverify.adapters.generic import export_markdown

        pack = export_markdown(EXAMPLES / "obsidian-vault")
        report = run_checks(pack)
        self.assertIn("links.broken", {f.rule for f in report.findings})

    def test_missing_corpus_raises(self) -> None:
        from ctxverify.adapters.generic import export_markdown

        with self.assertRaises(FileNotFoundError):
            export_markdown("/tmp/not-a-markdown-corpus-ctxverify")


class LlmwikiAdapterTests(unittest.TestCase):
    def test_export_reads_citation_markers(self) -> None:
        pack = export_llmwiki(FIXTURES / "llmwiki-project")
        self.assertEqual(len(pack.claims), 2)
        cited = [claim for claim in pack.claims if claim.evidence]
        self.assertEqual(len(cited), 1)
        self.assertEqual(len(pack.evidence), 2)
        self.assertEqual(pack.evidence[0].locator.get("line_start"), 3)

    def test_uncited_page_is_reported(self) -> None:
        pack = export_llmwiki(FIXTURES / "llmwiki-project")
        report = run_checks(pack)
        rules = {finding.rule for finding in report.findings}
        self.assertIn("provenance.missing", rules)

    def test_missing_project_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            export_llmwiki("/tmp/not-an-llmwiki-project-ctxverify")


class ScaffoldTests(unittest.TestCase):
    def test_scaffolded_pack_passes(self) -> None:
        from ctxverify.scaffold import scaffold_pack

        with tempfile.TemporaryDirectory() as tmp:
            pack = scaffold_pack(Path(tmp) / "pack")
            report = run_checks(pack)
            self.assertEqual(report.findings, [], msg=report.to_text())


if __name__ == "__main__":
    unittest.main()
