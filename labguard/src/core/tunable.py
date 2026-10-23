"""
可远程调整的参数白名单与校验（开发板网页、总后台、总后台下发三处共用）
src/core/tunable.py

不依赖 Qt / FastAPI，开发板和总后台都能导入。
断电类阈值的上限取本控制盒的硬上限（config.yaml → hardware），保证开发板的规则总比固件先动作。
"""
from typing import Any, Dict, Optional, Tuple

# 路径 → (类型, 最小值, 最大值, 说明, 分组)
TUNABLE: Dict[str, Tuple[type, float, float, str, str]] = {
    "rules.heating_on_c": (float, 30, 100, "判定为正在加热的热源温度 ℃", "热源"),
    "rules.dry_burn_c": (float, 80, 200, "干烧断电阈值 ℃", "热源"),
    "rules.rate_c_per_s": (float, 0.2, 10, "升温异常速率 ℃/s", "热源"),
    "rules.rate_min_c": (float, 40, 150, "升温异常最低温度 ℃", "热源"),
    "rules.unattended_heating_cut_s": (float, 10, 600, "加热无人值守断电时限 s", "人员"),
    "rules.predict_eta_warn_s": (float, 10, 600, "预测干烧提前预警 s", "热源"),
    "rules.boil_unattended_warn_s": (float, 30, 3600, "沸腾无人看守预警 s", "热源"),
    "rules.smoke_raw": (int, 300, 4000, "烟雾断电阈值（MQ-2 原始值）", "烟雾"),
    "rules.humidity_high": (float, 50, 95, "高湿告警 %", "环境"),
    "rules.ambient_high_c": (float, 28, 60, "环境高温告警 ℃", "环境"),
    "presence.absent_seconds": (float, 3, 120, "判定无人值守所需时长 s", "人员"),
    "voting.on_ratio": (float, 0.3, 1.0, "违规确认帧占比", "识别"),
    "events.reminder_s": (float, 0, 600, "违规持续时重复语音间隔 s（0 = 不重复）", "提醒"),
    "vision.conf": (float, 0.1, 0.9, "检测置信度阈值", "识别"),
    "vision.iou": (float, 0.1, 0.9, "NMS IoU 阈值", "识别"),
}


def tunable_spec(hard_limit_c: Optional[float] = None, smoke_limit_raw: Optional[int] = None) -> Dict[str, tuple]:
    """返回带硬上限的白名单。不传硬上限时读本机 config.yaml → hardware"""
    if hard_limit_c is None or smoke_limit_raw is None:
        from src.config import cfg
        hard_limit_c = float(cfg("hardware.hard_limit_c", 150.0)) if hard_limit_c is None else hard_limit_c
        smoke_limit_raw = int(cfg("hardware.smoke_limit_raw", 2500)) if smoke_limit_raw is None else smoke_limit_raw
    spec = dict(TUNABLE)
    typ, lo, _, label, grp = spec["rules.dry_burn_c"]
    spec["rules.dry_burn_c"] = (typ, lo, float(hard_limit_c) - 5,
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
    # 跨字段约束：干烧阈值必须比"正在加热"阈值高 10℃ 以上
    dry = changed.get("rules.dry_burn_c", current.get("rules.dry_burn_c"))
    heat = changed.get("rules.heating_on_c", current.get("rules.heating_on_c"))
    if dry is not None and heat is not None and float(dry) <= float(heat) + 10:
        errors["rules.dry_burn_c"] = "干烧阈值必须比加热阈值高 10℃ 以上"
        changed.pop("rules.dry_burn_c", None)
        changed.pop("rules.heating_on_c", None)
    return changed, errors


def label(key: str) -> str:
    s = TUNABLE.get(key)
    return s[3] if s else key
