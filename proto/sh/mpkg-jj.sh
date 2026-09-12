#!/bin/bash
# mpkg-jj —— mpkg trace ↔ jj commits 双向桥 (spec mpkg-v0 §6.5)
#
# 用法:
#   mpkg-jj record <pkg-dir> <repo-dir>   逐条执行 steps, 每步一个 jj commit
#   mpkg-jj replay <pkg-dir> <repo-dir>   逐 commit 检出重执行, 分叉即停
#
# 原理: record 模式每步执行后 jj 自动快照 → 历史 = trace 1:1 (空变化允许空提交);
#       replay 模式把 repo 重置到初始状态, 逐提交重跑命令, 每步后比对工作副本树与
#       记录提交的树 —— 分叉即停, jj diff 直接展示偏离内容。
set -euo pipefail

PKG="${1:?usage: mpkg-jj record|replay <pkg-dir> <repo-dir>}"
REPO="${2:?usage: mpkg-jj record|replay <pkg-dir> <repo-dir>}"
MODE="${3:-}"
ABS_PKG=$(cd "$PKG" && pwd)   # 绝对路径: record/replay 内部会 cd

command -v jj >/dev/null || { echo "jj not found"; exit 1; }

steps() { python3 - "$ABS_PKG/mpkg.json" <<'PY'
import json, sys
for i, s in enumerate(json.load(open(sys.argv[1]))["steps"], 1):
    print(f"{i}\t{s['run']}")
PY
}

case "$MODE" in
record)
  rm -rf "$REPO" && mkdir -p "$REPO" && cd "$REPO"
  jj git init --colocate . >/dev/null 2>&1
  steps | while IFS=$'\t' read -r n cmd; do
    full=${cmd//\{\{pkg\}\}/$ABS_PKG}
    full=${full//\{\{work\}\}/$PWD}
    echo "── step $n: $cmd"
    bash -c "$full" || { echo "FAILED at step $n"; exit 1; }
    jj commit -m "step $n: ${full:0:60}" >/dev/null 2>&1 || jj commit --allow-empty -m "step $n: $cmd" >/dev/null 2>&1
  done
  echo "== trace recorded: $(jj log -r 'ancestors(@, 20)' --no-graph -T 'commit_id.short()' | wc -l) commits =="
  jj log --no-pager -T 'description.first_line()' -r '::@' --limit 12 | head -10
  ;;
replay)
  cd "$REPO"
  FIRST=$(jj log -r 'root()' --no-graph -T 'commit_id.short()' | head -1)
  FAIL=0
  steps | while IFS=$'\t' read -r n cmd; do
    full=${cmd//\{\{pkg\}\}/$ABS_PKG}
    full=${full//\{\{work\}\}/$PWD}
    # 检出该步的父提交 (重放起点)
    rev=$(jj log -r "description(glob:\"step $n:*\")" --no-graph -T 'commit_id.short()' | head -1)
    [ -z "$rev" ] && { echo "step $n: no recorded commit"; FAIL=1; exit 1; }
    jj new "$rev-" >/dev/null 2>&1 || jj new "root()" >/dev/null 2>&1
    echo "── replay step $n: $cmd"
    if ! bash -c "$full"; then
      echo "REPLAY DIVERGED at step $n —— jj diff 查看偏离:"
      jj diff --stat 2>/dev/null | head -5
      FAIL=1; exit 1
    fi
    jj commit -m "replay step $n" >/dev/null 2>&1 || true
  done
  [ "$FAIL" = 0 ] && echo "== REPLAY CLEAN: 全部步骤一致 =="
  ;;
*)
  echo "unknown mode: $MODE (record|replay)"; exit 1;;
esac
