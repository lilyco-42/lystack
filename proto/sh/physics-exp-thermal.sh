#!/bin/bash
# physics-exp-thermal —— 物理实验配方 v0: CPU 负载-温升实验 (纯 CLI 仪器)
# 用法: physics-exp-thermal.sh <datadir>
# 输出: <datadir>/thermal.csv (t,temp_load,phase) + 实验 trace
set -euo pipefail
OUT="${1:?usage: physics-exp-thermal.sh <datadir>}"
mkdir -p "$OUT"
TZ=/sys/class/thermal/thermal_zone0/temp
SAMPLES=12   # 每阶段 12 个样本 x 5s = 60s/阶段

temp() { cat "$TZ"; }   # 毫摄氏度 (物理感官: CLI 仪器)

phase() { # $1=phase名 $2=是否施加载荷
  local phase="$1" load="$2" i t
  if [ "$load" = 1 ]; then
    for _ in $(nproc); do yes >/dev/null 2>&1 & done   # 物理扰动: 满载
  fi
  for i in $(seq 1 $SAMPLES); do
    t=$(temp)
    echo "$(date +%s),$t,$phase" >> "$OUT/thermal.csv"
    sleep 5
  done
  if [ "$load" = 1 ]; then pkill -f "yes >/dev/null" 2>/dev/null || pkill yes 2>/dev/null || true; fi
}

echo "t,temp,phase" > "$OUT/thermal.csv"
echo "=== phase 1: idle (基线) ===" >&2
phase idle 0
echo "=== phase 2: load (扰动) ===" >&2
phase load 1
echo "=== phase 3: idle (恢复) ===" >&2
phase cool 0
echo "=== experiment complete: $OUT/thermal.csv ===" >&2
