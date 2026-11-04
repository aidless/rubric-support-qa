"""校准库：人机一致性、κ、漂移、置信区间。

全部为纯函数，不读硬编码路径、不调模型、不写文件。

来源与改造说明
--------------
- `agreement.py`  改造自
  `judge-calibration-api/human_gold_consistency.py`（本地私有的 judge-calibration 仓）
  - 保留：`kappa` / `pearson` / `spearman` 的实现与门禁阈值
  - 改造：把 CLI 中的计算逻辑抽成 `binary_consistency` / `continuous_consistency`
  - 新增：`fleiss_kappa`（原文件没有，用于 3 家裁判一致性 H3）
- `drift.py`      改造自
  `judge-calibration-api/calibration_monitor.py`
  - 保留：`compute_fnr_fpr` / `load_baseline` / `check_drift` 与 0.05 阈值
  - 改造：去掉本机绝对路径硬编码、去掉对 `judge_run.judge_one` 的绑定
  - 保留原文件的"连续两次漂移"语义由调用方累计，不在库内做状态
- `intervals.py`  改编自
  `eval-gate/eval_gate/stats.py`（公开仓 aidless/eval-gate）
  - 保留：Wilson 区间实现
"""

from .agreement import (GATE_KAPPA, GATE_AGREEMENT, GATE_RHO, GATE_OFFSET,
                        binary_consistency, continuous_consistency, fleiss_kappa,
                        kappa, pearson, spearman)
from .drift import (DRIFT_FNR_DELTA, DRIFT_FPR_DELTA, check_drift,
                    compute_fnr_fpr, load_baseline)
from .intervals import ci_width, wilson_interval

__all__ = [
    "GATE_KAPPA", "GATE_AGREEMENT", "GATE_RHO", "GATE_OFFSET",
    "binary_consistency", "continuous_consistency", "fleiss_kappa",
    "kappa", "pearson", "spearman",
    "DRIFT_FNR_DELTA", "DRIFT_FPR_DELTA", "check_drift",
    "compute_fnr_fpr", "load_baseline",
    "ci_width", "wilson_interval",
]
