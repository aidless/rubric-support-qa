"""Wilson 95% 置信区间。

原始路径（只读复用）：
    eval-gate/eval_gate/stats.py（公开仓 aidless/eval-gate）
    （该实现本身由本项目 P2 落地，P1 这里按同一公式复用，避免两处口径不一致）

约定：n <= 0 时返回全程区间 (0.0, 1.0)，不伪造点估计。
"""
from __future__ import annotations

import math

Z95 = 1.959963984540054


def wilson_interval(successes: int, n: int, z: float = Z95) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def ci_width(successes: int, n: int, z: float = Z95) -> float:
    low, high = wilson_interval(successes, n, z)
    return high - low
