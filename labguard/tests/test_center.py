"""
总后台离线测试：登录与改密、混合粒度授权、终端上报与指令、按区域阈值、个人界面风格。
不需要开发板、摄像头或网络。运行：
    python tests/test_center.py
"""
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient

from center.app import create_app

PASSED = []


def check(cond, name):
    if not cond:
        raise AssertionError(name)
    PASSED.append(name)
    print(f"  ✔ {name}")


_tmp = tempfile.mkdtemp(prefix="labsafety_center_")
app = create_app(os.path.join(_tmp, "center.db"))
store = app.state.store
PW0 = app.state.initial_password


def login(user, pw):
    c = TestClient(app)
    r = c.post("/api/login", json={"username": user, "password": pw})
    return c, r


# ---------------------------------------------------------------------------
print("[1] 登录与首次改密")
check(PW0 and len(PW0) >= 10, "首次启动生成随机管理员密码")
c, r = login("admin", "wrong-pass1")
check(r.status_code == 401, "密码错误被拒绝")
admin, r = login("admin", PW0)
check(r.status_code == 200 and r.json()["user"]["must_change"] == 1, "初始密码可登录，但标记必须改密")
check(admin.get("/api/tree").status_code == 403, "未改密前不能访问业务接口")
r = admin.post("/api/me/password", json={"old": PW0, "new": "short"})
check(r.status_code == 422, "弱密码被拒绝")
r = admin.post("/api/me/password", json={"old": PW0, "new": "Admin2026pass"})
check(r.status_code == 200, "修改密码成功")
check(admin.get("/api/tree").status_code == 200, "改密后可正常访问")
anon = TestClient(app)
check(anon.get("/api/overview").status_code == 401, "未登录访问被拒绝")
for i in range(5):
    login("admin", f"bad-pass{i}x")
c, r = login("admin", "Admin2026pass")
check(r.status_code == 429, "连续输错 5 次后锁定")

# ---------------------------------------------------------------------------
print("[2] 区域树与混合授权")
ids = {}
bld = store.create_area("化学楼", None, "group")
for room in "ABCDEFG":
    ids[room] = store.create_area(f"{room}实验室", bld, "room")
    for n in (1, 2):
        ids[f"{room}{n}"] = store.create_area(f"{n}号桌", ids[room], "desk")
zid = store.create_user("zhang_t", "张老师", "teacher", "Teach2026a", must_change=False)
lid = store.create_user("li_t", "李老师", "teacher", "Teach2026b", must_change=False)
store.set_grants(zid, [ids["A"], ids["B"], ids["C"]])
store.set_grants(lid, [ids["D"], ids["E"], ids["F"], ids["G1"]])
zhang, _ = login("zhang_t", "Teach2026a")
li, _ = login("li_t", "Teach2026b")
zt = {a["id"]: a for a in zhang.get("/api/tree").json()}
check(ids["A1"] in zt and ids["C2"] in zt and ids["D1"] not in zt, "张老师只看到 A/B/C 三间及其实验桌")
check(zt[bld]["managed"] is False, "上级楼栋只用于显示路径，不可管理")
lt = {a["id"]: a for a in li.get("/api/tree").json()}
check(ids["G1"] in lt and ids["G2"] not in lt and lt[ids["G"]]["managed"] is False,
      "李老师：D/E/F 整间 + G 实验室只有 1 号桌")
check(li.get(f"/api/profiles/{ids['A1']}").status_code == 404, "越权访问别人的实验桌 → 404")
check(zhang.get("/api/users").status_code == 403, "教师不能管理账号")
r = admin.post("/api/areas", json={"name": "A实验室", "parent_id": bld, "kind": "room"})
check(r.status_code == 422, "同一层级不能重名")

# ---------------------------------------------------------------------------
print("[3] 终端登记、上报与指令")
r = admin.post("/api/nodes", json={"name": "LG-A01", "area_id": ids["A1"]})
check(r.status_code == 200 and r.json()["token"].startswith("lg_"), "登记终端，节点密钥只显示一次")
node_token, node_id = r.json()["token"], r.json()["id"]
check(admin.post("/api/nodes", json={"name": "LG-X", "area_id": ids["A"]}).status_code == 422,
      "终端只能绑定到实验桌")
node = TestClient(app)
check(node.post("/api/node/report", headers={"X-Node-Token": "lg_fake"}, json={}).status_code == 401,
      "错误节点密钥被拒绝")
snap = {"state": "WARNING", "risk": {"level": "mid", "level_text": "中危", "scene": "加热操作中"},
        "telemetry": {"obj_temp": 63.2}, "active_events": [{"title": "量器被加热"}]}
r = node.post("/api/node/report", headers={"X-Node-Token": node_token},
              json={"snapshot": snap, "meta": {"web_port": 8080, "hard_limit_c": 150, "smoke_limit_raw": 2500}})
check(r.status_code == 200 and r.json()["profile"]["rules"]["rules.dry_burn_c"] == 120, "上报后拿到默认阈值")
ov = zhang.get("/api/overview").json()
check(ov["summary"]["mid"] == 1 and ov["desks"][0]["scene"] == "加热操作中", "总览汇总终端风险等级")
check(li.get("/api/overview").json()["summary"]["total"] == 0, "李老师总览里看不到 A 实验室的终端")
r = zhang.post(f"/api/desks/{ids['A1']}/command", json={"cmd": "cut_power"})
check(r.status_code == 422, "断电需要确认")
r = zhang.post(f"/api/desks/{ids['A1']}/command", json={"cmd": "power_on", "confirm": True})
check(r.status_code == 422, "不存在上电指令")
r = zhang.post(f"/api/desks/{ids['A1']}/command", json={"cmd": "cut_power", "confirm": True})
check(r.status_code == 200, "授权教师可远程断电")
check(li.post(f"/api/desks/{ids['A1']}/command", json={"cmd": "mute"}).status_code == 404, "无权教师不能下发指令")
r = node.post("/api/node/report", headers={"X-Node-Token": node_token}, json={"snapshot": snap, "meta": {}})
check([c["cmd"] for c in r.json()["commands"]] == ["cut_power"], "终端下次上报取到断电指令")
r = node.post("/api/node/report", headers={"X-Node-Token": node_token}, json={"snapshot": snap, "meta": {}})
check(r.json()["commands"] == [], "指令只下发一次")
routes = {getattr(rt, "path", "") for rt in app.routes}
check(not any(k in p for p in routes for k in ("power/on", "power/restore", "unlock", "release")),
      "总后台不存在任何上电 / 解锁接口")

# ---------------------------------------------------------------------------
print("[4] 主控决策：按区域阈值")
r = admin.put(f"/api/profiles/{ids['D']}", json={"preset": "high_temp", "rules": {"rules.dry_burn_c": 240}})
check(r.status_code == 200 and r.json()["resolved"]["rules"]["rules.dry_burn_c"] == 240, "高温实验室可调高干烧阈值")
r = admin.get(f"/api/profiles/{ids['D1']}").json()
check(r["resolved"]["rules"]["rules.dry_burn_c"] == 240 and r["resolved"]["sources"]["rules.dry_burn_c"] == "D实验室",
      "实验桌继承房间阈值，并标明来源")
r = admin.put(f"/api/profiles/{ids['D']}", json={"rules": {"serial.port": "/dev/x"}})
check(r.status_code == 422, "白名单外参数被拒绝")
r = admin.put(f"/api/profiles/{ids['D']}", json={"rules": {"rules.dry_burn_c": 999}})
check(r.status_code == 422, "超出范围被拒绝")
r = admin.put(f"/api/profiles/{ids['C']}", json={"rules": {"cross.high_score": 35}})
check(r.status_code == 422, "交叉验证高危分界低于中危 + 10 被拒绝")
r = admin.put(f"/api/profiles/{ids['C']}", json={"rules": {"cross.mid_score": 25, "cross.high_score": 60}})
check(r.status_code == 200 and r.json()["resolved"]["rules"]["cross.high_score"] == 60, "交叉验证分界可按区域配置")

# ---------------------------------------------------------------------------
print("[5] 个人界面风格（旧版 Zpix 像素字体入口）")
check(zhang.get("/api/me").json()["user"]["ui_style"] == "standard", "默认使用新版字体")
r = zhang.patch("/api/me/prefs", json={"ui_style": "pixel"})
check(r.status_code == 200 and r.json()["user"]["ui_style"] == "pixel", "账号可切换为像素风格")
check(li.get("/api/me").json()["user"]["ui_style"] == "standard", "只影响本账号")
check(zhang.patch("/api/me/prefs", json={"ui_style": "comic"}).status_code == 422, "未知风格被拒绝")
r = admin.patch(f"/api/users/{lid}", json={"ui_style": "pixel"})
check(r.status_code == 200 and r.json()["ui_style"] == "pixel", "管理员可为指定账号设置风格")
r = anon.get("/font/zpix.ttf")
check(r.status_code == 200 and len(r.content) > 100_000, "像素字体文件可加载")

old = os.path.join(_tmp, "old.db")    # 旧版数据库（没有 ui_style 列）能自动升级
con = sqlite3.connect(old)
con.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,"
            " role TEXT NOT NULL, pw_hash TEXT NOT NULL, salt TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,"
            " must_change INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL)")
con.execute("INSERT INTO users (username, display_name, role, pw_hash, salt, created) VALUES ('a','a','admin','x','y',0)")
con.commit(); con.close()
from center.store import Store
check(Store(old).user(1)["ui_style"] == "standard", "旧数据库自动补上界面风格字段")

# ---------------------------------------------------------------------------
print("[6] 开发板 CenterLink 经真实 HTTP 接入总后台")
import socket
import threading
import time
import urllib.error

import uvicorn

from src import config as config_mod

config_mod.load()
config_mod._override_path = lambda: os.path.join(_tmp, "override.yaml")   # 不写真实 runtime/
config_mod._config["events"]["db"] = os.path.join(_tmp, "events.db")
config_mod._config["events"]["snapshot_dir"] = os.path.join(_tmp, "snaps")
config_mod._config["notify"]["webhook_url"] = ""
from src.core import voice as voice_mod
voice_mod.pack_dir = lambda: os.path.join(_tmp, "board_voice")
from src.core.center_link import CenterLink
from src.config import cfg


class FakeEngine:
    """只实现 CenterLink 用到的几个接口"""
    extensions, dual_system = {}, None

    def __init__(self):
        self.cuts, self.mutes = [], []

    def snapshot(self):
        return {"state": "NORMAL", "latched": False, "risk": {"level": "low"},
                "world_model": {"phase": "idle", "temp": 25.0, "history": [25.0] * 120, "forecast": [1] * 12},
                "center": {"online": True}}

    def cut_power(self, source):
        self.cuts.append(source)
        return "未接入下位机（演示模式），已在软件中模拟断电锁定"

    def mute(self, seconds):
        self.mutes.append(seconds)
        return time.time() + seconds


with socket.socket() as sk:
    sk.bind(("127.0.0.1", 0))
    port = sk.getsockname()[1]
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
threading.Thread(target=server.run, daemon=True).start()
for _ in range(100):
    if server.started:
        break
    time.sleep(0.05)

phys = store.create_area("物理楼", None, "group")
desk9 = store.create_area("9号桌", store.create_area("H实验室", phys, "room"), "desk")
tok = store.create_node("LG-H09", desk9)["token"]
eng = FakeEngine()
config_mod._config["center"].update({"url": "", "node_token": ""})
link = CenterLink(eng)                      # 先不填地址：不启动后台线程，测试里手动 report_once()
check(not link.enabled and link._thread is None, "未配置总后台地址时不启动上报线程")
config_mod._config["center"].update({"url": f"http://127.0.0.1:{port}", "node_token": "lg_wrong"})
try:
    link.report_once()
    bad = None
except urllib.error.HTTPError as e:
    bad = e.code
check(bad == 401, "节点密钥错误 → 401")
config_mod._config["center"]["node_token"] = tok
link.report_once()
n9 = store.node_by_area(desk9)
check(link.online and n9["last_ip"] == "127.0.0.1" and n9["hard_limit_c"] == 150.0, "上报成功，总后台记下终端地址与硬上限")
check(link.center_key == store.meta("center_key"), "终端拿到总后台访问密钥")
wm = n9["snapshot"]["world_model"]
check("history" not in wm and "forecast" not in wm and "center" not in n9["snapshot"], "上报快照裁掉温度曲线")

r = admin.put(f"/api/profiles/{desk9}", json={"rules": {"rules.dry_burn_c": 110}})
check(r.status_code == 200, "总后台为实验桌设置干烧阈值 110℃")
link.report_once()
check(cfg("rules.dry_burn_c") == 110 and not link.profile_errors, "终端应用下发的阈值")
admin.put(f"/api/profiles/{desk9}", json={"rules": {"rules.dry_burn_c": 160}})
link.report_once()
check(cfg("rules.dry_burn_c") == 110 and "rules.dry_burn_c" in link.profile_errors,
      "超过本机控制盒硬上限的阈值不生效，并回报原因")
link.report_once()
prof = admin.get(f"/api/profiles/{desk9}").json()
check("rules.dry_burn_c" not in prof["nodes"][0]["applied"] and prof["nodes"][0]["warnings"],
      "总后台看到该项未生效及硬上限提示")

admin.post(f"/api/desks/{desk9}/command", json={"cmd": "cut_power", "confirm": True})
admin.post(f"/api/desks/{desk9}/command", json={"cmd": "mute", "seconds": 30})
link.report_once()
check(len(eng.cuts) == 1 and eng.cuts[0].startswith("总后台·") and eng.mutes == [30], "终端执行断电与静音指令")
link.report_once()
results = {c["cmd"]: c["result"] for c in store.commands_of(n9["id"])}
check(results.get("cut_power", "").startswith("未接入下位机") and results.get("mute", "").startswith("已静音至"),
      "执行结果回写到总后台")
check(link.run_command({"cmd": "power_on"}) == "不支持的指令", "终端不执行任何上电指令")

vdir = os.path.join(_tmp, "center_files", "voice")
with open(os.path.join(vdir, "t9.mp3"), "wb") as f:
    f.write(b"ID3-test-audio")
aid = store.add_voice_asset("干烧提醒", "upload", "t9.mp3", "admin")
store.set_voice_map(desk9, "dry_burn", "stern", aid)
link.report_once()
with open(os.path.join(_tmp, "board_voice", f"{aid}.mp3"), "rb") as f:
    got = f.read()
check(got == b"ID3-test-audio" and voice_mod.voice.pack["map"]["dry_burn"]["stern"] == f"{aid}.mp3",
      "终端下载并安装语音包")
v0 = link.voice_version
link.report_once()
check(link.voice_version == v0, "语音包版本未变时不重复下载")

server.should_exit = True
time.sleep(0.5)
link._fail("URLError: 连接被拒绝")
check(not link.online and "连接被拒绝" in link.status()["error"], "总后台断开时只记录状态，不影响本机")

# ---------------------------------------------------------------------------
print("[7] 平面图位置与演示画面")
r = admin.patch(f"/api/areas/{ids['A']}", json={"layout": {"x": 2, "y": 4, "w": 44, "h": 40}})
check(r.status_code == 200 and r.json()["layout"] == {"x": 2.0, "y": 4.0, "w": 44.0, "h": 40.0}, "设置房间在楼层平面图里的位置")
check(admin.patch(f"/api/areas/{ids['A']}", json={"layout": {"x": 80, "y": 4, "w": 40, "h": 40}}).status_code == 422,
      "超出上级范围的位置被拒绝")
check(zhang.patch(f"/api/areas/{ids['A1']}", json={"layout": {"x": 1, "y": 1, "w": 10, "h": 10}}).status_code == 403,
      "教师不能修改区域位置")
tz = {a["id"]: a for a in zhang.get("/api/tree").json()}
check(tz[ids["A"]]["layout"]["w"] == 44.0 and tz[ids["A1"]]["layout"] is None, "区域树带位置（未设置 = 自动排布）")
admin.patch(f"/api/areas/{ids['A']}", json={"layout": None})
check(store.area(ids["A"])["layout"] is None, "清除位置后恢复自动排布")

JPG = b"\xff\xd8\xff\xe0" + b"0" * 64
check(admin.get(f"/api/desks/{ids['B1']}/frame/pano.jpg").status_code == 503, "没有终端也没有演示画面 → 503")
r = admin.put(f"/api/desks/{ids['B1']}/demo/pano", content=JPG, headers={"Content-Type": "image/jpeg"})
check(r.status_code == 200, "管理员上传演示画面")
check(zhang.put(f"/api/desks/{ids['B1']}/demo/pano", content=JPG, headers={"Content-Type": "image/jpeg"}).status_code == 403,
      "教师不能上传演示画面")
check(admin.put(f"/api/desks/{ids['B1']}/demo/pano", content=b"<svg/>", headers={"Content-Type": "image/jpeg"}).status_code == 422,
      "内容不是图片 → 拒绝")
check(admin.put(f"/api/desks/{ids['B']}/demo/pano", content=JPG, headers={"Content-Type": "image/jpeg"}).status_code == 404,
      "只能给实验桌设置演示画面")
r = zhang.get(f"/api/desks/{ids['B1']}/frame/pano.jpg")
check(r.status_code == 200 and r.content == JPG and r.headers["x-frame-source"] == "demo", "无实时画面时返回演示画面并标明来源")
check(li.get(f"/api/desks/{ids['B1']}/frame/pano.jpg").status_code == 404, "无权教师看不到演示画面")
check(zhang.get("/api/tree").json() and {a["id"]: a for a in zhang.get("/api/tree").json()}[ids["B1"]]["demo"] == ["pano"],
      "区域树标明哪些实验桌有演示画面")
r = node.post("/api/node/report", headers={"X-Node-Token": node_token}, json={"snapshot": snap, "meta": {}})
admin.put(f"/api/desks/{ids['A1']}/demo/desk", content=JPG, headers={"Content-Type": "image/jpeg"})
r = admin.get(f"/api/desks/{ids['A1']}/frame/desk.jpg")
check(r.status_code == 200 and r.headers["x-frame-source"] == "demo", "终端在线但取不到画面时也回落到演示画面")
admin.delete(f"/api/desks/{ids['B1']}/demo/pano")
check(admin.get(f"/api/desks/{ids['B1']}/frame/pano.jpg").status_code == 503, "清除演示画面")

# ---------------------------------------------------------------------------
print("[8] 分层上报：学生端 / 实验室 / 实验楼各自的等级")
from center.app import tier_levels
apple = {"state": "CRITICAL", "latched": False,
         "risk": {"level": "high", "level_text": "高危", "score": 89, "scene": "台面操作中（未加热）",
                  "tiers": {"student": {"name": "学生端", "level": "high", "action": "严厉干预"},
                            "teacher": {"name": "实验室老师", "level": "low", "action": "仅记录", "reasons": [],
                                        "notes": ["实验区饮食", "未佩戴口罩"]},
                            "building": {"name": "实验楼", "level": "low", "action": "无需介入", "reasons": []}}},
         "active_events": [{"title": "实验区饮食"}]}
node.post("/api/node/report", headers={"X-Node-Token": node_token}, json={"snapshot": apple, "meta": {}})
ov = zhang.get("/api/overview").json()
d = [x for x in ov["desks"] if x["area_id"] == ids["A1"]][0]
check(ov["tier"] == "teacher" and d["risk_level"] == "low" and ov["summary"]["high"] == 0,
      "教师默认看实验室层：摘防护吃东西不进处置队列")
check(d["levels"] == {"student": "high", "teacher": "low", "building": "low"} and "实验区饮食" in d["notes"],
      "概况同时带三层等级，行为违规记为知会")
check(admin.get("/api/overview").json()["tier"] == "building", "管理员默认看实验楼层")
ov = zhang.get("/api/overview?tier=student").json()
check(ov["tier"] == "student" and ov["summary"]["high"] == 1, "可切换到学生端视角，与实验台提醒一致")
check(zhang.get("/api/overview?tier=xyz").json()["tier"] == "teacher", "非法视角按角色回落")
old = {"latched": True, "risk": {"level": "high"}}
t = tier_levels(old)
check(t["student"]["level"] == "high" and t["teacher"]["level"] == "high" and t["building"]["level"] == "high",
      "旧版终端无分层数据：断电锁定时三层均为高危")
t = tier_levels({"risk": {"level": "mid"}})
check(t["teacher"]["level"] == "mid" and t["building"]["level"] == "low", "旧版终端兜底：老师层沿用原等级，实验楼不打扰")

print(f"\n全部通过：{len(PASSED)} 项")
