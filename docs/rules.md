# Rule catalogue

This is the reference for every rule in `ctxverify 0.1.0`: sixteen rules about packs, plus `ctxverify.internal`, which reports ctxverify's own bugs. Rule ids are stable and are part of the public contract: CI configurations select them, and reports carry them. Do not rename an existing id.

Each finding has a rule id, a severity, a message, an optional location and an optional hint. The rule registry assigns every rule a default severity, but some rules emit findings at more than one severity depending on what they find. Both levels are documented below.

## How checks are grouped

The CLI's `--rule` and `--exclude-rule` flags and the MCP `exclude_rules` argument accept either a **check group** or a **full rule id**. The group names are the check names printed by `ctxv rules`: `actions`, `consistency`, `duplicates`, `freshness`, `hygiene`, `identity`, `links`, `orphans`, `provenance`. They are usually the part of a rule id before the dot; the exception is `action.unverified`, whose group is `actions`, not `action`.

A full rule id resolves to the group that implements it, and then narrows the report to that one rule. `--rule provenance` runs the whole provenance group; `--rule provenance.missing` runs the same check but reports only `provenance.missing` findings, leaving `provenance.dangling` and `provenance.quote` out of the report. The mapping lives in `RULE_GROUPS` in `src/ctxverify/rules.py`.

| Check group | Rules it can emit |
|---|---|
| `actions` | `action.unverified` |
| `consistency` | `status.inconsistent`, `contradiction.unresolved` |
| `duplicates` | `duplicate.claim` |
| `freshness` | `freshness.stale` |
| `hygiene` | `hygiene.secret`, `hygiene.pii` |
| `identity` | `ids.duplicate`, `ids.collision` |
| `links` | `links.broken` |
| `orphans` | `orphan.source`, `orphan.entity` |
| `provenance` | `provenance.missing`, `provenance.dangling`, `provenance.quote` |

`pack.structure` and `ctxverify.internal` are the two rules that do not come from a check group. `pack.structure` is emitted by the loader, and `ctxverify.internal` by the check runner when a check raises. Both always appear in the report, even when `--rule` selects another group or another rule: a pack that cannot be parsed cannot be judged, and a tool that crashed still has to say so. `--exclude-rule pack.structure` and `--exclude-rule ctxverify.internal` are the only way to drop them. `ctxv rules` prints the registered check names at the end of its output.

## Severity and exit codes

| Severity | Meaning | Blocks by default |
|---|---|---|
| `error` | The pack contradicts itself or cannot be trusted as written | Yes |
| `warning` | The pack is readable but a reviewer should look | No, unless `--strict` |
| `info` | Inventory information, not a defect | No, unless `--strict` |

`--min-severity` is a display filter. The exit code is always derived from the complete finding set, so a finding that is not printed can still fail the run. `ctxv check --min-severity error` on a pack whose only findings are warnings exits `0`, because no error exists; the same command on a pack with any error exits `1` even though only errors are printed.

The PASS/FAIL verdict in the text header and the JSON `status` field both reflect the full set, so a filtered view never reads PASS while the process exits `1`. The counts printed beside the text header also cover every finding the run produced, not just the printed ones: `ctxv check --min-severity error` on a pack with 13 errors, 8 warnings and 2 information findings prints `FAIL  13 error(s), 8 warning(s), 2 info` and then lists only the error findings.

The JSON payload keeps the two views in separate fields. `findings` and `counts` describe what the filter allowed through, `reported` is the number listed, `total_findings` is the number the run produced, and `total_counts` is the counts of every finding the run produced. So `counts` and the text header are not the same number whenever a severity filter is active: the header counts every finding the run produced (the whole pack, unless `--rule` narrowed the run), while `counts` counts the shown findings.

## pack.structure

**Default severity:** error or info, depending on the finding

**Detects:** A pack cannot be judged at all, or a collection cannot be read. This covers, at error severity:

- One or more of the eight required files is missing.
- A `.json` file is empty.
- A `.json` file is not valid JSON.
- A JSONL file has a line that is not valid JSON, or a line that is not a JSON object.
- `manifest.json` does not contain a JSON object.
- `manifest.json` omits a required field: `pack_id` or `sources`.
- `manifest.json` gives a field the wrong type: `generator`, `stats` and `verification` must be objects, and `sources` must be an array of objects.
- `entities.json`, `relations.json` or `contradictions.json` is not an object holding an `entities`, `relations` or `contradictions` array. A bare array, an empty object and a wrong key all produce an error naming the file and the expected key.
- `freshness.json` is not a JSON object. A bare array is an error rather than an empty policy. Its `policy` must be an object, `policy.per_topic` must be an object, and a `claims` value that is not an object is an error when it holds anything.
- A claim's `evidence`, `entities`, `topics` or `links` value is not an array, or an evidence record's `locator` is not an object.
- A source `path` is missing, is not a string, or names a location outside the pack: an absolute path, a `~` path, or one that climbs out through `..`.
- `manifest.json` declares a `format_version` that is not `MAJOR.MINOR`. `0` and `0.1.5` are both errors; only a version shaped like `0.1` is accepted.
- `manifest.json` declares a `format_version` with a different major version. This build implements `0.1`, so `1.0` is an error.
- `freshness.json` policy has a `default_ttl_days` or `per_topic` value that is not a number, or that is negative. The bad value is reported and is not applied, so a policy of `-5` days does not also make every claim stale.

At info severity:

- `manifest.json` declares a newer minor of the same major, such as `0.2`. The pack is read, because minors are additive by rule, and the finding says so.

**Failure mode:** A pipeline writes `entities.json` as a string or with the wrong top-level key, or a merge conflict leaves `<<<<<<<` inside `claims.jsonl`. `ctxverify` names the malformed collection file instead of reading it as empty: the records are missing, and the report says why rather than letting the references fail one by one elsewhere. A field of the wrong type is a subtler case: the reader coerces it so the rest of the pack is still checked, and the finding names the field and the type it got.

**Fix:** Run `ctxv init <dir>` for a conforming skeleton. For a bad line, the finding names the file and line number. For a major-version mismatch, upgrade the linter or pin the pack to `0.1`. For a version that is not `MAJOR.MINOR`, write it as `0.1`. For a wrong collection shape, write `{"entities": [...]}`, `{"relations": [...]}` or `{"contradictions": [...]}`; the finding carries the exact shape as its hint. `freshness.json` must be `{"policy": {...}, "claims": {...}}`, and every TTL in the policy must be a non-negative number.

## provenance.missing

**Default severity:** error

**Detects:**

- A claim whose status is `verified` and whose evidence list contains no evidence record that exists in the pack: severity `error`.
- A claim whose status is `asserted` and whose evidence list contains no evidence record that exists in the pack: severity `warning`.

**Failure mode:** A compiler upgrades a claim to `verified` because a model said it was confident, without attaching the quote that supports it. A reader sees `verified` and treats the assertion as checked. The status is doing work the evidence is not.

**Fix:** Attach an evidence record, or downgrade the claim to `asserted`. If the claim came from reasoning rather than a source, use `inferred` and write the reasoning in `notes`.

## provenance.dangling

**Default severity:** error

**Detects:**

- An evidence record whose `claim_id` names no claim in the pack.
- An evidence record whose `source_id` names no source in `manifest.json`.
- An evidence record whose `claim_id` or `source_id` is empty. An empty id names nothing, so it is reported the same way as an id that names the wrong record.
- A claim whose `evidence` list names an evidence id that does not exist.

**Failure mode:** A recompile assigns new claim ids but keeps the old evidence file from the previous build. Every quote still exists, every claim still exists, and none of them point at each other. A consumer that joins on ids gets an empty result and reports no evidence, or worse, joins the wrong pair.

**Fix:** Regenerate evidence together with claims. If evidence is reused across builds, keep the claim ids stable. Delete evidence that no claim owns.

## provenance.quote

**Default severity:** error

**Detects:**

- An evidence record with an empty or whitespace-only `quote`.
- An evidence record with a `quote_sha256` that does not equal the sha256 of the UTF-8 bytes of `quote`.

**Failure mode:** Someone edits the quote to make it support a stronger claim, then forgets that the hash was recorded earlier. Or a compiler emits an evidence record with a locator but no quote, which cannot be checked by a human and cannot be checked by a machine.

**Fix:** Restore the original quote, or recompute `quote_sha256` after a deliberate edit and record why the quote changed. Never leave a quote empty; if there is no quotable text, the claim has no evidence.

The check compares the quote to its own recorded hash, case-insensitively: an upper-case hex digest is accepted. It does not fetch the source file and confirm that the quote appears there.

## links.broken

**Default severity:** error

**Detects:**

- A link on a claim whose `resolved` field names a path that is not in the manifest source list. The path is compared case-insensitively, the way the resolver compares it, so `Notes/A.MD` matches `notes/a.md`.
- A link on a claim whose `resolved` is absent or null whose target does not resolve against the manifest paths and source aliases. The checker re-resolves it; the link is reported as an error only when that resolution also fails.
- With `--scan-text-links`, a `[[wikilink]]` inside claim text that does not resolve.

**Failure mode:** A note is renamed or deleted. The claim that referenced it still reads as if the reference works. In an Obsidian vault this is the most common rot: the text says "see [[C-001]]" and `C-001` now belongs to a different file.

**Fix:** Update the link target, restore the file to the manifest, or remove the link. Resolution follows Obsidian rules: alias first, then exact path, path with `.md`, lowercase path, path suffix, basename without extension, lowercase basename, path suffix by stem. `[[target|label]]` and `[[target#heading]]` are stripped to `target`.

Three details are worth knowing:

- The index is built from `manifest.json` source paths plus the `aliases` array a source may carry. A link to one of those aliases resolves to that source, which is how Obsidian resolves a note's frontmatter aliases. The Obsidian adapter writes them onto the source record and uses them when it resolves note-to-note links.
- Entity names and entity aliases are a separate namespace. They resolve entity references, not links to files, so a link whose target is an entity name is reported as `links.broken` with a hint saying the name is an entity and should be referenced through the claim's `entities` field. Without that separation, a link to a missing file would look resolvable just because an entity happened to share its name.
- A deleted source file is not detected unless a link or an action record points at it. The pack format records source paths; `ctxverify` does not stat them.

## ids.duplicate

**Default severity:** error

**Detects:**

- An id used more than once within one collection: claims, evidence, entities, relations, contradictions or sources.
- A record with an empty id.

Ids are compared within a collection, not across collections. A claim id and an entity id may collide without a finding.

The location of a duplicate finding names the file the collection lives in, so it is a pointer the reader can follow: `claims.jsonl`, `evidence.jsonl`, `entities.json`, `relations.json`, `contradictions.json`, or `manifest.json` for a duplicated source id.

**Failure mode:** Two `clm-003` records are appended by a merge. Any consumer that builds a dictionary keyed by id keeps the last one, so one claim disappears without an error. The pack still reports nine claims in `stats` while the consumer can only retrieve eight.

**Fix:** Make ids unique. If two compilers wrote the same id, renumber one side and update every reference to it: evidence `claim_id`, claim `evidence`, relation `claim_id` and `evidence`, contradiction `claims`, and freshness keys.

## ids.collision

**Default severity:** error

**Detects:** Two or more source entries in `manifest.json` that claim the same number within one namespace. A number is taken from a source's `number` or `编号` field when it matches `PREFIX-123`, or from a filename that starts with that shape followed by an underscore. The source's own `id` is not a number: it identifies the source record, not a document in a series.

A source may carry a `namespace` field, and numbers are then compared within a namespace; a source without one belongs to the default namespace. The Obsidian adapter reads `namespace` or `编号空间` from frontmatter.

**Failure mode:** `C-001_Context_Packs.md` and `C-001_Evidence.md` both exist because two imports each started numbering at one. Every reference to `C-001` is ambiguous, and every link, index entry and citation built on that number is unreliable. The same pair in two different directories is more likely to be two deliberate numbering spaces, which is why the hint says so.

**Fix:** Renumber one file and update its references. If the number is meaningful, keep a single owner per number and choose a different prefix for the other series. If two directories really are separate numbering spaces, give the sources a `namespace` and declare it instead of renumbering.

The underscore matters. A number is inferred from a filename only when the number is followed by an underscore, so `C-001_Title.md` carries `C-001` but `acme-1077-transmission-pricing.md` is a document id, not card number 1077, and will not collide with its siblings. A file named exactly `C-001.md` carries no number from its filename at all; give the source a `number` field if it should.

## status.inconsistent

**Default severity:** error or warning, depending on the finding

**Detects, at error severity:**

- A claim status that is not one of `asserted`, `verified`, `inferred`, `disputed`, `refuted`.
- A claim with no text.
- A claim that lists an evidence record whose `claim_id` points at a different claim.
- A claim that references an entity id not present in `entities.json`.
- A relation that names no `type`, or names one that is empty or whitespace. The reader does not fill in a default: without a type the edge says nothing about how the two entities relate.
- A relation whose `from` or `to` entity does not exist.
- A relation whose `claim_id` does not exist.
- A relation whose `evidence` list names an evidence id that does not exist.

**Detects, at warning severity:**

- A claim marked `inferred` with no text in `notes`. An inference without a stated chain is indistinguishable from a guess.
- A claim marked `disputed` or `refuted` that no contradiction entry references. A disputed claim needs the contradiction it takes part in.

**Failure mode:** A relation points at `ent-404` after an entity merge. Or a claim says `disputed` but the pack contains no record of what disputes it, so the reader cannot evaluate the dispute. Or a model infers a conclusion and writes no reasoning, and the next reader cannot tell inference from invention.

**Fix:** Correct the status, add the missing `notes`, add the contradiction entry, or fix the reference. When a claim cites evidence, make sure the evidence's `claim_id` points back at that same claim. Every relation needs a non-empty `type`; write `related_to` yourself if that is genuinely all you mean.

## contradiction.unresolved

**Default severity:** error or warning

**Detects, at error severity:** A contradiction entry that names a claim id not present in the pack.

**Detects, at warning severity:**

- A contradiction with `status: "open"`.
- A contradiction with `status: "resolved"` but no non-empty `resolution`.
- A contradiction that names fewer than two claims.

**Failure mode:** The pack contains two claims that cannot both be true, such as "the wiki ships unchecked" and "the wiki is checked before shipping". The contradiction is recorded and left open. An agent reading the pack picks whichever claim appears first and presents it as fact. The pack knew about the conflict; the agent did not.

**Fix:** Resolve the contradiction and write the resolution, or mark one claim `refuted` and keep the contradiction record that explains why. If the contradiction is real and unresolved, leave it open and make sure the consumer is told that the pack contains conflicting claims. The warning is a signal, not noise.

`status` is conventionally `open` or `resolved`. Other values are preserved without a dedicated check.

## freshness.stale

**Default severity:** warning

**Detects:**

- A claim whose `expires_at` is in the past.
- A claim with no `reviewed_at` whose source date is older than the applicable TTL. The source date is `freshness.json` `source_date`, falling back to the claim's `updated_at`, then `created_at`. The TTL is the first matching entry in `policy.per_topic` for the claim's topics, falling back to `policy.default_ttl_days`. If neither is set, the age check is skipped.

Both findings can fire for the same claim.

Policy values are validated by the loader, not by this check. A `default_ttl_days` or `per_topic` value that is not a number, or that is negative, is a `pack.structure` error and is not applied: the claim is not additionally reported as stale under a policy that says `-5` days. Because the loader raises it, the finding survives `--rule` narrowing even when the freshness check itself is not selected.

**Failure mode:** A claim about pricing, a vendor's product status or a policy is compiled once and never reviewed. Two years later an agent quotes it as current. The pack has no marker that the claim is old, because nobody recorded a review window.

**Fix:** Review the claim and extend `expires_at`, or record `reviewed_at`. If the TTL does not fit the topic, add a `per_topic` override. If the claim is no longer true, remove it or mark it `refuted`.

`decay` and `last_verified` are carried through the format and written back by the writer, but no check interprets them today.

## duplicate.claim

**Default severity:** warning

**Detects:** Two or more claims whose text is identical after NFKC normalisation, lowercasing and removal of whitespace and punctuation, including CJK punctuation.

**Failure mode:** A recompile appends to the existing claims file instead of reconciling it. The same fact now appears twice with different ids, different confidence and possibly different evidence. A consumer that counts claims overstates coverage; a consumer that deduplicates by text has to decide which record wins.

**Fix:** Keep one claim and merge its evidence and topics into it. If the two statements only look identical after normalisation but mean different things, make the text distinguish them.

## orphan.source

**Default severity:** info

**Detects:** A source in `manifest.json` that no evidence record cites.

**Failure mode:** A compiler ingests a large source, extracts nothing from it, and leaves it in the manifest. The pack reports more sources than it actually used, and a reader assumes the source contributed.

**Fix:** Remove the source from the manifest, or attach the evidence that came from it. This is informational because ingesting a source and then not using it is a normal part of compilation.

## orphan.entity

**Default severity:** info

**Detects:** An entity that no claim's `entities` list and no relation's `from` or `to` references.

**Failure mode:** An entity extraction pass creates entities for every capitalized phrase. The pack carries hundreds of entities that support nothing and appear in no relation. Search and navigation over the pack return dead ends.

**Fix:** Remove the entity, or reference it from the claim or relation that justifies it.

## hygiene.secret

**Default severity:** error

**Detects:** A credential-shaped string anywhere a human would read in the pack: claim text, claim notes, claim link targets, evidence quotes, entity names and entity `properties` values (including strings inside a list), relation notes, contradiction descriptions, source titles, source paths and source URLs, the manifest's `title`, `description` and `generator` values, and the pack `README.md`. Patterns cover GitHub tokens (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`), Anthropic keys, OpenAI-style `sk-` keys, AWS access key ids, Google API keys, Slack tokens, private key blocks, JWT-shaped strings, and assignments such as `api_key = ...`, `password: ...` or `access_token=...`.

**Failure mode:** A claim quotes a configuration file, or a README explains how to call an API and includes a real token. The pack is committed, shared with a vendor, or pasted into a support ticket. The token travels with it.

**Fix:** Remove the value from the pack. If it was real, rotate it. Quote the shape of the credential, not the credential.

## hygiene.pii

**Default severity:** warning

**Detects:** An email address, a labelled phone number, a mainland China mobile number or an 18-character national id number in the narrower list this rule scans: claim text and notes, evidence quotes, entity names, relation notes, contradiction descriptions and the pack `README.md`. It deliberately does not scan claim link targets, entity `properties`, source titles, paths or URLs, the manifest, or `generator` values: contact details are sometimes the point of a record, so this scan stays on the fields where they are least likely to belong. `--no-pii` disables this rule; `hygiene.secret` still runs and still covers the whole list.

**Failure mode:** Evidence quotes an email from a source document, or a README lists a personal contact for support. The pack is shared between tools and people, and the contact detail travels further than intended.

**Fix:** Remove or redact the detail. If the contact is essential, replace it with a role address that is meant to be published. Review whether the quote needs the contact detail at all.

## action.unverified

**Default severity:** error

**Detects:** An agent's reported action that the filesystem contradicts. Input is a JSONL file of action records, one object per line. Blank lines and lines starting with `#` are skipped.

Every other line must be a JSON object. A line that is valid JSON but not an object is an error, not a line to skip: `ctxv verify-actions` and `ctxv check --actions` both exit `2`. A report that the verifier silently ignored would be a report nobody checked, and the exit code would say everything is fine.

| Field | Meaning |
|---|---|
| `id` | Action id. Defaults to `line-<n>` when absent |
| `action` | One of `archived`, `moved`, `deleted`, `wrote`, `exists` |
| `path` | A single path relative to the root |
| `paths` | A list of paths, used when the action covers several files. A value that is not a list is an error |
| `from` | For `moved`, the old path. Required: a move has two ends, and without the old one there is nothing to check |
| `sha256` | For `wrote` or any existing file, the expected content hash |
| `count` | Expected number of files. Read as an integer, and must equal the length of `paths`; a value that cannot be read as an integer is an error |

`path`, `paths` and `from` are relative to the root and may not escape it. An absolute path, a `~` path, or a path that resolves outside the root is reported as "names a path outside the root", and the verifier does not stat it. The root is a boundary, not a convenience: without it, an agent could use the verifier to confirm the existence of — and disclose the hash of — any file the user can read. Both `ctxv verify-actions --root <dir>` and `ctxv check --actions <file> --actions-root <dir>` enforce it.

Findings:

- Unknown action name.
- No path supplied.
- `paths` is present but is not a list.
- A path or `from` names a location outside the root.
- `count` cannot be read as an integer, or does not equal the number of paths.
- A `moved` record names no `from` path.
- `archived`, `exists` or `wrote`: the path does not exist.
- `deleted`: the path still exists.
- `moved`: the new path does not exist, or the old path still exists.
- `sha256` supplied and the file exists: the actual hash differs.

**Failure mode:** Eight agents each report "archived" for the same files. Not one of them moved anything. The report was the only thing that was wrong, the filesystem was the truth, and nobody looked. A single false archive is enough to make every later report from that agent untrustworthy.

**Fix:** Run the action again, or correct the report. Do not report work the filesystem cannot confirm. The verifier checks filesystem state, not intent and not authorship: it can tell you the file is there, not who put it there.

## ctxverify.internal

**Default severity:** error

**Detects:** A check raised an exception. The finding names the check and the exception, and says so in its hint. This is a bug in `ctxverify`, not a defect in the pack: the two are never reported under the same id, because the fix is different and the reader should not go looking for a problem that is not in their files.

The other checks still run, so the report is incomplete rather than empty. The run does not read as clean: an internal error is an error, so the exit code is `1`. It is not filtered away by `--rule` narrowing and it cannot be filtered away by `--min-severity`, which only ever lists findings at or above a severity and this one is an error.

**Failure mode:** A pack contains a field shape that one check did not anticipate, and the check indexes it without guarding. Without this rule the exception either takes down the whole run or is swallowed, and the report describes a run that did not happen.

**Fix:** Change nothing in the pack on account of this finding. Report the bug, with the pack and the exception message; the message names the check that failed. If the same pack reports `pack.structure` or another rule alongside it, fix those separately.

## Rule selection pitfalls

`--rule` and `--exclude-rule` validate their arguments. An unknown rule id or check group prints `ctxverify: unknown rule or check group: <name>` followed by the list of known groups, and exits `2`:

```text
ctxverify: unknown rule or check group: provanance
  known groups: actions, consistency, duplicates, freshness, hygiene, identity, links, orphans, provenance
```

This is deliberate. A misspelt rule used to select nothing, which turned a failing pack into a PASS — the worst possible failure mode for a gate. `ctxverify.internal` and every rule id in the tables above are valid values; `pack.structure` is a valid rule id even though `pack` is not a group.

- `--rule provenance` runs the `provenance` check group and can emit `provenance.missing`, `provenance.dangling` and `provenance.quote`.
- `--rule provenance.missing` runs the same group but reports only `provenance.missing`; the other two provenance rules are filtered out of the report.
- `--rule actions` and `--rule action.unverified` are equivalent. Without `--actions <file>`, the group returns no findings because no action records were supplied. `--rule action` is a usage error, because `action` is neither a group name nor a rule id.
- `--exclude-rule hygiene` skips both `hygiene.secret` and `hygiene.pii`.
- `--exclude-rule hygiene.secret` skips only `hygiene.secret`.
- `--exclude-rule provenance.missing` skips only `provenance.missing`; the rest of the provenance group still runs.
- Loader findings (`pack.structure`) and `ctxverify.internal` are always included when `--rule` narrows the selection; `--exclude-rule pack.structure` and `--exclude-rule ctxverify.internal` are the only way to drop them.
