# ctxverify

[![M8ven Score](https://m8ven.ai/badge/mcp/arronfly-ctxverify-1idj30)](https://m8ven.ai/mcp/arronfly-ctxverify-1idj30?s=readme)

A linter and verifier for agent context packs.

Compilers generate knowledge. Linters judge it. The judge should not belong to the compiler.

An agent is given a body of knowledge: claims, sources, quotes, entities, contradictions, review dates. A compiler turns that into a context pack. The pack is then trusted by an agent, copied between tools, and used to answer questions. If the pack is internally inconsistent, the agent has no way to notice. It will cite evidence that does not exist, repeat a fact that was retracted, or report that it archived files it never touched.

`ctxverify` loads a pack, checks it against a fixed rule catalogue, and returns findings plus an exit code, the way `eslint`, `ruff` and `tsc` do. It has zero runtime dependencies, runs on Python 3.10 or newer, and uses only the standard library.

## What breaks without a judge

An agent finishes a cleanup task and reports this:

```jsonl
{"id": "a-001", "action": "archived", "path": "notes/C-001_Context Packs.md"}
{"id": "a-002", "action": "moved", "path": "concepts/C-001_Context Packs.md", "from": "notes/C-001_Context Packs.md"}
{"id": "a-003", "action": "wrote", "path": "concepts/C-003_Linting.md", "sha256": "0000000000000000000000000000000000000000000000000000000000000000"}
{"id": "a-004", "action": "deleted", "path": "notes/old-draft.md"}
{"id": "a-005", "action": "archived", "paths": ["concepts/C-002_Evidence.md", "concepts/C-999_NotThere.md"], "count": 2}
```

`ctxv verify-actions` checks every record against the filesystem:

```bash
$ ctxv verify-actions examples/actions.jsonl --root examples/obsidian-vault
ctxverify 0.1.0 — examples/obsidian-vault
  FAIL  3 error(s), 0 warning(s), 0 info

ERROR   action.unverified — Reported actions really happened
    - action a-001 reports 'notes/C-001_Context Packs.md' as archived, but it does not exist  actions.jsonl#a-001
    - action a-003 reports content hash 000000000000… for 'concepts/C-003_Linting.md', actual 8474779cbaca…  actions.jsonl#a-003
    - action a-005 reports 'concepts/C-999_NotThere.md' as archived, but it does not exist  actions.jsonl#a-005
```

The same class of error appears inside the pack itself. A claim marked `verified` with no evidence record is an assertion wearing a lab coat. `ctxv check` reports it as an error:

```bash
$ ctxv check examples/broken-pack
ctxverify 0.1.0 — examples/broken-pack
  FAIL  13 error(s), 8 warning(s), 2 info
  pack: claims=9, evidence=6, entities=2, relations=1, contradictions=1, sources=4, freshness_entries=2

ERROR   hygiene.secret — No credentials in the pack
    - possible assigned credential in claims.jsonl#clm-009  claims.jsonl#clm-009
      hint: remove the value before sharing the pack; rotate it if it was real
ERROR   ids.collision — Numbered files do not collide
    - number 'C-001' is claimed by 2 files: notes/C-001_Alpha.md, notes/C-001_Gamma.md  manifest.json#C-001
      hint: one numbering scheme must map to one file; renumber one of them
ERROR   ids.duplicate — Identifiers are unique
    - claims: id 'clm-003' is used 2 times  claims.jsonl#clm-003
      hint: every consumer that keys on this id will keep only the last one
ERROR   links.broken — Links resolve to real files
    - claim clm-001 links to 'Missing Note', which resolves to nothing  claims.jsonl#clm-001
      hint: the target file is missing, or the link needs its full path
ERROR   provenance.dangling — Evidence points at things that exist
    - evidence ev-003 references unknown claim clm-999  evidence.jsonl#ev-003
    - evidence ev-003 references unknown source src-404  evidence.jsonl#ev-003
ERROR   provenance.missing — Claims are backed by evidence
    - claim clm-002 is marked 'verified' but has no evidence  claims.jsonl#clm-002
      hint: downgrade the status, or attach the evidence that verifies it
    - claim clm-008 is marked 'verified' but has no evidence  claims.jsonl#clm-008
      hint: downgrade the status, or attach the evidence that verifies it
ERROR   provenance.quote — Quotes are present and untampered
    - evidence ev-004 quote hash mismatch: recorded 000000000000…, actual a97323b6db27…  evidence.jsonl#ev-004
      hint: the quote was edited after the hash was recorded
    - evidence ev-005 has an empty quote  evidence.jsonl#ev-005
      hint: an evidence record without a quote cannot be checked by a human
ERROR   status.inconsistent — Claim status matches its evidence
    - claim clm-005 lists evidence ev-003, but that evidence points at claim clm-999  claims.jsonl#clm-005
    - relation rel-001 ends at unknown entity ent-404  relations.json#rel-001
    - relation rel-001 references unknown evidence ev-404  relations.json#rel-001
WARNING contradiction.unresolved — Contradictions are tracked and closed
    - contradiction con-001 is still open: One source says the wiki ships unchecked, another says it is checked before shipping.  contradictions.json#con-001
      hint: an open contradiction means the pack holds two incompatible statements
WARNING duplicate.claim — The same fact is not stated twice
    - 2 claims state the same thing: clm-007, clm-008  claims.jsonl#clm-007
      hint: a recompile that appends instead of reconciles produces these
WARNING freshness.stale — Claims are still fresh
    - claim clm-006 has not been reviewed for 1039 day(s) (policy TTL 180 days)  claims.jsonl#clm-006
      hint: record a review in freshness.json, or shorten the TTL if it does not apply
    - claim clm-005 expired 461 day(s) ago (expires_at 2025-08-01)  freshness.json#clm-005
      hint: review the claim and extend the window, or drop it
WARNING hygiene.pii — No personal contact details in the pack
    - possible email address in evidence.jsonl#ev-006  evidence.jsonl#ev-006
      hint: packs often travel between tools; contact details rarely need to travel
WARNING provenance.missing — Claims are backed by evidence
    - claim clm-003 is marked 'asserted' but has no evidence  claims.jsonl#clm-003
    - claim clm-009 is marked 'asserted' but has no evidence  claims.jsonl#clm-009
WARNING status.inconsistent — Claim status matches its evidence
    - claim clm-006 is marked 'inferred' but records no reasoning in 'notes'  claims.jsonl#clm-006
      hint: an inference without a stated chain is indistinguishable from a guess
INFO    orphan.entity — Entities are used
    - entity ent-002 (Nobody Uses This) is not referenced by any claim or relation  entities.json#ent-002
INFO    orphan.source — Sources are used
    - source src-004 (notes/never-read.md) is not cited by any evidence  manifest.json#src-004
```

The day counts in `freshness.stale` depend on when you run the check. The output above was recorded on 2026-11-05.

## What a context pack is

A context pack is a portable directory holding the knowledge an agent is given. It is deliberately boring: JSON and JSONL files, no database, no server, no required runtime. A pack contains atomic claims, the evidence behind each claim, entities, relations, contradictions, freshness state and a manifest.

| File | What it holds |
|---|---|
| `manifest.json` | Format version, pack id, title, generator, the source inventory, inventory counts |
| `claims.jsonl` | One JSON object per line. Each line is one atomic assertion with a status and evidence ids |
| `evidence.jsonl` | One JSON object per line. A quote, a locator, the source id and the claim id it supports |
| `entities.json` | Named things the claims are about, with aliases and properties |
| `relations.json` | Typed edges between entities |
| `contradictions.json` | Pairs of claims that cannot both be true, with status and resolution |
| `freshness.json` | The review policy and per-claim review dates and expiry dates |
| `README.md` | Human-readable overview. Must exist; its text is also scanned for secrets and PII |

A claim and its evidence look like this:

```json
{
  "claims": {"id": "clm-001", "text": "A context pack is a portable container for the knowledge an agent is given.", "status": "verified", "confidence": 1.0, "evidence": ["ev-001"], "topics": ["ctxverify"]},
  "evidence": {"id": "ev-001", "claim_id": "clm-001", "source_id": "src-001", "quote": "A context pack is a portable container for the knowledge an agent is given.", "locator": {"path": "sources/notes.md", "line_start": 3, "line_end": 3}, "quote_sha256": "e78ad35b4aa7a0f107349ce5c3cacb61e0d9618a842af7f41876d9c9b7f2d542", "retrieved_at": "2026-11-05T00:00:00Z"}
}
```

The layout on disk is flat:

```text
pack/
├── manifest.json
├── claims.jsonl
├── evidence.jsonl
├── entities.json
├── relations.json
├── contradictions.json
├── freshness.json
└── README.md
```

For the field-by-field guide to producing a pack, see [docs/format.md](docs/format.md).

## Install

```bash
pip install ctxverify
```

The package is also installable straight from the repository:

```bash
pip install git+https://github.com/arronfly/ctxverify.git
```

From a checkout:

```bash
git clone https://github.com/arronfly/ctxverify
cd ctxverify
pip install -e .
```

Requirements: Python 3.10 or newer. No runtime dependencies.

## Quick start

```bash
$ ctxv init demo-pack --id demo --title "Demo Pack"
ctxverify: created pack at demo-pack
  next: ctxv check demo-pack
$ ctxv check demo-pack
ctxverify 0.1.0 — demo-pack
  PASS  0 error(s), 0 warning(s), 0 info
  pack: claims=1, evidence=1, entities=1, relations=0, contradictions=0, sources=1, freshness_entries=0
```

The scaffolded pack passes because it is internally consistent, not because it contains anything valuable. Replace the example claim and evidence with your own, then run `ctxv check` again.

`ctxv check examples/clean-pack` produces the same shape:

```text
ctxverify 0.1.0 — examples/clean-pack
  PASS  0 error(s), 0 warning(s), 0 info
  pack: claims=2, evidence=2, entities=1, relations=0, contradictions=0, sources=2, freshness_entries=2
```

## Commands

| Command | What it does |
|---|---|
| `ctxv check <pack>` | Check a pack. Defaults to the current directory |
| `ctxv init <dir>` | Scaffold a conforming pack. Flags: `--id`, `--title`, `--force` |
| `ctxv export obsidian <vault> --out <pack>` | Build a pack from an Obsidian-style vault. Flags: `--id`, `--include`, `--exclude` |
| `ctxv export llmwiki <project> --out <pack>` | Build a pack from an llmwiki project |
| `ctxv export markdown <dir> --out <pack>` | Build a pack from a plain markdown directory. Flags: `--id`, `--include`, `--exclude` |
| `ctxv verify-actions <actions.jsonl> --root <dir>` | Check an agent's reported actions against the filesystem. Flag: `--format text\|json` |
| `ctxv rules` | List the rule catalogue |
| `ctxv mcp` | Run the MCP server on stdio. Flag: `--root` |

`ctxv check` flags:

| Flag | Effect |
|---|---|
| `--format text\|json\|sarif` | Output format. Default: `text` |
| `--strict` | Exit 1 on warnings and information findings as well as errors |
| `--rule <check>` | Run only this check group, or only the one rule whose full id you pass. Repeatable. Group names are the check names printed by `ctxv rules`: `actions`, `consistency`, `duplicates`, `freshness`, `hygiene`, `identity`, `links`, `orphans`, `provenance`. Usually the part of a rule id before the dot; the exception is `action.unverified`, whose group is `actions`. `--rule provenance` runs the whole group; `--rule provenance.missing` runs the group and reports only `provenance.missing` findings. An unknown rule id or group is a usage error: the tool prints `ctxverify: unknown rule or check group: <name>`, lists the known groups and exits `2`, rather than selecting nothing. When `--rule` narrows the selection, loader findings (`pack.structure`) and `ctxverify.internal` still appear |
| `--exclude-rule <check>` | Skip this check group, or only the named rule. Same naming rule as `--rule`: `--exclude-rule hygiene` skips both hygiene rules, `--exclude-rule hygiene.secret` skips only that one. An unknown value is a usage error, as with `--rule` |
| `--min-severity error\|warning\|info` | Display filter: list only findings at or above this severity. The header counts and the verdict still describe the whole pack, and the exit code still reflects every finding, so the filter never hides a failure |
| `--no-pii` | Skip `hygiene.pii`. `hygiene.secret` still runs |
| `--scan-text-links` | Also resolve `[[wikilinks]]` found inside claim text |
| `--actions <file>` | Also verify an agent's reported actions. The file is JSONL |
| `--actions-root <dir>` | Directory action paths are relative to. Default: the pack directory |
| `--color` | Colourize the text report |
| `--quiet` | Print nothing and rely on the exit code |

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Clean. No errors. Warnings and information findings are allowed unless `--strict` is set |
| `1` | Findings that block: at least one error, or any finding under `--strict` |
| `2` | The pack could not be opened at all: missing directory, not a directory. `ctxv check --actions <file>` and `ctxv verify-actions <file>` both return `2` when the actions file is missing, unreadable, or holds a line that is valid JSON but not an object. An invalid command line also exits `2` through argparse, and so does an unknown `--rule` or `--exclude-rule` value |

A pack that exists but is missing required files is exit `1`, not `2`. The tool can open the directory, so it reports `pack.structure` instead.

## Rule catalogue

`ctxverify 0.1.0` ships 16 rules about packs, plus one that reports ctxverify's
own bugs.

| Rule id | Default severity | What it catches |
|---|---|---|
| `pack.structure` | error / info | A required file is missing; a `.json` file is empty or unparseable; `pack_id` or `sources` is missing from the manifest, or a manifest field has the wrong type; `entities.json`, `relations.json` or `contradictions.json` is not an object with its collection array, or `freshness.json` is not an object; a freshness TTL is not a non-negative number; a source path escapes the pack; the format version is not `MAJOR.MINOR` or has a different major (error). A newer minor of the same major is read and reported as info |
| `provenance.missing` | error / warning | A `verified` claim has no evidence (error); an `asserted` claim has no evidence (warning) |
| `provenance.dangling` | error | Evidence points at a claim or source that does not exist, or a claim points at missing evidence |
| `provenance.quote` | error | An evidence quote is empty, or its recorded sha256 does not match the quote text |
| `links.broken` | error | A claim link resolves to no file in the manifest. Source aliases resolve; entity names do not, and are reported with a hint to use the claim's `entities` field |
| `ids.duplicate` | error | An id is repeated within a collection, or an id is empty |
| `ids.collision` | error | Two source files claim the same number, such as `C-001`, within one namespace |
| `status.inconsistent` | error / warning | Status obligations and references do not line up, including a relation that names no `type`. Structural problems are errors; a missing rationale or contradiction entry is a warning |
| `contradiction.unresolved` | warning / error | A contradiction is open, resolved without text, or names fewer than two claims (warning); it names an unknown claim (error) |
| `freshness.stale` | warning | A review window expired, or a claim has gone unreviewed past the policy TTL |
| `duplicate.claim` | warning | Two claims have the same normalised text |
| `orphan.source` | info | A source is cited by no evidence record |
| `orphan.entity` | info | An entity is referenced by no claim or relation |
| `hygiene.secret` | error | A string in the pack looks like a credential |
| `hygiene.pii` | warning | A string in the pack looks like an email address, phone number or national id |
| `action.unverified` | error | An agent's reported action is contradicted by the filesystem |
| `ctxverify.internal` | error | A check crashed. This is a bug in ctxverify, not a defect in the pack, and it is never filtered away by `--rule` or `--min-severity` |

See [docs/rules.md](docs/rules.md) for each rule's detection logic, failure mode and fix.

## CI usage

Gate on the exit code. It always reflects every finding the run produced, so `--min-severity` can narrow the printed output without weakening the gate, and `--strict` is visible in the report as well as in the exit code: the PASS/FAIL header, the JSON `status` field and the JSON `strict` boolean all agree with it.

`--min-severity` filters the listing, not the judgement. The text header counts every finding the run produced, whatever the filter hides: `ctxv check --min-severity error` on a pack with 13 errors, 8 warnings and 2 information findings prints `FAIL  13 error(s), 8 warning(s), 2 info` and then lists only the error findings. The same command on a pack whose only findings are warnings prints no findings and exits `0`, because there is no error. The same command on a pack with one error and many warnings exits `1` even though only the error is printed.

The JSON payload keeps the two views in separate fields. `findings` and `counts` describe what the filter allowed through, `reported` is how many were listed, `total_findings` is how many the run produced, and `total_counts` holds the counts of every finding the run produced. `status` is that run's verdict. Do not read `counts` and the text header as the same number: the header counts every finding the run produced (the whole pack, unless `--rule` narrowed the run), while `counts` counts only the shown findings.

The repository ships a composite GitHub Action in `action.yml`:

```yaml
name: ctxverify
on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: arronfly/ctxverify@v0.1.0
        with:
          pack: ./pack
          strict: true
```

The action installs ctxverify from its own checkout, so a tagged action runs the code in that tag and works on the day the repository is published. It runs `ctxv check` and fails the job on exit code `1` or `2`. `min-severity` defaults to `info`, so every finding is printed unless you ask for less. Severity filtering is a display filter: it changes what the log shows, never what the job gates on, so `strict: true` now genuinely fails the job on a pack that has warnings or information findings.

For SARIF upload to code scanning, run the CLI directly:

```yaml
name: ctxverify-sarif
on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install .
      - name: Produce SARIF
        run: ctxv check ./pack --format sarif > ctxverify.sarif || true
      - uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: ctxverify.sarif
      - name: Gate on exit code
        run: ctxv check ./pack
```

The first run writes SARIF even when the check fails. Artifact locations in the SARIF are repository-relative, so code scanning can attach a finding to a file: `claims.jsonl#clm-001` stays as it is, and an absolute path is rewritten relative to the working directory when that works and dropped to the pack directory when it does not. The last step is the gate: it fails the job on exit code `1`, and also on `2` if the pack cannot be read.

Pre-commit:

```yaml
repos:
  - repo: local
    hooks:
      - id: ctxverify
        name: ctxverify — check the context pack
        entry: ctxv check
        language: system
        files: \.(json|jsonl)$
        pass_filenames: false
        args: ["packs/knowledge"]
```

The `repo: local` form works today with the `ctxv` you already have installed. `entry` names the command, `args` names the pack directory, and `pass_filenames: false` is required: the hook checks a pack directory, not a list of changed files. The `files` pattern decides when the hook runs; adjust it with a `files:` override if the pack is not the only JSON in the repository. With no `args`, the hook checks the current directory. If `ctxv` is installed inside a virtualenv, point `entry` at it, for example `entry: .venv/bin/ctxv`.

Once the repository is tagged, the published hook is shorter:

```yaml
repos:
  - repo: https://github.com/arronfly/ctxverify
    rev: v0.1.0
    hooks:
      - id: ctxverify
        args: ["packs/knowledge"]
```

It fetches `.pre-commit-hooks.yaml` from the tag, which ships the same `files: \.(json|jsonl)$` and `pass_filenames: false`. Use it once the `v0.1.0` tag exists; until then, use the `repo: local` form.

If the pack lives in a private repository and you want SARIF in code scanning, upload it from a job that has `security-events: write`.

## MCP usage

`ctxv mcp` speaks MCP over stdio. It exposes four tools:

| Tool | Purpose |
|---|---|
| `check_pack` | Run the checks. Arguments: `path`, `strict`, `min_severity`, `exclude_rules`. `exclude_rules` takes the same check group names and full rule ids as `--exclude-rule` |
| `list_claims` | List claims with status and evidence counts. Arguments: `path`, `status`, `topic`, `limit` |
| `get_claim` | Return one claim with its evidence and source paths. Arguments: `path`, `claim_id` |
| `verify_actions` | Check reported actions against the filesystem. Arguments: `actions`, `root` |

Every tool declares the four standard MCP annotations — `readOnlyHint`, `destructiveHint`, `idempotentHint` and `openWorldHint` — as explicit booleans, because a client cannot infer them. All four tools are read-only: they read the filesystem and write nothing.

`check_pack` behaves the same way as the CLI. It returns `verdict` (`pass` or `fail`), `status`, `strict`, `counts` (the shown findings), `reported` (how many were listed), `total_findings` (how many the run produced) and `total_counts` (the counts of every finding the run produced). `min_severity` filters the listing only: the verdict, `status` and `total_counts` always describe the run before the filter. `strict` is honoured, so a pack whose only findings are warnings returns `verdict: "fail"` and `status: "fail"` when you pass `strict: true`. `get_claim` returns `isError: true` for a claim id that is not in the pack, and `list_claims` with `limit: 0` returns no claims. An unreadable pack is the one difference from the CLI: the CLI exits `2` with no JSON, while the tool returns `isError: true` with the message in its content.

Claude Code, project scope, `.mcp.json`:

```json
{
  "mcpServers": {
    "ctxverify": {
      "command": "ctxv",
      "args": ["mcp", "--root", "/absolute/path/to/pack"]
    }
  }
}
```

Or from the CLI:

```bash
claude mcp add ctxverify -- ctxv mcp --root /absolute/path/to/pack
```

Cursor, `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "ctxverify": {
      "command": "ctxv",
      "args": ["mcp", "--root", "/absolute/path/to/pack"]
    }
  }
}
```

The server implements `initialize`, `ping`, `tools/list`, `tools/call` and `shutdown`. It reports protocol version `2025-06-18`. It does not implement resources or prompts. If `--root` is set, tool calls that omit `path` use it.

See [docs/agents.md](docs/agents.md) for the full agent loop, including prompt text and the multi-agent action workflow.

## How it relates to llmwiki and other tools

`ctxverify` is not the first linter in this space, and it does not claim to be. The nearest existing tool is [llmwiki](https://github.com/atomicstrata/llm-wiki-compiler) (MIT). It compiles sources into a markdown wiki and has both `llmwiki lint` and `llmwiki eval`. Read from its own documentation on 2026-11-05, its lint covers broken wikilinks, duplicate concepts, broken or malformed citation markers, empty or orphaned pages, stale pages, low confidence, contradicted pages, paragraphs without citations and schema cross-link violations; its eval reports a health score, citation coverage and precision, judge-scored citation support, source utilization, claim-level citation rate and graph health. That is a real linter, and this is a comparison of scope, not a claim that the other project is missing the basics.

That is a real linter, and it is more than a link checker. The difference is scope.

| | ctxverify | llmwiki |
|---|---|---|
| What it judges | Any pack that implements the Context Pack Format, from any compiler | Its own compiled wiki and profile contract |
| Lint | Yes | Yes, `llmwiki lint` |
| Health score / eval | No | Yes, `llmwiki eval` |
| Exchange format | Context Pack Format, specified separately in `SPEC.md` | OKF |
| Provenance granularity | Each claim has its own evidence records and locators | Page-level and paragraph-level citation markers |
| Adapter for the other tool | `ctxv export llmwiki` | Not applicable |
| Reported-action verification | `action.unverified` checks an agent's report against the filesystem | Not part of its lint or eval |
| Pack hygiene | Credentials and personal contact details | Not part of its published lint list |
| Output | text, JSON, SARIF, exit codes | Its own reports |
| License | Apache-2.0 code, CC-BY-4.0 specification | MIT |

The positioning, stated plainly:

1. **Vendor-neutral.** `ctxverify` judges any pack, including llmwiki's output through `ctxv export llmwiki`. llmwiki's lint knows llmwiki's own layout and profile contract.
2. **A published format, separately licensed.** The format is specified in `SPEC.md` under CC-BY-4.0 so that anyone may implement it. The implementation is Apache-2.0. The intent is a standard, not a product.
3. **Claim-level provenance.** Each assertion maps to its own evidence records and locators, rather than to a paragraph on a page.
4. **Reported-action verification.** `action.unverified` checks what an agent says it did against what the filesystem shows. Knowledge tools do not do this.
5. **Pack hygiene.** A pack travels between tools and people. Credentials and contact details should not travel with it.

## Who it is for

- You compile knowledge into a pack and give it to an agent.
- You run more than one compiler and want one judge for all of their output.
- You let agents move, archive, write or delete files, and you want their reports checked.
- You ship packs to other people and want credentials and contact details caught before they leave.
- You want lint output in CI as SARIF, or as an MCP tool inside an agent loop.

## Who it is not for

- You need a compiler. Use llmwiki or your own compiler; `ctxverify` does not generate knowledge.
- You need retrieval, embeddings or a vector store. `ctxverify` does not retrieve anything.
- You need a quality score or a judge-scored evaluation. `ctxverify` reports rule violations, not a health score.
- You need the linter to prove that a source file exists, that a locator's line range is correct, or that a quote appears in the source. It checks internal consistency: that the quote matches its own recorded hash, that ids resolve, that references resolve. Verifying the source itself is the compiler's job; `verify-actions` only checks filesystem state for actions an agent reported.
- Your knowledge is not in a pack and you will not write an adapter.

## License

The implementation is licensed under [Apache-2.0](LICENSE). The format specification in [SPEC.md](SPEC.md) is dual-licensed under [CC-BY-4.0](LICENSE-SPEC) so that other implementations may use it.

## Contributing

```bash
git clone https://github.com/arronfly/ctxverify
cd ctxverify
pip install -e ".[dev]"
python -m pytest
```

Rule ids are part of the public contract. CI configurations select them, so do not rename an existing id. To add a rule, add it to `src/ctxverify/rules.py`, implement the check under `src/ctxverify/checks/`, register it, add a fixture that fails for the right reason, and add a test that asserts the rule fires and the clean pack stays clean. `examples/clean-pack` must continue to produce zero findings, and `examples/broken-pack` must continue to fail.

The format is versioned. Readers do not reject unknown keys: claims, evidence, sources, entities, relations, contradictions and the manifest all preserve them, so a pack written by a newer compiler remains checkable by an older linter and survives a load and write cycle intact.
