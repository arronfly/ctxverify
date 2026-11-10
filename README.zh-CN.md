# ctxverify

[![M8ven Score](https://m8ven.ai/badge/mcp/arronfly-ctxverify-1idj30?v=3c3d59d81c6c02b701066ecfb22791ea)](https://m8ven.ai/mcp/arronfly-ctxverify-1idj30?s=readme)

面向 agent context pack 的 linter 与验证器。

编译器生成知识，linter 判断知识。判断工具不应该属于编译器。

agent 会拿到一批知识：claim、来源、引文、实体、矛盾、复核日期。编译器把这批知识打成 context pack。随后 agent 信任它、在工具之间复制它、用它回答问题。如果 pack 内部不一致，agent 无从察觉：它会引用不存在的证据，重复一条已被撤回的事实，或者报告自己归档了从未碰过的文件。

`ctxverify` 加载一个 pack，按固定规则目录检查，输出 findings 和退出码，用法与 `eslint`、`ruff`、`tsc` 相同。它没有运行时依赖，要求 Python 3.10 或更高版本，只使用标准库。

## 没有判断工具时会出什么问题

一个 agent 完成清理任务，发来如下报告：

```jsonl
{"id": "a-001", "action": "archived", "path": "notes/C-001_Context Packs.md"}
{"id": "a-002", "action": "moved", "path": "concepts/C-001_Context Packs.md", "from": "notes/C-001_Context Packs.md"}
{"id": "a-003", "action": "wrote", "path": "concepts/C-003_Linting.md", "sha256": "0000000000000000000000000000000000000000000000000000000000000000"}
{"id": "a-004", "action": "deleted", "path": "notes/old-draft.md"}
{"id": "a-005", "action": "archived", "paths": ["concepts/C-002_Evidence.md", "concepts/C-999_NotThere.md"], "count": 2}
```

`ctxv verify-actions` 会逐条对照文件系统检查：

```bash
$ ctxv verify-actions examples/actions.jsonl --root examples/obsidian-vault
ctxverify 0.1.0 — examples/obsidian-vault
  FAIL  3 error(s), 0 warning(s), 0 info

ERROR   action.unverified — Reported actions really happened
    - action a-001 reports 'notes/C-001_Context Packs.md' as archived, but it does not exist  actions.jsonl#a-001
    - action a-003 reports content hash 000000000000… for 'concepts/C-003_Linting.md', actual 8474779cbaca…  actions.jsonl#a-003
    - action a-005 reports 'concepts/C-999_NotThere.md' as archived, but it does not exist  actions.jsonl#a-005
```

同一类错误也会出现在 pack 内部。一个标为 `verified` 但没有 evidence 记录的 claim，只是一句披着实验服外衣的断言。`ctxv check` 会把它报为 error：

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

`freshness.stale` 的天数取决于运行检查的日期。上面的输出记录于 2026-11-05。

## 什么是 context pack

context pack 是一个可移植目录，装的是交给 agent 的知识。它刻意保持朴素：JSON 和 JSONL 文件，没有数据库，没有服务端，不要求运行时。一个 pack 包含原子 claim、每条 claim 背后的 evidence、实体、关系、矛盾、新鲜度状态和 manifest。

| 文件 | 内容 |
|---|---|
| `manifest.json` | 格式版本、pack id、标题、生成器、来源清单、各项计数 |
| `claims.jsonl` | 每行一个 JSON 对象。每行一条原子断言，带状态和 evidence id |
| `evidence.jsonl` | 每行一个 JSON 对象。引文、locator、来源 id，以及它支撑的 claim id |
| `entities.json` | claim 涉及的命名实体，带别名和属性 |
| `relations.json` | 实体之间有类型的边 |
| `contradictions.json` | 不能同时成立的 claim 对，带状态和解决说明 |
| `freshness.json` | 复核策略，以及每条 claim 的复核日期和过期日期 |
| `README.md` | 给人看的概览。文件必须存在，其文本也会被扫描密钥和 PII |

一条 claim 和它的 evidence 如下：

```json
{
  "claims": {"id": "clm-001", "text": "A context pack is a portable container for the knowledge an agent is given.", "status": "verified", "confidence": 1.0, "evidence": ["ev-001"], "topics": ["ctxverify"]},
  "evidence": {"id": "ev-001", "claim_id": "clm-001", "source_id": "src-001", "quote": "A context pack is a portable container for the knowledge an agent is given.", "locator": {"path": "sources/notes.md", "line_start": 3, "line_end": 3}, "quote_sha256": "e78ad35b4aa7a0f107349ce5c3cacb61e0d9618a842af7f41876d9c9b7f2d542", "retrieved_at": "2026-11-05T00:00:00Z"}
}
```

磁盘上的目录是扁平的：

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

逐字段的生产指南见 [docs/format.md](docs/format.md)。

## 安装

```bash
pip install ctxverify
```

也可以直接从仓库装：

```bash
pip install git+https://github.com/arronfly/ctxverify.git
```

从源码安装：

```bash
git clone https://github.com/arronfly/ctxverify
cd ctxverify
pip install -e .
```

要求：Python 3.10 或更高版本。没有运行时依赖。

## 快速开始

```bash
$ ctxv init demo-pack --id demo --title "Demo Pack"
ctxverify: created pack at demo-pack
  next: ctxv check demo-pack
$ ctxv check demo-pack
ctxverify 0.1.0 — demo-pack
  PASS  0 error(s), 0 warning(s), 0 info
  pack: claims=1, evidence=1, entities=1, relations=0, contradictions=0, sources=1, freshness_entries=0
```

脚手架生成的 pack 能通过，是因为它内部一致，不是因为里面有什么有价值的内容。把示例 claim 和 evidence 换成你自己的，再运行一次 `ctxv check`。

`ctxv check examples/clean-pack` 输出同样的结构：

```text
ctxverify 0.1.0 — examples/clean-pack
  PASS  0 error(s), 0 warning(s), 0 info
  pack: claims=2, evidence=2, entities=1, relations=0, contradictions=0, sources=2, freshness_entries=2
```

## 命令

| 命令 | 作用 |
|---|---|
| `ctxv check <pack>` | 检查 pack。默认当前目录 |
| `ctxv init <dir>` | 生成符合格式的空 pack。参数：`--id`、`--title`、`--force` |
| `ctxv export obsidian <vault> --out <pack>` | 从 Obsidian 风格 vault 构建 pack。参数：`--id`、`--include`、`--exclude` |
| `ctxv export llmwiki <project> --out <pack>` | 从 llmwiki 项目构建 pack |
| `ctxv export markdown <dir> --out <pack>` | 从普通 markdown 目录构建 pack。参数：`--id`、`--include`、`--exclude` |
| `ctxv verify-actions <actions.jsonl> --root <dir>` | 对照文件系统检查 agent 报告的动作。参数：`--format text\|json` |
| `ctxv rules` | 列出规则目录 |
| `ctxv mcp` | 在 stdio 上运行 MCP server。参数：`--root` |

`ctxv check` 参数：

| 参数 | 作用 |
|---|---|
| `--format text\|json\|sarif` | 输出格式。默认 `text` |
| `--strict` | 除了 error，warning 和 info 也让退出码为 1 |
| `--rule <check>` | 只运行这一组检查，或只保留完整 rule id 所指定那条规则的 findings。可重复。组名就是 `ctxv rules` 末尾打印的 check 名：`actions`、`consistency`、`duplicates`、`freshness`、`hygiene`、`identity`、`links`、`orphans`、`provenance`。通常是 rule id 点号前的部分；例外是 `action.unverified`，它的组名是 `actions`。`--rule provenance` 运行整组；`--rule provenance.missing` 运行该组但只报 `provenance.missing` 的 findings。未知的 rule id 或组名是用法错误：工具会打印 `ctxverify: unknown rule or check group: <name>`，列出已知的组并退出 `2`，而不是什么都没选中。用 `--rule` 收窄时，loader 产生的 `pack.structure` 与 `ctxverify.internal` findings 始终出现 |
| `--exclude-rule <check>` | 跳过这一组检查，或只跳过指定的那一条规则。命名规则与 `--rule` 相同：`--exclude-rule hygiene` 跳过两条 hygiene 规则，`--exclude-rule hygiene.secret` 只跳过这一条。未知值同样是用法错误 |
| `--min-severity error\|warning\|info` | 显示过滤器：只列出不低于该严重度的 findings。表头的计数和 PASS/FAIL 仍然描述整个 pack，退出码也仍然反映全部 findings，因此过滤不会掩盖失败 |
| `--no-pii` | 跳过 `hygiene.pii`。`hygiene.secret` 仍然运行 |
| `--scan-text-links` | 同时解析 claim 正文里的 `[[wikilinks]]` |
| `--actions <file>` | 同时验证 agent 报告的动作。文件为 JSONL |
| `--actions-root <dir>` | 动作路径的相对根目录。默认是 pack 目录 |
| `--color` | 给文本报告上色 |
| `--quiet` | 不打印任何内容，只看退出码 |

退出码：

| 退出码 | 含义 |
|---|---|
| `0` | 干净。没有 error。除非设置 `--strict`，warning 和 info 可以通过 |
| `1` | 有阻断性 findings：至少一个 error，或 `--strict` 下的任意 finding |
| `2` | pack 完全无法打开：目录不存在、不是目录。`ctxv check --actions <file>` 与 `ctxv verify-actions <file>` 在读不了 actions 文件、或文件里某一行是合法 JSON 但不是对象时，都返回 `2`。非法命令行也会由 argparse 返回 `2`；未知的 `--rule` 或 `--exclude-rule` 值同样返回 `2` |

目录存在但缺少必需文件时退出码是 `1`，不是 `2`。工具能打开目录，因此报 `pack.structure`。

## 规则目录

`ctxverify 0.1.0` 带 16 条针对 pack 的规则，外加 1 条报告 ctxverify 自身 bug 的规则。

| Rule id | 默认严重度 | 检测内容 |
|---|---|---|
| `pack.structure` | error / info | 必需文件缺失；`.json` 文件为空或无法解析；manifest 缺少 `pack_id` 或 `sources`，或某个字段类型不对；`entities.json`、`relations.json` 或 `contradictions.json` 不是带集合数组的对象，或 `freshness.json` 不是对象；某个新鲜度 TTL 不是非负数；某个 source path 越出 pack；格式版本不是 `MAJOR.MINOR` 或主版本号不同（error）。同一主版本下的更新次版本会被读取并报为 info |
| `provenance.missing` | error / warning | `verified` claim 没有 evidence（error）；`asserted` claim 没有 evidence（warning） |
| `provenance.dangling` | error | evidence 指向不存在的 claim 或 source，或 claim 指向不存在的 evidence |
| `provenance.quote` | error | evidence 引文为空，或记录的 sha256 与引文文本不匹配 |
| `links.broken` | error | claim 的链接解析不到 manifest 里的任何文件。来源别名可以解析；实体名不可以，会附带「用 claim 的 `entities` 字段」的提示 |
| `ids.duplicate` | error | 同一集合内 id 重复，或 id 为空 |
| `ids.collision` | error | 同一命名空间内两个来源文件声明同一个编号，例如 `C-001` |
| `status.inconsistent` | error / warning | 状态义务和引用对不上，包括 relation 没有 `type`。结构性问题为 error；缺少理由或矛盾条目为 warning |
| `contradiction.unresolved` | warning / error | 矛盾处于 open、标为 resolved 但没有 resolution 文本、或少于两条 claim（warning）；引用了不存在的 claim（error） |
| `freshness.stale` | warning | 复核窗口已过期，或 claim 超过策略 TTL 未复核 |
| `duplicate.claim` | warning | 两条 claim 的规范化文本相同 |
| `orphan.source` | info | 没有任何 evidence 记录引用该 source |
| `orphan.entity` | info | 没有任何 claim 或 relation 引用该 entity |
| `hygiene.secret` | error | pack 中的字符串看起来像凭据 |
| `hygiene.pii` | warning | pack 中的字符串看起来像邮箱、电话或身份证号 |
| `action.unverified` | error | agent 报告的动作与文件系统矛盾 |
| `ctxverify.internal` | error | 某个检查抛了异常。这是 ctxverify 的 bug，不是 pack 的问题；`--rule` 与 `--min-severity` 都不会把它过滤掉 |

每条规则的检测逻辑、真实失败场景和修复方法见 [docs/rules.md](docs/rules.md)。

## CI 用法

以退出码为准。它始终反映本次运行产生的全部 findings，因此 `--min-severity` 可以收窄打印内容而不会削弱闸门；`--strict` 也会同时体现在报告里：PASS/FAIL 表头、JSON 的 `status` 字段和 JSON 的 `strict` 布尔值三者一致。

`--min-severity` 过滤的是列表，不是判断。文本表头统计的是本次运行产生的全部 findings，与过滤器隐藏了什么无关：`ctxv check --min-severity error` 跑在一个有 13 个 error、8 个 warning、2 个 info 的 pack 上，会打印 `FAIL  13 error(s), 8 warning(s), 2 info`，然后只列出 error 的 findings。当 pack 只有 warning 时，同一个命令不打印任何 finding 并退出 `0`，因为确实没有 error。同一个命令跑在一个有 1 个 error、多个 warning 的 pack 上仍然退出 `1`，尽管只打印了那 1 个 error。

JSON 输出把这两种视角放在不同字段里：`findings` 和 `counts` 是过滤器放行的部分，`reported` 是列出的条数，`total_findings` 是本次运行的产出条数，`total_counts` 是本次运行产生的全部 findings 的计数。`status` 是这次运行的判定。不要把 `counts` 和文本表头当成同一个数：表头数的是本次运行产生的全部 findings（没有用 `--rule` 收窄时就是整个 pack），`counts` 数的是被列出的 findings。

仓库自带一个 composite GitHub Action，定义在 `action.yml`：

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

action 从自己的 checkout 安装，因此打了 tag 的 action 跑的就是那个 tag 里的代码，仓库发布当天就能用。它运行 `ctxv check`，退出码为 `1` 或 `2` 时让 job 失败。`min-severity` 默认是 `info`，因此除非你主动收窄，所有 findings 都会打印。严重度过滤只是显示过滤：它改变日志内容，不改变闸门，所以 `strict: true` 现在会真的因为 warning 或 info 让 job 失败。

如果要把 SARIF 上传到 code scanning，直接运行 CLI：

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

第一步即使检查失败也会写出 SARIF。SARIF 里的 artifact 位置是相对仓库的，code scanning 才能把 finding 挂到文件上：`claims.jsonl#clm-001` 原样保留，绝对路径在可行时改写为相对当前工作目录的路径，不可行时退回 pack 目录。最后一步是闸门：退出码 `1` 会让 job 失败；pack 无法读取时的 `2` 也会让 job 失败。

pre-commit：

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

`repo: local` 这种写法今天就能用，配你已安装的 `ctxv` 即可。`entry` 是命令，`args` 是 pack 目录，`pass_filenames: false` 是必需的：hook 检查的是一个 pack 目录，不是变更文件列表。`files` 模式决定 hook 何时运行；如果仓库里的 JSON 不止 pack，用 `files:` 覆盖它。不传 `args` 时检查当前目录。如果 `ctxv` 装在 virtualenv 里，把 `entry` 指过去，例如 `entry: .venv/bin/ctxv`。

等仓库打好 tag 之后，用发布版 hook 更短：

```yaml
repos:
  - repo: https://github.com/arronfly/ctxverify
    rev: v0.1.0
    hooks:
      - id: ctxverify
        args: ["packs/knowledge"]
```

它会从该 tag 取 `.pre-commit-hooks.yaml`，其中自带同样的 `files: \.(json|jsonl)$` 和 `pass_filenames: false`。等 `v0.1.0` 这个 tag 存在之后再改用这种写法；在那之前用 `repo: local`。

如果 pack 在私有仓库里，且希望 SARIF 进入 code scanning，请从带有 `security-events: write` 权限的 job 上传。

## MCP 用法

`ctxv mcp` 通过 stdio 提供 MCP。它暴露四个工具：

| 工具 | 用途 |
|---|---|
| `check_pack` | 运行检查。参数：`path`、`strict`、`min_severity`、`exclude_rules`。`exclude_rules` 接受与 `--exclude-rule` 相同的 check 组名和完整 rule id |
| `list_claims` | 列出 claim 及状态和 evidence 数量。参数：`path`、`status`、`topic`、`limit` |
| `get_claim` | 返回一条 claim 及其 evidence 和来源路径。参数：`path`、`claim_id` |
| `verify_actions` | 对照文件系统检查报告的动作。参数：`actions`、`root` |

四个工具都显式声明了 MCP 的四个标准标注——`readOnlyHint`、`destructiveHint`、`idempotentHint` 和 `openWorldHint`，且都是布尔值，因为客户端无法推断。四个工具都是只读的：只读文件系统，不写入任何东西。

`check_pack` 的行为与 CLI 一致。它返回 `verdict`（`pass` 或 `fail`）、`status`、`strict`、`counts`（列出的 findings）、`reported`（列出条数）、`total_findings`（本次运行的产出条数）和 `total_counts`（本次运行产生的全部 findings 的计数）。`min_severity` 只过滤列表：`verdict`、`status` 和 `total_counts` 始终描述过滤之前的这次运行。`strict` 会被采纳，因此传入 `strict: true` 时，一个只有 warning、没有 error 的 pack 也会返回 `verdict: "fail"` 和 `status: "fail"`。`get_claim` 对不存在的 claim id 返回 `isError: true`；`list_claims` 传 `limit: 0` 返回空列表。与 CLI 的唯一差别是 pack 读不了：CLI 退出 `2` 且不输出 JSON，而 MCP 工具返回 `isError: true` 并在内容里带上错误信息。

Claude Code，项目级，`.mcp.json`：

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

或在命令行添加：

```bash
claude mcp add ctxverify -- ctxv mcp --root /absolute/path/to/pack
```

Cursor，`~/.cursor/mcp.json`：

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

server 实现 `initialize`、`ping`、`tools/list`、`tools/call` 和 `shutdown`。它报告的协议版本是 `2025-06-18`。它不实现 resources 或 prompts。设置 `--root` 后，未传 `path` 的工具调用会使用该目录。

完整的 agent 闭环、提示词文本和多 agent 动作工作流见 [docs/agents.md](docs/agents.md)。

## 与 llmwiki 及其他工具的关系

`ctxverify` 不是这个领域里第一个 linter，也不这样宣称。最接近的现有工具是 [llmwiki](https://github.com/atomicstrata/llm-wiki-compiler)（MIT）。它把来源编译成 markdown wiki，同时提供 `llmwiki lint` 和 `llmwiki eval`。按它自己 2026-11-05 的文档：lint 覆盖断掉的 wikilink、重复概念、损坏或格式错误的引文标记、空页面或孤岛页面、过期页面、低置信度、被矛盾页面、无引文段落、schema 交叉链接违规；eval 报告健康分、引文覆盖率与精确率、judge 评分的引文支持、来源利用率、claim 级引文率、图健康度。那是一个真的 linter，这里比的是适用范围的差别，不是说对方缺基础能力。

那是一个真实的 linter，而且比链接检查器做得多。区别在范围。

| | ctxverify | llmwiki |
|---|---|---|
| 判断对象 | 任何实现 Context Pack Format 的 pack，来自任何编译器 | 它自己编译的 wiki 和 profile 契约 |
| Lint | 有 | 有，`llmwiki lint` |
| 健康分 / eval | 没有 | 有，`llmwiki eval` |
| 交换格式 | Context Pack Format，单独在 `SPEC.md` 中规定 | OKF |
| 溯源粒度 | 每条 claim 有自己的 evidence 记录和 locator | 页面级和段落级引文标记 |
| 对另一方的适配器 | `ctxv export llmwiki` | 不适用 |
| 报告动作验证 | `action.unverified` 对照文件系统检查 agent 报告 | 不在其 lint 或 eval 中 |
| pack 卫生 | 凭据和个人联系方式 | 不在其公开的 lint 列表中 |
| 输出 | text、JSON、SARIF、退出码 | 自有报告 |
| 许可证 | 代码 Apache-2.0，规范 CC-BY-4.0 | MIT |

定位，直说：

1. **厂商中立。** `ctxverify` 判断任何 pack，包括通过 `ctxv export llmwiki` 转换的 llmwiki 输出。llmwiki 的 lint 只认识 llmwiki 自己的布局和 profile 契约。
2. **公开且单独许可的格式。** 格式在 `SPEC.md` 中规定，采用 CC-BY-4.0，任何人都可以实现。实现采用 Apache-2.0。目标是标准，不是产品。
3. **claim 级溯源。** 每条断言对应它自己的 evidence 记录和 locator，而不是页面上的一段话。
4. **报告动作验证。** `action.unverified` 检查 agent 声称做过的事与文件系统显示的事是否一致。知识工具不做这件事。
5. **pack 卫生。** pack 会在工具和人之间流动。凭据和联系方式不应该跟着流动。

## 适合谁

- 你把知识编译成 pack 并交给 agent。
- 你运行不止一个编译器，希望用同一个判断工具检查它们的输出。
- 你让 agent 移动、归档、写入或删除文件，并希望它们的报告被核对。
- 你把 pack 交付给别人，希望在离开之前抓到凭据和联系方式。
- 你希望在 CI 里得到 SARIF，或在 agent 闭环里把检查作为 MCP 工具使用。

## 不适合谁

- 你需要编译器。用 llmwiki 或你自己的编译器；`ctxverify` 不生成知识。
- 你需要检索、embedding 或向量库。`ctxverify` 不做任何检索。
- 你需要质量分或 judge 评分。`ctxverify` 报规则违规，不报健康分。
- 你需要 linter 证明来源文件存在、locator 的行号范围正确、或引文确实出现在来源里。它检查的是内部一致性：引文与它自己记录的哈希一致、id 能解析、引用能解析。验证来源本身是编译器的职责；`verify-actions` 只检查 agent 所报告动作对应的文件系统状态。
- 你的知识不在 pack 里，而且你不打算写适配器。

## 许可证

实现采用 [Apache-2.0](LICENSE)。[SPEC.md](SPEC.md) 中的格式规范采用 [CC-BY-4.0](LICENSE-SPEC) 双重许可，供其他实现使用。

## 贡献

```bash
git clone https://github.com/arronfly/ctxverify
cd ctxverify
pip install -e ".[dev]"
python -m pytest
```

Rule id 是公开契约。CI 配置会按 id 选择规则，因此不要重命名已有 id。新增规则时，在 `src/ctxverify/rules.py` 登记，在 `src/ctxverify/checks/` 下实现并注册，添加一个会因正确原因失败的 fixture，再补一个测试，断言规则会触发且干净 pack 保持干净。`examples/clean-pack` 必须继续产出零 findings，`examples/broken-pack` 必须继续失败。

格式是带版本的。读取方不拒绝未知字段：claim、evidence、source、entity、relation、contradiction 和 manifest 都会保留它们，因此新版编译器写出的 pack 仍可被旧版 linter 检查，读写一轮之后依然完整。
