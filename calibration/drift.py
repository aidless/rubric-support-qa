"""judge 校准漂移检测（纯库函数）。

原始路径（只读复用）：
    judge-calibration-api/calibration_monitor.py（本地私有仓，未公开）

与原文的差异：
  1. 原文硬编码一个本机绝对路径 `SCHED = Path(...)`，并直接
     `from judge_run import judge_one`；这里两者都删掉，本模块不碰模型、不碰文件系统。
  2. 原文 `--check` / `--selftest` 模式改成调用方驱动：本模块只提供
     `compute_fnr_fpr` / `load_baseline` / `check_drift`。
  3. 原文的"连续两次漂移 → UNCALIBRATED"是带状态的调度逻辑；这里不引入状态，
     由调用方用 `DriftTracker` 或自行累计（原语义见 `consecutive_drift_state`）。
  4. 阈值保持原文：ΔFNR > 0.05 或 ΔFPR > 0.05 即漂移。
"""
from __future__ import annotations

import json
from pathlib import Path

DRIFT_FNR_DELTA = 0.05
DRIFT_FPR_DELTA = 0.05


def compute_fnr_fpr(verdicts: list[dict]) -> dict:
    """从 verdicts（含 gold + judge_label）算 FNR/FPR。

    gold / judge_label 约定：1 = 正例（正确），0 = 负例（错误）。
    """
    tp = sum(1 for v in verdicts if v["gold"] == 1 and v["judge_label"] == 1)
    fn = sum(1 for v in verdicts if v["gold"] == 1 and v["judge_label"] == 0)
    tn = sum(1 for v in verdicts if v["gold"] == 0 and v["judge_label"] == 0)
    fp = sum(1 for v in verdicts if v["gold"] == 0 and v["judge_label"] == 1)
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    return {"fnr": round(fnr, 4), "fpr": round(fpr, 4),
            "tp": tp, "fn": fn, "tn": tn, "fp": fp,
            "n": len(verdicts)}


def load_baseline(path: Path) -> dict:
    """加载历史校准基线（calibration.json 格式，字段缺失时给保守默认值）。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {"fnr": data.get("fnr", 0.0), "fpr": data.get("fpr", 0.0),
            "n_gold": data.get("n_gold", 0),
            "prompt_version": data.get("prompt_version", "?"),
            "source": str(path)}


def check_drift(current: dict, baseline: dict) -> dict:
    """对比当前与基线，返回漂移判定（无状态）。"""
    delta_fnr = current["fnr"] - baseline["fnr"]
    delta_fpr = current["fpr"] - baseline["fpr"]
    drifted = abs(delta_fnr) > DRIFT_FNR_DELTA or abs(delta_fpr) > DRIFT_FPR_DELTA
    return {"delta_fnr": round(delta_fnr, 4), "delta_fpr": round(delta_fpr, 4),
            "drifted": drifted,
            "threshold_fnr": DRIFT_FNR_DELTA, "threshold_fpr": DRIFT_FPR_DELTA,
            "verdict": "DRIFT_DETECTED" if drifted else "STABLE"}


def consecutive_drift_state(history: list[dict]) -> str:
    """把多次 `check_drift` 结果折叠成校准状态。

    保留原文语义：连续两次漂移 → UNCALIBRATED；单次漂移 → DRIFT_DETECTED；
    否则 STABLE。history 按时间从旧到新排列。
    """
    if len(history) >= 2 and history[-1]["drifted"] and history[-2]["drifted"]:
        return "UNCALIBRATED"
    if history and history[-1]["drifted"]:
        return "DRIFT_DETECTED"
    return "STABLE"
