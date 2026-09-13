#!/usr/bin/env python3
"""asr_code —— Rust 官方文档知识蒸馏器 v0（spec: asr-code-v0.md）。

输入: The Book markdown 源 (rust-lang/book, raw 直取或本地)
输出: asr-code.json + atoms/*.json + code/*.rs —— mpkg atoms 兼容, 逐条源锚定

用法:
  python3 asr_code_distill.py fetch <outdir>            # 拉取书源 (ch01-03)
  python3 asr_code_distill.py distill <outdir>          # 蒸馏 → 知识原子
  python3 asr_code_distill.py query <outdir> <term...>  # 检索 (强关联优先)
  python3 asr_code_distill.py verify <outdir>           # 确定性重蒸对照 (mpkg verify 配方)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.request

BOOK_RAW = "https://raw.githubusercontent.com/rust-lang/book/main/src/"
CHAPTERS = [
    ("ch01-00-getting-started", "ch01-00-getting-started.md"),
    ("ch01-01-installation", "ch01-01-installation.md"),
    ("ch01-02-hello-world", "ch01-02-hello-world.md"),
    ("ch01-03-hello-cargo", "ch01-03-hello-cargo.md"),
    ("ch02-00-guessing-game-tutorial", "ch02-00-guessing-game-tutorial.md"),
]
ITEM_RE = re.compile(r"\b(fn|struct|enum|trait|impl|use|mod)\s+[A-Za-z_][\w:]*")
MACRO_RE = re.compile(r"\b(println|vec|panic|assert|format)!")


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def fetch(outdir: str) -> None:
    os.makedirs(os.path.join(outdir, "book"), exist_ok=True)
    for slug, md in CHAPTERS:
        dest = os.path.join(outdir, "book", md)
        url = BOOK_RAW + md
        urllib.request.urlretrieve(url, dest)
        print(f"fetched {md} ({os.path.getsize(dest)}B)")


def parse_sections(md_text: str) -> list[dict]:
    """按标题切节, 记录起始行号 (1-based 源锚定)。"""
    sections, cur = [], None
    for lineno, line in enumerate(md_text.splitlines(), 1):
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            cur = {"level": len(m.group(1)), "title": m.group(2).strip(),
                   "line": lineno, "body": []}
            sections.append(cur)
        elif cur is not None:
            cur["body"].append(line)
        else:
            cur = {"level": 0, "title": "(preamble)", "line": 1, "body": [line]}
            sections.append(cur)
    for s in sections:
        s["text"] = "\n".join(s["body"])
    return sections


CODE_FENCE = re.compile(r"```(\w*)\n(.*?)```", re.S)


def extract_blocks(text: str) -> list[dict]:
    blocks = []
    for lang, code in CODE_FENCE.findall(text):
        if lang and lang != "rust":
            blocks.append({"lang": lang, "items": [], "complete": False, "code": code})
            continue
        items = sorted({m.group(0) for m in ITEM_RE.finditer(code)} |
                       {m.group(0) for m in MACRO_RE.finditer(code)})
        blocks.append({
            "lang": "rust", "items": items,
            "complete": "fn main" in code,
            "code": code,
        })
    return blocks


def compile_gate(code: str, outdir: str, idx: int) -> str:
    """编译门禁: 只对含 fn main 的块; 依赖缺失如实标 needs-deps。"""
    if "fn main" not in code:
        return "fragment"
    tmp = os.path.join(outdir, "compile", f"b{idx:04d}")
    os.makedirs(tmp, exist_ok=True)
    src = os.path.join(tmp, "main.rs")
    open(src, "w", encoding="utf-8").write(code)
    import subprocess
    try:
        r = subprocess.run(
            ["rustc", "--edition", "2021", "--crate-type", "bin",
             "-o", os.path.join(tmp, "out.bin"), src],
            capture_output=True, text=True, timeout=60)
        err = r.stderr
        if r.returncode == 0:
            return "pass"
        if "unresolved import" in err or "can't find crate" in err or "E0432" in err or "E0433" in err:
            return "needs-deps"
        return "compile-error"
    except Exception as e:
        return f"error:{e}"


def distill(outdir: str) -> None:
    bookdir = os.path.join(outdir, "book")
    atoms_dir = os.path.join(outdir, "atoms")
    code_dir = os.path.join(outdir, "code")
    compile_dir = os.path.join(outdir, "compile")
    for d in (atoms_dir, code_dir, compile_dir):
        os.makedirs(d, exist_ok=True)

    atoms = []
    token_map: dict[str, set] = {}
    # 扫描 bookdir 全部 md —— 语料清单与构建脚本解耦
    mds = sorted(f for f in os.listdir(bookdir) if f.endswith(".md"))
    for md in mds:
        slug = md[:-3]
        path = os.path.join(bookdir, md)
        text = open(path, encoding="utf-8").read()
        for sec in parse_sections(text):
            blocks = extract_blocks(sec["text"])
            for bi, b in enumerate(blocks):
                b["compile"] = compile_gate(b["code"], outdir, len(atoms)) if b["complete"] else "fragment"
                if b["complete"]:
                    cf = f"code/{len(atoms):04d}-{bi:02d}.rs"
                    open(os.path.join(outdir, cf), "w", encoding="utf-8").write(b["code"])
                    b["code_ref"] = cf
            code_tokens: set[str] = set()
            for b in blocks:
                code_tokens |= set(b["items"])
            prose_tokens = {t.lower() for t in re.findall(r"`([^`]+)`", sec["text"])}
            strong = sorted(prose_tokens | {t for t in code_tokens})
            for t in strong:
                token_map.setdefault(t, set()).add(slug)
            aid = sha(slug + sec["title"] + str(sec["line"]))
            atoms.append({
                "id": aid,
                "source": {"repo": "rust-lang/book", "path": f"src/{md}",
                           "section": sec["title"], "line": sec["line"]},
                "title": sec["title"],
                "prose_summary": (sec["text"].strip().splitlines() or [""])[0][:160],
                "code_blocks": [
                    {k: b[k] for k in ("lang", "items", "complete", "compile", "code_ref") if k in b}
                    for b in blocks
                ],
                "concepts": {"strong": strong},
                "text": sec["text"][:4000],
                "chapter": slug,
            })

    # 弱关联: 同书共现但本原子未含 —— 全部补完后统一写盘
    for a in atoms:
        strong_set = set(a["concepts"]["strong"])
        weak = sorted({t for t, slugs in token_map.items()
                       if a["chapter"] in slugs and t not in strong_set})
        a["concepts"]["weak"] = weak[:20]
    for a in atoms:
        json.dump(a, open(os.path.join(atoms_dir, f"{a['id']}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)

    asr = {
        "asr_code": "0.1",
        "source_repo": "rust-lang/book",
        "chapters": [s for _, s in CHAPTERS],
        "atoms": [f"atoms/{a['id']}.json" for a in atoms],
        "generated_at": str(len(atoms)) + " atoms",
    }
    json.dump(asr, open(os.path.join(outdir, "asr-code.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"asr-code.json: {len(atoms)} atoms, {len(token_map)} concepts")


def query(outdir: str, terms: list[str]) -> None:
    idx = json.load(open(os.path.join(outdir, "asr-code.json"), encoding="utf-8"))
    hits = []

    for ref in idx["atoms"]:
        a = json.load(open(os.path.join(outdir, ref), encoding="utf-8"))
        hay = json.dumps(a).lower()
        score = sum(2 if t.lower() in a.get("text", "").lower() else (1 if t.lower() in hay else 0)
                    for t in terms)
        if score:
            src = a["source"]
            url = f"https://github.com/rust-lang/book/blob/main/{src['path']}#L{src['line']}"
            hits.append((score, a["title"], a["source"]["path"] + ":" + str(src["line"]), url))
    hits.sort(key=lambda x: -x[0])
    for score, title, loc, url in hits[:5]:
        print(f"score={score}  {title}\n    {loc}\n    {url}")
    if not hits:
        print("no hits")


def verify(outdir: str) -> None:
    """确定性重蒸对照: 再跑一遍蒸馏, 比 asr-code.json 逐字节 (mpkg verify 配方)。"""
    before = open(os.path.join(outdir, "asr-code.json"), "rb").read()
    distill(outdir)
    after = open(os.path.join(outdir, "asr-code.json"), "rb").read()
    print("VERIFY:", "PASS (deterministic)" if before == after else "FAIL (nondeterministic)")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "fetch":
        fetch(sys.argv[2])
    elif cmd == "distill":
        distill(sys.argv[2])
    elif cmd == "verify":
        verify(sys.argv[2])
    elif cmd == "query":
        query(sys.argv[2], sys.argv[3:])
    else:
        print(__doc__)
