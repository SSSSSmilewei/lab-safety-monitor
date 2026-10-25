"""
演示场景注入（网页大屏「环境控制 → 演示数据」）
src/core/demo.py

路演现场不能真的把烧杯烧干，所以用"场景注入"模拟遥测：
  · 只在 未接入下位机 且 config.demo.allow_ipc_telemetry = true 时可用（接上真硬件就拒绝，真假数据不混用）；
  · 写入一个临时 IPC 文件，SensorWorker 原样读取，后续研判链路与真实数据完全一致。
"""
import json
import os
import threading
import time
from typing import Dict, Any, Optional

from src.config import cfg
from src.hardware.sensor_worker import SensorWorker

# 场景：台面温度 temp 可以是常数，也可以是随时间 t（秒）变化的曲线
SCENARIOS: Dict[str, Dict[str, Any]] = {
    "normal": {"name": "正常环境", "temp": 25.0, "humi": 55.0, "smoke": None},
    "heating": {"name": "正常加热（缓慢升温）", "humi": 58.0, "smoke": 300,
                "temp": lambda t: min(38.0, 26.0 + 0.1 * t)},
    "overtemp": {"name": "台面超温（升温突破断电线）", "humi": 52.0, "smoke": 350,
                 "temp": lambda t: min(62.0, 30.0 + 0.4 * t)},
    "smoke": {"name": "烟雾超标", "temp": 30.0, "humi": 50.0, "smoke": 2300},
    "humid": {"name": "高湿受潮", "temp": 25.0, "humi": 86.0, "smoke": None},
    "dry_air": {"name": "空气过干", "temp": 25.0, "humi": 28.0, "smoke": None},
    "hot": {"name": "台面温度偏高", "temp": 42.0, "humi": 50.0, "smoke": None},
}


class DemoInjector:
    def __init__(self, engine=None):
        self.engine = engine
        self.scenario: Optional[str] = None
        self.custom: Dict[str, Any] = {}
        self.started = 0.0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def available(self) -> (bool, str):
        if not bool(cfg("demo.allow_ipc_telemetry", True)):
            return False, "配置 demo.allow_ipc_telemetry 为 false，演示注入已关闭"
        link = getattr(self.engine, "serial", None)
        if link is not None and getattr(link, "is_alive", False):
            return False, "已接入下位机，真实数据优先，拒绝演示注入"
        return True, ""

    def start(self, scenario: str, custom: Optional[Dict[str, Any]] = None) -> str:
        ok, why = self.available()
        if not ok:
            raise PermissionError(why)
        if scenario != "custom" and scenario not in SCENARIOS:
            raise ValueError("未知场景")
        self.scenario = scenario
        self.custom = dict(custom or {})
        self.started = time.time()
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="DemoInjector", daemon=True)
            self._thread.start()
        return SCENARIOS.get(scenario, {}).get("name", "自定义数值")

    def stop(self) -> str:
        self.scenario = None
        self._stop.set()
        try:
            os.remove(SensorWorker.IPC_TELEMETRY_PATH)
        except OSError:
            pass
        return "演示注入已停止"

    def _values(self) -> Dict[str, Any]:
        t = time.time() - self.started
        if self.scenario == "custom":
            c = self.custom
            return {"temp": float(c.get("temp", 25)), "humi": float(c.get("humi", 55)), "smoke": c.get("smoke")}
        sc = SCENARIOS[self.scenario]
        temp = sc["temp"](t) if callable(sc["temp"]) else sc["temp"]
        return {"temp": round(temp, 1), "humi": sc["humi"], "smoke": sc["smoke"]}

    def _loop(self):
        while not self._stop.is_set():
            if self.scenario is None or not self.available()[0]:
                break
            payload = dict(self._values(), scenario=SCENARIOS.get(self.scenario, {}).get("name", "自定义"),
                           source="WEB_DEMO", timestamp=time.time())
            path = SensorWorker.IPC_TELEMETRY_PATH
            try:
                with open(path + ".tmp", "w", encoding="utf-8") as f:
                    json.dump(payload, f)
                os.replace(path + ".tmp", path)
            except Exception as e:
                print(f"[Demo] 写入失败: {e}")
            self._stop.wait(0.5)
        self.scenario = None

    def status(self) -> Dict[str, Any]:
        ok, why = self.available()
        return {"available": ok, "reason": why, "scenario": self.scenario,
                "scenario_name": SCENARIOS.get(self.scenario, {}).get("name") if self.scenario else None,
                "elapsed_s": round(time.time() - self.started) if self.scenario else 0,
                "scenarios": {k: v["name"] for k, v in SCENARIOS.items()}}
