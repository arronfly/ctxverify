# Example — a pack that passes

This is what a healthy context pack looks like. Every claim has evidence,
every evidence record points at a source that exists, ids are unique, and the
freshness window is current.

```bash
ctxv check examples/clean-pack
# PASS  0 error(s), 0 warning(s), 0 info
```

## What is in here

| File | What it holds |
|---|---|
| `manifest.json` | Identity, the source list, and the inventory counts |
| `claims.jsonl` | Two atomic assertions, each with a status and evidence ids |
| `evidence.jsonl` | The quote and the locator that backs each claim |
| `entities.json` | One entity, with the alias it is also written under |
| `relations.json` | No relations in this example |
| `contradictions.json` | No contradictions in this example |
| `freshness.json` | The review window for each claim |
| `README.md` | This file |

The full format is specified in [SPEC.md](../../SPEC.md).
