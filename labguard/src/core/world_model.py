"""
台面温度趋势模型（板载轻量版）
src/core/world_model.py

作用：根据台面温度（SHT30，放在加热器旁 5～10 cm）的历史，预测"接下来会怎样"——
未来 120 秒的温度走势、多久后超过提醒线（rules.ambient_high_c）和断电线（rules.overtemp_cut_c）。
它只产生预测与风险分，供规则 R9（提前提醒，不断电）、界面与安全助手使用。

做法：对最近 fit_window_s 秒的温度做最小二乘直线拟合，得到升温速度（℃/s），按直线外推。
空气温度变化慢、噪声小，直线外推足够；不再做沸腾平台、一阶热平衡那一套（那是给热源表面测温用的）。

计算量：每秒一次、几十个点的最小二乘，适合开发板。
"""
import threading
import time
from collections import deque
from typing import Optional, Dict, Any, List, Tuple

from src.config import cfg


class ThermalWorldModel:
    HORIZON_S = 120.0
    MIN_SLOPE = 0.005          # ℃/s（0.3℃/min）以下算"基本不变"

    def __init__(self):
        self._lock = threading.Lock()
        self._hist: deque = deque(maxlen=400)   # (t, T)
        self._last: Dict[str, Any] = self._empty()

    @staticmethod
    def _empty() -> Dict[str, Any]:
        # eta_boil_s / plateau_s / t_inf / tau 是旧版热源模型的字段，保留为空值，旧调用方不报错
        return {"phase": "no_sensor", "temp": None, "slope": None, "slope_per_min": None,
                "eta_s": None, "eta_warn_s": None, "will_overheat": False, "risk": 0.0,
                "forecast": [], "model": None, "ts": time.time(),
                "eta_boil_s": None, "plateau_s": 0.0, "t_inf": None, "tau": None}

    def reset(self):
        with self._lock:
            self._hist.clear()
            self._last = self._empty()

    # ------------------------------------------------------------------
    def update(self, temp: Optional[float], now: Optional[float] = None,
               unattended: bool = False) -> Dict[str, Any]:
        now = time.time() if now is None else now
        with self._lock:
            if temp is None:
                self._hist.clear()
                self._last = self._empty()
                return dict(self._last)
            if self._hist and now - self._hist[-1][0] < 0.4:
                return dict(self._last)
            self._hist.append((now, float(temp)))
            self._last = self._predict(now, float(temp), unattended)
            return dict(self._last)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            out = dict(self._last)
            if self._hist:
                t_end = self._hist[-1][0]
                out["history"] = [[round(t - t_end, 1), round(v, 1)] for t, v in self._hist if t_end - t <= 120]
            else:
                out["history"] = []
            return out

    # ------------------------------------------------------------------
    @staticmethod
    def _linfit(xs, ys) -> Optional[Tuple[float, float]]:
        n = len(xs)
        if n < 3:
            return None
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        if sxx < 1e-9:
            return None
        k = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
        return k, my - k * mx

    def _predict(self, now: float, temp: float, unattended: bool) -> Dict[str, Any]:
        cut_c = float(cfg("rules.overtemp_cut_c", 55.0))
        warn_c = float(cfg("rules.ambient_high_c", 40.0))
        heat_on = float(cfg("rules.heating_on_c", 35.0))
        out = self._empty()
        out["temp"] = round(temp, 1)

        win: List[Tuple[float, float]] = [(t, v) for t, v in self._hist
                                          if now - t <= float(cfg("world_model.fit_window_s", 60.0))]
        if len(win) < 6 or win[-1][0] - win[0][0] < 8.0:
            out["phase"] = "overheat" if temp >= cut_c else "warming_up"
            return out

        t0 = win[0][0]
        fit = self._linfit([t - t0 for t, _ in win], [v for _, v in win])
        slope = fit[0] if fit else 0.0
        out["slope"] = round(slope, 4)
        out["slope_per_min"] = round(slope * 60.0, 2)
        out["model"] = "linear"
        out["forecast"] = [[k, round(temp + slope * k, 1)] for k in range(0, int(self.HORIZON_S) + 1, 10)]

        def time_to(target):
            if temp >= target:
                return 0.0
            return (target - temp) / slope if slope > self.MIN_SLOPE else None

        eta = time_to(cut_c)
        eta_warn = time_to(warn_c)
        out["eta_s"] = round(eta, 1) if eta is not None else None
        out["eta_warn_s"] = round(eta_warn, 1) if eta_warn is not None else None
        out["will_overheat"] = eta is not None

        if temp >= cut_c:
            phase, risk = "overheat", 1.0
        elif slope > self.MIN_SLOPE and temp >= heat_on * 0.8:
            phase = "heating"
            risk = 0.0 if eta is None else max(0.0, min(1.0, 1.0 - eta / (5 * self.HORIZON_S)))
        elif slope > self.MIN_SLOPE:
            phase, risk = "warming", 0.0
        elif slope < -self.MIN_SLOPE:
            phase, risk = "cooling", 0.0
        else:
            phase, risk = ("steady" if temp >= heat_on else "idle"), 0.0
        if temp >= warn_c:
            risk = max(risk, 0.5)
        if unattended and risk > 0:
            risk = min(1.0, risk * 1.5)
        out["phase"] = phase
        out["risk"] = round(risk, 2)
        return out


PHASE_TEXT = {
    "no_sensor": "温度计无数据", "idle": "常温", "warming_up": "采样中", "warming": "缓慢升温",
    "heating": "升温中", "steady": "温度稳定", "cooling": "降温中", "overheat": "已超断电线",
}
