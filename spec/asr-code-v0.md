# asr-code v0 —— 代码知识蒸馏格式（对齐 kbv：音频走 ASR，代码走 AST/结构解析）

> 状态：v0 草案 · 2026-09-13 · 依赖：无（纯 markdown 结构解析；syn/rustc 深解析为升级路径）
> 一句话：**官方文档与代码 → 逐条定位的知识原子 → mpkg 上架市场**。视频教程走 kbv（ASR/OCR），官方文档走 asr_code（结构解析+编译门禁）——同一市场，两种感官。

## 1. 数据源原则（工具是宝贵的）

不爬 HTML。Rust 官方教程（The Book）的**源文件就是 markdown**（rust-lang/book，18.3k★）：
结构化、逐章、可 raw 直取。HTML 爬取只作为无 markdown 源时的降级路径。

## 2. 原子结构（atoms/<slug>.json）

```json
{
  "id": "<sha256(源锚定+内容) 前 16>",
  "source": { "repo": "rust-lang/book", "path": "src/ch01-02-hello-world.md", "section": "Hello, World!", "line": 42 },
  "title": "Hello, World!",
  "prose_summary": "章节首段摘要…",
  "code_blocks": [
    { "lang": "rust", "items": ["fn main", "macro println!"], "complete": true,
      "compile": "pass|needs-deps|fragment|skipped", "code_ref": "code/0001.rs" }
  ],
  "concepts": { "strong": ["cargo new", "fn main"], "weak": ["crate", "toolchain"] }
}
```

- **逐条定位**：每个原子锚定 `源文件+标题+行号`，反查可到官方原文（源 URL 可拼接）。
- **AST-lite 条目提取**：`fn/struct/enum/trait/impl/use/macro` 正则定位（v0）；syn 全量解析 → v0.1。
- **编译门禁**：含 `fn main` 的块写入临时 crate 跑 `rustc --emit=metadata`，结果如实分类
  （pass / needs-deps / fragment）——书中的片段大多非独立程序，诚实标注而非假装通过（信条：验证 > 参数量）。
- **概念关联**：markdown 反引号内的代码词 = 天然概念标记（`cargo new`）→ 强关联；同章共现 → 弱关联。
- **asr-code.json**：{ asr_code, source_repo, atoms[], generated_at } —— 与 kbv.json 同构，可作 mpkg atoms 上架。

## 3. 验证配方（mpkg verify 兼容）

steps：重蒸馏（对打包内置的 md 源）→ 原子 id 与包内 asr-code.json 比对 → 一致即通过。
—— 蒸馏器确定性 = 验证配方（同输入必同输出，content-hash 闭环）。

## 4. CI 构建路径

lystack 仓库 workflow（dispatch/weekly）：拉取 rust-lang/book 最新源 → 蒸馏 → 打包 →
gh api 发布到 mpkg-registry。**官方文档更新 → 市场自动出新版知识包**（用 github 跑构建）。

## 5. MVP 验收

The Book ch01-03（安装 / Hello World / Hello Cargo）→ 蒸馏出原子 → 查询 "cargo new" 返回
强关联原子（源锚定到 ch01-03）→ 打包上架 + Windows 回放 attest。
