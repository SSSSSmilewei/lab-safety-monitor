"""
可远程调整的参数白名单与校验（开发板网页、总后台、总后台下发三处共用）
src/core/tunable.py

不依赖 Qt / FastAPI，开发板和总后台都能导入。
断电类阈值的上限取本控制盒的硬上限（config.yaml → hardware），保证开发板的规则总比固件先动作。
"""
from typing import Any, Dict, Optional, Tuple

# 路径 → (类型, 最小值, 最大值, 说明, 分组)
TUNABLE: Dict[str, Tuple[type, float, float, str, str]] = {
    "rules.heating_on_c": (float, 28, 80, "未接控制盒时判定为加热中的台面温度 ℃", "温度"),
    "rules.overtemp_cut_c": (float, 40, 120, "台面超温断电阈值 ℃", "温度"),
    "rules.rate_c_per_min": (float, 0.5, 20, "升温过快提醒 ℃/min", "温度"),
    "rules.unattended_heating_cut_s": (float, 10, 600, "加热无人值守断电时限 s", "人员"),
    "rules.predict_eta_warn_s": (float, 10, 600, "预测超温提前提醒 s", "温度"),
    "rules.smoke_raw": (int, 300, 4000, "烟雾断电阈值（MQ-2 原始值）", "烟雾"),
    "rules.humidity_high": (float, 50, 95, "高湿告警 %", "环境"),
    "rules.ambient_high_c": (float, 28, 60, "台面温度偏高提醒 ℃", "温度"),
    "presence.absent_seconds": (float, 3, 120, "判定无人值守所需时长 s", "人员"),
    "voting.on_ratio": (float, 0.3, 1.0, "违规确认帧占比", "识别"),
    "events.reminder_s": (float, 0, 600, "违规持续时重复语音间隔 s（0 = 不重复）", "提醒"),
    "vision.conf": (float, 0.1, 0.9, "检测置信度阈值", "识别"),
    "vision.iou": (float, 0.1, 0.9, "NMS IoU 阈值", "识别"),
    "cross.mid_score": (int, 10, 60, "交叉验证中危判定风险分", "交叉验证"),
    "cross.high_score": (int, 40, 100, "交叉验证高危判定风险分", "交叉验证"),
}


def tunable_spec(hard_limit_c: Optional[float] = None, smoke_limit_raw: Optional[int] = None) -> Dict[str, tuple]:
    """返回带硬上限的白名单。不传硬上限时读本机 config.yaml → hardware"""
    if hard_limit_c is None or smoke_limit_raw is None:
        from src.config import cfg
        hard_limit_c = float(cfg("hardware.hard_limit_c", 70.0)) if hard_limit_c is None else hard_limit_c
        smoke_limit_raw = int(cfg("hardware.smoke_limit_raw", 2500)) if smoke_limit_raw is None else smoke_limit_raw
    spec = dict(TUNABLE)
    typ, lo, _, label, grp = spec["rules.overtemp_cut_c"]
    spec["rules.overtemp_cut_c"] = (typ, lo, float(hard_limit_c) - 5,
                                f"{label}（需低于控制盒硬上限 {float(hard_limit_c):.0f}℃）", grp)
    typ, lo, _, label, grp = spec["rules.smoke_raw"]
    spec["rules.smoke_raw"] = (typ, lo, int(smoke_limit_raw) - 100,
                               f"{label}（需低于控制盒硬上限 {int(smoke_limit_raw)}）", grp)
    return spec


def validate(changes: Dict[str, Any], current: Dict[str, Any],
             spec: Optional[Dict[str, tuple]] = None) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """校验一组修改。current 用来检查跨字段约束（取当前值）。返回 (通过的修改, 错误说明)"""
    spec = spec or tunable_spec()
    changed, errors = {}, {}
    for key, val in (changes or {}).items():
        s = spec.get(key)
        if s is None:
            errors[key] = "不允许修改"
            continue
        typ, lo, hi = s[0], s[1], s[2]
        try:
            v = typ(val)
        except (TypeError, ValueError):
            errors[key] = "类型错误"
            continue
        if not (lo <= v <= hi):
            errors[key] = f"取值需在 {lo}–{hi}"
            continue
        changed[key] = v
    # 跨字段约束：断电线必须比偏高提醒线高 5℃ 以上
    cut = changed.get("rules.overtemp_cut_c", current.get("rules.overtemp_cut_c"))
    warn = changed.get("rules.ambient_high_c", current.get("rules.ambient_high_c"))
    if cut is not None and warn is not None and float(cut) < float(warn) + 5:
        errors["rules.overtemp_cut_c"] = "超温断电阈值必须比台面温度偏高提醒高 5℃ 以上"
        changed.pop("rules.overtemp_cut_c", None)
        changed.pop("rules.ambient_high_c", None)
    # 交叉验证：高危分界必须比中危高 10 分以上
    mid = changed.get("cross.mid_score", current.get("cross.mid_score"))
    high = changed.get("cross.high_score", current.get("cross.high_score"))
    if mid is not None and high is not None and float(high) < float(mid) + 10:
        errors["cross.high_score"] = "高危判定分必须比中危高 10 分以上"
        changed.pop("cross.mid_score", None)
        changed.pop("cross.high_score", None)
    return changed, errors


def label(key: str) -> str:
    s = TUNABLE.get(key)
    return s[3] if s else key
