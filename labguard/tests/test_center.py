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

print(f"\n全部通过：{len(PASSED)} 项")
