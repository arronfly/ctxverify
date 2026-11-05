# Example — a pack with something wrong in it

Every problem in this pack was planted on purpose, one per rule. Run the
linter and you should see:

```bash
ctxv check examples/broken-pack
```

| What is wrong | Rule that catches it |
|---|---|
| A claim marked `verified` with no evidence | `provenance.missing` |
| Evidence pointing at a claim and a source that do not exist | `provenance.dangling` |
| An evidence record with an empty quote | `provenance.quote` |
| A quote whose hash no longer matches its text | `provenance.quote` |
| A wikilink that resolves to nothing | `links.broken` |
| Two claims sharing the id `clm-003` | `ids.duplicate` |
| Two files both numbered `C-001` | `ids.collision` |
| A relation to an entity and evidence that do not exist | `status.inconsistent` |
| An inference with no reasoning recorded | `status.inconsistent` |
| A contradiction still open | `contradiction.unresolved` |
| A claim whose review window expired long ago | `freshness.stale` |
| Two claims stating exactly the same thing | `duplicate.claim` |
| A source no evidence points at | `orphan.source` |
| An entity no claim mentions | `orphan.entity` |
| An assigned credential sitting in a claim | `hygiene.secret` |
| An email address in a quote | `hygiene.pii` |
