"""人机一致性：Cohen κ、Pearson、Spearman、Fleiss κ。

原始路径（只读复用，未复制原仓其它部分）：
    /home/liuzewen/gh-publication-audit-20261029/judge-calibration-api/human_gold_consistency.py

与原文的差异：
  1. 原文把计算与 argparse/文件写出耦合在一个 `main()` 里；这里拆成纯函数，
     方便单测与后续 CLI 调用。
  2. 原文只输出 print/json；这里函数返回 dict，写文件由调用方负责。
  3. `fleiss_kappa` 为新增（原文没有），用于 3 家裁判一致性（预注册 H3）。
  4. 门禁阈值保持原文数值：κ≥0.6 或 agreement≥0.8；连续 |offset|≤0.5 且 ρ≥0.6。
"""
from __future__ import annotations

import math

GATE_KAPPA = 0.6
GATE_AGREEMENT = 0.80
GATE_RHO = 0.6
GATE_OFFSET = 0.5  # 10 分制下


def kappa(p11: int, p10: int, p01: int, p00: int) -> float:
    """Cohen's κ（二分类）。n=0 或 pe=1 时返回 nan。"""
    n = p11 + p10 + p01 + p00
    if n == 0:
        return float("nan")
    po = (p11 + p00) / n
    pe = ((p11 + p10) * (p11 + p01) + (p01 + p00) * (p10 + p00)) / (n * n)
    if pe == 1:
        return float("nan")
    return (po - pe) / (1 - pe)


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2 or n != len(ys):
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    vx = sum((a - mx) ** 2 for a in xs)
    vy = sum((b - my) ** 2 for b in ys)
    if vx == 0 or vy == 0:
        return float("nan")
    return cov / math.sqrt(vx * vy)


def spearman(xs: list[float], ys: list[float]) -> float:
    """秩相关；并列取平均秩（与原文一致）。"""

    def rank(vals: list[float]) -> list[float]:
        idx = sorted(range(len(vals)), key=lambda i: vals[i])
        ranks = [0.0] * len(vals)
        i = 0
        while i < len(idx):
            j = i
            while j + 1 < len(idx) and vals[idx[j + 1]] == vals[idx[i]]:
                j += 1
            r = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[idx[k]] = r
            i = j + 1
        return ranks

    return pearson(rank(xs), rank(ys))


def binary_consistency(human: list[int], judge: list[int]) -> dict:
    """二分类一致性：agreement、κ、以人为真的 judge FNR/FPR。"""
    if len(human) != len(judge):
        raise ValueError("human 与 judge 长度不一致")
    pairs = list(zip(human, judge))
    p11 = sum(1 for a, b in pairs if a == 1 and b == 1)
    p10 = sum(1 for a, b in pairs if a == 1 and b == 0)
    p01 = sum(1 for a, b in pairs if a == 0 and b == 1)
    p00 = sum(1 for a, b in pairs if a == 0 and b == 0)
    n = len(pairs)
    agreement = (p11 + p00) / n if n else float("nan")
    k = kappa(p11, p10, p01, p00)
    fnr = p10 / (p11 + p10) if (p11 + p10) else float("nan")
    fpr = p01 / (p01 + p00) if (p01 + p00) else float("nan")
    gate_ok = (not math.isnan(k) and k >= GATE_KAPPA) or agreement >= GATE_AGREEMENT
    return {
        "mode": "binary",
        "n": n,
        "agreement": round(agreement, 4) if not math.isnan(agreement) else None,
        "kappa": round(k, 4) if not math.isnan(k) else None,
        "judge_fnr_vs_human": round(fnr, 4) if not math.isnan(fnr) else None,
        "judge_fpr_vs_human": round(fpr, 4) if not math.isnan(fpr) else None,
        "confusion": {"tp": p11, "fn": p10, "fp": p01, "tn": p00},
        "gate": "PASS" if gate_ok else "FAIL",
        "gate_rule": "binary: kappa>=0.6 or agreement>=0.8",
    }


def continuous_consistency(human: list[float], judge: list[float]) -> dict:
    """连续分一致性：Pearson、Spearman、均值偏移、平均绝对差。"""
    if len(human) != len(judge):
        raise ValueError("human 与 judge 长度不一致")
    r_pearson = pearson(human, judge)
    rho = spearman(human, judge)
    diffs = [b - a for a, b in zip(human, judge)]
    offset = sum(diffs) / len(diffs) if diffs else float("nan")
    mad = sum(abs(d) for d in diffs) / len(diffs) if diffs else float("nan")
    gate_ok = abs(offset) <= GATE_OFFSET and (math.isnan(rho) or rho >= GATE_RHO)
    return {
        "mode": "continuous",
        "n": len(human),
        "pearson_r": round(r_pearson, 4) if not math.isnan(r_pearson) else None,
        "spearman_rho": round(rho, 4) if not math.isnan(rho) else None,
        "mean_offset": round(offset, 4) if not math.isnan(offset) else None,
        "mean_abs_diff": round(mad, 4) if not math.isnan(mad) else None,
        "gate": "PASS" if gate_ok else "FAIL",
        "gate_rule": "continuous: |mean_offset|<=0.5 (10pt) and rho>=0.6",
    }


def fleiss_kappa(counts: list[list[int]]) -> float:
    """Fleiss' κ（多评分者、类别计数矩阵）。

    counts[i][j] = 第 i 个样本被第 j 个类别评了几次；每行和必须相同且 >= 2。
    新增实现（原 judge-calibration 仓没有此函数，用于 H3 三家裁判一致性）。
    """
    if not counts or not counts[0]:
        return float("nan")
    n_raters = sum(counts[0])
    if n_raters < 2 or any(sum(row) != n_raters for row in counts):
        raise ValueError("每行评分者数量必须相同且 >= 2")
    big_n = len(counts)
    n_cat = len(counts[0])

    p_bar = 0.0
    for row in counts:
        p_bar += (sum(c * c for c in row) - n_raters) / (n_raters * (n_raters - 1))
    p_bar /= big_n

    totals = [sum(row[j] for row in counts) for j in range(n_cat)]
    p_e = sum((t / (big_n * n_raters)) ** 2 for t in totals)
    if p_e == 1:
        return float("nan")
    return (p_bar - p_e) / (1 - p_e)
