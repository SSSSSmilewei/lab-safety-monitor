"""
主控决策：实验室环境预设
center/presets.py

不同实验室的"正常"不一样：普通化学实验室热源过了 120℃ 就是干烧；油浴 / 高温合成实验室本来就工作在 150℃ 以上，
用同一套阈值要么天天误断电、要么形同虚设。所以阈值按区域配置，下级覆盖上级（楼 → 房间 → 实验桌）。

预设只是起点，管理员可以在面板里逐项再调。
断电类阈值最终还要满足每个终端控制盒的硬上限（终端上报，节点本地再校验一次）——
高温实验室需要配高量程测温仪，并把固件 HARD_LIMIT_C 和终端 config.yaml → hardware 一起调高。
"""
from typing import Any, Dict

PRESETS: Dict[str, Dict[str, Any]] = {
    "standard": {
        "name": "常规化学实验室",
        "desc": "水溶液加热、滴定、配制溶液等常见教学实验（系统出厂默认值）",
        "rules": {
            "rules.heating_on_c": 50, "rules.dry_burn_c": 120, "rules.rate_c_per_s": 2.0, "rules.rate_min_c": 80,
            "rules.unattended_heating_cut_s": 60, "rules.predict_eta_warn_s": 90, "rules.boil_unattended_warn_s": 300,
            "rules.smoke_raw": 1800, "rules.humidity_high": 80, "rules.ambient_high_c": 40,
            "presence.absent_seconds": 15,
        },
    },
    "organic": {
        "name": "有机溶剂实验室",
        "desc": "乙醇、丙酮等易燃溶剂：沸点低、蒸气易燃，离人与烟雾判断更严",
        "rules": {
            "rules.heating_on_c": 40, "rules.dry_burn_c": 100, "rules.rate_c_per_s": 1.5, "rules.rate_min_c": 60,
            "rules.unattended_heating_cut_s": 30, "rules.predict_eta_warn_s": 120, "rules.boil_unattended_warn_s": 180,
            "rules.smoke_raw": 1400, "rules.humidity_high": 80, "rules.ambient_high_c": 35,
            "presence.absent_seconds": 10,
        },
    },
    "high_temp": {
        "name": "高温实验室",
        "desc": "油浴、砂浴、高温合成：热源长期高于 120℃。需配高量程测温仪并调高控制盒硬上限",
        "rules": {
            "rules.heating_on_c": 80, "rules.dry_burn_c": 240, "rules.rate_c_per_s": 4.0, "rules.rate_min_c": 150,
            "rules.unattended_heating_cut_s": 60, "rules.predict_eta_warn_s": 60, "rules.boil_unattended_warn_s": 600,
            "rules.smoke_raw": 1800, "rules.humidity_high": 85, "rules.ambient_high_c": 45,
            "presence.absent_seconds": 15,
        },
    },
    "teaching": {
        "name": "学生教学实验室（初学者）",
        "desc": "初学者多：离人更快提醒，重复语音更频繁",
        "rules": {
            "rules.heating_on_c": 45, "rules.dry_burn_c": 115, "rules.rate_c_per_s": 1.8, "rules.rate_min_c": 75,
            "rules.unattended_heating_cut_s": 45, "rules.predict_eta_warn_s": 120, "rules.boil_unattended_warn_s": 240,
            "rules.smoke_raw": 1600, "rules.humidity_high": 80, "rules.ambient_high_c": 38,
            "presence.absent_seconds": 10, "events.reminder_s": 20,
        },
    },
}


def check_hard_limits(rules: Dict[str, Any], hard_limit_c: float, smoke_limit_raw: int) -> Dict[str, str]:
    """对照某个终端控制盒的硬上限检查；返回 {key: 说明}（只提示，最终以终端本地校验为准）"""
    warn = {}
    dry = rules.get("rules.dry_burn_c")
    if dry is not None and float(dry) > float(hard_limit_c) - 5:
        warn["rules.dry_burn_c"] = (f"该终端控制盒硬上限 {hard_limit_c:.0f}℃，干烧阈值 {float(dry):.0f}℃ 不会下发；"
                                    "请换高量程测温仪并调高固件硬上限")
    smoke = rules.get("rules.smoke_raw")
    if smoke is not None and int(smoke) > int(smoke_limit_raw) - 100:
        warn["rules.smoke_raw"] = f"该终端控制盒烟雾硬上限 {smoke_limit_raw}，烟雾阈值 {smoke} 不会下发"
    return warn
