"""
总后台（多实验室管理中心）
center/app.py

和每张实验桌上的开发板是两个独立程序：
  · 开发板：安全判断、断电、小屏，单机就能完整工作；
  · 总后台：账号与权限、实验室 / 实验桌树、按区域配置阈值、语音素材、模型看板，汇总所有终端的状态。
总后台挂了，每张实验桌照常守护；总后台也只能下发「断电」「静音」，不能远程上电。

鉴权：
  · 老师 / 管理员：账号密码登录，会话令牌放在 HttpOnly Cookie（也可用 Authorization: Bearer）；
    连续输错 5 次锁定 5 分钟；首次登录必须改密码。
  · 终端：X-Node-Token（节点密钥，只存哈希）。
权限：管理员看全部；老师只看被授权区域及其下级（可混合授权：整间房间 + 别的房间的某一张桌）。
"""
import asyncio
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from center import presets as presets_mod
from center import voice as voice_mod
from center.store import Store, StoreError, COMMANDS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATIC_DIR = os.path.join(HERE, "static")
COOKIE = "lg_session"
ONLINE_S = 10.0              # 超过这么久没上报视为离线
LOCK_FAILS, LOCK_S = 5, 300

# 可按区域配置的问答参数（节点上由 SafetyAgent.configure 再校验一次）
AGENT_KEYS = {
    "agent.route": ("线路", ["auto", "remote", "local", "off"]),
    "agent.temperature": ("回答发散程度 0–1", (0.0, 1.0)),
    "agent.max_tokens": ("回答最大长度", (200, 1500)),
    "agent.min_level": ("自动写处理建议的最低等级", ["NOTICE", "WARNING", "CRITICAL"]),
    "agent.extra_prompt": ("本实验室补充要求（最多 500 字）", 500),
}


def create_app(db_path: str, data_dir: Optional[str] = None, model_card: Optional[str] = None) -> FastAPI:
    from src.core.tunable import TUNABLE, validate

    store = Store(db_path)
    data_dir = data_dir or os.path.join(os.path.dirname(os.path.abspath(db_path)), "center_files")
    voice_dir = os.path.join(data_dir, "voice")
    os.makedirs(voice_dir, exist_ok=True)
    model_card = model_card or os.path.join(ROOT, "models", "model_card.json")
    fails: Dict[str, List[float]] = {}

    app = FastAPI(title="实验室安全 · 总后台", docs_url=None, redoc_url=None)
    app.state.store = store
    app.state.initial_password = store.ensure_admin()
    # 总后台访问终端网页（画面、问答）用的密钥：随上报回复交给已通过节点密钥认证的终端，终端只对少数只读接口认它
    if not store.meta("center_key"):
        store.set_meta("center_key", secrets.token_urlsafe(32))
    center_key = store.meta("center_key")

    # ------------------------------------------------------------------
    # 鉴权依赖
    # ------------------------------------------------------------------
    def session_token(request: Request) -> str:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return request.cookies.get(COOKIE, "")

    def current_user(request: Request) -> Dict[str, Any]:
        u = store.session_user(session_token(request))
        if u is None:
            raise HTTPException(401, "请先登录")
        if u["must_change"] and request.url.path not in ("/api/me", "/api/me/password", "/api/logout"):
            raise HTTPException(403, "首次登录请先修改密码")
        return u

    def admin_user(u=Depends(current_user)) -> Dict[str, Any]:
        if u["role"] != "admin":
            raise HTTPException(403, "需要管理员权限")
        return u

    def need_area(u: Dict[str, Any], area_id: int) -> Dict[str, Any]:
        a = store.area(area_id)
        if a is None or not store.can(u, area_id):
            raise HTTPException(404, "区域不存在或没有权限")
        return a

    def node_auth(request: Request) -> Dict[str, Any]:
        n = store.node_by_token(request.headers.get("x-node-token", ""))
        if n is None:
            raise HTTPException(401, "节点密钥无效")
        return n

    async def body(request: Request) -> Dict[str, Any]:
        try:
            data = await request.json()
        except Exception:
            raise HTTPException(400, "请求体必须是 JSON")
        if not isinstance(data, dict):
            raise HTTPException(400, "请求体必须是对象")
        return data

    def bad(e: Exception):
        raise HTTPException(422, str(e))

    def who(u) -> str:
        return f"{u['display_name']}({u['username']})"

    # ------------------------------------------------------------------
    # 页面
    # ------------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    def index():
        with open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8") as f:
            return f.read()

    if os.path.isdir(STATIC_DIR):
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/api/ping")
    def ping():
        return {"ok": True, "ts": time.time()}

    # ------------------------------------------------------------------
    # 登录与账号
    # ------------------------------------------------------------------
    @app.post("/api/login")
    async def login(request: Request, response: Response):
        data = await body(request)
        username = str(data.get("username", "")).strip()
        key = f"{request.client.host if request.client else ''}|{username}"
        now = time.time()
        recent = [t for t in fails.get(key, []) if now - t < LOCK_S]
        if len(recent) >= LOCK_FAILS:
            raise HTTPException(429, f"错误次数过多，请 {int(LOCK_S - (now - recent[0])) // 60 + 1} 分钟后再试")
        u = await asyncio.to_thread(store.verify, username, str(data.get("password", "")))
        if u is None:
            fails[key] = recent + [now]
            raise HTTPException(401, "用户名或密码错误")
        fails.pop(key, None)
        token = store.new_session(u["id"], request.client.host if request.client else "")
        response.set_cookie(COOKIE, token, httponly=True, samesite="strict", max_age=12 * 3600)
        store.audit(who(u), "登录", request.client.host if request.client else "")
        return {"user": u, "token": token}

    @app.post("/api/logout")
    def logout(request: Request, response: Response):
        store.end_session(session_token(request))
        response.delete_cookie(COOKIE)
        return {"ok": True}

    @app.get("/api/me")
    def me(u=Depends(current_user)):
        return {"user": u, "grants": store.grants_of(u["id"])}

    @app.post("/api/me/password")
    async def change_password(request: Request, response: Response, u=Depends(current_user)):
        data = await body(request)
        if store.verify(u["username"], str(data.get("old", ""))) is None:
            raise HTTPException(422, "原密码不正确")
        try:
            store.set_password(u["id"], str(data.get("new", "")), must_change=False)
        except StoreError as e:
            bad(e)
        store.audit(who(u), "修改密码", "")
        token = store.new_session(u["id"], request.client.host if request.client else "")
        response.set_cookie(COOKIE, token, httponly=True, samesite="strict", max_age=12 * 3600)
        return {"ok": True, "token": token}

    @app.get("/api/users")
    def list_users(u=Depends(admin_user)):
        return store.users()

    @app.post("/api/users")
    async def create_user(request: Request, u=Depends(admin_user)):
        data = await body(request)
        pw = str(data.get("password") or "") or (secrets.token_urlsafe(8) + "3x")
        try:
            uid = store.create_user(str(data.get("username", "")), str(data.get("display_name", "")),
                                    str(data.get("role", "teacher")), pw, must_change=True)
            if data.get("grants"):
                store.set_grants(uid, data["grants"])
        except (StoreError, TypeError, ValueError) as e:
            bad(e)
        store.audit(who(u), "新建账号", {"username": data.get("username"), "role": data.get("role", "teacher")})
        return {"id": uid, "initial_password": pw}

    @app.patch("/api/users/{uid}")
    async def update_user(uid: int, request: Request, u=Depends(admin_user)):
        data = await body(request)
        try:
            store.update_user(uid, data.get("display_name"), data.get("role"),
                              data["active"] if isinstance(data.get("active"), bool) else None)
        except StoreError as e:
            bad(e)
        store.audit(who(u), "修改账号", {"id": uid, **{k: data[k] for k in data if k != "password"}})
        return store.user(uid)

    @app.put("/api/users/{uid}/grants")
    async def set_grants(uid: int, request: Request, u=Depends(admin_user)):
        data = await body(request)
        if store.user(uid) is None:
            raise HTTPException(404, "用户不存在")
        try:
            store.set_grants(uid, [int(a) for a in data.get("areas") or []])
        except (StoreError, TypeError, ValueError) as e:
            bad(e)
        store.audit(who(u), "设置授权", {"user": uid, "areas": [store.path_name(a) for a in store.grants_of(uid)]})
        return {"grants": store.grants_of(uid)}

    @app.post("/api/users/{uid}/reset_password")
    def reset_password(uid: int, u=Depends(admin_user)):
        if store.user(uid) is None:
            raise HTTPException(404, "用户不存在")
        pw = secrets.token_urlsafe(8) + "3x"
        store.set_password(uid, pw, must_change=True)
        store.audit(who(u), "重置密码", {"user": uid})
        return {"initial_password": pw}

    @app.delete("/api/users/{uid}")
    def delete_user(uid: int, u=Depends(admin_user)):
        if uid == u["id"]:
            raise HTTPException(422, "不能删除自己")
        try:
            store.delete_user(uid)
        except StoreError as e:
            bad(e)
        store.audit(who(u), "删除账号", {"id": uid})
        return {"ok": True}

    # ------------------------------------------------------------------
    # 区域树
    # ------------------------------------------------------------------
    @app.get("/api/tree")
    def tree(u=Depends(current_user)):
        nodes = {n["area_id"]: n for n in store.nodes() if n["area_id"] is not None}
        out = []
        for a in store.visible_tree(u):
            n = nodes.get(a["id"]) if a["managed"] else None
            a["node"] = _node_brief(n) if n else None
            out.append(a)
        return out

    @app.post("/api/areas")
    async def create_area(request: Request, u=Depends(admin_user)):
        data = await body(request)
        try:
            aid = store.create_area(str(data.get("name", "")), data.get("parent_id"),
                                    str(data.get("kind", "group")), str(data.get("note", "")))
        except StoreError as e:
            bad(e)
        store.audit(who(u), "新建区域", store.path_name(aid))
        return store.area(aid)

    @app.post("/api/areas/batch_desks")
    async def batch_desks(request: Request, u=Depends(admin_user)):
        """一次给一个房间建多张实验桌：前缀 + 起止编号，如「1号桌」…「8号桌」"""
        data = await body(request)
        try:
            parent, start, end = int(data["parent_id"]), int(data.get("start", 1)), int(data.get("end", 1))
        except (KeyError, TypeError, ValueError):
            raise HTTPException(422, "参数不完整")
        if not (1 <= start <= end <= start + 49):
            raise HTTPException(422, "一次最多建 50 张")
        fmt = str(data.get("pattern") or "{n}号桌")
        if "{n}" not in fmt:
            raise HTTPException(422, "名称格式里要有 {n}")
        made = []
        for n in range(start, end + 1):
            try:
                made.append(store.create_area(fmt.replace("{n}", str(n)), parent, "desk"))
            except StoreError as e:
                if not made:
                    bad(e)
        store.audit(who(u), "批量新建实验桌", {"parent": store.path_name(parent), "count": len(made)})
        return {"created": made}

    @app.patch("/api/areas/{aid}")
    async def update_area(aid: int, request: Request, u=Depends(admin_user)):
        data = await body(request)
        try:
            store.update_area(aid, data.get("name"), data["parent_id"] if "parent_id" in data else "keep",
                              data.get("note"))
        except StoreError as e:
            bad(e)
        store.audit(who(u), "修改区域", {"id": aid, **data})
        return store.area(aid)

    @app.delete("/api/areas/{aid}")
    def delete_area(aid: int, u=Depends(admin_user)):
        name = store.path_name(aid)
        try:
            store.delete_area(aid)
        except StoreError as e:
            bad(e)
        store.audit(who(u), "删除区域", name)
        return {"ok": True}

    # ------------------------------------------------------------------
    # 终端节点
    # ------------------------------------------------------------------
    def _online(n: Dict[str, Any]) -> bool:
        return bool(n.get("last_seen") and time.time() - n["last_seen"] < ONLINE_S)

    def _node_brief(n: Dict[str, Any]) -> Dict[str, Any]:
        s = n.get("snapshot") or {}
        risk = s.get("risk") or {}
        tel = s.get("telemetry") or {}
        return {"id": n["id"], "name": n["name"], "online": _online(n), "last_seen": n.get("last_seen"),
                "state": s.get("state"), "state_text": s.get("state_text"), "latched": s.get("latched"),
                "risk_level": risk.get("level"), "risk_text": risk.get("level_text"), "scene": risk.get("scene"),
                "obj_temp": tel.get("obj_temp"), "temp": tel.get("temp"), "humi": tel.get("humi"),
                "events": [e.get("title") for e in (s.get("active_events") or [])[:3]]}

    @app.get("/api/nodes")
    def list_nodes(u=Depends(current_user)):
        sc = store.scope(u)
        out = []
        for n in store.nodes():
            if sc is not None and n["area_id"] not in sc:
                continue
            d = {k: n.get(k) for k in ("id", "name", "area_id", "token_hint", "created", "last_seen", "last_ip",
                                       "web_port", "hard_limit_c", "smoke_limit_raw", "report_count")}
            d["online"] = _online(n)
            d["path"] = store.path_name(n["area_id"]) if n["area_id"] else "（未绑定）"
            out.append(d)
        return out

    @app.post("/api/nodes")
    async def create_node(request: Request, u=Depends(admin_user)):
        data = await body(request)
        try:
            res = store.create_node(str(data.get("name", "")), data.get("area_id"))
        except StoreError as e:
            bad(e)
        store.audit(who(u), "登记终端", {"name": data.get("name"), "area": data.get("area_id")})
        return {**res, "hint": "把节点密钥填到该终端 config.yaml → center.node_token（只显示这一次）"}

    @app.patch("/api/nodes/{nid}")
    async def update_node(nid: int, request: Request, u=Depends(admin_user)):
        data = await body(request)
        try:
            store.update_node(nid, data.get("name"), data["area_id"] if "area_id" in data else "keep")
        except StoreError as e:
            bad(e)
        store.audit(who(u), "修改终端", {"id": nid, **data})
        return {"ok": True}

    @app.post("/api/nodes/{nid}/rotate")
    def rotate_node(nid: int, u=Depends(admin_user)):
        if store.node(nid) is None:
            raise HTTPException(404, "节点不存在")
        token = store.rotate_node_token(nid)
        store.audit(who(u), "更换节点密钥", {"id": nid})
        return {"token": token}

    @app.delete("/api/nodes/{nid}")
    def delete_node(nid: int, u=Depends(admin_user)):
        store.delete_node(nid)
        store.audit(who(u), "删除终端", {"id": nid})
        return {"ok": True}

    # ------------------------------------------------------------------
    # 终端上报（节点密钥）
    # ------------------------------------------------------------------
    @app.post("/api/node/report")
    async def node_report(request: Request, n=Depends(node_auth)):
        data = await body(request)
        snap = data.get("snapshot") if isinstance(data.get("snapshot"), dict) else {}
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        store.ack_commands(n["id"], data.get("acks") or {})
        store.record_report(n["id"], request.client.host if request.client else "", snap, meta)
        prof = _resolved_rules(n["area_id"])
        cmds = store.pending_commands(n["id"])
        for c in cmds:   # 下发即视为送达；执行结果在下一次上报的 acks 里回写
            store.ack_commands(n["id"], {str(c["id"]): "已下发，等待终端回报"})
        return {"profile": prof, "commands": [{"id": c["id"], "cmd": c["cmd"], "args": c["args"]} for c in cmds],
                "voice": _voice_pack(n["area_id"]), "center_key": center_key}

    @app.get("/api/node/voice/{asset_id}")
    def node_voice(asset_id: int, n=Depends(node_auth)):
        a = store.voice_asset(asset_id)
        if a is None:
            raise HTTPException(404)
        return FileResponse(os.path.join(voice_dir, a["filename"]))

    def _resolved_rules(area_id: Optional[int]) -> Dict[str, Any]:
        """出厂默认（常规实验室预设）打底，再按区域逐级覆盖；清掉某级设置会回到上级 / 默认值"""
        res = store.resolved_profile(area_id)
        rules = dict(presets_mod.PRESETS["standard"]["rules"])
        rules.update(res["rules"])
        return {"rules": rules, "sources": res["sources"], "version": res["version"]}

    def _voice_pack(area_id: Optional[int]) -> Dict[str, Any]:
        m = store.resolved_voice(area_id)
        packed = {}
        for kind, tones in m.items():
            for tone, aid in tones.items():
                a = store.voice_asset(aid)
                if a:
                    packed.setdefault(kind, {})[tone] = {"id": a["id"], "filename": a["filename"]}
        version = hashlib.sha1(json.dumps(packed, sort_keys=True).encode()).hexdigest()[:12] if packed else ""
        return {"version": version, "map": packed}

    # ------------------------------------------------------------------
    # 总览与实验桌
    # ------------------------------------------------------------------
    @app.get("/api/overview")
    def overview(u=Depends(current_user)):
        sc = store.scope(u)
        desks = []
        for n in store.nodes():
            if n["area_id"] is None or (sc is not None and n["area_id"] not in sc):
                continue
            b = _node_brief(n)
            b["area_id"] = n["area_id"]
            b["path"] = store.path_name(n["area_id"])
            desks.append(b)
        count = lambda f: sum(1 for d in desks if f(d))
        return {"desks": desks, "summary": {
            "total": len(desks), "online": count(lambda d: d["online"]),
            "high": count(lambda d: d["online"] and (d["risk_level"] == "high" or d["latched"])),
            "mid": count(lambda d: d["online"] and d["risk_level"] == "mid" and not d["latched"]),
            "low": count(lambda d: d["online"] and d["risk_level"] == "low" and not d["latched"]),
            "offline": count(lambda d: not d["online"])}}

    def _desk_node(u, area_id: int) -> Dict[str, Any]:
        need_area(u, area_id)
        n = store.node_by_area(area_id)
        if n is None:
            raise HTTPException(404, "这张实验桌还没有绑定终端")
        return n

    @app.get("/api/desks/{area_id}")
    def desk(area_id: int, u=Depends(current_user)):
        n = _desk_node(u, area_id)
        meta = {k: n.get(k) for k in ("id", "name", "last_seen", "last_ip", "web_port", "hard_limit_c",
                                      "smoke_limit_raw", "applied_profile")}
        meta["online"] = _online(n)
        return {"area": store.area(area_id), "path": store.path_name(area_id), "node": meta,
                "snapshot": n.get("snapshot") or {}, "commands": store.commands_of(n["id"], 10)}

    def _node_http(n: Dict[str, Any], path: str, payload: Optional[dict] = None, timeout: float = 30.0) -> bytes:
        """总后台 → 终端网页（同一局域网）：只调用终端开放给节点密钥的只读 / 问答接口"""
        if not (n.get("last_ip") and n.get("web_port")) or not _online(n):
            raise HTTPException(503, "终端离线")
        url = f"http://{n['last_ip']}:{n['web_port']}{path}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET",
                                     headers={"Content-Type": "application/json", "X-Center-Key": center_key})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            raise HTTPException(502, f"终端返回 {e.code}")
        except Exception as e:
            raise HTTPException(502, f"连不上终端：{type(e).__name__}")

    @app.get("/api/desks/{area_id}/frame/{which}.jpg")
    async def desk_frame(area_id: int, which: str, u=Depends(current_user)):
        if which not in ("pano", "desk"):
            raise HTTPException(404)
        n = _desk_node(u, area_id)
        data = await asyncio.to_thread(_node_http, n, f"/api/frame/{which}.jpg", None, 5.0)
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.post("/api/desks/{area_id}/ask")
    async def desk_ask(area_id: int, request: Request, u=Depends(current_user)):
        data = await body(request)
        n = _desk_node(u, area_id)
        q = str(data.get("question", "")).strip()
        if not q:
            raise HTTPException(422, "问题不能为空")
        raw = await asyncio.to_thread(_node_http, n, "/api/agent/ask",
                                      {"question": q[:500], "history": data.get("history") or []}, 60.0)
        store.audit(who(u), "向安全助手提问", {"desk": store.path_name(area_id), "q": q[:80]})
        return json.loads(raw.decode("utf-8"))

    @app.post("/api/desks/{area_id}/report")
    async def desk_report(area_id: int, u=Depends(current_user)):
        n = _desk_node(u, area_id)
        raw = await asyncio.to_thread(_node_http, n, "/api/agent/report", {}, 90.0)
        return json.loads(raw.decode("utf-8"))

    @app.post("/api/desks/{area_id}/command")
    async def desk_command(area_id: int, request: Request, u=Depends(current_user)):
        data = await body(request)
        n = _desk_node(u, area_id)
        cmd = data.get("cmd")
        if cmd not in COMMANDS:
            raise HTTPException(422, "只支持断电与静音")
        if cmd == "cut_power" and data.get("confirm") is not True:
            raise HTTPException(422, "断电需要确认")
        args = {"by": u["display_name"]}
        if cmd == "mute":
            args["seconds"] = max(0, min(60, int(data.get("seconds", 60))))
        cid = store.queue_command(n["id"], cmd, args, who(u))
        store.audit(who(u), "下发指令", {"desk": store.path_name(area_id), "cmd": cmd})
        return {"id": cid, "note": "终端下次上报（约 2 秒内）执行；恢复供电只能现场按复位键"}

    # ------------------------------------------------------------------
    # 主控决策：按区域配置阈值
    # ------------------------------------------------------------------
    @app.get("/api/presets")
    def get_presets(u=Depends(current_user)):
        return {"presets": presets_mod.PRESETS,
                "spec": {k: {"min": v[1], "max": v[2], "label": v[3], "group": v[4]} for k, v in TUNABLE.items()},
                "agent_spec": {k: {"label": v[0], "range": v[1]} for k, v in AGENT_KEYS.items()}}

    @app.get("/api/profiles/{area_id}")
    def get_profile(area_id: int, u=Depends(current_user)):
        need_area(u, area_id)
        resolved = _resolved_rules(area_id)
        sc = store.descendants([area_id])
        limits = []
        for n in store.nodes():
            if n["area_id"] in sc and n.get("hard_limit_c"):
                w = presets_mod.check_hard_limits(resolved["rules"] if n["area_id"] == area_id
                                                  else _resolved_rules(n["area_id"])["rules"],
                                                  n["hard_limit_c"], n["smoke_limit_raw"] or 2500)
                limits.append({"node": n["name"], "path": store.path_name(n["area_id"]),
                               "hard_limit_c": n["hard_limit_c"], "smoke_limit_raw": n["smoke_limit_raw"],
                               "warnings": w,
                               "applied": (n.get("applied_profile") or {}),
                               "online": _online(n)})
        return {"own": store.profile(area_id), "resolved": resolved, "nodes": limits,
                "path": store.path_name(area_id)}

    @app.put("/api/profiles/{area_id}")
    async def put_profile(area_id: int, request: Request, u=Depends(current_user)):
        need_area(u, area_id)
        data = await body(request)
        preset = str(data.get("preset") or "")
        if preset and preset not in presets_mod.PRESETS:
            raise HTTPException(422, "未知预设")
        rules = data.get("rules") or {}
        if not isinstance(rules, dict):
            raise HTTPException(422, "rules 必须是对象")
        rule_part = {k: v for k, v in rules.items() if k in TUNABLE}
        agent_part = {k: v for k, v in rules.items() if k in AGENT_KEYS}
        unknown = [k for k in rules if k not in TUNABLE and k not in AGENT_KEYS]
        if unknown:
            raise HTTPException(422, {"errors": {k: "不允许配置" for k in unknown}})
        # 总后台这里只做通用范围校验（硬上限放宽到 300℃ / 4000）；各终端按自己控制盒的硬上限再校验
        merged = dict(presets_mod.PRESETS["standard"]["rules"])
        merged.update(_resolved_rules(store.area(area_id)["parent_id"])["rules"]
                      if store.area(area_id)["parent_id"] else {})
        from src.core.tunable import tunable_spec
        ok, errors = validate(rule_part, merged, tunable_spec(305.0, 4100))
        for k, v in agent_part.items():
            label, rng = AGENT_KEYS[k]
            if isinstance(rng, list) and v not in rng:
                errors[k] = f"只能是 {' / '.join(rng)}"
            elif isinstance(rng, tuple):
                try:
                    fv = float(v)
                    if not (rng[0] <= fv <= rng[1]):
                        errors[k] = f"取值需在 {rng[0]}–{rng[1]}"
                    else:
                        ok[k] = int(fv) if k == "agent.max_tokens" else fv
                except (TypeError, ValueError):
                    errors[k] = "类型错误"
            elif isinstance(rng, int):
                ok[k] = str(v)[:rng]
            if k not in errors and k not in ok:
                ok[k] = v
        if errors:
            raise HTTPException(422, {"errors": errors})
        store.set_profile(area_id, preset, ok, who(u))
        store.audit(who(u), "修改决策阈值", {"area": store.path_name(area_id), "preset": preset, "rules": ok})
        return get_profile(area_id, u)

    # ------------------------------------------------------------------
    # 模型看板
    # ------------------------------------------------------------------
    @app.get("/api/models")
    def models(u=Depends(current_user)):
        try:
            with open(model_card, "r", encoding="utf-8") as f:
                card = json.load(f)
        except (OSError, ValueError):
            card = {"models": [], "missing": "未找到 models/model_card.json，请运行 python tools/export_model_card.py"}
        dataset = json.loads(store.meta("dataset", "{}") or "{}")
        for m in card.get("models", []):
            m["dataset"] = dataset.get(m["file"], {})
        # 现场复核：老师在终端「事件复核」里判定识别对 / 错，汇总所有终端
        field = {"reviewed": 0, "correct": 0, "nodes": 0}
        sc = store.scope(u)
        for n in store.nodes():
            if sc is not None and n["area_id"] not in sc:
                continue
            st = (n.get("snapshot") or {}).get("stats") or {}
            if st:
                field["nodes"] += 1
                field["reviewed"] += int(st.get("reviewed", 0) or 0)
                field["correct"] += int(st.get("correct", st.get("review_ok", 0)) or 0)
        card["field"] = field
        return card

    @app.put("/api/models/dataset")
    async def put_dataset(request: Request, u=Depends(admin_user)):
        data = await body(request)
        file = os.path.basename(str(data.get("file", "")))
        if not file:
            raise HTTPException(422, "缺少 file")
        info = {}
        for k in ("train_images", "val_images", "test_images", "instances"):
            if data.get(k) not in (None, ""):
                try:
                    info[k] = max(0, int(data[k]))
                except (TypeError, ValueError):
                    raise HTTPException(422, f"{k} 必须是整数")
        for k in ("source", "note"):
            if data.get(k):
                info[k] = str(data[k])[:200]
        ds = json.loads(store.meta("dataset", "{}") or "{}")
        ds[file] = info
        store.set_meta("dataset", json.dumps(ds, ensure_ascii=False))
        store.audit(who(u), "填写数据集信息", {"file": file, **info})
        return info

    # ------------------------------------------------------------------
    # 语音
    # ------------------------------------------------------------------
    @app.get("/api/voice")
    def voice_info(u=Depends(current_user)):
        return {"assets": store.voice_assets(), "voices": voice_mod.TTS_VOICES, "tones": voice_mod.TONES,
                "kinds": {k: {"name": v[0], "gentle": v[1], "stern": v[2]} for k, v in voice_mod.KINDS.items()},
                "tts_available": voice_mod.tts_available()}

    @app.post("/api/voice/upload")
    async def voice_upload(request: Request, name: str = "", consent: int = 0, u=Depends(current_user)):
        """原始音频作为请求体上传（mp3 / wav / ogg / flac，≤5MB）；录的是真人声音时 consent=1"""
        data = await request.body()
        if not data or len(data) > voice_mod.MAX_UPLOAD:
            raise HTTPException(422, "音频为空或超过 5MB")
        ext = voice_mod.sniff_ext(data)
        if ext is None:
            raise HTTPException(422, "只支持 mp3 / wav / ogg / flac")
        if not consent:
            raise HTTPException(422, "上传真人录音需勾选「已获得本人同意」")
        fname = f"u_{secrets.token_hex(8)}{ext}"
        with open(os.path.join(voice_dir, fname), "wb") as f:
            f.write(data)
        aid = store.add_voice_asset(voice_mod.safe_name(name), "upload", fname, who(u), consent=True)
        store.audit(who(u), "上传语音", {"id": aid, "name": name})
        return store.voice_asset(aid)

    @app.post("/api/voice/tts")
    async def voice_tts(request: Request, u=Depends(current_user)):
        data = await body(request)
        if not voice_mod.tts_available():
            raise HTTPException(501, "总后台未安装 edge-tts（pip install edge-tts），请改为上传音频")
        fname = f"t_{secrets.token_hex(8)}.mp3"
        path = os.path.join(voice_dir, fname)
        try:
            await asyncio.to_thread(voice_mod.tts, str(data.get("text", "")), str(data.get("voice", "")), path,
                                    str(data.get("rate", "+0%")))
        except ValueError as e:
            bad(e)
        except Exception as e:
            raise HTTPException(502, f"TTS 失败（需联网）：{type(e).__name__}")
        aid = store.add_voice_asset(voice_mod.safe_name(data.get("name") or data.get("text", "")), "tts", fname,
                                    who(u), voice=str(data.get("voice")), text=str(data.get("text", "")))
        store.audit(who(u), "生成语音", {"id": aid})
        return store.voice_asset(aid)

    @app.get("/api/voice/{asset_id}/audio")
    def voice_audio(asset_id: int, u=Depends(current_user)):
        a = store.voice_asset(asset_id)
        if a is None:
            raise HTTPException(404)
        return FileResponse(os.path.join(voice_dir, a["filename"]))

    @app.delete("/api/voice/{asset_id}")
    def voice_delete(asset_id: int, u=Depends(current_user)):
        a = store.voice_asset(asset_id)
        if a is None:
            raise HTTPException(404)
        if u["role"] != "admin" and a["created_by"] != who(u):
            raise HTTPException(403, "只能删除自己上传的素材")
        store.delete_voice_asset(asset_id)
        try:
            os.remove(os.path.join(voice_dir, a["filename"]))
        except OSError:
            pass
        store.audit(who(u), "删除语音", {"id": asset_id})
        return {"ok": True}

    @app.get("/api/voice/map/{area_id}")
    def get_voice_map(area_id: int, u=Depends(current_user)):
        if area_id != 0:
            need_area(u, area_id)
        return {"own": store.voice_map(area_id), "resolved": store.resolved_voice(area_id or None)}

    @app.put("/api/voice/map/{area_id}")
    async def put_voice_map(area_id: int, request: Request, u=Depends(current_user)):
        if area_id == 0 and u["role"] != "admin":
            raise HTTPException(403, "全局语音只有管理员能改")
        if area_id != 0:
            need_area(u, area_id)
        data = await body(request)
        kind, tone = str(data.get("kind", "")), str(data.get("tone", ""))
        if kind not in voice_mod.KINDS or tone not in voice_mod.TONES:
            raise HTTPException(422, "事件类型或语气无效")
        try:
            store.set_voice_map(area_id, kind, tone, data.get("asset_id"))
        except StoreError as e:
            bad(e)
        store.audit(who(u), "设置语音", {"area": area_id, "kind": kind, "tone": tone, "asset": data.get("asset_id")})
        return get_voice_map(area_id, u)

    # ------------------------------------------------------------------
    @app.get("/api/audit")
    def audit(n: int = 100, u=Depends(admin_user)):
        return store.audit_log(max(1, min(int(n), 500)))

    return app
