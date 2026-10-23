"""
交叉验证：人员模型 × 器皿模型 × 传感器 → 当前工况与三级风险
src/core/cross_check.py

单看一路数据容易误判："没戴护目镜"在整理台面时只是提醒，在加热沸腾的烧杯旁边就是飞溅风险；
"台面有试剂瓶"本身没事，和"有人在吃东西"同时出现才危险。这里把三路数据放在一起看：
  · 人员模型（全景）：是否有人、缺哪件防护、饮食、伏案
  · 器皿模型（台面）：可加热器皿、不可加热量器、靠近桌边
  · 传感器与温度预测：是否在加热、沸腾、干烧风险分、断电锁定
得到：工况（在做什么）+ 风险等级（低 / 中 / 高）+ 每条依据，信号灯按风险等级亮（绿 / 黄 / 红）。

纯函数、确定性、可测试；只决定"提醒到什么程度"，不参与断电（断电只由 state_machine 的规则执行）。
安全助手（大模型）读取这里的结果来回答"现在有多危险、该怎么办"。
"""
from typing import Any, Dict, Iterable, List

LEVELS = ("low", "mid", "high")
LEVEL_TEXT = {"low": "低危", "mid": "中危", "high": "高危"}
LEVEL_LIGHT = {"low": 0, "mid": 1, "high": 2}     # 与心跳灯光等级一致：0 绿 1 黄 2 红
MID_SCORE, HIGH_SCORE = 30, 70

HEATABLE = {"beaker", "conical flask", "flat bottom flask", "round bottom flask", "pear shaped flask", "test tube"}
NON_HEATABLE = {"volumetric flask", "measuring cylinder", "reagent bottle", "burette", "pipette", "wash bottle"}
REAGENT = {"reagent bottle", "wash bottle"}

PPE_NAMES = {"ppe_goggles": "护目镜", "ppe_coat": "实验服", "ppe_gloves": "手套", "ppe_mask": "口罩",
             "ppe_headmask": "头罩"}


def _norm(items: Iterable[str]) -> set:
    return {str(i).strip().lower() for i in items or []}


def assess(d: Dict[str, Any], mid_score: float = MID_SCORE, high_score: float = HIGH_SCORE) -> Dict[str, Any]:
    """
    输入字段（缺省视为未知 / 没有）：
      person_present: True / False / None（画面无效）
      ppe_missing:    ["ppe_goggles", ...]  已确认的防护缺失
      eating, sleeping, edge_risk: bool
      chem_items:     器皿类别名列表
      obj_temp:       热源温度 ℃ 或 None
      heating:        是否正在加热（继电器闭合且热源温度达到加热阈值）
      wm_phase, wm_risk, wm_eta_s: 温度预测
      latched:        是否断电锁定中
      event_levels:   当前活动事件的等级列表（NOTICE / WARNING / CRITICAL）
    返回：level / level_text / light / score / scene / factors[{source, text, points}]
    """
    factors: List[Dict[str, Any]] = []

    def add(source: str, text: str, points: int):
        factors.append({"source": source, "text": text, "points": points})

    items = _norm(d.get("chem_items"))
    heatable = sorted(items & HEATABLE)
    non_heatable = sorted(items & NON_HEATABLE)
    reagents = sorted(items & REAGENT)
    present = d.get("person_present")
    missing = [k for k in d.get("ppe_missing") or [] if k in PPE_NAMES]
    heating = bool(d.get("heating"))
    phase = d.get("wm_phase") or ""
    boiling = phase in ("boiling", "overheat") or (phase == "heating" and d.get("wm_eta_s") is not None)
    wm_risk = float(d.get("wm_risk") or 0.0)
    latched = bool(d.get("latched"))
    ev_levels = set(d.get("event_levels") or [])

    # ---------- 工况 ----------
    if latched:
        scene = "已断电，等待现场处理"
    elif heating and present is False:
        scene = "加热中，人员不在台前"
    elif heating and boiling:
        scene = "加热中（沸腾 / 高温阶段）"
    elif heating:
        scene = "加热操作中"
    elif present and items:
        scene = "台面操作中（未加热）"
    elif present:
        scene = "人员在台前，台面空闲"
    elif present is None:
        scene = "画面不可用，仅凭传感器判断"
    else:
        scene = "无人，台面空闲"

    # ---------- 交叉规则：人员 × 器皿 × 温度 ----------
    if latched:
        add("规则引擎", "断电锁定中：已发生过高危情况", 100)
    if "CRITICAL" in ev_levels and not latched:
        add("规则引擎", "存在紧急事件", 100)
    elif "WARNING" in ev_levels:
        add("规则引擎", "存在警告事件", 40)

    if heating and present is False:
        add("人员 × 传感器", "正在加热但台前无人", 70)
    if heating and d.get("sleeping"):
        add("人员 × 传感器", "加热中人员疑似伏案", 70)
    if d.get("eating") and (reagents or heating):
        add("人员 × 器皿", "台面有试剂 / 正在加热时出现饮食行为", 60)
    elif d.get("eating"):
        add("人员模型", "实验区饮食", 25)

    for k in missing:
        name = PPE_NAMES[k]
        if heating and k in ("ppe_goggles", "ppe_gloves"):
            add("人员 × 传感器", f"加热中未佩戴{name}（飞溅 / 烫伤风险）", 35 if boiling else 30)
        elif items and k in ("ppe_goggles", "ppe_gloves", "ppe_coat"):
            add("人员 × 器皿", f"台面有器皿时未佩戴{name}", 15)
        else:
            add("人员模型", f"未佩戴{name}", 8)

    if heating and non_heatable:
        add("器皿 × 传感器", f"加热时台面有不可加热量器（{', '.join(non_heatable)}）", 35)
    if d.get("edge_risk"):
        add("器皿模型" if not heating else "器皿 × 传感器",
            "器皿靠近桌边" + ("，且正在加热" if heating else ""), 35 if heating else 12)
    if heating and not heatable and present is not None and not items:
        add("器皿 × 传感器", "在加热但台面未识别到器皿，请确认摄像头角度", 10)

    if wm_risk >= 0.6:
        add("温度预测", f"干烧风险分 {wm_risk:.2f}", 70)
    elif wm_risk >= 0.3:
        add("温度预测", f"干烧风险分 {wm_risk:.2f}", 30)

    score = min(100, sum(f["points"] for f in factors))
    level = "high" if score >= high_score else "mid" if score >= mid_score else "low"
    factors.sort(key=lambda f: -f["points"])
    return {"level": level, "level_text": LEVEL_TEXT[level], "light": LEVEL_LIGHT[level], "score": score,
            "scene": scene, "factors": factors, "thresholds": {"mid": mid_score, "high": high_score},
            "inputs": {"person_present": present, "ppe_missing": missing, "heatable": heatable,
                       "non_heatable": non_heatable, "heating": heating, "phase": phase}}
