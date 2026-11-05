"""The README quotes real tool output. This keeps that true.

A README that quotes output the tool no longer produces is worse than no
README: it teaches a reader the wrong thing with the authority of a
first-hand example. Every quoted block in the two READMEs is checked here
against the tool as it actually runs.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from ctxverify.cli import main

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "examples"

#: Commands whose output the READMEs quote, mapped to the working directory
#: the command should run in.
QUOTED_COMMANDS = [
    ("ctxv check examples/clean-pack", REPO),
    ("ctxv check examples/broken-pack", REPO),
    ("ctxv verify-actions examples/actions.jsonl --root examples/obsidian-vault", REPO),
]


def run(command: str, cwd: Path) -> tuple[int, str]:
    import io
    import os
    from contextlib import redirect_stdout

    arguments = command.split()
    if arguments and arguments[0] == "ctxv":
        arguments = arguments[1:]

    previous = os.getcwd()
    os.chdir(cwd)
    try:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(arguments)
        return code, buffer.getvalue()
    finally:
        os.chdir(previous)


class QuotedOutputTests(unittest.TestCase):
    def test_readme_quotes_match_the_tool(self) -> None:
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        checked = 0
        for command, cwd in QUOTED_COMMANDS:
            code, output = run(command, cwd)
            lines = [line for line in output.splitlines() if line.strip()]
            for line in lines:
                if line.startswith(("  pack:", "ctxverify ", "  PASS", "  FAIL")):
                    self.assertIn(
                        line,
                        readme,
                        msg=f"README.md does not quote this line of `{command}`:\n{line}",
                    )
                    checked += 1
        self.assertGreater(checked, 5, "the README quotes nothing to check")

    def test_every_rule_is_listed_in_the_readme(self) -> None:
        from ctxverify.rules import RULES

        readme = (REPO / "README.md").read_text(encoding="utf-8")
        missing = [rule.id for rule in RULES if rule.id not in readme]
        self.assertEqual(missing, [], msg=f"rules missing from README.md: {missing}")

    def test_every_rule_is_listed_in_the_chinese_readme(self) -> None:
        from ctxverify.rules import RULES

        readme = (REPO / "README.zh-CN.md").read_text(encoding="utf-8")
        missing = [rule.id for rule in RULES if rule.id not in readme]
        self.assertEqual(missing, [], msg=f"rules missing from README.zh-CN.md: {missing}")

    def test_broken_pack_counts_are_current(self) -> None:
        """The broken example's finding counts are quoted in both READMEs."""
        code, output = run("ctxv check examples/broken-pack", REPO)
        self.assertEqual(code, 1)
        match = re.search(r"FAIL\s+(\d+) error\(s\), (\d+) warning\(s\), (\d+) info", output)
        self.assertIsNotNone(match, msg=output)
        errors, warnings, infos = match.groups()
        for readme_name in ("README.md", "README.zh-CN.md"):
            readme = (REPO / readme_name).read_text(encoding="utf-8")
            self.assertIn(f"{errors} error(s)", readme)
            self.assertIn(f"{warnings} warning(s)", readme)
            self.assertIn(f"{infos} info", readme)


class SpecTests(unittest.TestCase):
    def test_spec_lists_every_required_file(self) -> None:
        from ctxverify.model import REQUIRED_FILES

        spec = (REPO / "SPEC.md").read_text(encoding="utf-8")
        for name in REQUIRED_FILES:
            self.assertIn(name, spec)

    def test_spec_and_code_agree_on_the_format_version(self) -> None:
        from ctxverify.model import FORMAT_VERSION

        spec = (REPO / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn(f"version {FORMAT_VERSION}", spec)


if __name__ == "__main__":
    unittest.main()
