#!/usr/bin/env python3
"""
总后台演示：建一套示例楼栋（三层楼、各实验室与实验桌的平面位置）、账号，并模拟多台终端持续上报（不需要开发板）。
用于答辩演示与前端调试；数据放在独立的数据库里（默认 runtime/center_demo.db），不碰正式的 runtime/center.db。

  python tools/center_demo.py                          # http://127.0.0.1:8210
  python tools/center_demo.py --images 演示图片目录      # 把目录里的图片设为各实验桌的演示画面
  python tools/center_demo.py --reset                  # 删掉旧的演示数据库，重新生成
  python tools/center_demo.py --live LG-A01            # 这台终端不模拟，留给真实开发板程序接入（实时画面、问答）

真实终端接入（--live）：节点密钥写入 runtime/center_demo_live.yaml，开发板程序用它启动即可
  LAB_SAFETY_CONFIG=runtime/center_demo_live.yaml python run_app.py --mode headless
该文件是完整配置（config.yaml + center 段），串口、摄像头沿用 config.yaml。A 实验室 1 号桌对应 LG-A01。

演示画面：文件名含 desk / 台面 的图片作为「台面」画面，其余作为「全景」画面，按顺序轮流分给各实验桌；
也可以登录后在实验桌页面的画面上直接上传。终端拿不到实时画面时显示演示画面，并标明「演示画面」。

账号：demo / Demo2026show（演示账号，管理员权限，可上传演示画面）· admin / Demo2026admin（管理员）
      zhang_t / Demo2026teach（张老师，A/B/C 实验室）· li_t / Demo2026teach（李老师，D 高温合成室 + C 实验室 1 号桌）
      pixel / Demo2026pixel（像素风格示例账号）
"""
import argparse
import math
import os
import sys
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


# 演示楼栋：楼层 → 实验室（在楼层平面图里的位置，单位 %）→ 实验桌数 / 实验桌位置
# 平面图是示意布局，不是真实建筑图纸；换成真实布局时在总后台「区域」页改位置即可
BUILDING = [
    ("一楼", [("A实验室", (2, 4, 46, 40), 4), ("B实验室", (50, 4, 30, 40), 2), ("危化品库", (82, 4, 16, 40), 0),
             ("试剂准备室", (2, 56, 26, 40), 0)]),
    ("二楼", [("C实验室", (2, 4, 46, 40), 3), ("天平室", (50, 4, 22, 40), 0), ("D高温合成室", (40, 56, 44, 40), 2)]),
    ("三楼", [("资料室", (2, 4, 24, 40), 0), ("E仪器分析室", (2, 56, 46, 40), 2)]),
]
# 终端名 → (场景, 控制盒硬上限)；场景 None = 模拟一台离线终端
PLAN = {
    "LG-A01": ("safe_heat", 150), "LG-A02": ("bench", 150), "LG-A03": ("idle", 150), "LG-A04": (None, 150),
    "LG-B01": ("away", 150), "LG-B02": ("idle", 150),
    "LG-C01": ("cylinder", 150), "LG-C02": ("bench", 150), "LG-C03": ("latched", 150),
    "LG-D01": ("oil", 150), "LG-D02": ("oil", 400),
    "LG-E01": ("idle", 150), "LG-E02": ("safe_heat", 150),
}
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def desk_boxes(n: int):
    """实验桌在实验室里的位置：两列排布，留出过道（与前端自动排布同一思路）"""
    cols = 1 if n == 1 else 2
    rows = max(1, (n + cols - 1) // cols)
    out = []
    for i in range(n):
        r, c = divmod(i, cols)
        w, h = (84 - 8 * (cols - 1)) / cols, (76 - 8 * (rows - 1)) / rows
        out.append((8 + c * (w + 8), 16 + r * (h + 8), w, h))
    return out


def seed(st):
    from center import presets
    admin = st.users()[0]
    st.set_password(admin["id"], "Demo2026admin")
    bld = st.create_area("化学楼", None, "group")
    rooms, desks = {}, {}
    for floor, rlist in BUILDING:
        fid = st.create_area(floor, bld, "group")
        for name, box, n in rlist:
            rid = rooms[name] = st.create_area(name, fid, "room")
            st.set_layout(rid, dict(zip("xywh", box)))
            for i, dbox in enumerate(desk_boxes(n), 1):
                did = desks[(name, i)] = st.create_area(f"{i}号桌", rid, "desk")
                st.set_layout(did, dict(zip("xywh", dbox)))
                st.create_node(f"LG-{name[0]}{i:02d}", did)
    st.create_user("demo", "演示账号", "admin", "Demo2026show", must_change=False)
    z = st.create_user("zhang_t", "张老师", "teacher", "Demo2026teach", must_change=False)
    l = st.create_user("li_t", "李老师", "teacher", "Demo2026teach", must_change=False)
    p = st.create_user("pixel", "像素风格", "teacher", "Demo2026pixel", must_change=False)
    st.update_user(p, ui_style="pixel")
    st.set_grants(z, [rooms["A实验室"], rooms["B实验室"], rooms["C实验室"]])
    st.set_grants(l, [rooms["D高温合成室"], desks[("C实验室", 1)]])
    st.set_grants(p, [bld])
    st.set_profile(rooms["B实验室"], "organic", presets.PRESETS["organic"]["rules"], "演示")
    st.set_profile(rooms["C实验室"], "teaching", presets.PRESETS["teaching"]["rules"], "演示")
    st.set_profile(rooms["D高温合成室"], "high_temp", dict(presets.PRESETS["high_temp"]["rules"]), "演示")


def load_images(st, folder: str) -> int:
    files = sorted(f for f in os.listdir(folder) if f.lower().endswith(IMAGE_EXT))
    pano = [f for f in files if not any(k in f.lower() for k in ("desk", "台面"))]
    bench = [f for f in files if f not in pano]
    desk_ids = [n["area_id"] for n in st.nodes() if n["area_id"] is not None]
    count = 0
    for which, pool in (("pano", pano), ("desk", bench)):
        for i, aid in enumerate(desk_ids if pool else []):
            f = pool[i % len(pool)]
            with open(os.path.join(folder, f), "rb") as fh:
                st.set_demo_frame(aid, which, MIME[os.path.splitext(f)[1].lower()], fh.read(), "演示脚本")
            count += 1
    return count


def write_live_config(name: str, token: str, port: int):
    """给真实开发板程序写一份配置：config.yaml 全部内容 + 指向本演示总后台的 center 段（runtime/config_override.yaml 照常叠加）"""
    import yaml
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as f:
        conf = yaml.safe_load(f) or {}
    conf["center"] = {**conf.get("center", {}), "url": f"http://127.0.0.1:{port}", "node_token": token}
    path = os.path.join(ROOT, "runtime", "center_demo_live.yaml")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# center_demo.py --live {name} 自动生成；每次启动演示都会换新密钥\n")
        yaml.safe_dump(conf, f, allow_unicode=True, sort_keys=False)
    print(f"[演示] {name} 留给真实终端：LAB_SAFETY_CONFIG={os.path.relpath(path, ROOT)} python run_app.py")


def main():
    ap = argparse.ArgumentParser(description="总后台演示数据")
    ap.add_argument("--port", type=int, default=8210)
    ap.add_argument("--db", default=os.path.join(ROOT, "runtime", "center_demo.db"))
    ap.add_argument("--images", default="", help="演示画面图片目录")
    ap.add_argument("--reset", action="store_true", help="删除旧的演示数据库后重新生成")
    ap.add_argument("--live", default="", help="留给真实开发板接入的终端名，如 LG-A01（多个用逗号分隔）")
    args = ap.parse_args()

    import uvicorn
    from fastapi.testclient import TestClient
    from center.app import create_app

    if args.reset and os.path.exists(args.db):
        os.remove(args.db)
    app = create_app(args.db)
    st = app.state.store
    if not st.areas():
        seed(st)
    elif not any(n["name"] in PLAN for n in st.nodes()):
        print(f"[演示] {args.db} 不是演示数据库，请换 --db 或加 --reset")
        return
    if args.images:
        print(f"[演示] 已设置 {load_images(st, args.images)} 张演示画面")
    # 节点密钥只存哈希：每次启动给演示终端换一把新密钥，用于模拟上报
    live = [x.strip() for x in args.live.split(",") if x.strip()]
    tokens = [(st.rotate_node_token(n["id"]),) + PLAN[n["name"]] for n in st.nodes()
              if n["name"] in PLAN and n["name"] not in live]
    for name in live:
        node = next((n for n in st.nodes() if n["name"] == name), None)
        if node is None:
            print(f"[演示] 没有名为 {name} 的终端，可选：{', '.join(sorted(PLAN))}")
            return
        write_live_config(name, st.rotate_node_token(node["id"]), args.port)

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
    print(f"[演示] 打开 http://127.0.0.1:{args.port}  ·  demo / Demo2026show  ·  admin / Demo2026admin  ·  "
          f"zhang_t / Demo2026teach  ·  li_t / Demo2026teach  ·  pixel / Demo2026pixel")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
