# recall-mcp

**给 AI agent 用的间隔重复记忆卡片工具。** 一个零依赖的 [MCP](https://modelcontextprotocol.io) 服务器：让 Claude Code、Cursor、Codex 等编程 agent 直接帮你建卡、复习、按 SM-2 算法排下一次出现的时间。数据存在本地单个 SQLite 文件里，不联网、不花钱、没有账号。

*A zero-dependency MCP server for spaced-repetition flashcards. Pure Python standard library — SM-2 scheduling, SQLite storage, no SDK, no network, no cost.*

## 为什么做这个

背单词、记概念，最难的不是记，是**知道今天该复习哪些**。间隔重复算法（SM-2，SuperMemo 提出、Anki 沿用）按你的遗忘曲线排复习节奏。这个项目把这套算法包成 MCP 工具，agent 就能：

- 把你随手丢给它的单词、知识点做成卡片
- 每天告诉你哪些卡到期了
- 按你的评分（0–5）算好每张卡下次出现的日子

服务器只用 Python 标准库手写了 MCP 的 stdio 协议部分，没有第三方依赖，Python 3.10+ 任何环境都能跑——顺便也适合拿来读：一个最小可用的 MCP 服务器到底长什么样，这里就是完整答案。

## 快速开始

```bash
git clone https://github.com/mindnext-ai/recall-mcp.git
cd recall-mcp
pip install .
```

把服务器注册到你的 agent（Claude Code / Cursor / Codex 等 MCP 客户端通用格式）：

```json
{
  "mcpServers": {
    "recall": {
      "command": "python",
      "args": ["-m", "recall_mcp"],
      "env": { "RECALL_MCP_DB": "~/.recall-mcp/recall.db" }
    }
  }
}
```

然后就可以对 agent 说：「把这 20 个四级单词做成卡片放进 cet4 牌组」「今天有哪些卡要复习」「这张卡我完全忘了，评 1 分」。

## MCP 工具一览

| 工具 | 作用 |
| --- | --- |
| `create_deck` | 新建牌组 |
| `list_decks` | 列出牌组及卡片数、今日到期数 |
| `add_card` | 加一张卡（正面问题、背面答案） |
| `list_cards` | 列出牌组里的卡 |
| `due_cards` | 取今天到期的卡（可跨牌组） |
| `review_card` | 记录一次复习评分（0–5），SM-2 自动排期 |
| `deck_stats` | 牌组统计：总数、到期、新卡、平均难度系数 |
| `delete_card` | 删卡 |

## 命令行（给人用的）

同一个数据库还有一套 CLI，不通过 agent 也能用：

```bash
recall deck create cet4 --description "四级词汇"
recall card add cet4 --front "abandon" --back "v. 放弃；抛弃"
recall import cet4 examples/cet4_sample.json   # 附带 20 个四级词示例
recall due
recall review 3 5     # 卡片 id 3，评分 5
recall stats cet4
```

## SM-2 排期规则

- 评分 ≥ 3 算记住：间隔依次为 1 天、6 天、之后按 `上次间隔 × 难度系数` 增长
- 评分 < 3 算忘记：回到 1 天后重来，难度系数下调
- 难度系数（ease factor）随评分浮动，下限 1.3，答得越稳间隔拉得越长

实现在 `recall_mcp/sm2.py`，是纯函数，配有单元测试。

## 项目结构

```
recall_mcp/
  server.py   MCP 服务器（stdio JSON-RPC，标准库手写协议）
  store.py    SQLite 存储层
  sm2.py      SM-2 算法
  cli.py      命令行界面
examples/     示例牌组与客户端配置
tests/        单元测试 + 协议级端到端测试
```

## 测试

```bash
python -m unittest discover -s tests -v
```

## 协议

MIT
