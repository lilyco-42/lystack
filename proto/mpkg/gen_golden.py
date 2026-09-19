#!/usr/bin/env python3
"""mpkg golden 向量生成器 —— 契约源 lystack proto/mpkg（单一出处，勿手改 cases.json）。

对齐 lilyco lilyco-mpkg/src/pack.rs 的 canon 实现（逐字核对过）：
  canon_json = 递归键排序（按 Unicode 码点，与 Rust UTF-8 字节序等价）
             + 紧凑分隔符 ',' ':' + UTF-8 原样（ensure_ascii=False）
  等价 Python 一行式：json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
  这里显式递归排序（sort_keys=False）以逐行镜像 pack.rs 的 sorted() 递归。

两层哈希（易混淆，见 GOLDEN.md 警告）：
  content_id  = "sha256:" + sha256(canon_json(包JSON) 的 UTF-8 字节)   ← 语义身份
  blob_sha256 = sha256(包文件原始字节)                                  ← 存储地址
  本表输入包为 canon 形式，故两者十六进制相同；非 canon 字节（如 pretty print）
  落盘时 blob 变、content_id 不变。

用法：python proto/mpkg/gen_golden.py   （在 lystack 仓库任意目录可跑，路径相对本脚本）
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "golden", "cases.json")


def canon(obj) -> str:
    """镜像 pack.rs canon()：显式递归排序 + serde_json to_string 默认行为（紧凑、UTF-8 原样）。"""

    def sorted_value(v):
        if isinstance(v, dict):
            return {k: sorted_value(v[k]) for k in sorted(v.keys())}
        if isinstance(v, list):
            return [sorted_value(x) for x in v]
        return v

    return json.dumps(sorted_value(obj), sort_keys=False, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# files 里引用的外部内容（仅用于复算 files 哈希；不属于包格式本身）
FILES_CONTENT = {
    "multi-file-demo/README.md": "# multi-file-demo\n\n含 files 的多文件 golden 包。\n",
    "multi-file-demo/artifacts/main.py": 'print("multi-file-demo")\n',
    "multi-file-demo/artifacts/lib/util.py": 'def greet():\n    return "hi from util"\n',
    "full-replay-suite/artifacts/out.txt": "42\n",
}


def build_cases() -> list:
    hashes = {k: sha256_hex(v.encode("utf-8")) for k, v in FILES_CONTENT.items()}

    # ── 用例 1：最小包 —— 仅 manifest，无 files 键（files 为可选字段） ──
    case1 = {
        "manifest": {
            "mpkg": "0.1",
            "name": "hello-mpkg",
            "version": "0.1.0",
            "intent": "最小合法包：仅 manifest，无 files 键",
            "steps": [{"run": "echo hello-mpkg"}],
            "verify": ["true"],
        }
    }

    # ── 用例 2：含 files 的多文件包 —— 嵌套路径哈希引用 + expect.exit ──
    case2 = {
        "manifest": {
            "mpkg": "0.1",
            "name": "multi-file-demo",
            "version": "0.2.0",
            "intent": "含 files 的多文件包：嵌套路径哈希引用",
            "steps": [{"run": "echo multi", "expect": {"exit": 0}}],
            "verify": ["test -f artifacts/main.py", "test -f artifacts/lib/util.py"],
        },
        "files": {
            "README.md": hashes["multi-file-demo/README.md"],
            "artifacts/lib/util.py": hashes["multi-file-demo/artifacts/lib/util.py"],
            "artifacts/main.py": hashes["multi-file-demo/artifacts/main.py"],
        },
    }

    # ── 用例 3：步骤齐全包 —— 多步 expect.exit / 多 verify / requirements 等可选字段 ──
    case3 = {
        "manifest": {
            "mpkg": "0.1",
            "name": "full-replay-suite",
            "version": "1.0.0",
            "intent": "步骤齐全包：expect.exit / 多 verify / requirements / 溯源可选字段",
            "author": "agent:lilyco",
            "requirements": {"tools": [{"name": "python3", "min_version": "3.10"}]},
            "steps": [
                {"run": "echo step-1"},
                {"run": "python3 -c 'print(6*7)'", "expect": {"exit": 0}},
                {"run": "test -d {{work}}", "expect": {"exit": 0}},
            ],
            "verify": ["test -f artifacts/out.txt", "grep -q 42 artifacts/out.txt"],
            "tags": ["demo", "replay"],
            "license": "MIT",
        },
        "files": {"artifacts/out.txt": hashes["full-replay-suite/artifacts/out.txt"]},
    }

    cases = []
    for name, desc, pack in [
        ("minimal-manifest-only", "最小包：仅 manifest，无 files 键（files 为可选字段）", case1),
        ("multi-file-pack", "含 files 的多文件包：嵌套相对路径 → 64 位小写 sha256 引用", case2),
        ("full-replay-suite", "步骤齐全包：expect.exit、多 verify 命令、requirements/author/tags/license 可选字段", case3),
    ]:
        blob = canon(pack)  # 输入包以 canon 形式落盘 → 原始字节 = canon 字节
        cases.append(
            {
                "name": name,
                "desc": desc,
                "pack": json.loads(blob),  # 输入包 JSON（canon 形式，键序即 canon 键序）
                "canon_json": blob,        # 序列化后的精确字节（UTF-8 文本）
                "content_id": "sha256:" + sha256_hex(blob.encode("utf-8")),
                "blob_sha256": sha256_hex(blob.encode("utf-8")),
            }
        )
    return cases


def main() -> None:
    cases = build_cases()
    doc = {
        "format": "mpkg-golden-v1",
        "contract": "lystack proto/mpkg —— mpkg 格式单一契约源（schema: ../mpkg.schema.json，规则: ../GOLDEN.md）",
        "canon_rule": "递归键排序（Unicode 码点序）+ 紧凑分隔符 ',' ':' + UTF-8 原样；等价 json.dumps(obj, sort_keys=True, separators=(',',':'), ensure_ascii=False)；生成脚本 ../gen_golden.py（镜像 lilyco pack.rs canon）",
        "hash_rules": {
            "content_id": "'sha256:' + sha256(canon_json(包JSON) 的 UTF-8 字节) —— 语义身份，对序列化空白不敏感",
            "blob_sha256": "sha256(包文件原始字节) —— 存储地址；本表输入为 canon 形式故与 content_id 十六进制相同，非 canon 字节落盘时 blob 变而 content_id 不变（两层哈希，勿混用，详见 GOLDEN.md）",
        },
        "files_content": FILES_CONTENT,
        "files_content_note": "files_content 仅用于复算 pack.files 里的哈希引用（JSON 包形态不内嵌文件本体），不属于包格式",
        "cases": cases,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")
    for c in cases:
        print(f"{c['name']}: content_id={c['content_id'][:20]}… blob={c['blob_sha256'][:12]}…")
    print(f"written: {OUT}")


if __name__ == "__main__":
    main()
