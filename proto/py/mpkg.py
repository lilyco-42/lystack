#!/usr/bin/env python3
"""mpkg v0 —— 记忆包构建与验证 CLI（Python 原型；Rust 基建后继，性能压榨归 lilyco 系）。

命令:
  mpkg new <dir> <name>            脚手架
  mpkg build <pkg-dir>             打包 → dist/<name>-<ver>-<id12>.mpkg
  mpkg check <file.mpkg>           校验清单 + 重算 content id
  mpkg verify <file.mpkg>          回放 steps + 运行 verify → attestation (PASS/FAIL)
  mpkg publish <pkg-dir> -r REPO   打包并上架 GitHub 注册表（gh api contents PUT）
  mpkg search TERM -r REPO         检索注册表（name/intent/tags）
  mpkg install NAME -r REPO -o DIR 下载 + check + 解包 artifacts（--verify 加回放）
  mpkg attest ATTEST.json -r REPO  回放回执上架 → 信任复利（search 显示计数）
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

MANIFEST = "mpkg.json"
STEP_TIMEOUT = 120


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def die(msg: str, code: int = 1):
    print(f"mpkg: error: {msg}", file=sys.stderr)
    sys.exit(code)


# ── 清单 ────────────────────────────────────────────────────────────────

def load_manifest(root: str) -> dict:
    path = os.path.join(root, MANIFEST)
    if not os.path.isfile(path):
        die(f"{MANIFEST} not found in {root}")
    with open(path, encoding="utf-8") as f:
        m = json.load(f)
    validate(m)
    return m


def validate(m: dict):
    for key in ("mpkg", "name", "version", "intent", "steps", "verify"):
        if key not in m:
            die(f"manifest missing required field: {key}")
    if m.get("mpkg") != "0.1":
        die(f"unsupported mpkg format version: {m.get('mpkg')!r} (want '0.1')")
    if not m["steps"] or not all("run" in s for s in m["steps"]):
        die("steps must be a non-empty list of {run, expect?}")
    if not m["verify"]:
        die("verify must be a non-empty list of commands")


def collect_files(root: str) -> dict:
    hashes = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ("dist", "__pycache__") and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith(".mpkg"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            with open(full, "rb") as f:
                hashes[rel] = hashlib.sha256(f.read()).hexdigest()
    if MANIFEST not in hashes:
        die("package dir has no files besides manifest?")
    return hashes


def package_id(manifest: dict, files: dict) -> str:
    blob = canon({"manifest": manifest, "files": files}).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


# ── 命令 ────────────────────────────────────────────────────────────────

def cmd_new(args):
    root = os.path.abspath(args.dir)
    os.makedirs(os.path.join(root, "artifacts"), exist_ok=True)
    os.makedirs(os.path.join(root, "atoms"), exist_ok=True)
    manifest = {
        "mpkg": "0.1",
        "name": args.name,
        "version": "0.1.0",
        "intent": "TODO: 一句话意图（搜索主键）",
        "requirements": {"tools": [{"name": "python", "min_version": "3.8"}]},
        "steps": [{"run": "echo hello from {{pkg}}", "expect": {"exit": 0}}],
        "verify": ["echo ok"],
        "atoms": [],
        "tags": [],
        "license": "MIT",
    }
    with open(os.path.join(root, MANIFEST), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({"created": root}, ensure_ascii=False))


def cmd_build(args):
    root = os.path.abspath(args.dir)
    m = load_manifest(root)
    files = collect_files(root)
    pid = package_id(m, files)
    outdir = os.path.join(root, "dist")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, f"{m['name']}-{m['version']}-{pid[7:19]}.mpkg")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(files):
            z.write(os.path.join(root, rel), arcname=rel)
    print(json.dumps({"id": pid, "file": out, "files": len(files)}, ensure_ascii=False))


def cmd_check(args):
    with zipfile.ZipFile(args.file) as z:
        names = z.namelist()
        m = json.loads(z.read(MANIFEST).decode("utf-8"))
        validate(m)
        files = {}
        for rel in names:
            files[rel] = hashlib.sha256(z.read(rel)).hexdigest()
    pid = package_id(m, files)
    print(json.dumps({"id": pid, "name": m["name"], "files": len(files), "ok": True},
                     ensure_ascii=False))


# ── verify（回放） ──────────────────────────────────────────────────────

def find_shell() -> list:
    for sh in ("bash", "sh"):
        path = shutil.which(sh)
        if path:
            return [path, "-c"]
    die("replay requires a POSIX shell (bash/sh); on Windows use Git Bash")


def check_tools(m: dict) -> list:
    missing = []
    for t in (m.get("requirements") or {}).get("tools", []):
        if shutil.which(t["name"]) is None:
            missing.append(t["name"])
    return missing


def run_cmd(shell: list, cmd: str, work: str, timeout: int) -> dict:
    t0 = time.monotonic()
    p = subprocess.run(shell + [cmd], cwd=work, capture_output=True,
                       text=True, timeout=timeout)
    return {"cmd": cmd, "exit": p.returncode, "ms": int((time.monotonic() - t0) * 1000),
            "stdout_tail": p.stdout.strip()[-400:], "stderr_tail": p.stderr.strip()[-400:]}


def cmd_verify(args):
    m_root = tempfile.mkdtemp(prefix="mpkg-")
    pkg = os.path.join(m_root, "pkg").replace("\\", "/")   # bash 会吃反斜杠
    work = os.path.join(m_root, "work").replace("\\", "/")
    os.makedirs(pkg)
    os.makedirs(work)
    try:
        with zipfile.ZipFile(args.file) as z:
            z.extractall(pkg)
        m = load_manifest(pkg)
        missing = check_tools(m)
        if missing:
            die(f"tool requirements not met, missing on PATH: {', '.join(missing)}")
        shell = find_shell()
        subst = lambda s: s.replace("{{pkg}}", pkg).replace("{{work}}", work)
        steps, ok = [], True
        for i, step in enumerate(m["steps"], 1):
            r = run_cmd(shell, subst(step["run"]), work, STEP_TIMEOUT)
            want = (step.get("expect") or {}).get("exit", 0)
            r["n"] = i
            r["ok"] = r["exit"] == want
            steps.append(r)
            if not r["ok"]:
                ok = False
                print(f"step {i} FAIL: exit {r['exit']} != {want}\n  stderr: {r['stderr_tail'][:200]}",
                      file=sys.stderr)
                break
        verifies = []
        if ok:
            for cmd in m["verify"]:
                r = run_cmd(shell, subst(cmd), work, STEP_TIMEOUT)
                verifies.append(r)
                if r["exit"] != 0:
                    ok = False
                    print(f"verify FAIL: {cmd}\n  stderr: {r['stderr_tail'][:200]}", file=sys.stderr)
                    break
        attestation = {
            "mpkg_id": package_id(m, collect_files(pkg)),
            "name": m["name"],
            "ok": ok,
            "steps": steps,
            "verify": verifies,
            "host": {"os": platform.platform(), "python": platform.python_version(),
                     "shell": shell[0]},
            "replayed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        out = json.dumps(attestation, ensure_ascii=False, indent=2)
        keep = args.keep
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(out + "\n")
        print(out)
        if not keep:
            shutil.rmtree(m_root, ignore_errors=True)
        else:
            print(f"workdir kept: {work}", file=sys.stderr)
        sys.exit(0 if ok else 2)
    finally:
        if not keep:
            shutil.rmtree(m_root, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(prog="mpkg", description="memory package tool v0")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new"); p.add_argument("dir"); p.add_argument("name"); p.set_defaults(fn=cmd_new)
    p = sub.add_parser("build"); p.add_argument("dir"); p.set_defaults(fn=cmd_build)
    p = sub.add_parser("check"); p.add_argument("file"); p.set_defaults(fn=cmd_check)
    p = sub.add_parser("verify")
    p.add_argument("file")
    p.add_argument("--out", help="write attestation json to file")
    p.add_argument("--keep", action="store_true", help="keep replay workdir")
    p.set_defaults(fn=cmd_verify)
    p = sub.add_parser("publish")
    p.add_argument("dir")
    p.add_argument("-r", "--registry", required=True, help="GitHub repo, e.g. lilyco-42/mpkg-registry")
    p.set_defaults(fn=cmd_publish)
    p = sub.add_parser("search")
    p.add_argument("term")
    p.add_argument("-r", "--registry", required=True)
    p.set_defaults(fn=cmd_search)
    p = sub.add_parser("install")
    p.add_argument("name", help="package name 或 id 前缀")
    p.add_argument("-r", "--registry", required=True)
    p.add_argument("-o", "--out", default=".", help="artifacts 解包目录")
    p.add_argument("--verify", action="store_true", help="安装前完整回放验证")
    p.set_defaults(fn=cmd_install)
    p = sub.add_parser("attest")
    p.add_argument("file", help="attestation json（mpkg verify --out 的产物）")
    p.add_argument("-r", "--registry", required=True)
    p.set_defaults(fn=cmd_attest)
    args = ap.parse_args()
    args.fn(args)


# ── 注册表（GitHub repo 即 registry，普通人路径：raw 下载 + gh api 上架） ──────────

def _gh(*argv: str) -> str:
    r = subprocess.run(["gh", "api", *argv], capture_output=True, text=True)
    if r.returncode != 0:
        die(f"gh api failed: {r.stderr.strip()[:300]}")
    return r.stdout


def gh_put_file(repo: str, path: str, data: bytes, message: str):
    # contents API：更新需带旧文件 sha
    sha = None
    r = subprocess.run(["gh", "api", f"repos/{repo}/contents/{path}",
                        "--jq", ".sha"], capture_output=True, text=True)
    if r.returncode == 0:
        sha = r.stdout.strip()
    argv = ["-X", "PUT", f"repos/{repo}/contents/{path}",
            "-f", f"message={message}",
            "-f", f"content={base64.b64encode(data).decode()}"]
    if sha:
        argv += ["-f", f"sha={sha}"]
    _gh(*argv)


def registry_index(repo: str) -> dict:
    # gh api 读 contents = 实时且无 CDN 缓存; raw 有 ~5min 缓存, 仅作匿名回退
    r = subprocess.run(["gh", "api", f"repos/{repo}/contents/index.json",
                        "--jq", ".content"], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        return json.loads(base64.b64decode(r.stdout.strip()))
    url = f"https://raw.githubusercontent.com/{repo}/main/index.json"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return json.load(r)
    except Exception as e:
        die(f"cannot read registry index {url}: {e}")


def build_bytes(root: str) -> tuple:
    """打包到内存，返回 (manifest, files, pid, zip_bytes, filename)"""
    m = load_manifest(root)
    files = collect_files(root)
    pid = package_id(m, files)
    bio = tempfile.SpooledTemporaryFile(max_size=32 * 1024 * 1024)
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(files):
            z.write(os.path.join(root, rel), arcname=rel)
    bio.seek(0)
    blob = bio.read()
    fname = f"{m['name']}-{m['version']}-{pid[7:19]}.mpkg"
    return m, files, pid, blob, fname


def cmd_publish(args):
    m, files, pid, blob, fname = build_bytes(os.path.abspath(args.dir))
    entry = {
        "name": m["name"], "version": m["version"], "id": pid, "file": f"packages/{fname}",
        "intent": m.get("intent", ""), "tags": m.get("tags", []),
        "author": m.get("author", ""), "size": len(blob),
        "published_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    print(f"publishing {fname} ({len(blob)} bytes) id={pid[:27]}…")
    gh_put_file(args.registry, f"packages/{fname}", blob, f"publish {m['name']} {m['version']} {pid[:19]}")
    idx = None
    r = subprocess.run(["gh", "api", f"repos/{args.registry}/contents/index.json",
                        "--jq", ".content"], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        idx = json.loads(base64.b64decode(r.stdout.strip()))
    else:
        idx = {"registry": "mpkg", "version": "0.1", "packages": []}
    idx["packages"] = [p for p in idx.get("packages", [])
                       if not (p.get("name") == m["name"] and p.get("version") == m["version"])]
    idx["packages"].append(entry)
    gh_put_file(args.registry, "index.json",
                (json.dumps(idx, ensure_ascii=False, indent=2) + "\n").encode(),
                f"index: +{m['name']}@{m['version']}")
    print(json.dumps({"published": entry["file"], "id": pid}, ensure_ascii=False))


def cmd_attest(args):
    a = json.load(open(args.file, encoding="utf-8"))
    if not a.get("ok"):
        die("refusing to attest a failed replay (attestation ok != true)")
    pid, name = a["mpkg_id"], a.get("name", "unknown")
    id12, ts = pid[7:19], time.strftime("%Y%m%dT%H%M%S")
    host = a.get("host", {})
    payload = {
        "id": pid, "name": name, "ok": True,
        "replayed_at": a.get("replayed_at"),
        "host_os": host.get("os"), "python": host.get("python"), "shell": host.get("shell"),
        "steps": len(a.get("steps", [])), "verify": len(a.get("verify", [])),
    }
    path = f"attestations/{name}/{id12}/{ts}.json"
    gh_put_file(args.registry, path,
                json.dumps(payload, ensure_ascii=False, indent=2).encode(),
                f"attest {name} {id12} @ {ts}")
    r = subprocess.run(["gh", "api", f"repos/{args.registry}/contents/index.json",
                        "--jq", ".content"], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        idx = json.loads(base64.b64decode(r.stdout.strip()))
        for p in idx.get("packages", []):
            if p.get("id") == pid:
                p["attestations"] = p.get("attestations", 0) + 1
        gh_put_file(args.registry, "index.json",
                    (json.dumps(idx, ensure_ascii=False, indent=2) + "\n").encode(),
                    f"index: attest count {name} {id12}")
    print(json.dumps({"attested": name, "id": pid[:27], "file": path},
                     ensure_ascii=False))


def cmd_search(args):
    idx = registry_index(args.registry)
    t = args.term.lower()
    hits = [p for p in idx.get("packages", [])
            if t in p.get("name", "").lower()
            or t in p.get("intent", "").lower()
            or any(t in str(tag).lower() for tag in p.get("tags", []))]
    for p in hits:
        print(f"{p['id'][:19]}  {p['name']}@{p['version']}  {p.get('size', 0)}B  "
              f"attest:{p.get('attestations', 0)}  {p.get('intent', '')[:60]}")
    print(f"-- {len(hits)} hit(s) in {args.registry}", file=sys.stderr)


def cmd_install(args):
    idx = registry_index(args.registry)
    q = args.name.lower()
    hits = [p for p in idx.get("packages", [])
            if p.get("name", "").lower() == q or p.get("id", "").startswith(q)]
    if not hits:
        die(f"not found in registry: {args.name}")
    hits.sort(key=lambda p: p.get("published_at", ""), reverse=True)
    entry = hits[0]
    url = f"https://raw.githubusercontent.com/{args.registry}/main/{entry['file']}"
    print(f"install {entry['name']}@{entry['version']} id={entry['id'][:27]}…")
    with tempfile.TemporaryDirectory() as td:
        fpath = os.path.join(td, "p.mpkg")
        urllib.request.urlretrieve(url, fpath)
        # 安装门禁：重算 content id 必须与注册表登记一致（防篡改）
        with zipfile.ZipFile(fpath) as z:
            m = json.loads(z.read(MANIFEST).decode("utf-8"))
            validate(m)
            files = {rel: hashlib.sha256(z.read(rel)).hexdigest() for rel in z.namelist()}
        got = package_id(m, files)
        if got != entry["id"]:
            die(f"content id mismatch: got {got}, registry says {entry['id']}")
        if args.verify:
            print("running replay verification…", file=sys.stderr)
            cmd_verify_core(fpath, None, keep=False, expect_ok=True)
        os.makedirs(args.out, exist_ok=True)
        with zipfile.ZipFile(fpath) as z:
            for rel in z.namelist():
                if rel.startswith("artifacts/"):
                    dest = os.path.join(args.out, rel[len("artifacts/"):])
                    os.makedirs(os.path.dirname(dest) or args.out, exist_ok=True)
                    with z.open(rel) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
        print(json.dumps({"installed": entry["name"], "id": got, "out": args.out},
                         ensure_ascii=False))


def cmd_verify_core(file: str, out: str | None, keep: bool, expect_ok: bool):
    """cmd_verify 的可复用内核（install --verify 调用）"""
    sys.argv = ["mpkg", "verify", file] + (["--out", out] if out else [])
    try:
        cmd_verify(argparse.Namespace(file=file, out=out, keep=keep))
    except SystemExit as e:
        if expect_ok and e.code not in (0, None):
            die(f"replay verification failed (exit {e.code})")
        raise


if __name__ == "__main__":
    main()
