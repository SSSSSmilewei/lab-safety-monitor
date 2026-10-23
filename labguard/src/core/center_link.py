"""
接入总后台（多实验室管理）
src/core/center_link.py

开发板每隔 center.report_s 秒把状态快照上报给总后台，并从回复里拿到：
  · 本实验桌所在区域的规则阈值（主控决策）：先按本机控制盒硬上限再校验一次，超限的项不生效并回报原因；
  · 待执行指令：只有「断电」「静音」两种 —— 总后台同样不能远程上电；
  · 语音包版本：变了就下载对应音频，交给 src/core/voice.py 播放。

总后台挂掉 / 断网不影响本机的安全判断与断电：这里只是一个可选扩展，失败只记录，不抛异常。
"""
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from src.config import cfg, set_value
from src.core.events import events
from src.core.tunable import tunable_spec, validate, label

TRIM_WM = ("phase", "phase_text", "temp", "slope", "eta_s", "eta_boil_s", "plateau_s", "risk")
RULE_PREFIXES = ("rules.", "presence.", "voting.", "events.", "vision.", "cross.")


def node_token() -> str:
    return str(cfg("center.node_token", "") or os.environ.get("LABGUARD_NODE_TOKEN", "") or "").strip()


class CenterLink:
    def __init__(self, engine=None):
        self.engine = engine
        self.online = False
        self.last_ok = 0.0
        self.last_error = ""
        self.profile_version = ""
        self.applied: Dict[str, Any] = {}
        self.profile_errors: Dict[str, str] = {}
        self.voice_version = ""
        self.center_key = ""     # 总后台访问本机画面 / 问答用；只从已认证的上报回复里取得，只存内存
        self._acks: Dict[str, str] = {}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        if self.enabled:
            self._thread = threading.Thread(target=self._loop, name="CenterLink", daemon=True)
            self._thread.start()

    @property
    def enabled(self) -> bool:
        return bool(str(cfg("center.url", "") or "").strip() and node_token())

    # ------------------------------------------------------------------
    def _request(self, path: str, payload: Optional[dict] = None, timeout: float = 5.0) -> bytes:
        url = str(cfg("center.url", "")).rstrip("/") + path
        data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET",
                                     headers={"Content-Type": "application/json", "X-Node-Token": node_token()})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def build_report(self) -> Dict[str, Any]:
        snap = self.engine.snapshot() if self.engine is not None else {}
        wm = snap.get("world_model") or {}
        snap["world_model"] = {k: wm.get(k) for k in TRIM_WM}
        snap.pop("center", None)
        from src.core.voice import voice
        return {
            "snapshot": snap,
            "meta": {
                "web_port": int(cfg("web.port", 8080)),
                "hostname": socket.gethostname(),
                "hard_limit_c": float(cfg("hardware.hard_limit_c", 150.0)),
                "smoke_limit_raw": int(cfg("hardware.smoke_limit_raw", 2500)),
                "profile_version": self.profile_version,
                "applied_profile": self.applied,
                "profile_errors": self.profile_errors,
                "voice_version": self.voice_version or voice.pack.get("version", ""),
                "voice": voice.status(),
            },
            "acks": dict(self._acks),
        }

    def report_once(self) -> Dict[str, Any]:
        """上报一次并处理回复（测试里直接调用）"""
        body = self.build_report()
        sent_acks = dict(self._acks)
        reply = json.loads(self._request("/api/node/report", body).decode("utf-8"))
        for k in sent_acks:
            self._acks.pop(k, None)
        self.online, self.last_ok, self.last_error = True, time.time(), ""
        self.center_key = str(reply.get("center_key") or "")
        self.apply_profile(reply.get("profile") or {})
        for c in reply.get("commands") or []:
            self._acks[str(c.get("id"))] = self.run_command(c)
        v = reply.get("voice") or {}
        if v.get("version") and v.get("version") != self.voice_version:
            self.sync_voice(v)
        return reply

    # ------------------------------------------------------------------
    def apply_profile(self, prof: Dict[str, Any]):
        version = prof.get("version", "")
        if not version or version == self.profile_version:
            return
        rules = prof.get("rules") or {}
        cur = {k: cfg(k) for k in ("rules.dry_burn_c", "rules.heating_on_c", "cross.mid_score", "cross.high_score")}
        rule_part = {k: v for k, v in rules.items() if k.startswith(RULE_PREFIXES)}
        ok, errors = validate(rule_part, cur, tunable_spec())
        changed = {k: v for k, v in ok.items() if cfg(k) != v}
        for k, v in changed.items():
            set_value(k, v)
        if any(k.startswith("vision.") for k in changed) and self.engine is not None:
            ds = self.engine.dual_system
            ds.set_config(ds.camera_mode, ds.enable_ppe, ds.enable_chem,
                          float(cfg("vision.conf")), float(cfg("vision.iou")), ds.img_size)
        agent_part = {k[len("agent."):]: v for k, v in rules.items() if k.startswith("agent.")}
        if agent_part and self.engine is not None and "agent" in self.engine.extensions:
            ag = self.engine.extensions["agent"]
            route = agent_part.pop("route", None)
            try:
                ag.configure({"params": agent_part, **({"route": route} if route else {})})
            except ValueError as e:
                errors.update({f"agent.{k}": v for k, v in (e.args[0] or {}).items()})
        self.profile_version = version
        self.applied = {**ok, **{f"agent.{k}": v for k, v in agent_part.items()}}
        self.profile_errors = errors
        if changed or errors:
            msg = "，".join(f"{label(k)}={v}" for k, v in changed.items()) or "无变化"
            if errors:
                msg += "；未生效：" + "，".join(f"{label(k)}（{v}）" for k, v in errors.items())
            events.log("总后台下发阈值", msg, level="WARNING" if errors else "INFO", kind="config")

    def run_command(self, c: Dict[str, Any]) -> str:
        cmd, args = c.get("cmd"), c.get("args") or {}
        who = str(args.get("by", "总后台"))[:20]
        if self.engine is None:
            return "终端未就绪"
        if cmd == "cut_power":
            return self.engine.cut_power(f"总后台·{who}")
        if cmd == "mute":
            until = self.engine.mute(float(args.get("seconds", 60)))
            return f"已静音至 {time.strftime('%H:%M:%S', time.localtime(until))}"
        return "不支持的指令"   # 没有上电 / 解锁指令

    def sync_voice(self, v: Dict[str, Any]):
        from src.core.voice import voice
        mapping, files = {}, {}
        for kind, tones in (v.get("map") or {}).items():
            for tone, asset in tones.items():
                name = f"{int(asset['id'])}{os.path.splitext(asset.get('filename', '.mp3'))[1] or '.mp3'}"
                if name not in files:
                    files[name] = self._request(f"/api/node/voice/{int(asset['id'])}", timeout=15)
                mapping.setdefault(kind, {})[tone] = name
        voice.install_pack(v["version"], mapping, files)
        self.voice_version = v["version"]
        events.log("语音包已更新", f"{len(files)} 段音频，覆盖 {len(mapping)} 类提醒", kind="config")

    # ------------------------------------------------------------------
    def _loop(self):
        while not self._stop.is_set():
            try:
                self.report_once()
            except urllib.error.HTTPError as e:
                self._fail(f"HTTP {e.code}" + ("（节点密钥无效）" if e.code == 401 else ""))
            except Exception as e:
                self._fail(f"{type(e).__name__}: {e}")
            self._stop.wait(max(0.5, float(cfg("center.report_s", 2.0))))

    def _fail(self, msg: str):
        if self.online:
            events.log("总后台连接断开", f"{msg}（本机安全判断不受影响）", level="NOTICE", kind="link")
        self.online = False
        self.last_error = msg[:200]

    def stop(self):
        self._stop.set()

    def status(self) -> Dict[str, Any]:
        return {"enabled": self.enabled, "online": self.online, "url": str(cfg("center.url", "") or ""),
                "last_ok": self.last_ok, "error": self.last_error, "profile_version": self.profile_version,
                "profile_errors": self.profile_errors, "voice_version": self.voice_version}
