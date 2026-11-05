# Wiring ctxverify into an agent loop

An agent reporting on its own work is an unchecked assertion. The report and the artifact are written by the same system, at the same time, with the same blind spots. `ctxverify` adds an independent check at the points where an agent hands work back: before it claims a pack is ready, before it claims files were moved, and before a change is committed or merged.

There are four integration points.

| Point | Command or tool | What it gates |
|---|---|---|
| Inside the agent | MCP `check_pack`, `verify_actions` | The agent's own report before it is sent |
| Before commit | pre-commit hook running `ctxv check` | A pack that cannot pass a local check |
| In CI | `ctxv check` exit code, SARIF upload | The merge |
| After file operations | `ctxv verify-actions` | Claims that archived, moved, wrote or deleted files |

## MCP server

`ctxv mcp` speaks MCP over stdio and exposes four tools. It has no dependencies, so it can be installed alongside an agent without another package manager.

| Tool | Arguments | Returns |
|---|---|---|
| `check_pack` | `path`, `strict`, `min_severity`, `exclude_rules` | The report object plus `verdict`, `status`, `strict`, `counts`, `reported`, `total_findings` and `total_counts` |
| `list_claims` | `path`, `status`, `topic`, `limit` | Claim ids, text preview, status, confidence, evidence count, topics |
| `get_claim` | `path`, `claim_id` | One claim plus its evidence, source paths, locators and quote previews |
| `verify_actions` | `actions`, `root` | `{"verified": bool, "findings": [...]}` |

`strict` is honoured by `check_pack`: warnings and information findings make the verdict `fail` when it is set. `get_claim` for an id that is not in the pack returns `isError: true` with the message, rather than a success payload with no claim. `list_claims` with `limit: 0` returns no claims; an absent `limit` defaults to 100.

### Claude Code

Project scope, `.mcp.json` in the repository root:

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

Or register it from the command line:

```bash
claude mcp add ctxverify -- ctxv mcp --root /absolute/path/to/pack
```

Use an absolute path. The server process inherits the working directory of the client, which is not always the repository root.

### Cursor

`~/.cursor/mcp.json` for a global server, or `.cursor/mcp.json` in the project:

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

### What the agent sees

A `check_pack` call returns the same report object as `ctxv check --format json`, plus a `verdict` of `pass` or `fail`. One case differs: an unreadable pack makes the CLI exit `2` with no JSON on stdout, while the MCP tool returns `isError: true` with the message in its content. The agent sees the reason either way, but a client that parses the payload must check `isError` before it reads a report that is not there.

```json
{
  "tool": "ctxverify",
  "tool_version": "0.1.0",
  "pack": "examples/clean-pack",
  "checked_at": "2026-11-05T14:10:53+00:00",
  "duration_ms": 0,
  "strict": false,
  "status": "pass",
  "counts": {"error": 0, "warning": 0, "info": 0},
  "stats": {"claims": 2, "evidence": 2, "entities": 1, "relations": 0, "contradictions": 0, "sources": 2, "freshness_entries": 2},
  "findings": [],
  "reported": 0,
  "total_findings": 0,
  "total_counts": {"error": 0, "warning": 0, "info": 0},
  "verdict": "pass"
}
```

`duration_ms` is a real measurement now, in milliseconds. It can legitimately be `0` on a small pack; treat it as a rough signal, not a benchmark.

Two details matter when an agent interprets the result:

- `verdict` is the exit-code style judgement and it honours `strict`. The payload's `strict` boolean, its `status` string and `verdict` all agree: pass `strict: true` and a pack whose only findings are warnings returns `strict: true`, `status: "fail"` and `verdict: "fail"`. Gate on `verdict`, or on the CLI exit code.
- `min_severity` filters the listing only. `verdict`, `status` and `total_counts` always describe the run before the filter; `counts` counts the findings that were listed, `reported` says how many were listed, and `total_findings` says how many the run produced. `min_severity: "error"` on a pack with one error and many warnings returns `verdict: "fail"` and `counts` of `{"error": 1, "warning": 0, "info": 0}`, while `total_counts` still shows the warnings. A filtered response cannot hide a failure: if the pack has an error, `verdict` is `fail` and `total_counts` still counts it.

`exclude_rules` takes check group names or full rule ids, the same two forms as `--exclude-rule`. `["hygiene"]` excludes both hygiene rules. `["hygiene.secret"]` excludes only that one. The group for `action.unverified` is `actions`, plural.

## Prompt-level guidance

The most reliable integration is telling the agent, in its instructions, that checking is part of the task. A short block is enough:

```text
Before you report a task as complete:

1. If you produced or modified a context pack, call the ctxverify check_pack tool
   on the pack directory. Fix every error. If you intentionally leave a warning,
   say which warning and why.
2. If you moved, archived, wrote or deleted files, call verify_actions with one
   record per file. Do not summarise the work until the verifier confirms it.
3. Never describe an action as done when verify_actions returns verified: false.
   Report the finding instead.
```

Three properties make this work:

- The instruction is conditional, so it does not fire on tasks that touch no pack and no files.
- It names the tool, so the agent does not have to infer which check applies.
- It requires reporting a failure, not retrying silently until the output looks clean.

If your agent framework supports tool-use policies, make `check_pack` mandatory after any write to a pack directory. The MCP server's `initialize` response already includes this instruction: "Check a context pack after writing it. Use check_pack on the pack you just produced; fix what it reports before you report the work as done."

## The loop

```text
write pack
  -> check_pack
      -> no errors: continue
      -> errors: read findings, fix, check again
  -> verify_actions (if files changed)
      -> verified: report the work
      -> not verified: fix the files or correct the report
```

A concrete CLI equivalent:

```bash
ctxv check ./pack --format json > report.json
# read report.json, fix the findings
ctxv verify-actions actions.jsonl --root ./pack
```

When the agent cannot fix an error, it should report the finding rather than downgrade the claim or delete the evidence. A pack that says "this claim is asserted, not verified" is more useful than a pack that lies about being verified.

## verify-actions for multi-agent file operations

This is the check for the failure mode that motivated the project: several agents each report that they archived the same files, and none of them did.

The input is JSONL, one action record per line:

```jsonl
{"id": "a-001", "action": "archived", "path": "notes/C-001_Context Packs.md"}
{"id": "a-002", "action": "moved", "path": "concepts/C-001_Context Packs.md", "from": "notes/C-001_Context Packs.md"}
{"id": "a-003", "action": "wrote", "path": "concepts/C-003_Linting.md", "sha256": "0000000000000000000000000000000000000000000000000000000000000000"}
{"id": "a-004", "action": "deleted", "path": "notes/old-draft.md"}
{"id": "a-005", "action": "archived", "paths": ["concepts/C-002_Evidence.md", "concepts/C-999_NotThere.md"], "count": 2}
```

Run it against the directory the paths are relative to:

```bash
$ ctxv verify-actions examples/actions.jsonl --root examples/obsidian-vault
ctxverify 0.1.0 — examples/obsidian-vault
  FAIL  3 error(s), 0 warning(s), 0 info

ERROR   action.unverified — Reported actions really happened
    - action a-001 reports 'notes/C-001_Context Packs.md' as archived, but it does not exist  actions.jsonl#a-001
    - action a-003 reports content hash 000000000000… for 'concepts/C-003_Linting.md', actual 8474779cbaca…  actions.jsonl#a-003
    - action a-005 reports 'concepts/C-999_NotThere.md' as archived, but it does not exist  actions.jsonl#a-005
```

Exit code `0` means every record is consistent with the filesystem. Exit code `1` means at least one record is not. Exit code `2` means the actions file could not be read, or one of its lines is valid JSON that is not an object; `ctxv check --actions <file>` returns the same `2` for the same file, so the two commands agree on what an unusable input means.

### Action semantics

| Action | Passes when |
|---|---|
| `archived` | Every listed path exists |
| `exists` | Every listed path exists |
| `wrote` | Every listed path exists, and every supplied `sha256` matches |
| `deleted` | Every listed path does not exist |
| `moved` | Every listed new path exists, and the `from` path does not |

Other checks:

- `count`, when supplied, must be readable as an integer and must equal the number of paths.
- `paths`, when supplied, must be a list.
- A `moved` record must name a `from` path: a move has two ends, and without the old one there is nothing to check.
- Every path, `from` included, must stay inside the root. An absolute path, a `~` path or one that resolves outside the root is reported as "names a path outside the root" and is not stat'd. The root is a boundary: it stops an agent from using the verifier to confirm the existence of, and disclose the hash of, any file the user can read.
- `sha256` is checked for any action when the file exists and is a regular file.
- Unknown action names and records with no path are findings.

### Working with several agents

Write one JSONL file per agent or per task, then verify each file against the same root. A merged file works too, but action ids must be unique across the merge; the verifier does not deduplicate records.

```bash
ctxv verify-actions actions/agent-01.jsonl --root ./workspace
ctxv verify-actions actions/agent-02.jsonl --root ./workspace
```

Keep one record per file when the record carries `from` or `sha256`. A `moved` record applies its single `from` to every path in `paths`, and a hash applies its single `sha256` to every path. If two files moved from different places, use two records.

Record actions when they happen, not from memory at the end. A record written after the fact describes what the agent believes it did; a record written during the work describes the call it actually made, and the verifier can still catch a call that failed silently.

The verifier checks filesystem state, not authorship. It can tell you the file exists and has the expected hash. It cannot tell you which agent wrote it.

## Pre-commit

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

The `repo: local` form works today with the `ctxv` you already have installed. `pass_filenames: false` is required: the hook checks a pack directory, not a list of changed files, so the directory is passed through `args` rather than appended by pre-commit. The `files` pattern decides when the hook runs; adjust it with a `files:` override if the pack is not the only JSON in the repository. With no `args`, the hook checks the current directory. If `ctxv` is installed inside a virtualenv, use `entry: .venv/bin/ctxv`.

Once the repository is tagged, the published hook is shorter:

```yaml
repos:
  - repo: https://github.com/arronfly/ctxverify
    rev: v0.1.0
    hooks:
      - id: ctxverify
        args: ["packs/knowledge"]
```

It fetches `.pre-commit-hooks.yaml` from the tag, which ships the same `files: \.(json|jsonl)$` and `pass_filenames: false`. Use it once the `v0.1.0` tag exists; until then, use `repo: local`.

## CI gating

The process exit code is the contract:

| Code | Gate behaviour |
|---|---|
| `0` | Pass |
| `1` | Fail: blocking findings |
| `2` | Fail: the pack or the actions file could not be read, an actions line is not a JSON object, or the command line is invalid, including an unknown `--rule` or `--exclude-rule` value |

The text header, the JSON `status` field and the exit code all agree, including under `--strict`: a pack with warnings renders `FAIL`, reports `"status": "fail"` and exits `1`. The JSON output also carries `"strict": true`. `min-severity` cannot change any of them, because it is a display filter applied after the exit code is computed. Gate on the exit code.

The repository ships a composite action in `action.yml`:

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

The action installs ctxverify from its own checkout and runs `ctxv check`, so a tagged action runs the code in that tag and does not depend on PyPI. It fails on exit code `1` or `2`. Its `min-severity` input defaults to `info`, so the log shows everything unless you narrow it. Filtering is display-only, so it never weakens the gate: `strict: true` fails the job on a pack that has warnings or information findings, and `min-severity` only decides how much of that is printed. Lower it when the log is noisy, not to make the job pass.

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

SARIF artifact locations are repository-relative: a location like `claims.jsonl#clm-001` stays as it is, and an absolute path is rewritten relative to the working directory when that works and dropped to the pack directory when it does not. That is what lets code scanning attach a finding to a file it can open.

If you only need the gate, drop the SARIF steps and keep the last one. If you want warnings to block, add `--strict` to the gate command; the log says `FAIL` and the JSON `status` says `fail`, so the report and the exit code tell the same story.

## A note on rule selection

`--rule` and `--exclude-rule` accept a check group or a full rule id. An unknown value is a usage error: the tool prints `ctxverify: unknown rule or check group: <name>`, lists the known groups and exits `2`, rather than silently selecting nothing. The group names are `actions`, `consistency`, `duplicates`, `freshness`, `hygiene`, `identity`, `links`, `orphans` and `provenance`:

```bash
ctxv check ./pack --rule provenance
ctxv check ./pack --rule provenance.missing
ctxv check ./pack --exclude-rule hygiene
```

Groups are usually the part of a rule id before the dot. The exception is `action.unverified`, whose group is `actions`, not `action`. A full rule id resolves to its group and then narrows the report to that one rule, so `--rule provenance.missing` reports only `provenance.missing` findings and `--exclude-rule provenance.missing` skips only those. You can generate these flags from a rule id directly; strip to the prefix only if you want the whole group. Loader findings (`pack.structure`) and `ctxverify.internal` are always included when `--rule` narrows the selection; `--exclude-rule pack.structure` and `--exclude-rule ctxverify.internal` drop them.

## Troubleshooting

**`ctxv: command not found` inside the agent.** The MCP client starts the process with a different `PATH`. Use an absolute path to the executable in the MCP config, or install it in an environment the client can see.

**Exit code 2 on a path that exists.** The path is a file, not a directory, or the pack cannot be opened. The message is written to stderr.

**A pack with warnings exits 0.** That is the default. Use `--strict` or change the rules' severity expectations.

**`action.unverified` is not a top-level command.** The subcommand is `verify-actions`. Within `ctxv check`, the flag is `--actions`.

**An action record with `paths` fails on `count`.** `count` must equal the number of entries in `paths`, not the number of files the agent thinks it touched.

**A moved file fails even though the new path exists.** The old path still exists. The verifier treats a move as incomplete if both paths are present.
