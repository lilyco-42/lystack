# mpkg 契约源 —— 格式规则与 golden 向量

> 定位：**mpkg 格式的单一契约源**。schema（`mpkg.schema.json`，JSON Schema draft 2020-12）+ golden 向量（`golden/cases.json`，由 `gen_golden.py` 生成）定义权威格式；所有实现（lilyco `lilyco-mpkg/src/pack.rs`、cache-node `src/mpkg_verify.rs`、mpkg-registry 前端）必须与本目录对齐。**改格式先改这里，再同步实现**；实现与 golden 不一致 = 实现错了。

## 1. 包文件格式（JSON 形态）

包文件 = 单个 UTF-8 JSON，即 content-id 的计算输入：

```json
{
  "manifest": {
    "mpkg": "0.1", "name": "…", "version": "…", "intent": "…",
    "steps": [ { "run": "…", "expect": { "exit": 0 } } ],
    "verify": [ "…" ]
  },
  "files": { "<相对路径>": "<64位小写 sha256 hex>" }
}
```

- 顶层只允许 `manifest`（必需）与 `files`（可选）两个键——多出的字段会悄悄改变 content-id 语义。
- `files` 只存哈希引用，不内嵌文件本体（最小子集；文件本体由 zip 容器形态承载，见 §5）。
- 全部字段与约束见 `mpkg.schema.json`（必需六字段、name kebab-case、steps 非空且每条含字符串 `run`、verify 非空字符串数组、files 路径安全、spec/mpkg-v0.md §3 的可选字段 author/requirements/atoms/provenance/tags/license）。

## 2. canon_json 算法（逐字节定死）

1. **递归键排序**：对象各层按键的 Unicode 码点序排序（与 Rust `String` 的 UTF-8 字节序等价）；数组不排序、保持原序。
2. **紧凑分隔符**：`,` 与 `:`，无空白。
3. **UTF-8 原样**：非 ASCII 字符不转义（`ensure_ascii=False`）。

等价写法：

```python
json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)   # Python
serde_json::to_string(&recursively_sorted(value))                            # Rust（pack.rs canon）
```

golden 的生成脚本 `gen_golden.py` 显式递归排序（`sort_keys=False` + 自实现 `sorted_value`），逐行镜像 `pack.rs` 的 `canon()`，不依赖 `json.dumps(sort_keys=True)` 的隐式行为。

## 3. 两层哈希 —— ⚠️ 显式警告（曾踩坑）

mpkg 有**两层不同用途的哈希，绝不混用**：

| | content-id | blob 地址 |
|---|---|---|
| 公式 | `sha256:` + sha256( **canon_json(包JSON)** 的 UTF-8 字节 ) | sha256( **包文件原始字节** ) |
| 敏感性 | 对序列化空白**不敏感**（pretty print / 键序不同 → 同一 id） | 对**每一个字节**敏感 |
| 用途 | 语义身份：市场寻址、防篡改、包的"这是谁" | 存储地址：内容寻址 KV 的 blob 文件名（`blobs/<hex>.mpkg`）、名字索引里的定位键 |
| 前缀 | 恒带 `sha256:` 前缀 | 裸 64 位小写 hex（解析时接受可带前缀） |

**踩坑记录**：把 blob hex 当 content-id（或反之）会导致 verify 报「content-id 重算不符」或「内容 sha256 与存储地址不符（内容被篡改）」的假阳性。两者仅在**包文件以 canon 形式落盘**时十六进制恰好相同（golden 即此形态）；任何非 canon 字节（如 pretty print）落盘 → blob 变而 content-id 不变。

`files` 表里的哈希是**第三处** sha256：指向外部文件内容（或 zip 条目字节），与上述两层均无关。

## 4. golden 向量（golden/cases.json）

| 用例 | 覆盖点 | content-id 前 8 位 |
|---|---|---|
| `minimal-manifest-only` | 最小包：仅 manifest，**无 files 键**（files 可选） | `830d8d92` |
| `multi-file-pack` | 多文件包：嵌套相对路径哈希引用 + `expect.exit` | `f501b428` |
| `full-replay-suite` | 步骤齐全：多步 `expect.exit`、多 verify、requirements/author/tags/license 可选字段 | `7bc60dd2` |

- 每例含：`pack`（输入包 JSON，canon 键序）、`canon_json`（精确字节串）、`content_id`、`blob_sha256`。
- `files_content` 仅供复算 `pack.files` 的哈希引用，不属于包格式。
- 重新生成：`python proto/mpkg/gen_golden.py`（勿手改 cases.json）。
- 消费方：lilyco 仓库 `lilyco-mpkg/tests/golden.rs` 硬编码同批向量，CI 断言 Rust 实现逐字节一致。

## 5. 实现漂移表（pack.rs vs mpkg_verify.rs，2026-09-19 逐行核对）

一致的部分：sha256 小写 hex、`sha256:` 前缀、canon = 递归排序 + 紧凑 + UTF-8 原样、id 输入同为 `{"manifest":…, "files":{…}}` 形态。以下为**已核实的差异**：

1. **容器形态**：pack.rs = 单 JSON 包文件（files 只存哈希引用）；mpkg_verify.rs = zip 容器（`mpkg.json` + 内嵌全部文件条目）。
2. **files 映射来源**：pack.rs 直接信任包 JSON 里的 `files` 表（只校验 hex 格式与路径安全，内容不在包内、无法核验）；mpkg_verify.rs 对 zip 条目字节**实算** sha256。
3. **content-id 输入的 files 键**：pack.rs 对"包文件解析后的整体"取 canon——**缺 `files` 键的包，id 输入就没有 files 键**（golden 用例 1 即此形态）；mpkg_verify.rs 恒构造含 `files` 键的对象（zip 场景 files 至少含 mpkg.json，永不为空）。
4. **mpkg.json 自引用**：mpkg_verify.rs 把 zip 内 `mpkg.json` 自身也计入 files（manifest 字节哈希进 id）；pack.rs 无此概念。
5. **校验严格度**：pack.rs 额外校验 name kebab-case（防路径穿越）、version/intent 非空、verify 元素须字符串、**顶层字段白名单**（未知顶层键直接拒）、files 路径安全（禁 `..` / 空段 / `\` / 前导 `/`）；mpkg_verify.rs 只查必需字段存在 + steps 形状 + verify 非空，且 verify 元素非字符串会被 `as_str().unwrap_or("")` 静默吞成空命令。
6. **`expect.exit`**：mpkg_verify.rs 回放时逐条比对 `steps[].expect.exit`（缺省 0）；pack.rs 只要求 `run` 存在，`expect` 结构不校验。
7. **执行语义**：mpkg_verify.rs 真执行（POSIX shell + `{{pkg}}`/`{{work}}` 替换 + 120s 超时 + `requirements.tools` 逐个 `which` 检查）；pack.rs 明确不执行（只做结构/完整性校验，执行属 T3 级动作）。
8. **blob 概念**：pack.rs 有内容寻址存储层（blob = 原始字节哈希，put 不要求输入已 canon）；mpkg_verify.rs 无 blob 层（zip 自带传输形态）。

> mpkg-registry（HTML 前端）为展示/检索层，不参与 id 计算；接入检索时以本目录 content-id 为准。

## 6. 消费与演进约定

- 新实现（语言不限）验收标准：validate 过 golden 三例 + `canon_json`/`content_id`/`blob_sha256` 逐字节一致 + §5 漂移表中选择的行为侧与声明一致。
- 改格式流程：改 `mpkg.schema.json` → 跑 `gen_golden.py` 出新 golden → 各实现 PR 对齐（lilyco 侧 `tests/golden.rs` 必须同步更新）→ 本文件漂移表更新。
