#!/bin/bash
# kbv-distill —— 视频知识蒸馏管线 v0（kbv spec §5 六原子，全部 CLI 进程，可回放）
# 用法: kbv-distill.sh <video.(mp4|mkv|webm)> <outdir>
# 依赖: ffmpeg / whisper.cpp main / tesseract / python3
set -euo pipefail

V="${1:?usage: kbv-distill.sh <video> <outdir>}"
OUT="${2:?usage: kbv-distill.sh <video> <outdir>}"
WHISPER="${WHISPER:-/home/radxa/whisper/whisper.cpp/build/bin/whisper-cli}"
MODEL="${MODEL:-/home/radxa/whisper/ggml-base.bin}"

VID=$(sha256sum "$V" | cut -d' ' -f1)
mkdir -p "$OUT/frames" "$OUT/slices" "$OUT/prompts"
echo "== video_id = sha256:$VID"

# 原子1: 提音频 (16k mono, whisper 输入)
echo "== atom1: audio =="
ffmpeg -y -v error -i "$V" -vn -ac 1 -ar 16000 "$OUT/audio.wav"

# 原子2: ASR → srt
echo "== atom2: asr =="
"$WHISPER" -m "$MODEL" -f "$OUT/audio.wav" -osrt -of "$OUT/subtitles" 2> "$OUT/asr.log" || {
  tail -5 "$OUT/asr.log" >&2; exit 1;
}
ls "$OUT"/subtitles.srt

# 原子3: 关键帧 —— 幻灯片类视频场景分低, 用 fps=1 每秒一帧; 第 N 帧 pts = N-1 秒 (确定性, 不依赖 showinfo)
echo "== atom3: keyframes =="
ffmpeg -y -v error -i "$V" -vf "fps=1" -vsync vfr "$OUT/frames/f%06d.jpg"
ls "$OUT/frames"/*.jpg | sort | xargs -n1 basename | awk '{print $0, NR-1}' > "$OUT/frames.txt"
wc -l < "$OUT/frames.txt" | xargs echo "keyframes:"

# 原子4: OCR 每帧 (OCR_LANG 可覆盖; 幻灯片类英文源用 eng 最稳)
echo "== atom4: ocr =="
for f in "$OUT/frames"/*.jpg; do
  tesseract "$f" "${f%.jpg}" -l "${OCR_LANG:-eng}" 2>/dev/null || true
done

# 原子5+6: 切片聚类 + 关联索引 → kbv.json + slices/*.json
echo "== atom5+6: index =="
python3 "$(dirname "$0")/kbv-index.py" "$OUT" "$VID" "$V"
echo "== DONE: $OUT/kbv.json"
