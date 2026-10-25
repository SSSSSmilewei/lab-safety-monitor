"""
主控决策：实验室环境预设
center/presets.py

不同实验室的"正常"不一样：易燃溶剂实验室离人要更快断电、台面温度更低就该停；加热操作多的实验室台面本来就偏热。
用同一套阈值要么天天误断电、要么形同虚设。所以阈值按区域配置，下级覆盖上级（楼 → 房间 → 实验桌）。

温度都指"台面温度"：控制盒的 SHT30 放在加热器旁 5～10 cm。
预设只是起点，管理员可以在面板里逐项再调。
断电类阈值最终还要满足每个终端控制盒的硬上限（终端上报，节点本地再校验一次）。
"""
from typing import Any, Dict

PRESETS: Dict[str, Dict[str, Any]] = {
    "standard": {
        "name": "常规化学实验室",
        "desc": "水溶液加热、滴定、配制溶液等常见教学实验（系统出厂默认值）",
        "rules": {
            "rules.heating_on_c": 35, "rules.overtemp_cut_c": 55, "rules.rate_c_per_min": 3.0,
            "rules.unattended_heating_cut_s": 60, "rules.predict_eta_warn_s": 90,
            "rules.smoke_raw": 1800, "rules.humidity_high": 80, "rules.ambient_high_c": 40,
            "presence.absent_seconds": 15,
        },
    },
    "organic": {
        "name": "有机溶剂实验室",
        "desc": "乙醇、丙酮等易燃溶剂：蒸气易燃，离人、升温与烟雾判断更严",
        "rules": {
            "rules.heating_on_c": 32, "rules.overtemp_cut_c": 48, "rules.rate_c_per_min": 2.0,
            "rules.unattended_heating_cut_s": 30, "rules.predict_eta_warn_s": 120,
            "rules.smoke_raw": 1400, "rules.humidity_high": 80, "rules.ambient_high_c": 35,
            "presence.absent_seconds": 10,
        },
    },
    "high_temp": {
        "name": "加热操作较多的实验室",
        "desc": "长时间加热、多台加热器：台面本来就偏热，断电线放宽，但不超过控制盒硬上限",
        "rules": {
            "rules.heating_on_c": 40, "rules.overtemp_cut_c": 62, "rules.rate_c_per_min": 4.0,
            "rules.unattended_heating_cut_s": 60, "rules.predict_eta_warn_s": 60,
            "rules.smoke_raw": 1800, "rules.humidity_high": 85, "rules.ambient_high_c": 45,
            "presence.absent_seconds": 15,
        },
    },
    "teaching": {
        "name": "学生教学实验室（初学者）",
        "desc": "初学者多：离人更快提醒，重复语音更频繁",
        "rules": {
            "rules.heating_on_c": 33, "rules.overtemp_cut_c": 52, "rules.rate_c_per_min": 2.5,
            "rules.unattended_heating_cut_s": 45, "rules.predict_eta_warn_s": 120,
            "rules.smoke_raw": 1600, "rules.humidity_high": 80, "rules.ambient_high_c": 38,
            "presence.absent_seconds": 10, "events.reminder_s": 20,
        },
    },
}


def check_hard_limits(rules: Dict[str, Any], hard_limit_c: float, smoke_limit_raw: int) -> Dict[str, str]:
    """对照某个终端控制盒的硬上限检查；返回 {key: 说明}（只提示，最终以终端本地校验为准）"""
    warn = {}
    cut = rules.get("rules.overtemp_cut_c")
    if cut is not None and float(cut) > float(hard_limit_c) - 5:
        warn["rules.overtemp_cut_c"] = (f"该终端控制盒台面温度硬上限 {hard_limit_c:.0f}℃，"
                                        f"超温断电阈值 {float(cut):.0f}℃ 不会下发")
    smoke = rules.get("rules.smoke_raw")
    if smoke is not None and int(smoke) > int(smoke_limit_raw) - 100:
        warn["rules.smoke_raw"] = f"该终端控制盒烟雾硬上限 {smoke_limit_raw}，烟雾阈值 {smoke} 不会下发"
    return warn
