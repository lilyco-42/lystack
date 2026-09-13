#!/usr/bin/env python3
"""physics-verify —— 物理实验统计验证器 v0。

确定性验证 (mesh/mpkg) 在物理世界不成立: 温度有噪声与漂移。
物理回放的"一致" = 定性模式成立 + 定量容差内:
  P1 负载期温升显著 (≥ RISE_MIN 毫度)
  P2 恢复期温度回落 (峰谷差 ≥ FALL_MIN 毫度)
  P3 全程读数在物理合理区间 (0..110 °C)

用法: physics-verify.py <thermal.csv> [--json]
退出码: 0 = 物理模式一致; 2 = 模式不符; 1 = 数据不足。
"""
from __future__ import annotations

import json
import statistics
import sys

RISE_MIN = 1500   # 1.5°C 毫度单位
FALL_MIN = 800    # 0.8°C


def load(path: str) -> dict[str, list[int]]:
    data: dict[str, list[int]] = {}
    with open(path, encoding="utf-8") as f:
        next(f)
        for line in f:
            parts = line.strip().split(",")
            if len(parts) == 3:
                data.setdefault(parts[2], []).append(int(parts[1]))
    return data


def verify(path: str) -> dict:
    data = load(path)
    if not all(k in data for k in ("idle", "load", "cool")):
        return {"ok": False, "error": "missing phases", "phases": list(data)}
    idle = statistics.median(data["idle"])
    load_mean = statistics.mean(data["load"])
    load_max = max(data["load"])
    cool_end = statistics.median(data["cool"][-3:])

    rise = load_mean - idle
    fall = load_max - cool_end
    p1 = rise >= RISE_MIN
    p2 = fall >= FALL_MIN
    p3 = 0 < idle < 110000 and 0 < load_max < 110000

    checks = {
        "P1_load_rise": {"ok": p1, "rise_mc": round(rise), "threshold": RISE_MIN},
        "P2_cool_fall": {"ok": p2, "fall_mc": round(fall), "threshold": FALL_MIN},
        "P3_physical_range": {"ok": p3, "idle_mc": round(idle), "max_mc": round(load_max)},
    }
    verdict = {
        "ok": all(c["ok"] for c in checks.values()),
        "model": "统计容差 (定性模式 + 定量容差) —— 物理回放的非确定性验证",
        "idle_mc": round(idle),
        "load_mean_mc": round(load_mean),
        "peak_mc": round(load_max),
        "cool_end_mc": round(cool_end),
        "checks": checks,
    }
    return verdict


if __name__ == "__main__":
    v = verify(sys.argv[1])
    if "--json" in sys.argv:
        print(json.dumps(v, ensure_ascii=False, indent=2))
    else:
        for k, c in v["checks"].items():
            print(f"  {'PASS' if c['ok'] else 'FAIL'}  {k}")
        print(f"  => {'PHYSICS PATTERN MATCH' if v['ok'] else 'PATTERN MISMATCH'}")
    sys.exit(0 if v["ok"] else 2)
