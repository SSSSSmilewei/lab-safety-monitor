"""
Edge API + 大屏总后台（FastAPI）
src/web/server.py

与安全引擎跑在同一进程（uvicorn 独立线程），局域网内任意设备用浏览器打开 http://<板子IP>:8080 即可。

安全约定：
  · 除静态页面与 /api/ping 外，所有接口都需要口令（请求头 X-Token 或 ?token=）。
    口令默认自动生成并保存在 runtime/web_token.txt（不进仓库），小屏设置页可查看。
  · 写接口只允许修改白名单内的参数，并做取值范围校验。
  · 只提供"断电"，不提供任何"上电 / 解除锁定"接口 —— 恢复供电只能现场按复位键。
  · 演示注入在接入下位机时一律拒绝（409）。
"""
import asyncio
import glob
import json
import os
import secrets
import socket
import threading
import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.config import cfg, set_value, resolve_path, PROJECT_ROOT
from src.core.events import events
from src.core import desk_zone
from src.core.tunable import tunable_spec, validate as validate_tunable, label as tunable_label

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
FONT_PATH = os.path.join(PROJECT_ROOT, "LabSafetyMonitor", "Zpix.ttf")

# 可调参数白名单与校验见 src/core/tunable.py（总后台下发阈值时用同一套校验）


def web_token() -> str:
    tok = str(cfg("web.token", "") or "").strip()
    if tok:
        return tok
    path = resolve_path(os.path.join("runtime", "web_token.txt"))
    try:
        with open(path, "r", encoding="utf-8") as f:
            tok = f.read().strip()
    except OSError:
        tok = ""
    if not tok:
        tok = secrets.token_hex(3).upper()   # 6 位，方便在小屏上看着输入
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(tok)
        except OSError as e:
            print(f"[Web] 口令文件写入失败（本次运行口令仅内存有效）: {e}")
    set_value("web.token", tok, persist=False)
    return tok


def create_app(engine) -> FastAPI:
    app = FastAPI(title="实验室安全监测 · 总后台", docs_url=None, redoc_url=None)
    token = web_token()

    def auth(request: Request):
        got = request.headers.get("x-token") or request.query_params.get("token") or ""
        if not secrets.compare_digest(got, token):
            raise HTTPException(401, "口令错误")

    def auth_or_center(request: Request):
        """总后台凭它下发的访问密钥调用：只开放画面、快照与安全助手问答，不开放任何写配置 / 控制接口"""
        link = ext.get("center")
        key = getattr(link, "center_key", "") if link is not None else ""
        got = request.headers.get("x-center-key") or ""
        if key and got and secrets.compare_digest(got, key):
            return
        auth(request)

    ext = engine.extensions

    def need(name):
        m = ext.get(name)
        if m is None:
            raise HTTPException(503, f"{name} 模块未启用")
        return m

    async def body(request: Request) -> Dict[str, Any]:
        try:
            data = await request.json()
        except Exception:
            raise HTTPException(400, "请求体不是 JSON")
        if not isinstance(data, dict):
            raise HTTPException(400, "请求体必须是对象")
        return data

    # ---------------- 页面与静态资源 ----------------
    @app.get("/", response_class=HTMLResponse)
    def index():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    @app.get("/font/zpix.ttf")
    def font():
        return FileResponse(FONT_PATH, media_type="font/ttf")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    fonts_dir = os.path.join(PROJECT_ROOT, "fonts")   # 得意黑、JetBrains Mono（SIL OFL），与总后台共用
    if os.path.isdir(fonts_dir):
        app.mount("/fonts", StaticFiles(directory=fonts_dir), name="fonts")

    @app.get("/api/ping")
    def ping():
        return {"ok": True, "ts": time.time()}

    # ---------------- 只读 ----------------
    @app.get("/api/snapshot", dependencies=[Depends(auth_or_center)])
    def snapshot():
        return JSONResponse(engine.snapshot())

    @app.get("/api/events", dependencies=[Depends(auth)])
    def list_events(n: int = 50, min_level: str = "NOTICE"):
        return events.history(max(1, min(n, 300)), min_level)

    @app.get("/api/events/{uid}/snapshot.jpg", dependencies=[Depends(auth)])
    def event_image(uid: str):
        ev = events.get_event(uid)
        path = ev.get("snapshot") if ev else None
        if not path or not os.path.isfile(path):
            raise HTTPException(404, "该事件没有截图")
        return FileResponse(path, media_type="image/jpeg")

    @app.get("/api/config", dependencies=[Depends(auth)])
    def get_config():
        return {k: {"value": cfg(k), "min": v[1], "max": v[2], "label": v[3]} for k, v in tunable_spec().items()}

    @app.get("/api/models", dependencies=[Depends(auth)])
    def list_models():
        files = sorted(set(glob.glob(os.path.join(PROJECT_ROOT, "models", "*.pt")) +
                           glob.glob(os.path.join(PROJECT_ROOT, "models", "*.onnx")) +
                           glob.glob(os.path.join(PROJECT_ROOT, "models", "*_rknn_model"))))
        ds = engine.dual_system
        return {"files": [os.path.basename(f) for f in files], "loaded": dict(ds.model_info),
                "enable_ppe": ds.enable_ppe, "enable_chem": ds.enable_chem}

    @app.get("/api/media", dependencies=[Depends(auth)])
    def list_media():
        # 演示视频放在 labguard/media/，或仓库根目录的 local_private/（不上传 GitHub）
        repo = os.path.dirname(PROJECT_ROOT)
        roots = [resolve_path("media"), os.path.join(repo, "local_private"), repo]
        files = []
        for r in roots:
            for ext_ in ("*.mp4", "*.avi", "*.mov", "*.mkv"):
                files += glob.glob(os.path.join(r, ext_))
        return {"files": [os.path.basename(f) for f in sorted(files)], "current": engine.media_label}

    # ---------------- MJPEG 画面 ----------------
    @app.get("/stream/{which}.mjpg", dependencies=[Depends(auth)])
    async def stream(which: str):
        if which not in ("pano", "desk"):
            raise HTTPException(404)
        fps = max(1.0, float(cfg("web.stream_fps", 6)))

        async def gen():
            last = -1
            while True:
                seq = engine.frame_seq
                if seq != last:
                    last = seq
                    data = await asyncio.to_thread(engine.latest_jpeg, which)
                    if data:
                        yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                               + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n")
                await asyncio.sleep(1.0 / fps)

        return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.get("/api/frame/{which}.jpg", dependencies=[Depends(auth_or_center)])
    def frame(which: str):
        data = engine.latest_jpeg(which if which in ("pano", "desk") else "pano")
        if not data:
            raise HTTPException(404, "暂无画面")
        return StreamingResponse(iter([data]), media_type="image/jpeg")

    # ---------------- WebSocket 推送（2 Hz） ----------------
    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        if not secrets.compare_digest(sock.query_params.get("token", ""), token):
            await sock.close(code=4401)
            return
        await sock.accept()
        try:
            while True:
                snap = await asyncio.to_thread(engine.snapshot)
                snap["recent_events"] = events.history(12, "NOTICE")
                await sock.send_text(json.dumps(snap, ensure_ascii=False, default=str))
                await asyncio.sleep(0.5)
        except (WebSocketDisconnect, RuntimeError):
            pass

    # ---------------- 写接口 ----------------
    @app.patch("/api/config", dependencies=[Depends(auth)])
    async def patch_config(request: Request):
        data = await body(request)
        changed, errors = validate_tunable(data, {k: cfg(k) for k in ("rules.dry_burn_c", "rules.heating_on_c", "cross.mid_score", "cross.high_score")})
        if errors:
            raise HTTPException(422, {"errors": errors})
        for k, v in changed.items():
            set_value(k, v)
        if any(k.startswith("vision.") for k in changed):
            ds = engine.dual_system
            ds.set_config(ds.camera_mode, ds.enable_ppe, ds.enable_chem,
                          float(cfg("vision.conf")), float(cfg("vision.iou")), ds.img_size)
        events.log("参数已调整", "，".join(f"{tunable_label(k)}={v}" for k, v in changed.items()), kind="config")
        return {"changed": changed}

    # ---------------- 台面安全区（器皿靠近桌边判定） ----------------
    @app.get("/api/desk/zone", dependencies=[Depends(auth)])
    def get_desk_zone():
        return {"zone": cfg("desk.zone", None), "margin": float(cfg("desk.edge_margin", 0.06)),
                "line": cfg("desk.edge_line", desk_zone.DEFAULT_LINE)}

    @app.put("/api/desk/zone", dependencies=[Depends(auth)])
    async def put_desk_zone(request: Request):
        data = await body(request)
        try:
            zone = desk_zone.validate_zone(data)
        except desk_zone.ZoneError as e:
            raise HTTPException(422, str(e))
        margin = data.get("margin")
        if margin is not None:
            try:
                margin = float(margin)
            except (TypeError, ValueError):
                raise HTTPException(422, "预警距离必须是数字")
            if not (0.01 <= margin <= 0.3):
                raise HTTPException(422, "预警距离需在 0.01–0.3（画面比例）")
            set_value("desk.edge_margin", round(margin, 3))
        set_value("desk.zone", zone)
        events.log("台面安全区已调整",
                   f"{len(zone['points'])} 个顶点、{sum(zone['danger'])} 条危险边" if zone else "已清除，改用默认桌边线",
                   kind="config")
        return get_desk_zone()

    @app.post("/api/model", dependencies=[Depends(auth)])
    async def switch_model(request: Request):
        data = await body(request)
        slot, name = data.get("slot"), os.path.basename(str(data.get("name", "")))
        if slot not in ("ppe", "chem"):
            raise HTTPException(400, "slot 只能是 ppe 或 chem")
        if "enabled" in data:
            ds = engine.dual_system
            ppe = bool(data["enabled"]) if slot == "ppe" else ds.enable_ppe
            chem = bool(data["enabled"]) if slot == "chem" else ds.enable_chem
            ds.set_config(ds.camera_mode, ppe, chem, ds.conf_thres, ds.iou_thres, ds.img_size)
            if not name:
                return {"ok": True, "msg": "已" + ("启用" if data["enabled"] else "停用")}
        path = os.path.join(PROJECT_ROOT, "models", name)
        if not name or not os.path.exists(path):
            raise HTTPException(404, "models/ 目录下没有这个模型")
        ok, msg = await asyncio.to_thread(engine.dual_system.reload_model, slot, path)
        return {"ok": ok, "msg": msg}

    @app.post("/api/camera", dependencies=[Depends(auth)])
    async def switch_camera(request: Request):
        data = await body(request)
        mode = data.get("mode")
        ds = engine.dual_system

        def src(v):
            if isinstance(v, int) or (isinstance(v, str) and v.strip().isdigit()):
                return int(v)
            v = str(v or "").strip()
            if v.startswith(("http://", "https://", "rtsp://")):
                return v
            raise HTTPException(400, "画面源只能是摄像头序号或 http/rtsp 地址")

        if mode == "camera":
            ds.load_media(src1=0, src2=0, force_reload=True)
            engine.media_label = "摄像头（config.yaml 机位）"
        elif mode == "url":
            ds.load_media(src1=src(data.get("pano", 0)), src2=src(data.get("desk", 0)))
            engine.media_label = f"网络 / 外接摄像头"
        elif mode == "video":
            if getattr(engine.serial, "is_alive", False):
                raise HTTPException(409, "已接入下位机，真实数据优先，不能播放演示视频")
            name = os.path.basename(str(data.get("name", "")))
            repo = os.path.dirname(PROJECT_ROOT)
            path = next((p for p in (os.path.join(resolve_path("media"), name),
                                     os.path.join(repo, "local_private", name),
                                     os.path.join(repo, name)) if os.path.isfile(p)), None)
            if not path:
                raise HTTPException(404, "找不到该视频")
            ds.load_media(src1=path, src2=path)
            engine.media_label = f"视频：{name}"
        elif mode == "pause":
            ds.set_pause(bool(data.get("pause", not ds.is_paused)))
        else:
            raise HTTPException(400, "mode 只能是 camera / url / video / pause")
        return {"ok": True, "media": engine.media_label, "paused": ds.is_paused}

    @app.post("/api/power/cut", dependencies=[Depends(auth)])
    async def power_cut(request: Request):
        data = await body(request)
        if data.get("confirm") is not True:
            raise HTTPException(400, "需要 confirm: true")
        msg = engine.cut_power("总后台")
        return {"ok": True, "msg": msg, "note": "恢复供电只能在现场按控制盒复位键"}

    @app.post("/api/mute", dependencies=[Depends(auth)])
    async def mute(request: Request):
        data = await body(request)
        until = engine.mute(float(data.get("seconds", 60)))
        return {"mute_until": until}

    @app.post("/api/events/{uid}/review", dependencies=[Depends(auth)])
    async def review(uid: str, request: Request):
        data = await body(request)
        if events.get_event(uid) is None:
            raise HTTPException(404, "事件不存在")
        events.set_review(uid, bool(data.get("correct")))
        return {"ok": True}

    @app.post("/api/manual_snapshot", dependencies=[Depends(auth)])
    def manual_snapshot():
        pano, desk = engine.latest_frames()
        if pano is None:
            raise HTTPException(409, "暂无画面")
        events.set_latest_frames(pano, desk)
        events.log("人工抓拍", "总后台手动记录当前画面", level="NOTICE", kind="manual", snapshot=True)
        return {"ok": True}

    # ---------------- Agent ----------------
    @app.get("/api/agent", dependencies=[Depends(auth)])
    def agent_status():
        return need("agent").status()

    @app.post("/api/agent/config", dependencies=[Depends(auth)])
    async def agent_config(request: Request):
        try:
            return need("agent").configure(await body(request))
        except ValueError as e:
            raise HTTPException(422, {"errors": e.args[0] if e.args else str(e)})

    @app.post("/api/agent/test", dependencies=[Depends(auth)])
    async def agent_test(request: Request):
        data = await body(request)
        return await asyncio.to_thread(need("agent").llm.test, str(data.get("route", "remote")))

    @app.post("/api/agent/ask", dependencies=[Depends(auth_or_center)])
    async def agent_ask(request: Request):
        data = await body(request)
        q = str(data.get("question", "")).strip()
        if not q:
            raise HTTPException(400, "问题不能为空")
        hist = data.get("history") if isinstance(data.get("history"), list) else []
        return await asyncio.to_thread(need("agent").ask, q, hist)

    @app.post("/api/agent/report", dependencies=[Depends(auth_or_center)])
    async def agent_report():
        return await asyncio.to_thread(need("agent").report)

    @app.post("/api/events/{uid}/agent", dependencies=[Depends(auth)])
    async def agent_review(uid: str):
        note = await asyncio.to_thread(need("agent").review_event, uid)
        if note is None:
            raise HTTPException(404, "事件不存在")
        return {"note": note}

    # ---------------- 环境控制 ----------------
    @app.get("/api/env", dependencies=[Depends(auth)])
    def env_status():
        return need("env").status()

    @app.post("/api/env/setpoint", dependencies=[Depends(auth)])
    async def env_setpoint(request: Request):
        data = await body(request)
        try:
            msg = need("env").set_setpoint(data.get("t_set"), data.get("h_low"), data.get("h_high"))
        except (TypeError, ValueError) as e:
            raise HTTPException(422, str(e))
        return {"msg": msg, "env": need("env").status()}

    @app.post("/api/env/manual", dependencies=[Depends(auth)])
    async def env_manual(request: Request):
        data = await body(request)
        fan = data.get("fan_pwm")
        msg = need("env").set_manual(None if fan is None else int(fan), bool(data.get("humid")))
        return {"msg": msg, "env": need("env").status()}

    # ---------------- 演示注入 ----------------
    @app.get("/api/demo", dependencies=[Depends(auth)])
    def demo_status():
        return need("demo").status()

    @app.post("/api/demo/start", dependencies=[Depends(auth)])
    async def demo_start(request: Request):
        data = await body(request)
        try:
            name = need("demo").start(str(data.get("scenario", "")), data.get("custom"))
        except PermissionError as e:
            raise HTTPException(409, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))
        events.log("演示场景", f"开始注入：{name}", kind="demo")
        return need("demo").status()

    @app.post("/api/demo/stop", dependencies=[Depends(auth)])
    def demo_stop():
        need("demo").stop()
        return need("demo").status()

    # ---------------- 世界模型（主机侧 JEPA worker 回写） ----------------
    @app.post("/api/jepa/score", dependencies=[Depends(auth)])
    async def jepa_score(request: Request):
        data = await body(request)
        try:
            score = float(data["score"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(400, "需要数值 score")
        need("jepa").push(score, str(data.get("note", ""))[:200], str(data.get("model", ""))[:80])
        return {"ok": True}

    return app


# 实际使用的端口：配置的端口被别的程序（如 Dify、Docker）占用时会自动往后顺延
_web_port: Optional[int] = None


def web_port() -> int:
    return _web_port or int(cfg("web.port", 8080))


def local_ips():
    """本机局域网 IPv4 地址（不含 127.0.0.1）；网线 / Wi-Fi 都没连时返回空列表"""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))        # UDP 不会真的发包，只用来查出默认网卡的地址
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return [ip for ip in ips if not ip.startswith("127.")]


def web_urls():
    port = web_port()
    return [f"http://127.0.0.1:{port}"] + [f"http://{ip}:{port}" for ip in local_ips()]


def _port_free(host: str, port: int) -> bool:
    # 先看本机这个端口有没有程序在应答：Docker（Dify 等）有时只占 127.0.0.1，单纯试绑 0.0.0.0 查不出来
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return False
    except OSError:
        pass
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name != "nt":   # 与 uvicorn 一致；Windows 上这个选项含义不同，会把占用的端口也判成可用
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def _pick_port(host: str, port: int, tries: int = 20) -> Optional[int]:
    for p in range(port, port + tries):
        if _port_free(host, p):
            return p
    return None


def start_server(engine) -> Optional[threading.Thread]:
    """在后台线程启动 uvicorn；失败只打印，不影响安全主循环"""
    global _web_port
    if not bool(cfg("web.enabled", True)):
        return None
    try:
        import uvicorn
    except ImportError:
        print("[Web] 未安装 fastapi / uvicorn，总后台未启动（pip install fastapi uvicorn）")
        return None
    host, want = str(cfg("web.host", "0.0.0.0")), int(cfg("web.port", 8080))
    port = _pick_port(host, want)
    if port is None:
        print(f"[Web] 端口 {want}–{want + 19} 都被占用，总后台未启动。请在 config.yaml → web.port 换一个端口")
        return None
    if port != want:
        print(f"[Web] 端口 {want} 已被其他程序占用（例如 Dify / Docker），自动改用 {port}")
    _web_port = port
    app = create_app(engine)
    # rknn-toolkit-lite2 导入时会把 logging 的级别名换成 C/E/W/I/D，uvicorn 配置日志时会报 Unknown level，这里补回标准名字
    import logging
    for _name, _lvl in (("CRITICAL", 50), ("FATAL", 50), ("ERROR", 40), ("WARN", 30), ("WARNING", 30),
                        ("INFO", 20), ("DEBUG", 10), ("NOTSET", 0)):
        logging._nameToLevel.setdefault(_name, _lvl)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None   # 在子线程运行，信号交给 Qt 主线程
    t = threading.Thread(target=server.run, name="WebServer", daemon=True)
    t.start()

    urls = web_urls() if host == "0.0.0.0" else [f"http://{host}:{port}"]
    tok = web_token()
    lines = [f"[Web] 总后台已启动，口令 {tok}。用浏览器打开："]
    lines += [f"        {u}/?token={tok}" + ("    （本机）" if "127.0.0.1" in u else "    （同一局域网的其他设备）")
              for u in urls]
    print("\n".join(lines))
    try:
        path = resolve_path(os.path.join("runtime", "web_url.txt"))
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(f"{u}/?token={tok}" for u in urls) + "\n")   # 带口令，复制整行就能直接登录
    except OSError:
        pass
    return t
