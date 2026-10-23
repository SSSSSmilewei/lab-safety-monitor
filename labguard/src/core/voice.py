"""
语音提醒（软件层）
src/core/voice.py

两条输出，可同时用（config.yaml → voice.output）：
  · dfplayer：下位机 DFPlayer 按 TF 卡曲目号播放（原有方式，曲目号见 events.voice）
  · local：开发板本机扬声器播放语音包里的音频（ffplay / mpg123 / paplay / aplay 任一可用即可）

语音包由总后台下发：每类事件可以有两种语气 ——
  gentle 温和提醒（低 / 中危：如"同学，记得戴好护目镜哦"）
  stern  严厉干预（高危 / 紧急：如"立即停止加热，离开实验台"）
素材可以是 TTS 生成的多种音色，也可以是任课老师本人录音（需本人同意，总后台上传时勾选确认）。
本地没有对应素材时回退到 DFPlayer 曲目。
"""
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from typing import Dict, Optional

from src.config import cfg, resolve_path

PLAYERS = (
    ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]),
    ("mpg123", ["mpg123", "-q"]),
    ("paplay", ["paplay"]),
    ("aplay", ["aplay", "-q"]),
)


def pack_dir() -> str:
    return resolve_path(os.path.join("runtime", "voice"))


class VoicePlayer:
    def __init__(self):
        self._q: "queue.Queue[str]" = queue.Queue(maxsize=3)
        self._lock = threading.Lock()
        self._worker: Optional[threading.Thread] = None
        self.pack: Dict = {"version": "", "map": {}}
        self.last_played = ""
        self._load_pack()

    # ------------------------------------------------------------------
    @staticmethod
    def player_cmd():
        for name, cmd in PLAYERS:
            if shutil.which(name):
                return cmd
        return None

    def _load_pack(self):
        try:
            with open(os.path.join(pack_dir(), "pack.json"), "r", encoding="utf-8") as f:
                self.pack = json.load(f)
        except (OSError, ValueError):
            self.pack = {"version": "", "map": {}}

    def install_pack(self, version: str, mapping: Dict[str, Dict[str, str]], files: Dict[str, bytes]):
        """总后台下发的语音包：mapping {kind: {tone: 文件名}}，files {文件名: 内容}"""
        d = pack_dir()
        os.makedirs(d, exist_ok=True)
        for name, data in files.items():
            safe = os.path.basename(name)
            with open(os.path.join(d, safe), "wb") as f:
                f.write(data)
        pack = {"version": version, "map": mapping}
        tmp = os.path.join(d, "pack.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(pack, f, ensure_ascii=False)
        os.replace(tmp, os.path.join(d, "pack.json"))
        with self._lock:
            self.pack = pack

    def local_file(self, kind: str, tone: str) -> Optional[str]:
        m = (self.pack.get("map") or {}).get(kind) or {}
        name = m.get(tone) or m.get("gentle" if tone == "stern" else "stern")
        if not name:
            return None
        path = os.path.join(pack_dir(), os.path.basename(name))
        return path if os.path.isfile(path) else None

    # ------------------------------------------------------------------
    def play(self, kind: str, tone: str, serial_link=None) -> str:
        """按配置播放；返回实际走的通道（local / dfplayer / none）"""
        output = str(cfg("voice.output", "dfplayer") or "dfplayer")
        used = "none"
        if output in ("local", "both"):
            path = self.local_file(kind, tone)
            if path and self.player_cmd():
                try:
                    self._q.put_nowait(path)
                    self._ensure_worker()
                    used = "local"
                except queue.Full:
                    pass
        if output in ("dfplayer", "both") or used == "none":
            track = (cfg("events.voice", {}) or {}).get(kind)
            if track and serial_link is not None and serial_link.play_voice(int(track)):
                used = "dfplayer" if used == "none" else "both"
        if used != "none":
            self.last_played = f"{time.strftime('%H:%M:%S')} {kind}（{'严厉' if tone == 'stern' else '温和'}）· {used}"
        return used

    def _ensure_worker(self):
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._loop, name="VoicePlayer", daemon=True)
            self._worker.start()

    def _loop(self):
        while True:
            try:
                path = self._q.get(timeout=30)
            except queue.Empty:
                return
            cmd = self.player_cmd()
            if not cmd:
                continue
            try:
                subprocess.run(cmd + [path], timeout=20, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"[Voice] 播放失败: {e}")

    def status(self) -> Dict:
        cmd = self.player_cmd()
        return {"output": cfg("voice.output", "dfplayer"), "player": cmd[0] if cmd else None,
                "pack_version": self.pack.get("version", ""),
                "kinds": sorted((self.pack.get("map") or {}).keys()), "last_played": self.last_played}


voice = VoicePlayer()
