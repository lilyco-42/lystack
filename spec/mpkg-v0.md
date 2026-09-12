# mpkg v0 —— 记忆包格式规范（Memory Package Format）

> 状态：P0 草案 v0 · 2026-09-12 · 作者：lyco_agent 预研（lyco OODA 循环产出）
> 一句话：**agent 干过的事，打包成可回放、可验证、content-addressed 的记忆原子，学习一次，所有 agent 复用。**

## 1. 目的与非目的

**目的**
- 把 agent 的一次完整工作（如"做一个贪吃蛇"）沉淀为可分发的记忆包：别人的 agent 搜到 → 本机回放验证 → 直接使用。
- 消除重复记忆学习与工作（信条 1 的市场化形态）。

**非目的（v0 明确不做）**
- 不做加密签名（v0 用 content-hash 锚定，v0.1 加 Ed25519 签名）
- 不做网络隔离执行（v0.1 由沙箱执行器兑现 `requirements.network=false` 声明）
- 不做视频知识蒸馏管线（`atoms[].ref` 字段已预留，管线属 P2）

## 2. 包结构

```
make-snake-game/            # 包目录
├── mpkg.json               # 清单（唯一必需文件）
├── artifacts/              # 不可变产物（源码、资源……）
└── atoms/                  # 知识原子（md/图片/视频切片引用）
```

打包后：`<name>-<version>-<id12>.mpkg`（zip）。

## 3. 清单字段（mpkg.json）

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `mpkg` | string | ✓ | 格式版本，恒为 `"0.1"` |
| `name` | string | ✓ | kebab-case 包名 |
| `version` | string | ✓ | semver |
| `intent` | string | ✓ | 一句话意图（搜索主键） |
| `author` | string | | `agent:<origin>` |
| `requirements.tools` | array | | `{"name","min_version"}`，回放前逐个 `which` 检查 |
| `requirements.os` | array | | windows/linux/android |
| `steps` | array | ✓ | 有序 CLI 命令，每条 `{"run","expect":{"exit"}}` |
| `verify` | array | ✓ | 验证命令，全过 → 包可信 |
| `atoms` | array | | `{"kind":"text\|image","path","title","ref"}`；`ref` 预留视频寻址：`video:<id>#t=1234,1256` |
| `provenance` | object | | openvibe 钩子（v0 预留，见 §8）：prompt 谱系与每步溯源 |
| `tags` / `license` | array/string | | 市场检索与合规 |

**铁律（工具优先）**：`steps` 只允许真实 CLI 进程调用——AI 编排工具、工具操作数据。禁止把"脚本改数据"塞进 steps：CLI 进程自带进程树、退出码、日志，天然可追踪可回放；这是记忆包可跨 agent 信任的技术前提。

## 4. 包 ID（content-addressed）

```
id = sha256( canon_json({ "manifest": <manifest 无 id 字段>, "files": { "<相对路径>": "<sha256>" … } }) )
```

- `canon_json`：`sort_keys` + 紧凑分隔符 + UTF-8。
- 文件集 = 包目录内除 `*.mpkg` 外全部文件。
- ID 即身份：市场按 ID 寻址，防篡改免费获得（改一个字节 = 另一个包）。

## 5. 回放协议（verify 命令）

1. 解包到临时目录 `{{pkg}}`，建空工作目录 `{{work}}`。
2. 逐条执行 `steps[].run`：`bash -c "<run>"`（cwd=`{{work}}`），逐条比对 `expect.exit`（默认 0），单步超时 120s。任一步失败 → 回放失败。
3. 依次执行 `verify[]`，同规则。
4. 全部通过 → 产出 **attestation**（回执）：

```json
{ "mpkg_id": "sha256:…", "ok": true,
  "steps": [ {"n":1,"exit":0,"ms":12} … ],
  "verify": [ {"cmd":"…","exit":0} ],
  "host": {"os":"…","python":"…"}, "replayed_at": "…" }
```

**市场信任模型**：包的可信度 = 独立回放 attestation 的数量与新鲜度。消费端先回放再信任，回执可再上架——信任是复利的，不是签署一次终身的。

## 6. 与三条设计信条的对应

| 信条 | 在 mpkg 中的落点 |
|---|---|
| 工具是宝贵的（CLI 可追踪） | steps 仅限 CLI 进程；JS/内联脚本禁止入库 |
| 验证 > 参数量 | verify 命令 + attestation 回执 = 信任原语 |
| 原子化构建 | 包 = 最小记忆原子；市场 = 原子组合层 |

## 7. v0 验收（纸上流程 → 可执行）

`make-snake-game` 示例包：agent A 记录"写贪吃蛇"的 trace → `mpkg build` → agent B `mpkg verify`（回放 steps + 跑 verify）→ PASS → B 的机器上出现可玩的贪吃蛇 + 知识原子。全程零人工。

## 8. provenance（openvibe 钩子，v0 预留字段）

> 定位：mpkg 记录"做了什么"，provenance 记录"怎么被提示出来的"。同一意图 N 个人 / N 个 AI 的实现可对比、可学习、可二开（fork = 新 content id + `parent` 指针）。

```json
"provenance": {
  "generator": "human | ai:<model> | human+ai:<model>",
  "prompts": [ { "n": 1, "text": "prompts/001.md", "step_refs": [1, 2] } ],
  "parent": "sha256:<父包id>"
}
```

- `prompts[].text` 指向包内 `prompts/*.md` 原文；`step_refs` 声明该提示词驱动了哪些 steps。
- 市场侧的"对比视图"= 同 `intent`/`tags` 分组按 attestation 数量与回放成功率排序。
- 需求证据：vibe coding 学习类仓库合计 10万+★（claude-code-best-practice 65.8k、vibe-coding-cn 23k、easy-vibe 19.4k、vibe-vibe 6k），全部是静态教程——**带溯源的可回放对比语料零先例**（gh 搜索 2026-09-12）。
- 注：`openvibe` 名字已被占（vitalops/openvibe 1450★），模块市场化前另定名。
