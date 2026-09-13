#!/bin/bash
# asr-code-build —— 官方书源 → 蒸馏 → 打包 → 发布 mpkg (GitHub Runner 上跑)
# 需要: MPKG_TOKEN (对 mpkg-registry 有写权的 PAT, gh 认证用)
# 用法: MPKG_TOKEN=xxx asr-code-build.sh [registry]
set -euo pipefail

REGISTRY="${1:-lilyco-42/mpkg-registry}"
: "${MPKG_TOKEN:?need MPKG_TOKEN}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "== 1. fetch book sources (gh api, 稳定路由) =="
mkdir -p "$WORK/book"
for md in ch01-00-getting-started ch01-01-installation ch01-02-hello-world           ch01-03-hello-cargo ch02-00-guessing-game-tutorial           ch03-00-common-programming-concepts ch03-01-variables-and-mutability           ch03-02-data-types ch03-03-functions ch03-04-comments ch03-05-control-flow           ch04-00-understanding-ownership ch04-01-what-is-ownership           ch04-02-references-and-borrowing ch04-03-slices; do
  if gh api "repos/rust-lang/book/contents/src/$md.md" --jq .content | base64 -d > "$WORK/book/$md.md" 2>/dev/null; then
    echo "  $md $(stat -c%s "$WORK/book/$md.md")B"
  else
    echo "  $md SKIP (源缺失)"
    rm -f "$WORK/book/$md.md"
    continue
  fi
done

echo "== 2. distill =="
python3 "$HERE/../py/asr_code_distill.py" distill "$WORK"

echo "== 3. assemble package =="
PKG="$WORK/pkg"
mkdir -p "$PKG/artifacts" "$PKG/atoms"
cp "$HERE/../py/asr_code_distill.py" "$PKG/artifacts/"
cp -r "$WORK/book" "$PKG/book"
cp -r "$WORK/atoms/." "$PKG/atoms/"
cp "$WORK/asr-code.json" "$PKG/asr-code.json"
cat > "$PKG/mpkg.json" <<EOF2
{
  "mpkg": "0.1",
  "name": "asr-code-rust-book",
  "version": "0.1.$(date +%j)",
  "intent": "Rust 官方教程 (The Book ch01-02) 知识蒸馏包: 逐条定位知识原子 + 确定性重蒸验证配方 (asr_code 蒸馏器)",
  "author": "agent:lilyco-42/lyco_agent (CI)",
  "created": "$(date +%Y-%m-%d)",
  "requirements": { "tools": [{ "name": "python3" }] },
  "steps": [
    { "run": "mkdir -p {{work}}/out && cp -r {{pkg}}/book {{work}}/out/book && cp {{pkg}}/asr-code.json {{work}}/out/asr-code.json", "expect": { "exit": 0 } },
    { "run": "python3 -B {{pkg}}/artifacts/asr_code_distill.py distill {{work}}/out", "expect": { "exit": 0 } },
    { "run": "python3 -c \"import json,sys; a=json.load(open(sys.argv[1])); b=json.load(open(sys.argv[2])); sys.exit(0 if a==b else 1)\" {{work}}/out/asr-code.json {{pkg}}/asr-code.json", "expect": { "exit": 0 } }
  ],
  "verify": [
    "python3 -c \"import json,sys; a=json.load(open(sys.argv[1])); b=json.load(open(sys.argv[2])); sys.exit(0 if a==b else 1)\" {{pkg}}/asr-code.json {{work}}/out/asr-code.json"
  ],
  "atoms": [
    { "kind": "text", "path": "asr-code.json", "title": "asr-code 知识原子索引" }
  ],
  "provenance": { "generator": "human+ai:z-ai/glm-5.3-flash (CI)" },
  "tags": ["rust", "asr-code", "knowledge", "learning", "book"],
  "license": "MIT OR Apache-2.0"
}
EOF2

echo "== 4. publish =="
unset GH_TOKEN   # gh 回退到 auth login 的 MPKG_TOKEN (跨仓写权)
echo "$MPKG_TOKEN" | gh auth login --with-token
python3 "$HERE/../py/mpkg.py" publish "$PKG" -r "$REGISTRY"
echo "== ASR_BUILD_DONE =="
