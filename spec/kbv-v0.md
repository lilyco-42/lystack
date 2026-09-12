# kbv v0 —— 视频知识切片格式（Knowledge-from-Video, 时间轴地址空间）

> 状态：P2 spec 草案 v0 · 2026-09-12 · 依赖：ffmpeg + whisper.cpp（Radxa 已就绪）
> 一句话：**视频时间轴 = 程序性知识的地址空间。`video:<id>#t=起,止` 是知识原子的门牌号。**

## 1. 为什么需要新格式

文本/图片承载 GUI 操作时会丢失两样东西：**精确位置**（点了哪里）和**时序**（先做什么后做什么）——这恰是 scaling law 最盲的程序性知识区。kbv 把视频切成可寻址、可验证、可关联的知识原子，成为 mpkg `atoms[].ref` 的落地容器。

## 2. 文件结构

```
<video-id>/                 # 一个源视频 = 一个知识库单元
├── kbv.json                # 清单
├── audio.wav               # ffmpeg 提取（16k mono，whisper 输入）
├── subtitles.srt           # whisper ASR 输出
├── frames/                 # ffmpeg 关键帧（场景切换点抽帧）
│   ├── f000123.jpg         # 命名 = 帧所在秒
│   └── …
└── slices/                 # 知识切片（管线产物，见 §4）
    └── 000123-000151.json  # 命名 = 起止秒
```

## 3. 清单（kbv.json）

| 字段 | 说明 |
|---|---|
| `kbv` | 格式版本，恒 `"0.1"` |
| `video_id` | 内容寻址：sha256(源视频文件)，与 mpkg 同一套 trust 原语 |
| `source` | 原始来源（URL/本地路径/版权注记） |
| `duration_s` / `lang` | 元信息 |
| `slices` | 切片索引数组（见 §4） |

## 4. 切片（slices/000123-000151.json）

```json
{
  "t": [123, 151],
  "ref": "video:<video_id>#t=123,151",
  "frames": ["frames/f000130.jpg"],
  "asr": "这一句的完整语音转写…",
  "ocr": ["frames/f000130.jpg 的 OCR 文字…"],
  "gui": [ { "app": "VS Code", "element": "终端", "action": "输入 cargo new" } ],
  "topic": "cargo-new",
  "links": { "strong": ["cargo-new"], "weak": ["rust-install", "hello-world"] }
}
```

- **强关联 `links.strong`**：查询词 → 直接命中的切片（"怎么新建 rust 项目" → `cargo-new`）。
- **次关联 `links.weak`**：上下文相关切片（学习路径/前置知识）。
- **`gui[]`**：GUI 操作三元组（应用/元素/动作），来源 = OCR + 关键帧人工/AI 标注。

## 5. 蒸馏管线（六个原子步骤，每步 CLI、可回放——铁律适用）

1. `ffmpeg -i in.mp4 -vn -ac 1 -ar 16000 audio.wav` —— 提音频
2. `whisper-cli -m base -f audio.wav -osrt -osub subtitles.srt` —— ASR（Radxa 已编译）
3. `ffmpeg -i in.mp4 -vf "select=gt(scene,0.3)" -vsync vfr frames/f%06d.jpg` —— 场景切换抽帧
4. OCR 关键帧（tesseract / PaddleOCR，OCR 失败 → 降级内部识图 NN 打分——降级链首次落地）
5. **切片聚类**：srt 语句边界 + 场景帧时间戳 → 合并成语义切片（一条语句或一个 GUI 操作 = 一片）
6. **关联索引**：抽取术语表（ASR+OCR 词频 + 代码标识符正则）→ 强/次关联图，写入 slices 与 kbv.json

## 6. 检索与验证闭环

```
用户问 "怎么新建 rust 项目"
  → 术语归一 "cargo-new" → 命中强关联切片 000123-000151
  → 输出：帧图（GUI 现场截图）+ ASR 文字 + ref 时间戳
  → OCR 复核：帧图重新 OCR 确认 "cargo new" 可见 → 可信返回
  → OCR 不可见 → 降级取相邻帧 / NN 打分挑最清晰帧 → 仍失败则标注低置信
```

**验收标准（P2 管线）**：投入一条"如何学 Rust"真实教程视频 → 管线产出 kbv 单元 → 提问"怎么 cargo new" 返回精确切片（帧图 + 文字 + `#t=` 引用），OCR 复核通过率 ≥ 80%。

## 7. 与既有件的关系

- slices 的 `ref` 即 mpkg `atoms[].ref` 的取值格式——视频知识原子可直接挂进记忆包上架市场。
- `video_id` content-hash 与 cache-node 的 blob 寻址同构——帧图/音频可入缓存节点分发。
- 学习闭环（信条 5）：一个视频 = 一次原子化构建；多视频 = 知识图谱自然生长。
