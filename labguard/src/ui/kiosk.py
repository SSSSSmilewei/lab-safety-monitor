"""
实验台小屏 Kiosk 界面（4–7 寸触摸屏，香橙派本机运行）
src/ui/kiosk.py

定位：面向正在做实验的同学，"自我管理"——一眼看清自己现在的风险、该做什么，主动规避危险。
  · 一眼看懂：顶栏状态（颜色 + √/▲/■ 形状 + 文字三重编码）；守护页左侧「待处理事项」直接给出动作
    （来自交叉验证的每条依据，例如"佩戴护目镜""移出量器，改用烧杯加热"）；中间热源大数字与干烧预测；右侧防护装备与环境；
  · 戴手套也能点：按钮 ≥ 64px（800×480 基准），只有 3 个页签 + 3 个常驻操作；
  · 紧急时整屏接管：断电锁定后红色全屏提示恢复步骤（排查后按控制盒复位键）；
  · 分辨率自适应：以 800×480 为设计基准按短边等比缩放（480×320 ~ 1024×600），竖屏自动改为上下布局；
    config.yaml → ui.kiosk_size: [宽, 高] 可手动指定（PC 调试时常用）。
  · 性能：无动画；画面页不可见时不转换图像；状态 2 Hz 刷新。
风格：ui.style = standard（默认，墨色硬边 + 得意黑标题 + 等宽数字，与总后台一致）/ pixel（旧版 Zpix 像素风格）。
"""
import socket
import time
from collections import deque
from typing import Optional

import cv2

try:
    from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
                                   QStackedWidget, QScrollArea, QFrame, QApplication, QSizePolicy)
    from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QPolygonF
except ImportError:
    from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
                                 QStackedWidget, QScrollArea, QFrame, QApplication, QSizePolicy)
    from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QPolygonF

from src.config import cfg
from src.core.events import events
from src.ui import main_window as mw
from src.ui.main_window import T, STATE_ICON, ink_on, Card, Chip, get_qss

STATE_COLOR = {"NORMAL": T.SAFE, "WARNING": T.WARN, "CRITICAL": T.DANGER}
STATE_SOFT = {"NORMAL": T.PAPER, "WARNING": T.WARN_SOFT, "CRITICAL": T.DANGER_SOFT}
STATE_WORD = {"NORMAL": "安全", "WARNING": "警告", "CRITICAL": "危险"}
LEVEL_TAG = {"NOTICE": "提醒", "WARNING": "▲ 警告", "CRITICAL": "■ 紧急", "INFO": "信息"}
RISK_COLOR = {"low": T.SAFE, "mid": T.WARN, "high": T.DANGER}
PO_TEXT = {"pending": "断电指令已下发，等待下位机确认", "acked": "下位机已确认断电，继电器已断开",
           "failed_no_link": "串口未连接 —— 请立即人工切断加热电源！",
           "failed_no_ack": "下位机未应答 —— 请立即人工切断加热电源！"}


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def todo_items(s: dict, limit: int = 3) -> list:
    """守护页「待处理事项」：交叉验证依据里的处置动作（按分值从高到低去重）；没有时退回活动事件标题"""
    out, seen = [], set()
    for f in sorted((s.get("risk") or {}).get("factors") or [], key=lambda f: -f.get("points", 0)):
        act = (f.get("action") or "").strip()
        if act and act not in seen:
            seen.add(act)
            out.append((act, f.get("text", "")))
    if not out:
        for e in s.get("active_events") or []:
            if e.get("level") in ("WARNING", "CRITICAL") and e.get("title") not in seen:
                seen.add(e["title"])
                out.append((e["title"], e.get("message", "")))
    return out[:limit]


class Spark(QWidget):
    """热源温度迷你曲线：实测（实线）+ 世界模型预测（虚线）+ 干烧阈值（红虚线）"""

    def __init__(self, line_color=T.PRIMARY, parent=None):
        super().__init__(parent)
        self.hist = deque(maxlen=120)
        self.forecast = []
        self.threshold = 120.0
        self.line_color = line_color

    def set_data(self, temp, forecast, threshold):
        if temp is None:
            self.hist.clear()
        else:
            self.hist.append(float(temp))
        self.forecast = [p[1] for p in (forecast or [])]
        self.threshold = float(threshold)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        vals = list(self.hist) + self.forecast + [self.threshold, 20.0]
        lo, hi = min(vals) - 5, max(vals) + 5
        y = lambda v: 3 + (h - 6) * (1 - (v - lo) / (hi - lo or 1))
        pen = QPen(QColor(T.DANGER), 1, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawLine(0, int(y(self.threshold)), w, int(y(self.threshold)))
        split = w * 0.72

        def poly(data, x0, x1, dash):
            if len(data) < 2:
                return
            pts = QPolygonF([QPointF(x0 + i * (x1 - x0) / (len(data) - 1), y(v)) for i, v in enumerate(data)])
            p.setPen(QPen(QColor(self.line_color), 2, Qt.PenStyle.DashLine if dash else Qt.PenStyle.SolidLine))
            p.drawPolyline(pts)

        poly(list(self.hist), 0, split, False)
        if self.hist:
            poly(self.forecast, split, w, True)
        p.end()


class HoldButton(QPushButton):
    """长按确认按钮：按住 hold_s 秒才触发，防误触"""

    def __init__(self, text, hold_s, on_fire, parent=None):
        super().__init__(text, parent)
        self._text, self._hold, self._fire = text, hold_s, on_fire
        self._t0 = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.pressed.connect(self._start)
        self.released.connect(self._cancel)

    def _start(self):
        self._t0 = time.time()
        self._timer.start(100)

    def _cancel(self):
        self._timer.stop()
        self._t0 = None
        self.setText(self._text)

    def _tick(self):
        if self._t0 is None:
            return
        left = self._hold - (time.time() - self._t0)
        if left <= 0:
            self._timer.stop()
            self._t0 = None
            self.setText(self._text)
            self._fire()
        else:
            self.setText(f"继续按住 {left:.1f}s")


class KioskWindow(QWidget):
    def __init__(self, engine, fullscreen: bool = True):
        super().__init__()
        self.engine = engine
        self.setWindowTitle("实验台安全终端")
        # ---- 风格：standard（默认）/ pixel（旧版） ----
        self.pixel = str(cfg("ui.style", "standard")).lower() == "pixel"
        self.LINE = T.PRIMARY if self.pixel else "#1A1F3D"      # 描边与硬阴影
        self.INK = T.INK if self.pixel else "#1A1F3D"            # 正文
        self.DIM = T.DIM if self.pixel else "#4B5394"            # 次要文字
        if not self.pixel:
            mw.load_ui_fonts()
        size = cfg("ui.kiosk_size", None)
        screen = QApplication.primaryScreen()
        if size and len(size) == 2:
            W, H = int(size[0]), int(size[1])
        elif fullscreen and screen is not None:
            g = screen.geometry()
            W, H = g.width(), g.height()
        else:
            W, H = 800, 480
        self.portrait = H > W
        base_w, base_h = (480, 800) if self.portrait else (800, 480)
        self.k = max(0.6, min(W / base_w, H / base_h))
        qss = get_qss() if self.pixel else mw.get_qss_standard(self.LINE, self.INK)
        self.setStyleSheet(qss + f"QWidget#kiosk {{ background: {T.BG}; }}")
        self.setObjectName("kiosk")
        self._show_page = 0
        self._cam = "pano"
        self._last_frame_ts = 0.0
        self._overlay_snooze = 0.0
        self._ev_key = None
        self._todo_key = None
        self._build()
        self.engine.frames_ready.connect(self._on_frames)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(500)
        if fullscreen and not size:
            self.showFullScreen()
            self.setCursor(Qt.CursorShape.BlankCursor) if cfg("ui.kiosk_hide_cursor", True) else None
        else:
            self.resize(W, H)
            self.show()
        self.refresh()

    # ------------------------------------------------------------------
    def px(self, n) -> int:
        return max(1, int(n * self.k))

    def _font(self, kind: str) -> str:
        """kind: hd 标题 / num 数字 / body 正文 → 样式表里的 font-family 片段（像素风格统一用全局字体）"""
        if self.pixel:
            return ""
        fam = {"hd": f"'{mw.HD_FONT_FAMILY}', {mw.BODY_FONTS}", "num": f"'{mw.NUM_FONT_FAMILY}', monospace"}.get(kind)
        return f" font-family: {fam};" if fam else ""

    def _lbl(self, text="", size=16, color=None, kind="body"):
        l = QLabel(text)
        l._kind = kind
        l.setStyleSheet(f"color: {color or self.INK}; font-size: {self.px(size)}px; background: transparent;{self._font(kind)}")
        return l

    def _restyle(self, lbl, size, color, extra=""):
        lbl.setStyleSheet(f"color: {color}; font-size: {self.px(size)}px; background: transparent;"
                          f"{self._font(getattr(lbl, '_kind', 'body'))}{extra}")

    def _card(self, **kw):
        kw.setdefault("border", self.LINE)
        kw.setdefault("shadow", self.LINE)
        kw.setdefault("border_w", 2 if self.pixel else 3)
        return Card(**kw)

    def _header(self, text, bg=None, fg=T.PAPER, size=15):
        """卡片标题条：标准风格底边加 3px 墨色分隔"""
        hdr = QWidget()
        hdr.setObjectName("cardhdr")
        bottom = "" if self.pixel else f" border-bottom: {self.px(3)}px solid {self.LINE};"
        hdr.setStyleSheet(f"QWidget#cardhdr {{ background: {bg or T.PRIMARY};{bottom} }}")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(self.px(10), self.px(4), self.px(8), self.px(4))
        title = self._lbl(text, size, fg, "hd")
        hl.addWidget(title, 1)
        hdr._layout, hdr._title = hl, title
        return hdr

    def _btn(self, text, size=18, h=64):
        b = QPushButton(text)
        b.setMinimumHeight(self.px(h))
        b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        b.setStyleSheet(f"font-size: {self.px(size)}px;")
        return b

    def _build(self):
        root = QVBoxLayout(self)
        m = self.px(8)
        root.setContentsMargins(m, m, m, m)
        root.setSpacing(self.px(8))

        # ---- 顶栏 ----
        self.top = self._card(offset=self.px(4), padding=(0, 0, 0, 0))
        tl = QHBoxLayout()
        tl.setContentsMargins(0, 0, self.px(8), 0)
        tl.setSpacing(self.px(10))
        self.badge = QLabel("√ SAFE")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setMinimumWidth(self.px(150))
        self.badge.setMinimumHeight(self.px(52))
        self.state_lbl = self._lbl("正常守护中", 20, kind="hd")
        self.state_sub = self._lbl("", 12, self.DIM)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(self.state_lbl)
        col.addWidget(self.state_sub)
        self.links = self._lbl("", 12, self.DIM)
        self.clock = self._lbl("", 18, kind="num")
        self.btn_set = QPushButton("设置")
        self.btn_set.setFixedSize(self.px(72), self.px(52))
        self.btn_set.setStyleSheet(f"font-size: {self.px(16)}px; padding: 0;")
        self.btn_set.clicked.connect(lambda: self._goto(3))
        tl.addWidget(self.badge)
        tl.addLayout(col, 1)
        tl.addWidget(self.links)
        tl.addWidget(self.clock)
        tl.addWidget(self.btn_set)
        self.top.body.addLayout(tl)
        root.addWidget(self.top)

        # ---- 页面 ----
        self.stack = QStackedWidget()
        self.stack.addWidget(self._page_guard())
        self.stack.addWidget(self._page_cam())
        self.stack.addWidget(self._page_events())
        self.stack.addWidget(self._page_settings())
        root.addWidget(self.stack, 1)

        # ---- 底栏：3 个页签 + 3 个常驻操作 ----
        bar = QHBoxLayout() if not self.portrait else QGridLayout()
        self.tab_btns = []
        for i, name in enumerate(["状态", "画面", "记录"]):
            b = self._btn(name)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, i=i: self._goto(i))
            self.tab_btns.append(b)
        self.btn_mute = self._btn("静音 60s", 16)
        self.btn_mute.clicked.connect(lambda: self.engine.mute(60))
        self.btn_call = self._btn("呼叫教师", 16)
        self.btn_call.clicked.connect(self._call)
        self.btn_cut = HoldButton("长按 2s 断电", 2.0, lambda: self.engine.cut_power("实验台小屏"))
        self.btn_cut.setMinimumHeight(self.px(64))
        self.btn_cut.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_cut.setStyleSheet(f"QPushButton {{ font-size: {self.px(16)}px; background: {T.DANGER}; color: {T.PAPER};"
                                   f" border: 2px solid {T.DANGER_DEEP if self.pixel else self.LINE}; }}")
        items = self.tab_btns + [self.btn_mute, self.btn_call, self.btn_cut]
        if self.portrait:
            for i, b in enumerate(items):
                bar.addWidget(b, i // 3, i % 3)
        else:
            for b in items:
                bar.addWidget(b)
        bar.setSpacing(self.px(6))
        root.addLayout(bar)
        self._goto(0)

        # ---- 紧急整屏接管 ----
        self.overlay = QFrame(self)
        self.overlay.setStyleSheet(f"QFrame {{ background: {T.DANGER}; }} QLabel {{ color: {T.PAPER}; background: transparent; }}")
        ol = QVBoxLayout(self.overlay)
        ol.setContentsMargins(self.px(24), self.px(20), self.px(24), self.px(20))
        ol.setSpacing(self.px(10))
        self.ov_title = self._lbl("■ 加热电源已切断", 40, T.PAPER, "hd")
        self.ov_reason = self._lbl("", 20, T.PAPER)
        self.ov_reason.setWordWrap(True)
        self.ov_po = self._lbl("", 16, T.PAPER)
        self.ov_po.setWordWrap(True)
        self.ov_ai = self._lbl("", 14, T.PAPER)
        self.ov_ai.setWordWrap(True)
        self.ov_hint = self._lbl("恢复步骤：① 回到实验台，勿触碰受热器皿　② 确认器皿与液面状态，待温度回落\n"
                                 "③ 长按控制盒复位键，控制盒复检温度与烟雾后通电（软件与远程均不可恢复供电）", 17, T.PAPER)
        self.ov_hint.setWordWrap(True)
        row = QHBoxLayout()
        b1 = self._btn("静音 30s", 18)
        b1.clicked.connect(lambda: self.engine.mute(30))
        b2 = self._btn("查看详情（30 秒）", 18)
        b2.clicked.connect(self._snooze_overlay)
        for b in (b1, b2):
            b.setStyleSheet(f"QPushButton {{ font-size: {self.px(18)}px; background: {T.PAPER}; color: {T.DANGER_DEEP if self.pixel else self.LINE};"
                            f" border: 3px solid {T.DANGER_DEEP if self.pixel else self.LINE}; }}")
            row.addWidget(b)
        for w in (self.ov_title, self.ov_reason, self.ov_po, self.ov_ai):
            ol.addWidget(w)
        ol.addStretch(1)
        ol.addWidget(self.ov_hint)
        ol.addLayout(row)
        self.overlay.hide()

    def _page_guard(self):
        page = QWidget()
        lay = QHBoxLayout(page) if not self.portrait else QVBoxLayout(page)
        lay.setContentsMargins(0, 0, self.px(4), self.px(4))
        lay.setSpacing(self.px(10))

        # 左：待处理事项（交叉验证 → 同学能直接做的动作）
        self.todo = self._card(offset=self.px(4), padding=(0, 0, 0, 0))
        self.todo.body.setSpacing(0)
        self.todo_hdr = self._header("待处理事项", T.SAFE)
        self.todo_count = self._lbl("", 15, T.PAPER, "num")
        self.todo_hdr._layout.addWidget(self.todo_count)
        self.todo.body.addWidget(self.todo_hdr)
        self.todo_rows = []
        for i in range(3):
            w = QWidget()
            w.setObjectName("todorow")
            hl = QHBoxLayout(w)
            hl.setContentsMargins(self.px(10), self.px(6), self.px(8), self.px(6))
            hl.setSpacing(self.px(8))
            num = QLabel(str(i + 1))
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num.setFixedSize(self.px(26), self.px(26))
            num.setStyleSheet(f"background: {self.LINE}; color: {T.PAPER}; font-size: {self.px(15)}px;{self._font('num')}")
            col = QVBoxLayout()
            col.setSpacing(0)
            act = self._lbl("", 18, kind="hd")
            act.setWordWrap(True)
            why = self._lbl("", 12, self.DIM)
            why.setWordWrap(True)
            col.addWidget(act)
            col.addWidget(why)
            hl.addWidget(num, 0, Qt.AlignmentFlag.AlignTop)
            hl.addLayout(col, 1)
            w.setStyleSheet(f"QWidget#todorow {{ border-bottom: 2px solid {self.LINE}; }}")
            self.todo.body.addWidget(w)
            self.todo_rows.append((w, act, why))
        self.todo_empty = self._lbl("√ 当前无待处理事项", 16, T.SAFE, "hd")
        self.todo_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.todo_empty.setMinimumHeight(self.px(60))
        self.todo.body.addWidget(self.todo_empty)
        self.todo.body.addStretch(1)
        self.todo_foot = self._lbl("", 12, self.INK)
        self.todo_foot.setWordWrap(True)
        self.todo_foot.setContentsMargins(self.px(10), self.px(4), self.px(8), self.px(6))
        self.todo.body.addWidget(self.todo_foot)
        lay.addWidget(self.todo, 3)

        # 中：热源温度
        self.heat = self._card(offset=self.px(4), padding=(self.px(12), self.px(8), self.px(12), self.px(8)))
        self.heat.body.setSpacing(self.px(2))
        self.heat_hdr = self._lbl("热源表面温度", 13, self.DIM)
        vrow = QHBoxLayout()
        self.heat_val = self._lbl("--.-", 60, kind="num")
        self.heat_unit = self._lbl("℃", 22)
        self.heat_tag = Chip("未接入", self.INK, T.PRIMARY_SOFT, size=self.px(14))
        vrow.addWidget(self.heat_val)
        vrow.addWidget(self.heat_unit, 0, Qt.AlignmentFlag.AlignBottom)
        vrow.addStretch(1)
        self.spark = Spark(T.PRIMARY if self.pixel else "#3949AB")
        self.spark.setMinimumHeight(self.px(56))
        self.heat_eta = self._lbl("—", 15)
        self.heat_eta.setWordWrap(True)
        self.heat.body.addWidget(self.heat_hdr)
        self.heat.body.addLayout(vrow)
        self.heat.body.addWidget(self.heat_tag, 0, Qt.AlignmentFlag.AlignLeft)
        self.heat.body.addWidget(self.spark, 1)
        self.heat.body.addWidget(self.heat_eta)
        lay.addWidget(self.heat, 3)

        # 右：防护装备 + 环境
        right = QVBoxLayout()
        right.setSpacing(self.px(8))
        ppe_card = self._card(offset=self.px(4), padding=(self.px(8), self.px(6), self.px(8), self.px(6)))
        self.presence = self._lbl("人员：—", 15, kind="hd")
        ppe_card.body.addWidget(self.presence)
        grid = QGridLayout()
        grid.setSpacing(self.px(6))
        self.ppe_lbls = []
        for i in range(4):
            l = QLabel("")
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setMinimumHeight(self.px(36))
            grid.addWidget(l, i // 2, i % 2)
            self.ppe_lbls.append(l)
        ppe_card.body.addLayout(grid)
        right.addWidget(ppe_card, 3)

        env = self._card(offset=self.px(4), padding=(self.px(10), self.px(6), self.px(10), self.px(6)))
        self.env_lbl = self._lbl("环境 --℃\n湿度 --%\n烟雾 --", 14, kind="num")
        self.env_lbl.setWordWrap(True)
        self.act_lbl = self._lbl("排风 — · 加湿 —", 12, self.DIM)
        env.body.addWidget(self.env_lbl)
        env.body.addWidget(self.act_lbl)
        right.addWidget(env, 2)
        lay.addLayout(right, 2)
        return page

    def _page_cam(self):
        page = self._card(offset=self.px(4), padding=(0, 0, 0, 0))
        page.body.setSpacing(0)
        hdr = self._header("全景 · 人员模型（点画面切换）")
        self.cam_title = hdr._title
        self.cam_chip = Chip("等待画面", T.PRIMARY, T.PAPER, size=self.px(13))
        hdr._layout.addWidget(self.cam_chip)
        self.cam_view = QLabel("NO SIGNAL")
        self.cam_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cam_view.setStyleSheet(f"background: {T.SCREEN}; color: {T.PRIMARY_MID}; font-size: {self.px(16)}px;")
        self.cam_view.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.cam_view.mousePressEvent = lambda _e: self._toggle_cam()
        page.body.addWidget(hdr)
        page.body.addWidget(self.cam_view, 1)
        return page

    def _page_events(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner.setStyleSheet(f"background: {T.BG};")
        self.ev_lay = QVBoxLayout(inner)
        self.ev_lay.setSpacing(self.px(8))
        self.ev_lay.addStretch(1)
        scroll.setWidget(inner)
        lay.addWidget(scroll)
        return page

    def _page_settings(self):
        page = self._card(offset=self.px(4), padding=(self.px(16), self.px(12), self.px(16), self.px(12)))
        self.set_lbl = self._lbl("", 17)
        self.set_lbl.setWordWrap(True)
        self.set_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        page.body.addWidget(self._lbl("▌本机控制台访问", 18, T.PRIMARY, "hd"))
        page.body.addWidget(self.set_lbl)
        page.body.addStretch(1)
        back = self._btn("返回状态页", 18)
        back.clicked.connect(lambda: self._goto(0))
        page.body.addWidget(back)
        return page

    # ------------------------------------------------------------------
    def _goto(self, i):
        self._show_page = i
        self.stack.setCurrentIndex(i)
        for j, b in enumerate(self.tab_btns):
            b.setChecked(j == i)
        if i == 3:
            from src.web.server import web_token
            port = int(cfg("web.port", 8080))
            self.set_lbl.setText(f"浏览器访问：\nhttp://{_local_ip()}:{port}\n\n口令：{web_token()}\n\n"
                                 f"功能：双路画面、参数配置、台面安全区、安全助手、温度预测、环境控制、事件复核。")

    def _toggle_cam(self):
        self._cam = "desk" if self._cam == "pano" else "pano"
        self.cam_title.setText("台面 · 器皿模型（点画面切换）" if self._cam == "desk" else "全景 · 人员模型（点画面切换）")
        self._last_frame_ts = 0

    def _call(self):
        self.engine.call_admin("实验员")
        self.btn_call.setText("已呼叫 √")
        QTimer.singleShot(5000, lambda: self.btn_call.setText("呼叫教师"))

    def _snooze_overlay(self):
        self._overlay_snooze = time.time() + 30
        self.overlay.hide()

    def resizeEvent(self, e):
        self.overlay.setGeometry(self.rect())
        super().resizeEvent(e)

    def _on_frames(self, pano, desk, *_):
        if self._show_page != 1:
            return
        now = time.time()
        if now - self._last_frame_ts < 0.1:   # 小屏画面 10 fps 足够
            return
        self._last_frame_ts = now
        img = pano if self._cam == "pano" else desk
        if img is None:
            return
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        q = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        pm = QPixmap.fromImage(q).scaled(self.cam_view.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.FastTransformation)
        self.cam_view.setPixmap(pm)

    # ------------------------------------------------------------------
    def refresh(self):
        s = self.engine.snapshot()
        state = s["state"]
        color = STATE_COLOR.get(state, T.SAFE)
        if self.pixel:
            self.badge.setText(f"{STATE_ICON.get(state, '')} {({'NORMAL': 'SAFE'}).get(state, state)}")
        else:
            self.badge.setText(f"{STATE_ICON.get(state, '')} {STATE_WORD.get(state, state)}")
        border = "" if self.pixel else f" border-right: {self.px(3)}px solid {self.LINE};"
        self.badge.setStyleSheet(f"background: {color}; color: {ink_on(color)}; font-size: {self.px(24)}px;"
                                 f"{self._font('hd')}{border}")
        if self.pixel:
            self.top.set_colors(bg=STATE_SOFT.get(state), border=color if state != "NORMAL" else T.PRIMARY,
                                shadow=color if state != "NORMAL" else T.PRIMARY)
        else:
            self.top.set_colors(bg=STATE_SOFT.get(state))
        txt = {"NORMAL": self.INK, "WARNING": T.WARN_TEXT, "CRITICAL": T.DANGER_DEEP}[state]
        self.state_lbl.setText(s["state_text"])
        self._restyle(self.state_lbl, 20, txt)
        act = s["active_events"]
        self.state_sub.setText(" · ".join(e["title"] for e in act[:2]) if act else "无活动告警")
        self._restyle(self.state_sub, 12, txt)
        mcu = "●" if s["link"]["mcu"] else "○"
        cam = "●" if s["vision"]["ok"] else "○"
        self.links.setText(f"{mcu}下位机 {cam}视觉")
        self.clock.setText(time.strftime("%H:%M"))
        mute_left = int(s["mute_until"] - time.time()) if s["mute_until"] else 0
        self.btn_mute.setText(f"静音中 {mute_left}s" if mute_left > 0 else "静音 60s")

        self._refresh_todo(s)
        self._refresh_guard(s)
        if self._show_page == 2:
            self._refresh_events()

        # 紧急整屏接管
        if s["latched"] and time.time() > self._overlay_snooze:
            self.ov_reason.setText(f"原因：{s['latch_reason']}")
            demo = s["telemetry"].get("source") != "hardware" and not s["link"]["mcu"]
            self.ov_po.setText("未接入下位机：软件已模拟断电锁定（演示模式）" if demo
                               else PO_TEXT.get(s["power_off_state"], "断电处理中"))
            self.ov_ai.setText(self._advice(events.history(8, "WARNING")))
            self.overlay.setGeometry(self.rect())
            self.overlay.show()
            self.overlay.raise_()
        elif not s["latched"]:
            self.overlay.hide()

    def _refresh_todo(self, s):
        risk = s.get("risk") or {}
        lv = "high" if s.get("latched") else risk.get("level", "low")
        items = todo_items(s)
        r = s["rules"]
        heating = (s["telemetry"].get("obj_temp") or 0) >= r["heating_on_c"]
        foot = (f"加热中：离岗 {cfg('presence.absent_seconds', 15):.0f} s 判定无人 · "
                f"{r['unattended_heating_cut_s']:.0f} s 后自动断电") if heating else ""
        key = (lv, tuple(items), foot)
        if key == self._todo_key:
            return
        self._todo_key = key
        col = RISK_COLOR.get(lv, T.SAFE)
        fg = ink_on(col)
        bottom = "" if self.pixel else f" border-bottom: {self.px(3)}px solid {self.LINE};"
        self.todo_hdr.setStyleSheet(f"QWidget#cardhdr {{ background: {col};{bottom} }}")
        self._restyle(self.todo_hdr._title, 15, fg)
        self.todo_count.setText(str(len(items)) if items else "")
        self._restyle(self.todo_count, 15, fg)
        for i, (w, act, why) in enumerate(self.todo_rows):
            if i < len(items):
                act.setText(items[i][0])
                why.setText(items[i][1])
                w.show()
            else:
                w.hide()
        self.todo_empty.setVisible(not items)
        self.todo_foot.setText(foot)
        self.todo_foot.setVisible(bool(foot))
        self.todo_foot.setStyleSheet(f"color: {self.INK}; font-size: {self.px(12)}px; background: {T.WARN_SOFT if heating else 'transparent'};")

    def _refresh_guard(self, s):
        t = s["telemetry"]
        wm = s["world_model"]
        r = s["rules"]
        obj = t.get("obj_temp")
        thr = r["dry_burn_c"]
        self.heat_hdr.setText(f"热源温度 · 断电 {thr:.0f}℃")
        self.heat_val.setText("--.-" if obj is None else f"{obj:.1f}")
        lv, tag, eta = "ok", "√ 常温", "未在加热 · 无干烧风险"
        if obj is None:
            tag, eta = "未接入", "未接入热源测温"
        elif obj >= thr:
            lv, tag, eta = "bad", "■ 干烧", "已超过干烧阈值"
        elif obj >= r["heating_on_c"]:
            tag = "▲ " + (wm.get("phase_text") or "加热中")
            if wm.get("eta_s") is not None:
                eta = f"越过沸点仍在升温 · 约 {wm['eta_s']:.0f} 秒后干烧"
                if wm["eta_s"] <= r["predict_eta_warn_s"]:
                    lv = "warn"
            elif wm.get("eta_boil_s") is not None:
                eta = f"预计约 {wm['eta_boil_s']:.0f} 秒后沸腾"
            elif wm.get("phase") == "boiling":
                eta = f"沸腾 {wm['plateau_s']:.0f} 秒 · 请留意液面"
            elif 90 <= obj < 104:
                eta = "接近沸点"
            elif wm.get("t_inf") is not None and wm["t_inf"] < 90:
                eta = f"将稳定在约 {wm['t_inf']:.0f}℃"
            else:
                eta = "温度预测采样中…"
        bg = {"ok": T.PAPER, "warn": T.WARN_SOFT, "bad": T.DANGER_SOFT}[lv]
        if self.pixel:
            border = {"ok": T.PRIMARY, "warn": T.WARN, "bad": T.DANGER}[lv]
            self.heat.set_colors(bg=bg, border=border, shadow=border)
        else:
            self.heat.set_colors(bg=bg)
        if obj is None:
            self.heat_tag.set(tag, self.INK, T.PRIMARY_SOFT, None if self.pixel else self.LINE)
        else:
            tbg = {"ok": T.SAFE_SOFT, "warn": T.WARN, "bad": T.DANGER}[lv]
            self.heat_tag.set(tag, {"ok": T.SAFE, "warn": T.WARN_INK, "bad": T.PAPER}[lv], tbg,
                              None if self.pixel else self.LINE)
        self.heat_eta.setText(eta)
        self._restyle(self.heat_eta, 15, {"ok": self.INK, "warn": T.WARN_TEXT, "bad": T.DANGER_DEEP}[lv])
        self.spark.set_data(obj, wm.get("forecast"), thr)

        v = s["vision"]
        if v["person_present"] is None:
            pres = "人员：画面无效"
        elif v["unattended"]:
            uh = next((e for e in s["active_events"] if e["kind"] == "unattended_heating"), None)
            left = uh["message"].split("，")[-1] if uh and "后将自动断电" in uh["message"] else ""
            pres = "▲ 无人值守" + (f" · {left}" if left else "")
        else:
            pres = "√ 人员在岗"
        self.presence.setText(pres)
        icon = {"ok": "√", "bad": "×", "unknown": "?"}
        for lbl, item in zip(self.ppe_lbls, v["ppe"]):
            st = item["status"]
            if self.pixel:
                fg, bgc, bd = {"ok": (T.SAFE, T.PAPER, T.SAFE), "bad": (T.PAPER, T.DANGER, T.DANGER_DEEP),
                               "unknown": (T.DIM, T.PRIMARY_SOFT, T.PRIMARY_MID)}[st]
            else:
                fg, bgc, bd = {"ok": (self.INK, T.PAPER, self.LINE), "bad": (T.PAPER, T.DANGER, self.LINE),
                               "unknown": (self.DIM, T.PRIMARY_SOFT, self.LINE)}[st]
            lbl.setText(f"{icon[st]} {item['name']}")
            lbl.setStyleSheet(f"color: {fg}; background: {bgc}; border: 2px solid {bd}; font-size: {self.px(15)}px; font-weight: bold;")

        def f(x, d, u):
            return "--" if x is None else f"{x:.{d}f}{u}"
        smoke = t.get("smoke")
        sep = " · " if self.pixel else "\n"     # 像素字体行距紧，沿用旧版单行写法
        self.env_lbl.setText(f"环境 {f(t.get('temp'), 1, '℃')}{sep}湿度 {f(t.get('humi'), 0, '%')}{sep}"
                             f"烟雾 {smoke if smoke is not None else '--'}")
        env = s.get("env") or {}
        if env:
            self.act_lbl.setText(f"排风 {env.get('fan_pwm', 0)}% · 加湿 {'开' if env.get('humid_on') else '关'}"
                                 f" · {'手动' if env.get('mode') == 'manual' else '自动'}")

    @staticmethod
    def _advice(hist) -> str:
        """从事件里取第一条处理建议的"处置"一行"""
        for e in hist:
            note = e.get("agent_note") or ""
            line = next((l for l in note.split("\n") if l.startswith("处置")), "")
            if line:
                return "建议：" + line.split("：", 1)[-1]
        return ""

    def _refresh_events(self):
        hist = [e for e in events.history(10, "NOTICE")]
        key = tuple((e["uid"], bool(e.get("agent_note")), e.get("review")) for e in hist)
        if key == self._ev_key:
            return
        self._ev_key = key
        while self.ev_lay.count() > 1:
            w = self.ev_lay.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        for e in hist:
            color = {"WARNING": T.WARN, "CRITICAL": T.DANGER}.get(e["level"], T.PRIMARY)
            if self.pixel:
                card = Card(offset=self.px(3), border=color, shadow=color,
                            padding=(self.px(10), self.px(6), self.px(10), self.px(6)))
            else:   # 标准风格：墨色描边 + 左侧等级色条
                card = self._card(offset=self.px(3), border_w=2, accent=color,
                                  padding=(self.px(10), self.px(6), self.px(10), self.px(6)))
            card.body.setSpacing(self.px(2))
            card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)   # 卡片多时滚动，而不是被压扁
            head = QHBoxLayout()
            tag = Chip(LEVEL_TAG.get(e["level"], e["level"]), ink_on(color), color,
                       None if self.pixel else self.LINE, size=self.px(13))
            head.addWidget(tag)
            head.addWidget(self._lbl(e["title"], 17, kind="hd"), 1)
            head.addWidget(self._lbl(e["time_str"], 13, self.DIM, "num"))
            card.body.addLayout(head)
            msg = self._lbl(e["message"], 13, self.DIM)
            msg.setWordWrap(True)
            card.body.addWidget(msg)
            note = e.get("agent_note")
            if note:
                ai = self._lbl(self._advice([e]) or ("建议：" + note.split("\n")[0]), 14)
                ai.setWordWrap(True)
                ai.setStyleSheet(ai.styleSheet() + f"background: {T.PRIMARY_SOFT}; padding: 4px;")
                card.body.addWidget(ai)
            # 换行标签在显示前算不出准确高度，这里按字数估算最小高度，卡片多时滚动而不是被压扁
            per_line = max(10, (self.width() - self.px(70)) // self.px(13))
            lines = -(-len(e["message"]) // per_line)
            h = self.px(28) + self.px(34) + lines * self.px(19)
            if note:
                h += -(-len(ai.text()) // max(10, per_line * 13 // 14)) * self.px(21) + self.px(12)
            card.setMinimumHeight(h)
            self.ev_lay.insertWidget(self.ev_lay.count() - 1, card)
