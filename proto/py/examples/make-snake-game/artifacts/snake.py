#!/usr/bin/env python3
"""贪吃蛇 —— mpkg 示例包的可回放产物。纯标准库；--selftest 无头自检（CI/回放友好）。"""
from __future__ import annotations

import argparse
import json
import random
import sys

GRID_W, GRID_H = 24, 16
DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


class Game:
    def __init__(self, seed: int = 7):
        self.rng = random.Random(seed)
        self.snake = [(4, 8), (3, 8), (2, 8)]  # head first
        self.dir = DIRS["right"]
        self.food = self._spawn_food()
        self.score = 0
        self.alive = True

    def _spawn_food(self):
        free = [(x, y) for x in range(GRID_W) for y in range(GRID_H)
                if (x, y) not in self.snake]
        return self.rng.choice(free)

    def turn(self, d: str):
        if d not in DIRS:
            return
        dx, dy = DIRS[d]
        if (dx, dy) != (-self.dir[0], -self.dir[1]):  # 禁止 180° 掉头
            self.dir = (dx, dy)

    def step(self):
        if not self.alive:
            return
        hx, hy = self.snake[0]
        nx, ny = (hx + self.dir[0]) % GRID_W, (hy + self.dir[1]) % GRID_H  # 穿墙环绕
        if (nx, ny) in self.snake[:-1]:  # 尾巴本步会腾出，不算碰撞
            self.alive = False
            return
        self.snake.insert(0, (nx, ny))
        if (nx, ny) == self.food:
            self.score += 1
            self.food = self._spawn_food()
        else:
            self.snake.pop()


def selftest(steps: int, seed: int) -> dict:
    g = Game(seed=seed)
    # 脚本化走位：先转一圈避开初始直线，再一路向右直线环绕——确定性存活
    script = ["up", "right"] + ["right"] * max(steps - 2, 0)
    for i, d in enumerate(script[:steps]):
        g.turn(d)
        g.step()
        if not g.alive:
            break
    assert g.alive, f"snake died at step {i}"
    assert len(g.snake) >= 3, "snake length corrupted"
    assert 0 <= g.food[0] < GRID_W and 0 <= g.food[1] < GRID_H, "food out of grid"
    return {"selftest": "pass", "steps": steps, "score": g.score,
            "len": len(g.snake), "alive": g.alive}


def render(g: Game) -> str:
    rows = [["."] * GRID_W for _ in range(GRID_H)]
    fx, fy = g.food
    rows[fy][fx] = "*"
    for x, y in g.snake:
        rows[y][x] = "O"
    hx, hy = g.snake[0]
    rows[hy][hx] = "@"
    return "\n".join("".join(r) for r in rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="snake (mpkg example artifact)")
    ap.add_argument("--selftest", type=int, metavar="STEPS",
                    help="headless 自检 N 步，退出码 0=通过")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--render-steps", type=int, metavar="N",
                    help="渲染前 N 步 ASCII 画面（演示用）")
    args = ap.parse_args()
    if args.selftest is not None:
        print(json.dumps(selftest(args.selftest, args.seed)))
        return 0
    if args.render_steps is not None:
        g = Game(seed=args.seed)
        print(render(g))
        for _ in range(args.render_steps):
            g.step()
        print("\n--- after ---")
        print(render(g))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
