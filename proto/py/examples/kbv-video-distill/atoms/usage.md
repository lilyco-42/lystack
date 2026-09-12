# kbv 蒸馏管线使用说明

一条命令把教程视频变成可检索的知识库：

```bash
WHISPER=<whisper-cli 路径> MODEL=<ggml 模型> bash kbv-distill.sh <video.mp4> <输出目录>
python3 kbv-index.py query <输出目录> "cargo new"   # 检索
```

- 六原子：提音频 → ASR → 抽帧(1fps) → OCR → 切片聚类 → 关联索引
- 输出：kbv.json + slices/*.json（每片含时间戳 ref / 帧图 / asr / ocr / 强次关联）
- 环境变量：WHISPER（whisper-cli 路径）、MODEL（ggml 模型）、OCR_LANG（默认 eng）
- 验收标准：查询术语返回精确切片（帧图 + 文字 + `#t=` 引用）
- 完整 spec：lystack 仓 spec/kbv-v0.md
