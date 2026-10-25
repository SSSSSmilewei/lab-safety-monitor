"""
跨模态边缘状态机联合决策逻辑
src/core/state_machine.py

输入：
  · 宏观通道（全景摄像头）：是否无人值守
  · 微观通道（台面摄像头）：台面上识别到的器皿
  · 环境遥测：台面温度、湿度（SHT30，放在加热器旁 5～10 cm）；烟雾（MQ-2）

"正在加热"的判断：接着下位机时 = 继电器闭合（加热片有电）；没接下位机（演示）时 = 台面温度 ≥ heating_on_c。

判决规则（阈值见 config.yaml → rules）：
  R1 台面超温      台面温度 ≥ overtemp_cut_c                                → CRITICAL，断电
  R2 升温过快      正在加热 且 最近 60 秒升温 ≥ rate_c_per_min ℃/min        → WARNING
  R3 加热无人值守  正在加热 且 无人值守：先 WARNING，持续 ≥ cut_s 秒后       → CRITICAL，断电
  R5 烟雾          MQ-2 读数 ≥ smoke_raw                                    → CRITICAL，断电
  R6 高湿          湿度 > humidity_high                                      → WARNING
  R7 台面高温      台面温度 > ambient_high_c                                 → WARNING
  R8 量器加热      正在加热 且 台面出现容量瓶/量筒等量器                     → NOTICE 提醒
  R9 预测超温      温度趋势预测 ≤ predict_eta_warn_s 秒后达到 overtemp_cut_c → WARNING（只提醒，不断电）
  （R4 旧的"环境温度兜底"已并入 R1）

断电锁定（LATCH）：
  一旦断电，状态保持 CRITICAL，直到现场按下控制盒的复位键（下位机上报）才解除。
  软件只能断电、不能上电。未接入下位机的演示模式下，危险解除 sim_latch_release_s 秒后自动解除。
"""
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

try:
    from PySide6.QtCore import QObject, Signal
except ImportError:
    from PyQt6.QtCore import QObject, pyqtSignal as Signal

from src.config import cfg
from src.core.events import events
from src.core.telemetry import telemetry
from src.core.world_model import ThermalWorldModel

LEVEL_RANK = {"NOTICE": 1, "WARNING": 2, "CRITICAL": 3}

CUT_REASON_TEXT = {
    0: "未知原因",
    1: "台面超温（下位机本地规则）",
    2: "烟雾超标（下位机本地规则）",
    3: "上位机失联兜底（下位机看门狗）",
    4: "上位机联合决策",
    5: "现场按键断电",
}


class SafetyStateMachine(QObject):
    """跨模态边缘状态机：联合宏观监控、微观监控与环境遥测进行安全决策"""

    # 推送结构化告警（只在事件开始或断电动作发生时推送，不会每帧重复）
    alert_triggered = Signal(dict)
    # 综合安全等级切换（NORMAL / WARNING / CRITICAL）
    state_changed = Signal(str)

    # 兼容旧代码的阈值常量
    HIGH_TEMP_THRESHOLD = float(cfg("rules.overtemp_cut_c", 55.0))
    HIGH_HUMI_THRESHOLD = float(cfg("rules.humidity_high", 80.0))

    # 可以加热的器皿（与 chem_best.pt 的类别名对应，小写比较）
    HEATABLE_VESSELS = {
        "beaker", "conical flask", "flat bottom flask", "round bottom flask",
        "pear shaped flask", "test tube",
    }
    # 规范上禁止直接加热的量器 / 容器
    NON_HEATABLE_VESSELS = {
        "volumetric flask", "measuring cylinder", "reagent bottle", "burette",
        "pipette", "wash bottle",
    }
    # 兼容旧接口名
    DEFAULT_HEATING_KEYWORDS = HEATABLE_VESSELS

    HAZARD_KINDS = (
        "overtemp", "temp_rate", "unattended_heating",
        "smoke", "humidity_high", "ambient_high", "non_heatable_heating", "overtemp_predict",
        "env_sensor_fault",
    )

    def __init__(self, serial_controller=None, parent=None):
        super().__init__(parent)
        self.serial_controller = None
        self.heating_keywords = set(self.HEATABLE_VESSELS)

        self.current_state = "NORMAL"
        self.latched = False
        self.heating = False
        self.latch_reason = ""
        self.latch_since = 0.0
        self.last_power_off_time = 0.0
        self.power_off_cooldown = 3.0
        self.last_alert_time: Dict[str, float] = {}

        self._unattended_heat_since: Optional[float] = None
        self._hazard_clear_since: Optional[float] = None
        self._last_tel_ts = 0.0
        self._prev_hw_latched: Optional[bool] = None
        self._field_reset_flag = False
        self._listener_hooked = set()
        # 器皿识别结果会逐帧跳动：最近 ITEM_HOLD_S 秒内出现过就算"在台面上"，避免规则反复触发 / 解除
        self._item_seen: Dict[str, float] = {}
        # 台面温度趋势模型：预测温度走势与超温 ETA（只用于提醒与展示，不参与断电）
        self.world_model = ThermalWorldModel()

        self.set_serial_controller(serial_controller)

    # ------------------------------------------------------------------
    # 下位机挂载
    # ------------------------------------------------------------------
    def set_serial_controller(self, serial_controller):
        self.serial_controller = serial_controller
        if serial_controller is not None and hasattr(serial_controller, "add_listener"):
            if id(serial_controller) not in self._listener_hooked:
                serial_controller.add_listener(self._on_serial_event)
                self._listener_hooked.add(id(serial_controller))

    def _on_serial_event(self, kind: str, info: dict):
        """串口线程回调：只记录日志、设置标志，界面相关动作留给 evaluate()（主线程）处理"""
        if kind == "power_off_acked":
            events.log("断电已确认", "下位机已执行断电，继电器已断开", level="CRITICAL", kind="power_off_ack")
        elif kind == "power_off_failed":
            events.log("断电指令未确认", f"{info.get('reason', '')}，请立即人工切断加热电源！",
                       level="CRITICAL", kind="power_off_fail")
        elif kind == "mcu_event":
            code = info.get("code")
            level = "CRITICAL" if code in (1, 2, 3) else "WARNING" if code == 8 else "INFO"
            events.log("下位机上报", info.get("desc", ""), level=level, kind="mcu_event")
            if code == 5:
                self._field_reset_flag = True
        elif kind == "link_up":
            events.log("下位机已连接", info.get("port", ""), kind="link")
        elif kind == "link_lost":
            events.log("下位机连接断开", info.get("reason", ""), level="WARNING", kind="link")

    def _hw(self) -> Optional[dict]:
        link = self.serial_controller
        if link is not None and getattr(link, "is_alive", False):
            return link.get_sensor_data()
        return None

    # ------------------------------------------------------------------
    # 辅助判断
    # ------------------------------------------------------------------
    def is_heating_device_detected(self, micro_detections: List[str]) -> bool:
        """兼容旧接口：台面上是否有可加热器皿"""
        return bool(self._match(micro_detections, self.heating_keywords))

    @staticmethod
    def _match(items: List[str], names) -> List[str]:
        found = set()
        for item in items or []:
            low = str(item).strip().lower()
            if low in names:
                found.add(str(item))
        return sorted(found)

    # ------------------------------------------------------------------
    # 主评估入口（接口保持不变）
    # ------------------------------------------------------------------
    def evaluate(
        self,
        micro_detections: List[str],
        macro_unattended: bool,
        current_temp: float,
        current_humi: float,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        now = time.time()
        extra = extra_context or {}
        rules = lambda k, d: float(cfg(f"rules.{k}", d))

        snap = telemetry.snapshot()
        smoke = extra.get("smoke", snap.get("smoke"))
        # 台面温度（SHT30）是唯一的温度来源；只在遥测真正更新时喂给趋势模型
        if current_temp is not None and snap.get("ts", 0) != self._last_tel_ts:
            self._last_tel_ts = snap.get("ts", 0)
            wm = self.world_model.update(float(current_temp), now, bool(macro_unattended))
        elif current_temp is None:
            wm = self.world_model.update(None, now)
        else:
            wm = self.world_model.snapshot()

        for item in micro_detections or []:
            self._item_seen[str(item)] = now
        hold = float(cfg("rules.item_hold_s", 3.0))
        recent_items = [k for k, t in self._item_seen.items() if now - t <= hold]
        heatable = self._match(recent_items, self.heating_keywords)
        non_heatable = self._match(recent_items, self.NON_HEATABLE_VESSELS)
        hw = self._hw()
        # 接着下位机：继电器闭合 = 加热片有电 = 正在加热（断电后自然不算）；
        # 没接下位机（演示 / 模拟）：台面温度达到 heating_on_c 视为正在加热
        if hw is not None:
            heating = bool(hw.get("relay_on"))
        else:
            heating = current_temp is not None and current_temp >= rules("heating_on_c", 35.0)
        self.heating = heating   # 供交叉验证读取

        hazards: Dict[str, Dict[str, Any]] = {}

        def add(kind, level, title, message, cut=False, event_type=None):
            hazards[kind] = {"kind": kind, "level": level, "title": title, "message": message,
                             "cut": cut, "event_type": event_type or kind.upper()}

        # R1 台面超温
        cut_c = rules("overtemp_cut_c", 55.0)
        if current_temp is not None and current_temp >= cut_c:
            add("overtemp", "CRITICAL", "台面温度超限",
                f"台面温度 {current_temp:.1f}℃ ≥ {cut_c:.0f}℃，加热器附近温度异常，立即断电",
                cut=True, event_type="HIGH_RISK_OVERTEMP")

        # R2 升温过快（趋势模型最近 60 秒的直线斜率）
        rate = wm.get("slope_per_min")
        rate_warn = rules("rate_c_per_min", 3.0)
        if heating and rate is not None and rate >= rate_warn and "overtemp" not in hazards:
            add("temp_rate", "WARNING", "台面升温过快",
                f"台面温度 {current_temp:.1f}℃，最近 1 分钟升温 {rate:.1f}℃（≥ {rate_warn:.1f}℃/min），请检查加热功率")

        # R9 预测超温（趋势模型）：只提醒，不断电
        eta = wm.get("eta_s")
        eta_warn = rules("predict_eta_warn_s", 90.0)
        if (current_temp is not None and "overtemp" not in hazards and eta is not None
                and 0 < eta <= eta_warn and wm.get("phase") == "heating"):
            add("overtemp_predict", "WARNING", "预测即将超温",
                f"台面温度 {current_temp:.1f}℃，正以 {wm.get('slope_per_min') or 0:.1f}℃/min 上升，"
                f"预计约 {eta:.0f} 秒后达到断电线 {cut_c:.0f}℃，请降低功率或关闭加热")

        # R3 加热中无人值守
        cut_s = rules("unattended_heating_cut_s", 60.0)
        if heating and macro_unattended:
            if self._unattended_heat_since is None:
                self._unattended_heat_since = now
            dur = now - self._unattended_heat_since
            if dur >= cut_s:
                add("unattended_heating", "CRITICAL", "加热中无人值守超时",
                    f"人员离开已 {dur:.0f} 秒，加热仍在进行，执行断电", cut=True)
            else:
                add("unattended_heating", "WARNING", "加热中无人值守",
                    f"加热中人员已离开，{cut_s - dur:.0f} 秒后将自动断电")
        else:
            self._unattended_heat_since = None

        # R5 烟雾
        smoke_raw = rules("smoke_raw", 1800)
        if smoke is not None and smoke >= smoke_raw:
            add("smoke", "CRITICAL", "烟雾 / 可燃气体超标", f"MQ-2 读数 {smoke} ≥ {smoke_raw:.0f}，立即断电", cut=True)

        # R6 高湿
        humi_high = rules("humidity_high", 80.0)
        if current_humi is not None and current_humi > humi_high:
            add("humidity_high", "WARNING", "高湿受潮环境告警",
                f"湿度 {current_humi:.1f}% > {humi_high:.0f}%，仪器与试剂有受潮风险，请开启除湿",
                event_type="ENV_ALERT_HUMIDITY")

        # R7 环境高温
        amb_high = rules("ambient_high_c", 40.0)
        if current_temp is not None and current_temp > amb_high:
            add("ambient_high", "WARNING", "台面温度偏高",
                f"台面温度 {current_temp:.1f}℃ > {amb_high:.0f}℃，请检查加热器与通风")

        # R8 量器加热
        if heating and non_heatable:
            add("non_heatable_heating", "NOTICE", "加热中台面出现量器",
                f"检测到 {', '.join(non_heatable)}：量器不可直接加热，请确认")

        # 温湿度传感器无数据：如实提醒，不再拿旧数值做判断
        if hw is not None and (current_temp is None or current_humi is None):
            add("env_sensor_fault", "WARNING", "温湿度传感器无数据",
                "控制盒未读到 SHT30 温湿度，温度与高湿规则暂停判断，请检查接线")

        # ---------------- 断电与锁定 ----------------
        new_alert: Optional[Dict[str, Any]] = None
        cut_hazards = [h for h in hazards.values() if h["cut"]]

        # 现场复位（下位机上报复位事件，或硬件锁定由 True 变为 False）
        hw_latched = hw.get("latched") if hw else None
        field_reset = self._field_reset_flag or (self._prev_hw_latched is True and hw_latched is False)
        self._field_reset_flag = False
        if hw is not None:
            self._prev_hw_latched = hw_latched
        if field_reset and self.latched:
            self._release_latch("现场已按下复位键，解除断电锁定，恢复供电")

        # 下位机自主断电（本地超温 / 烟雾 / 看门狗）→ 同步锁定
        if hw is not None and hw_latched and not self.latched:
            reason = CUT_REASON_TEXT.get(hw.get("cut_reason", 0), "未知原因")
            self._set_latch(f"下位机已自主断电：{reason}")
            new_alert = self._make_alert("CRITICAL", "MCU_LOCAL_POWER_OFF", "下位机自主断电",
                                         f"{reason}。继电器已断开，需现场复位", current_temp, current_humi)

        if cut_hazards:
            top = cut_hazards[0]
            need_send = (not self.latched) or (
                (hw is None or not hw_latched) and now - self.last_power_off_time > self.power_off_cooldown)
            if need_send:
                first_time = not self.latched
                self.last_power_off_time = now
                ok, action_msg = self._execute_power_off()
                if first_time:
                    self._set_latch(top["title"])
                    level = "CRITICAL"
                    events.log("执行断电", action_msg, level=level, kind="power_off", snapshot=True)
                    new_alert = self._make_alert(level, top["event_type"], top["title"],
                                                 f"{top['message']}。{action_msg}",
                                                 current_temp, current_humi,
                                                 micro_detections, macro_unattended, ok)
            self._hazard_clear_since = None
        elif self.latched:
            # 无下位机时（演示模式），危险解除一段时间后自动解锁
            if hw is None:
                if self._hazard_clear_since is None:
                    self._hazard_clear_since = now
                elif now - self._hazard_clear_since >= rules("sim_latch_release_s", 10.0):
                    self._release_latch("（未接入下位机）危险已解除，软件锁定自动解除；现场继电器状态以控制盒为准")

        # ---------------- 事件上报 ----------------
        for kind in self.HAZARD_KINDS:
            h = hazards.get(kind)
            if h is None:
                events.update(kind, False)
                continue
            started = events.update(kind, True, h["level"], h["title"], h["message"],
                                    details={"temp": current_temp, "humi": current_humi,
                                             "vessels": list(micro_detections or []), "unattended": macro_unattended,
                                             "eta_s": wm.get("eta_s"), "phase": wm.get("phase"),
                                             "risk": wm.get("risk")})
            if started and not h["cut"] and new_alert is None:
                new_alert = self._make_alert(h["level"], h["event_type"], h["title"], h["message"],
                                             current_temp, current_humi)
        events.update("power_latched", self.latched, "CRITICAL", "断电锁定中",
                      f"原因：{self.latch_reason}。需现场按复位键恢复供电", snapshot=False)

        # ---------------- 综合状态 ----------------
        if self.latched or any(h["level"] == "CRITICAL" for h in hazards.values()):
            new_state = "CRITICAL"
        elif any(h["level"] == "WARNING" for h in hazards.values()):
            new_state = "WARNING"
        else:
            new_state = "NORMAL"
        if new_state != self.current_state:
            self.current_state = new_state
            self.state_changed.emit(new_state)

        if new_alert is not None:
            self.last_alert_time[new_alert["event_type"]] = now
            self.alert_triggered.emit(new_alert)

        # 判断完整跑完才喂心跳：主线程卡死或这里之前抛异常，心跳就会停，下位机看门狗接管
        if self.serial_controller is not None and hasattr(self.serial_controller, "feed"):
            self.serial_controller.feed()

        top_alert = new_alert
        if top_alert is None and hazards:
            h = max(hazards.values(), key=lambda x: LEVEL_RANK[x["level"]])
            top_alert = self._make_alert(h["level"], h["event_type"], h["title"], h["message"],
                                         current_temp, current_humi)
        return self.current_state, top_alert

    # ------------------------------------------------------------------
    def _make_alert(self, level, event_type, title, message, temp, humi,
                    micro=None, unattended=None, power_off_sent=None) -> Dict[str, Any]:
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event_type": event_type,
            "level": level,
            "title": title,
            "message": message,
            "details": {
                "temperature": temp, "humidity": humi,
                "micro_detections": list(micro or []), "macro_unattended": unattended,
                "power_off_sent": power_off_sent, "latched": self.latched,
            },
        }

    def _set_latch(self, reason: str):
        self.latched = True
        self.latch_reason = reason
        self.latch_since = time.time()
        self._hazard_clear_since = None

    def _release_latch(self, msg: str):
        self.latched = False
        self.latch_reason = ""
        self._hazard_clear_since = None
        events.log("解除断电锁定", msg, kind="power_reset")

    def _execute_power_off(self) -> Tuple[bool, str]:
        """向下位机下发断电指令；返回 (是否成功下发, 如实描述)"""
        link = self.serial_controller
        if link is None or not hasattr(link, "send_power_off"):
            return False, "未挂载下位机，已在软件中锁定（演示模式）"
        try:
            ok = link.send_power_off()
        except Exception as e:
            return False, f"断电指令下发异常：{e}，请立即人工切断加热电源！"
        if ok is False:
            if getattr(link, "is_open", False) is False and telemetry.get("source") != "hardware":
                return False, "未接入下位机（演示模式），已在软件中模拟断电锁定"
            return False, "串口未连接，断电指令无法下发！请立即人工切断加热电源（下位机本地保护仍独立生效）"
        return True, "断电指令已下发，等待下位机确认"

    def manual_power_off(self, source: str = "人工") -> str:
        """人工一键断电（小屏长按 / 总后台）。只能断电；恢复供电仍需现场按复位键"""
        ok, action_msg = self._execute_power_off()
        self.last_power_off_time = time.time()
        if not self.latched:
            self._set_latch(f"人工一键断电（{source}）")
        events.log("人工一键断电", f"来源：{source}。{action_msg}", level="CRITICAL", kind="manual_power_off",
                   snapshot=True)
        if self.current_state != "CRITICAL":
            self.current_state = "CRITICAL"
            self.state_changed.emit("CRITICAL")
        return action_msg

    def reset(self):
        """软件复位（仅清除软件状态；若下位机已锁定，仍需现场复位）"""
        self.latched = False
        self.latch_reason = ""
        self._unattended_heat_since = None
        self._hazard_clear_since = None
        self.last_alert_time.clear()
        self.current_state = "NORMAL"
        self.state_changed.emit("NORMAL")
