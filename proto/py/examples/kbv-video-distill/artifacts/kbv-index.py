#!/usr/bin/env python3
"""kbv-index —— 视频知识切片聚类 + 关联索引 + 查询（kbv spec §5 步骤5/6 与 §6）。

用法:
  kbv-index.py <outdir> <video_sha256> <video_path>     # 蒸馏后被 distill.sh 调用
  kbv-index.py query <outdir> <term> [term...]          # 检索: 返回切片证据
"""
from __future__ import annotations

import json
import os
import re
import sys


def parse_srt(path: str) -> list[dict]:
    raw = open(path, encoding="utf-8-sig", errors="replace").read().strip()
    out = []
    for block in re.split(r"\n\s*\n", raw):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) >= 3:
            m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->", lines[1])
            if m:
                h, mi, s, ms = map(int, m.groups())
                out.append({
                    "start": h * 3600 + mi * 60 + s + ms / 1000,
                    "text": " ".join(lines[2:]).strip(),
                })
    return out


def parse_frames(path: str) -> list[dict]:
    """frames.txt: 每行 '<basename> <pts>'（空白分隔）"""
    frames = []
    for line in open(path, encoding="utf-8"):
        parts = line.strip().split()
        if len(parts) == 2:
            try:
                frames.append({"file": f"frames/{parts[0]}", "pts": float(parts[1])})
            except ValueError:
                pass
    return frames


def ocr_of(outdir: str, frame_file: str) -> str:
    txt = os.path.join(outdir, frame_file.replace("frames/", "frames/").replace(".jpg", ".txt"))
    if os.path.isfile(txt):
        return " ".join(open(txt, encoding="utf-8", errors="replace").read().split())
    return ""


TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_\-]{1,}")


def tokens(text: str) -> list[str]:
    return sorted({t.lower() for t in TOKEN_RE.findall(text or "")})


def build(outdir: str, vid: str, video_path: str):
    srt = os.path.join(outdir, "subtitles.srt")
    sents = parse_srt(srt)
    frames = parse_frames(os.path.join(outdir, "frames.txt"))
    dur = 0.0
    r = os.popen(f'ffprobe -v quiet -show_entries format=duration -of csv=p=0 "{video_path}"')
    try:
        dur = float(r.read().strip() or 0)
    except ValueError:
        pass

    slices = []
    all_tokens: dict[str, set] = {}
    for i, sent in enumerate(sents):
        end = sents[i + 1]["start"] if i + 1 < len(sents) else (dur or sent["start"] + 30)
        # 附帧: 切片起点前最近的关键帧（幻灯片起点）
        cand = [f for f in frames if f["pts"] <= sent["start"] + 0.5] or frames[:1]
        frame = max(cand, key=lambda f: f["pts"]) if cand else {"file": "", "pts": 0}
        ocr = ocr_of(outdir, frame["file"])
        toks = tokens(sent["text"]) + tokens(ocr)
        for t in toks:
            all_tokens.setdefault(t, set()).add(str(i))
        slices.append({
            "t": [round(sent["start"], 2), round(end, 2)],
            "ref": f"video:{vid}#t={int(sent['start'])},{int(end)}",
            "frames": [frame["file"]] if frame["file"] else [],
            "asr": sent["text"],
            "ocr": ocr,
            "topic": "",
        })

    # 关联: 强=本切片词, 次=仅出现在其他切片的词
    for i, s in enumerate(slices):
        text = " ".join([s["asr"], s["ocr"]])
        toks = tokens(text)
        s["topic"] = toks[0] if toks else ""
        s["links"] = {
            "strong": toks,
            "weak": sorted({t for t, ids in all_tokens.items() if str(i) not in ids}),
        }
        path = os.path.join(outdir, "slices", f"{i:04d}.json")
        json.dump(s, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    kbv = {
        "kbv": "0.1",
        "video_id": f"sha256:{vid}" if not vid.startswith("sha256:") else vid,
        "source": video_path,
        "duration_s": round(dur, 2),
        "lang": "zh",
        "slices": [f"slices/{i:04d}.json" for i in range(len(slices))],
    }
    json.dump(kbv, open(os.path.join(outdir, "kbv.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"kbv.json written: {len(slices)} slices, {len(all_tokens)} topic tokens")


def query(outdir: str, terms: list[str]):
    kbv = json.load(open(os.path.join(outdir, "kbv.json"), encoding="utf-8"))
    hits = []
    for ref in kbv["slices"]:
        s = json.load(open(os.path.join(outdir, ref), encoding="utf-8"))
        hay = " ".join([s.get("asr", ""), s.get("ocr", ""), " ".join(s.get("links", {}).get("strong", []))]).lower()
        score = sum(1 for t in terms if t.lower() in hay)
        if score:
            hits.append((score, s))
    hits.sort(key=lambda x: -x[0])
    for score, s in hits[:3]:
        print(json.dumps({
            "ref": s["ref"],
            "score": score,
            "frame": s["frames"],
            "asr": s["asr"][:80],
            "ocr": s["ocr"][:80],
        }, ensure_ascii=False))
    if not hits:
        print("no hits")


if __name__ == "__main__":
    if sys.argv[1] == "query":
        query(sys.argv[2], sys.argv[3:])
    else:
        build(sys.argv[1], sys.argv[2], sys.argv[3])
