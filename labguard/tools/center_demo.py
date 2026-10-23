#!/usr/bin/env python3
"""
总后台演示：建一套示例楼栋 / 实验室 / 实验桌 / 账号，并模拟多台终端持续上报（不需要开发板）。
用于答辩演示与前端调试；数据放在独立的数据库里，不碰正式的 runtime/center.db。

  python tools/center_demo.py                 # http://127.0.0.1:8210
  python tools/center_demo.py --port 8300 --db runtime/center_demo.db

账号：admin / Demo2026admin（管理员）· zhang_t / Demo2026teach（张老师，A/B/C 实验室）
      li_t / Demo2026teach（李老师，D 高温合成室 + C 实验室 1 号桌）· pixel / Demo2026pixel（像素风格示例账号）
"""
import argparse
import math
import os
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# 场景：(工况, 风险等级, 风险分, 热源℃, 依据[(来源, 文字, 分)], 进行中的事件[(等级, 标题)], 锁定)
SCENES = {
    "idle": ("无人，台面空闲", "low", 0, 24.0, [], [], False),
    "safe_heat": ("加热操作中", "low", 0, 86.0, [], [], False),
    "bench": ("台面操作中", "mid", 30, None, [("人员 × 器皿", "台面有器皿时未佩戴护目镜", 15), ("人员 × 器皿", "台面有器皿时未佩戴手套", 15)],
              [("NOTICE", "未佩戴护目镜"), ("NOTICE", "未佩戴手套")], False),
    "cylinder": ("加热操作中", "mid", 65, 63.2, [("器皿 × 传感器", "加热时台面有不可加热量器（measuring cylinder）", 35),
                                            ("人员 × 传感器", "加热中未佩戴护目镜（飞溅 / 烫伤风险）", 30)],
                 [("WARNING", "量器被加热"), ("NOTICE", "未佩戴护目镜")], False),
    "away": ("加热中，人员离岗", "high", 100, 97.8, [("人员 × 传感器", "正在加热但台前无人", 70), ("规则引擎", "存在警告事件", 40)],
             [("WARNING", "加热无人值守")], False),
    "latched": ("断电锁定中", "high", 100, 131.5, [("规则引擎", "断电锁定中：已发生过高危情况", 100)],
                [("CRITICAL", "干烧")], True),
    "oil": ("加热操作中", "low", 8, 186.0, [("人员模型", "未佩戴口罩", 8)], [], False),
}
PPE = [("ppe_goggles", "护目镜"), ("ppe_coat", "实验服"), ("ppe_gloves", "手套"), ("ppe_mask", "口罩")]


def snapshot(scene: str, t: float):
    s, lv, score, temp, factors, evs, latched = SCENES[scene]
    wobble = math.sin(t / 7.0) * 0.6
    bad = {"未佩戴护目镜": "ppe_goggles", "未佩戴手套": "ppe_gloves", "未佩戴口罩": "ppe_mask"}
    missing = {bad[k] for k in bad for f in factors if k.replace("未佩戴", "") in f[1]}
    present = scene not in ("idle", "away")
    return {
        "state": "CRITICAL" if latched or lv == "high" else "WARNING" if lv == "mid" else "NORMAL",
        "state_text": "断电锁定中" if latched else {"high": "危险", "mid": "注意", "low": "正常"}[lv],
        "latched": latched, "latch_reason": "热源 131℃ 超过干烧阈值 120℃" if latched else "",
        "telemetry": {"temp": round(24.5 + wobble, 1), "humi": round(52 + wobble * 3), "obj_temp": None if temp is None else round(temp + wobble * 2, 1),
                      "smoke": 210 + int(wobble * 20), "source": "demo"},
        "link": {"mcu": True, "relay_on": not latched},
        "vision": {"ok": True, "person_present": present, "fps": "9.8 FPS",
                   "ppe": [{"kind": k, "name": n, "status": ("bad" if k in missing else "ok") if present else "unknown"} for k, n in PPE]},
        "world_model": {"phase_text": "升温中" if temp and temp < 100 else "高温", "temp": temp, "eta_boil_s": 240 if scene == "cylinder" else None, "eta_s": None},
        "risk": {"level": lv, "level_text": {"high": "高危", "mid": "中危", "low": "低危"}[lv], "light": {"low": 0, "mid": 1, "high": 2}[lv],
                 "score": score, "scene": s, "factors": [{"source": a, "text": b, "points": c} for a, b, c in factors]},
        "active_events": [{"level": l, "title": ti, "message": "", "time_str": time.strftime("%H:%M:%S", time.localtime(t - 40 * i))}
                          for i, (l, ti) in enumerate(evs)],
        "stats": {"reviewed": 12, "correct": 11},
        "rules": {"dry_burn_c": 120, "smoke_raw": 1800},
        "mute_until": 0,
    }


def main():
    ap = argparse.ArgumentParser(description="总后台演示数据")
    ap.add_argument("--port", type=int, default=8210)
    ap.add_argument("--db", default=os.path.join(tempfile.mkdtemp(prefix="labguard_center_demo_"), "center.db"))
    args = ap.parse_args()

    import uvicorn
    from fastapi.testclient import TestClient
    from center.app import create_app

    app = create_app(args.db)
    st = app.state.store
    if not st.areas():
        admin = st.users()[0]
        st.set_password(admin["id"], "Demo2026admin")
        bld = st.create_area("化学楼", None, "group")
        rooms = {}
        for name, n in (("A实验室", 4), ("B实验室", 2), ("C实验室", 3), ("D高温合成室", 2)):
            rooms[name] = st.create_area(name, bld, "room")
            for i in range(1, n + 1):
                st.create_area(f"{i}号桌", rooms[name], "desk")
        desk = lambda room, i: [a["id"] for a in st.areas() if a["parent_id"] == rooms[room] and a["name"] == f"{i}号桌"][0]
        z = st.create_user("zhang_t", "张老师", "teacher", "Demo2026teach", must_change=False)
        l = st.create_user("li_t", "李老师", "teacher", "Demo2026teach", must_change=False)
        p = st.create_user("pixel", "像素风格", "teacher", "Demo2026pixel", must_change=False)
        st.update_user(p, ui_style="pixel")
        st.set_grants(z, [rooms["A实验室"], rooms["B实验室"], rooms["C实验室"]])
        st.set_grants(l, [rooms["D高温合成室"], desk("C实验室", 1)])
        st.set_grants(p, [bld])
        from center import presets
        st.set_profile(rooms["B实验室"], "organic", presets.PRESETS["organic"]["rules"], "演示")
        st.set_profile(rooms["C实验室"], "teaching", presets.PRESETS["teaching"]["rules"], "演示")
        st.set_profile(rooms["D高温合成室"], "high_temp", dict(presets.PRESETS["high_temp"]["rules"]), "演示")
        plan = [("A实验室", 1, "safe_heat", 150), ("A实验室", 2, "bench", 150), ("A实验室", 3, "idle", 150), ("A实验室", 4, None, 150),
                ("B实验室", 1, "away", 150), ("B实验室", 2, "idle", 150), ("C实验室", 1, "cylinder", 150), ("C实验室", 2, "bench", 150),
                ("C实验室", 3, "latched", 150), ("D高温合成室", 1, "oil", 150), ("D高温合成室", 2, "oil", 400)]
        tokens = []
        for room, i, scene, hard in plan:
            r = st.create_node(f"LG-{room[0]}{i:02d}", desk(room, i))
            tokens.append((r["token"], scene, hard))
        app.state.demo_tokens = tokens
    tokens = getattr(app.state, "demo_tokens", [])

    def report_loop():
        c = TestClient(app)
        while True:
            t = time.time()
            for tok, scene, hard in tokens:
                if scene is None:          # 模拟一台离线终端
                    continue
                c.post("/api/node/report", headers={"X-Node-Token": tok},
                       json={"snapshot": snapshot(scene, t), "meta": {"hard_limit_c": hard, "smoke_limit_raw": 2500}})
            time.sleep(2)

    threading.Thread(target=report_loop, daemon=True).start()
    print(f"[演示] 数据库 {args.db}")
    print(f"[演示] 打开 http://127.0.0.1:{args.port}  ·  admin / Demo2026admin  ·  zhang_t / Demo2026teach  ·  li_t / Demo2026teach  ·  pixel / Demo2026pixel")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
