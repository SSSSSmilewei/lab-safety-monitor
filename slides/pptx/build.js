// 生成答辩 PPT：node slides/pptx/build.js  →  slides/实验室安全答辩.pptx
// 内容与 slides/web/index.html 一一对应（8 章 24 页）；照片页为图片占位符，在 PowerPoint 里点图标即可插入。
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.PPTX_SKILL_DIR ? path.join(process.env.PPTX_SKILL_DIR, "scripts/apply_theme.js") : "/mnt/skills/public/pptx/scripts/apply_theme.js");

const OUT = path.join(__dirname, "..", "实验室安全答辩.pptx");
const WEBIMG = (f) => path.join(__dirname, "..", "web", "img", f);
const IMG = WEBIMG("center-floorplan.png");
const THEME = {
  name: "LabGuard",
  headFontFace: "思源宋体",
  bodyFontFace: "更纱黑体 SC",
  colors: { dk1: "1A1F3D", lt1: "FFFFFF", dk2: "4E5577", lt2: "F1F3F8", accent1: "16A362", accent2: "EC9808", accent3: "E03A32", accent4: "5C6BC0", accent5: "171B33", accent6: "7F86A3", hlink: "5C6BC0", folHlink: "4E5577" },
};
const HEX = { ink: "1A1F3D", g: "16A362", y: "EC9808", r: "E03A32", n: "969DB8", code: "171B33" };
const MONO = "Consolas"; // 代码与数字；中文注释会落到正文字体
const HEAD = THEME.headFontFace;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 × 7.5 in；1 in = 144 px（与网页 1920×1080 舞台同比例）
pres.title = "基于双摄协同的实验室安全事前干预监测系统";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const INK = C.text1, INK2 = C.text2, BG = C.background2, WHITE = C.background1;
const G = C.accent1, Y = C.accent2, R = C.accent3, IND = C.accent4, CODE = C.accent5, MUTE = C.accent6;
const px = (v) => v / 144;

// ---------------- 版式 ----------------
const footer = { text: { text: "基于双摄协同的实验室安全事前干预监测系统", options: { x: 0.83, y: 7.05, w: 7, h: 0.3, fontSize: 10, color: MUTE, margin: 0 } } };
pres.defineSlideMaster({
  title: "TITLE", background: { color: BG },
  objects: [{ placeholder: { options: { name: "title", type: "title", fontFace: HEAD, x: 1, y: 3.4, w: 11.33, h: 1.8, fontSize: 48, bold: true, color: INK, align: "center", valign: "middle" }, text: "" } },
            { placeholder: { options: { name: "body", type: "body", x: 1, y: 5.35, w: 11.33, h: 0.6, fontSize: 18, color: MUTE, align: "center" }, text: "" } }],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: BG },
  objects: [{ placeholder: { options: { name: "title", type: "title", fontFace: HEAD, x: 0.83, y: 0.55, w: 11.6, h: 0.8, fontSize: 32, bold: true, color: INK, valign: "middle", align: "left", margin: 0 }, text: "" } }, footer],
  slideNumber: { x: 12.2, y: 7.05, w: 0.5, h: 0.3, fontSize: 10, color: MUTE, align: "right" },
});
pres.defineSlideMaster({
  title: "PHOTO3", background: { color: BG },
  objects: [{ placeholder: { options: { name: "title", type: "title", fontFace: HEAD, x: 0.83, y: 0.55, w: 11.6, h: 0.8, fontSize: 32, bold: true, color: INK, valign: "middle", margin: 0 }, text: "" } },
            { placeholder: { options: { name: "photo1", type: "pic", x: 0.83, y: 1.67, w: 5.83, h: 4.9 }, text: "照片 1：实验台终端整机运行" } },
            { placeholder: { options: { name: "photo2", type: "pic", x: 7.0, y: 1.67, w: 5.5, h: 2.35 }, text: "照片 2：控制盒与传感器接线" } },
            { placeholder: { options: { name: "photo3", type: "pic", x: 7.0, y: 4.22, w: 5.5, h: 2.35 }, text: "照片 3：小屏提醒或总后台联调" } }, footer],
  slideNumber: { x: 12.2, y: 7.05, w: 0.5, h: 0.3, fontSize: 10, color: MUTE, align: "right" },
});

// ---------------- 小工具 ----------------
let n = 0, lastSection = null;
function slide(master, section, title, notes) {
  if (section !== lastSection) { pres.addSection({ title: section }); lastSection = section; }
  const s = pres.addSlide({ masterName: master, sectionTitle: section });
  if (title) s.addText(title, { placeholder: "title" });
  if (notes) s.addNotes(notes);
  s._n = ++n;
  return s;
}
// 信号灯圆点：全场唯一的高饱和元素
function orb(s, cx, cy, d, c, name) {
  s.addShape(pres.shapes.OVAL, { x: px(cx) - d / 2, y: px(cy) - d / 2, w: d, h: d, fill: { color: c === "n" ? MUTE : { g: G, y: Y, r: R }[c] }, line: { color: WHITE, width: 1.5 },
    shadow: { type: "outer", color: HEX[c], blur: 14, offset: 0, angle: 90, opacity: 0.55 }, objectName: name || "信号灯" });
}
const T = (s, text, o) => s.addText(text, Object.assign({ isTextBox: true, margin: 0, color: INK2, fontSize: 16, valign: "top", paraSpaceAfter: 4 }, o.bold && o.fontSize >= 17 && !o.fontFace ? { fontFace: HEAD } : {}, o));
// 实机截图 + 图注
function shot(s, file, x, y, w, ratio, cap, alt) {
  const h = w * ratio;
  s.addImage({ path: WEBIMG(file), x, y, w, h, altText: alt || cap });
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { type: "none" }, line: { color: "DDE0EA", width: 0.75 } });
  T(s, cap, { x, y: y + h + 0.08, w, h: 0.3, fontSize: 11, color: MUTE });
  return h;
}
function card(s, x, y, w, h, o) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, Object.assign({ x, y, w, h, rectRadius: 0.16, fill: { color: WHITE }, line: { color: "DDE0EA", width: 0.75 } }, o));
}
function code(s, x, y, w, title, file, lines, body, size) {
  const fs = size || 11, lh = fs * 1.45 / 72;
  const h = 0.48 + body.split("\n").length * lh + 0.22;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.14, fill: { color: CODE }, line: { type: "none" }, objectName: "代码块" });
  s.addText([{ text: title + "  ", options: { bold: true, color: WHITE, fontFace: THEME.bodyFontFace } }, { text: file, options: { color: "A9B0D3" } }],
    { isTextBox: true, x: x + 0.2, y: y + 0.1, w: w - 1.9, h: 0.3, fontFace: MONO, fontSize: 11, margin: 0, valign: "middle" });
  T(s, lines, { x: x + w - 1.75, y: y + 0.1, w: 1.55, h: 0.3, fontFace: MONO, fontSize: 10, color: "7B83AB", align: "right", valign: "middle" });
  T(s, body, { x: x + 0.2, y: y + 0.5, w: w - 0.4, h: h - 0.6, fontFace: MONO, fontSize: fs, color: "E4E7F5", lineSpacingMultiple: 1.2, paraSpaceAfter: 0 });
  return h;
}
function kv(s, x, y, w, rows, kw, fs) {
  const rh = 0.48; kw = kw || 1.6; fs = fs || 16;
  rows.forEach((r, i) => {
    T(s, r[0], { x, y: y + i * rh, w: kw, h: rh, fontSize: fs, color: MUTE, valign: "middle" });
    T(s, r[1], { x: x + kw, y: y + i * rh, w: w - kw, h: rh, fontSize: fs, color: INK, valign: "middle", fontFace: r[2] ? MONO : undefined });
    if (i < rows.length - 1) s.addShape(pres.shapes.LINE, { x, y: y + (i + 1) * rh, w, h: 0, line: { color: "DDE0EA", width: 0.75 } });
  });
}
function level(s, x, y, c, text, w) {
  const fill = { g: G, y: Y, r: R }[c], fg = { g: "0C6B42", y: "8A5200", r: "A3221B" }[c];
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: w || 1.45, h: 0.38, rectRadius: 0.08, fill: { color: fill, transparency: 88 }, line: { type: "none" } });
  s.addShape(pres.shapes.OVAL, { x: x + 0.14, y: y + 0.14, w: 0.1, h: 0.1, fill: { color: fill }, line: { type: "none" } });
  T(s, text, { x: x + 0.32, y, w: (w || 1.45) - 0.36, h: 0.38, fontSize: 14, bold: true, color: fg, valign: "middle" });
}
function steps(s, x, y, items) {
  let cx = x;
  items.forEach((t, i) => {
    const w = 0.4 + t.length * 0.22;
    card(s, cx, y, w, 0.6);
    T(s, t, { x: cx, y, w, h: 0.6, fontSize: 16, color: INK, align: "center", valign: "middle" });
    cx += w;
    if (i < items.length - 1) { s.addShape(pres.shapes.LINE, { x: cx + 0.08, y: y + 0.3, w: 0.32, h: 0, line: { color: MUTE, width: 1.25, endArrowType: "triangle" } }); cx += 0.48; }
  });
}


// ---------------- 片头 ----------------
let s = slide("TITLE", "片头", null, "开场：每张实验桌一台安全终端，由三个独立程序组成：控制盒固件、实验台终端、总后台。下面每一页都对应仓库里的具体模块。");
s.addText("基于双摄协同的实验室安全\n事前干预监测系统", { placeholder: "title" });
s.addText("放在每一张实验桌上的安全终端", { placeholder: "body" });
orb(s, 960, 400, 0.85, "g", "信号灯（片头）");


// ---------------- 需求 ----------------
function camera(s) {
  s.addShape(pres.shapes.RECTANGLE, { x: px(296), y: 0, w: px(8), h: px(175), fill: { color: "CDD2E3" }, line: { type: "none" } });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: px(180), y: px(170), w: px(250), h: px(120), rectRadius: px(60), fill: { color: WHITE }, line: { color: "DDE0EA", width: 0.75 }, shadow: { type: "outer", color: "262E6E", blur: 18, offset: 6, angle: 90, opacity: 0.18 } });
  orb(s, 362, 230, 0.52, "n", "监控镜头");
}
s = slide("CONTENT", "需求", null, "需求先翻译成工程约束：能断电而且程序坏了也能断，所以有独立的控制盒和固件硬规则；要事前预警，所以判断放在本机；要看清台面，所以加第二路摄像头和红外测温。");
camera(s);
s.addText("监控只能事后回看", { isTextBox: true, x: px(560), y: px(150), w: 8, h: 0.9, fontSize: 40, bold: true, fontFace: HEAD, color: INK, margin: 0 });
T(s, "三个缺口，对应三条工程约束，再落到具体的硬件和模块。", { x: px(560), y: px(280), w: 8, h: 0.5, fontSize: 20 });
{
  const cols = [[0.83, 2.6], [3.55, 4.0], [7.75, 4.75]];
  const rows = [["事故发生时不能干预", "能直接切断加热电源；开发板程序出故障时也要能断", "ESP32-S3 控制盒 + 继电器；固件本地硬规则与心跳看门狗"],
    ["事故发生前不能预警", "识别和判断在实验桌本机实时完成，不依赖网络和人工盯守", "每桌一台 RK3588 终端，NPU 推理，SafetyEngine 本地运行"],
    ["俯拍看不清台面", "器皿种类、离桌边的距离、热源温度都要测得到", "第二路台面摄像头 + 器皿模型；MLX90614 红外测温"]];
  ["缺口", "工程约束", "落到哪里"].forEach((h, k) => T(s, h, { x: cols[k][0], y: 2.9, w: cols[k][1], h: 0.35, fontSize: 12, color: MUTE }));
  rows.forEach((r, i) => {
    const y = 3.3 + i * 0.95;
    s.addShape(pres.shapes.LINE, { x: 0.83, y, w: 11.67, h: 0, line: { color: "DDE0EA", width: 0.75 } });
    r.forEach((t, k) => T(s, t, { x: cols[k][0], y: y + 0.14, w: cols[k][1] - 0.2, h: 0.75, fontSize: 15, color: k === 1 ? INK2 : INK }));
  });
  s.addShape(pres.shapes.LINE, { x: 0.83, y: 3.3 + 3 * 0.95, w: 11.67, h: 0, line: { color: "DDE0EA", width: 0.75 } });
}

s = slide("CONTENT", "需求", "系统组成：三个独立程序", "三个程序：控制盒固件、实验台终端 run_app.py、总后台 run_center.py。终端和控制盒走 USB 串口自定义帧，终端和总后台走 HTTP。安全判断集中在 SafetyEngine，所有界面只读快照。");
function mod(s, x, y, w, h, t, sub, core) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.07, fill: { color: core ? INK : "F4F6FB" }, line: core ? { type: "none" } : { color: "DDE0EA", width: 0.5 } });
  s.addText([{ text: t, options: { fontSize: 13, color: core ? WHITE : INK, breakLine: !!sub } }].concat(sub ? [{ text: sub, options: { fontSize: 9, color: core ? "A9B0D3" : MUTE, fontFace: MONO } }] : []),
    { isTextBox: true, x: x + 0.1, y, w: w - 0.2, h, margin: 0, valign: "middle" });
}
card(s, 0.83, 1.7, 2.7, 3.95); T(s, "控制盒", { x: 1.0, y: 1.85, w: 2.4, h: 0.4, fontSize: 20, bold: true, color: INK }); T(s, "ESP32-S3，Arduino 固件", { x: 1.0, y: 2.25, w: 2.4, h: 0.25, fontSize: 11, color: MUTE });
mod(s, 1.0, 2.6, 2.36, 0.85, "SHT30 温湿度\nMLX90614 红外测温\nMQ-2 烟雾"); mod(s, 1.0, 3.55, 2.36, 0.65, "继电器（加热电源）\n控制键、信号灯、蜂鸣器"); mod(s, 1.0, 4.3, 2.36, 0.6, "本地硬规则", "150℃ / 2500 / 心跳 30 s", true);
card(s, 4.72, 1.7, 4.6, 3.95); T(s, "实验台终端", { x: 4.9, y: 1.85, w: 3, h: 0.4, fontSize: 20, bold: true, color: INK }); T(s, "RK3588，Python，run_app.py", { x: 4.9, y: 2.25, w: 3.5, h: 0.25, fontSize: 11, color: MUTE });
mod(s, 4.9, 2.6, 2.07, 0.55, "识别线程", "dual_inference.py"); mod(s, 7.07, 2.6, 2.07, 0.55, "传感器线程", "sensor_worker.py");
mod(s, 4.9, 3.25, 4.24, 0.62, "SafetyEngine：R1–R9 → 交叉验证 → 温度预测", "engine.py / state_machine.py / cross_check.py", true);
mod(s, 4.9, 3.97, 2.07, 0.55, "事件中心", "语音、灯、截图、SQLite"); mod(s, 7.07, 3.97, 2.07, 0.55, "安全助手", "只读工具");
mod(s, 4.9, 4.6, 2.07, 0.55, "实验台小屏", "kiosk.py（Qt）"); mod(s, 7.07, 4.6, 2.07, 0.55, "本机控制台", "FastAPI :8180");
card(s, 10.5, 1.7, 2.0, 3.95); T(s, "总后台", { x: 10.65, y: 1.85, w: 1.7, h: 0.4, fontSize: 20, bold: true, color: INK }); T(s, "run_center.py", { x: 10.65, y: 2.25, w: 1.7, h: 0.25, fontSize: 10, color: MUTE, fontFace: MONO });
mod(s, 10.65, 2.6, 1.7, 0.55, "FastAPI", ":8200"); mod(s, 10.65, 3.25, 1.7, 0.75, "SQLite", "账号、区域、指令、审计"); mod(s, 10.65, 4.1, 1.7, 0.55, "原生 JS 前端", "无构建");
[[3.53, 4.72, "USB 串口", "AA 55 帧\nCRC16"], [9.32, 10.5, "HTTP", "上报快照\n取回阈值、指令"]].forEach((w) => {
  s.addShape(pres.shapes.LINE, { x: w[0] + 0.08, y: 3.4, w: w[1] - w[0] - 0.16, h: 0, line: { color: MUTE, width: 1.25, beginArrowType: "triangle", endArrowType: "triangle" } });
  T(s, w[2], { x: w[0], y: 3.0, w: w[1] - w[0], h: 0.3, fontSize: 11, align: "center", fontFace: MONO });
  T(s, w[3], { x: w[0] - 0.05, y: 3.5, w: w[1] - w[0] + 0.1, h: 0.5, fontSize: 9, align: "center", fontFace: MONO });
});
T(s, "安全判断不依赖任何界面：小屏、本机控制台和总后台都只读取 SafetyEngine.snapshot()。", { x: 0.83, y: 5.95, w: 11, h: 0.35, fontSize: 13, color: MUTE });
orb(s, 1196, 296, 0.2, "g");

s = slide("CONTENT", "需求", "一次判断：三个触发源，一条调用链", "判断有三个触发源：每帧识别结果、每次遥测、每秒一次定时器，摄像头掉线时也照常判断。每次都跑同一条调用链，最后一步才喂心跳；交叉验证每秒算一次，界面只读 snapshot。");
code(s, 0.83, 1.5, 5.85, "SafetyEngine.__init__", "src/core/engine.py", "L104–112 节选",
`# 每一帧识别结果
self.inference_thread.update_frames_signal.connect(self._on_frames)
# 每一次控制盒遥测
self.sensor_worker.sensor_data_updated.connect(self._on_sensor)
# 每秒一次：摄像头全部掉线时也照常判断
self._tick = QTimer(self)
self._tick.timeout.connect(self._on_tick)
self._tick.start(1000)`, 9);
kv(s, 0.83, 4.1, 5.85, [["线程边界", "识别、串口各在后台线程，结果经 Qt 信号回到主线程再判断"], ["帧队列", "maxsize=2，满了丢最旧的（put_latest）"], ["网页线程", "不碰 numpy 画面，只取 latest_jpeg() 编码好的字节"]], 1.2, 13);
[["_evaluate()", "每次触发都跑", 0], ["state_machine.evaluate()", "规则 R1–R9", 1], ["world_model.update()", "温度预测", 1], ["events.update()", "事件、语音、灯、截图、SQLite", 1],
 ["send_power_off()", "需要断电时", 1], ["serial.feed()", "最后一步：喂心跳", 1], ["update_risk()", "每秒：交叉验证三级 + 三层定级", 0], ["snapshot()", "小屏、本机控制台、总后台都只读它", 0]].forEach((p, i) => {
  const sub = p[2] === 1, x = sub ? 7.7 : 7.3, w = sub ? 4.8 : 5.2, y = 1.5 + i * 0.52;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.44, rectRadius: 0.07, fill: { color: sub ? "F7F8FC" : CODE }, line: sub ? { color: "DDE0EA", width: 0.5 } : { type: "none" } });
  s.addText([{ text: p[0], options: { fontFace: MONO, bold: true, fontSize: 12, color: sub ? INK : WHITE } }, { text: "   " + p[1], options: { fontSize: 11, color: sub ? INK2 : "A9B0D3" } }],
    { isTextBox: true, x: x + 0.15, y, w: w - 0.3, h: 0.44, margin: 0, valign: "middle" });
});
T(s, "断电只由规则执行；交叉验证、温度预测和安全助手只影响提醒，不参与断电。", { x: 0.83, y: 6.45, w: 11, h: 0.35, fontSize: 12, color: MUTE });
orb(s, 1048, 254, 0.2, "g");


// ---------------- 识别 ----------------
s = slide("CONTENT", "识别", "两路摄像头、两个模型：类别名怎么变成事件", "人员模型 12 类、器皿模型 14 类。类别名通过映射表变成事件 kind，比如 no googles 变成 ppe_goggles；器皿按可加热、不可加热分组，供规则和交叉验证使用。");
[[1.5, 1.9, "全景摄像头", "ppe_best，12 类", "护目镜　手套　实验服　口罩　头罩　以上五项的未佩戴类　进食　饮水", "模型没有 person 类：检出任意一类装备即视为有人"],
 [3.6, 2.4, "台面摄像头", "chem_best，14 类", "烧杯　锥形瓶　圆底烧瓶　平底烧瓶　梨形瓶　试管　量筒　容量瓶　滴定管　移液管　试剂瓶　洗瓶　漏斗　滴定装置", ""]].forEach((c) => {
  card(s, 0.83, c[0], 5.3, c[1]);
  T(s, c[2], { x: 1.05, y: c[0] + 0.18, w: 2.6, h: 0.42, fontSize: 20, bold: true, color: INK });
  T(s, c[3], { x: 3.4, y: c[0] + 0.24, w: 2.55, h: 0.35, fontSize: 11, color: MUTE, align: "right", fontFace: MONO });
  T(s, c[4], { x: 1.05, y: c[0] + 0.72, w: 4.9, h: 1.0, fontSize: 14, color: INK, lineSpacingMultiple: 1.4 });
  if (c[5]) T(s, c[5], { x: 1.05, y: c[0] + 1.45, w: 4.9, h: 0.3, fontSize: 11, color: MUTE });
});
code(s, 6.45, 1.5, 6.05, "PPE_VIOLATION_KINDS", "dual_inference.py", "L117–126",
`PPE_VIOLATION_KINDS = {
    "no googles": ("ppe_goggles", "未佩戴护目镜"),
    "no goggles": ("ppe_goggles", "未佩戴护目镜"),
    "no lab coat": ("ppe_coat", "未穿实验服"),
    "no gloves": ("ppe_gloves", "未佩戴手套"),
    "no mask": ("ppe_mask", "未佩戴口罩"),
    "no head mask": ("ppe_headmask", "未佩戴头罩"),
    "eating": ("eating", "实验区饮食"),
    "drinking": ("eating", "实验区饮食"),
}`, 10);
code(s, 6.45, 4.35, 6.05, "器皿分组", "src/core/cross_check.py", "L22–23",
`HEATABLE = {"beaker", "conical flask", "flat bottom flask",
            "round bottom flask", "pear shaped flask", "test tube"}
NON_HEATABLE = {"volumetric flask", "measuring cylinder",
                "reagent bottle", "burette", "pipette", "wash bottle"}`, 9);
T(s, "训练集把护目镜拼成了 googles，映射表两种拼写都收；表里没有的「no xxx」类按规则自动生成 ppe_xxx 事件。", { x: 6.45, y: 5.9, w: 6.05, h: 0.6, fontSize: 11, color: MUTE });
orb(s, 1760, 216, 0.2, "g");

s = slide("CONTENT", "识别", "YOLO11n 微调，各约 2.59 M 参数", "两个模型都是 YOLO11n 微调。人员模型训练 80 轮、取第 77 轮权重，mAP@0.5 为 89.0%；器皿模型 50 轮，mAP@0.5 为 89.3%。这是验证集上的检测指标，不是事故识别准确率。");
const CUR = require("./curves.json");
[[160, "人员模型", "全景摄像头，12 类，训练 80 轮", "ppe", 77, [["mAP@0.5", "89.0%"], ["Precision", "83.4%"], ["Recall", "87.7%"], ["mAP@0.5:0.95", "64.3%"]]],
 [980, "器皿模型", "台面摄像头，14 类，训练 50 轮", "chem", 50, [["mAP@0.5", "89.3%"], ["Precision", "86.7%"], ["Recall", "85.1%"], ["mAP@0.5:0.95", "73.7%"]]]].forEach((m) => {
  const x = px(m[0]); card(s, x, px(270), px(780), px(660));
  T(s, m[1], { x: x + 0.24, y: px(270) + 0.22, w: 2, h: 0.45, fontSize: 22, bold: true, color: INK });
  T(s, m[2], { x: x + 2.2, y: px(270) + 0.27, w: 2.95, h: 0.4, fontSize: 13, color: MUTE, align: "right" });
  m[5].forEach((v, i) => {
    T(s, v[1], { x: x + 0.24 + i * 1.24, y: px(270) + 0.8, w: 1.2, h: 0.5, fontSize: 24, bold: true, color: INK, fontFace: MONO });
    T(s, v[0], { x: x + 0.24 + i * 1.24, y: px(270) + 1.3, w: 1.2, h: 0.3, fontSize: 11, color: MUTE });
  });
  const c = CUR[m[3]], labels = c.a.map((_, i) => String(i + 1));
  s.addChart(pres.charts.LINE, [{ name: "mAP@0.5", labels, values: c.a }, { name: "mAP@0.5:0.95", labels, values: c.b }], {
    x: x + 0.15, y: px(270) + 1.7, w: px(780) - 0.3, h: 2.5, chartColors: ["2A78D6", "EB6834"], lineSize: 2, lineDataSymbol: "none",
    valAxisMinVal: 0, valAxisMaxVal: 1, valAxisMajorUnit: 0.25, valAxisLabelFormatCode: "0.00", catAxisLabelFrequency: 10,
    valAxisLabelColor: "7F86A3", catAxisLabelColor: "7F86A3", valAxisLabelFontSize: 10, catAxisLabelFontSize: 10, valAxisLabelFontFace: "+mn-lt", catAxisLabelFontFace: "+mn-lt",
    valGridLine: { color: "E3E6EF", size: 0.75 }, catGridLine: { style: "none" }, catAxisLabelRotate: 0, showLegend: true, legendPos: "b", legendFontSize: 11, legendColor: "4E5577", legendFontFace: "+mn-lt",
    showTitle: true, title: "验证集指标随轮次变化（横轴：轮次）", titleFontSize: 12, titleColor: "4E5577", titleFontFace: "+mn-lt" });
  T(s, "best.pt：第 " + m[4] + " 轮　mAP@0.5 " + (c.a[m[4] - 1] * 100).toFixed(1) + "%", { x: x + 0.24, y: px(270) + 4.25, w: 4, h: 0.3, fontSize: 12, color: INK2 });
});
T(s, "指标为 best.pt 所在轮次（人员模型第 77 轮，器皿模型第 50 轮）的验证集检测指标，数据来自 models/model_card.json", { x: 0.83, y: px(212), w: 10, h: 0.3, fontSize: 12, color: MUTE });
orb(s, 1760, 150, 0.2, "g");

s = slide("CONTENT", "识别", "部署：按 RKNN → ONNX → .pt 加载，失败自动回退", "部署按 RKNN、ONNX、.pt 的顺序尝试；RKNN 要先试跑一次才真正加载 NPU，失败就换下一种格式，并写一条事件。帧队列只保留最新的两帧，判断不会被积压的旧帧拖慢。NPU 单帧人员 120 ms、器皿 116 ms。");
code(s, 0.83, 1.5, 6.85, "_load_model", "dual_inference.py", "L292–313 节选",
`for path in paths:          # 按 vision.prefer_format 排好的候选
    if path.endswith("_rknn_model") and not ON_ROCKCHIP:
        continue
    try:
        model = YOLO(path, task="detect")
        if path.endswith("_rknn_model"):
            imgsz = int(cfg("vision.imgsz", 640))
            # 第一次推理才真正加载 NPU，先试跑一次
            model(np.zeros((imgsz, imgsz, 3), np.uint8),
                  verbose=False, imgsz=imgsz)
            self._fixed_imgsz = imgsz
        if err:
            events.log("NPU 模型没加载上", ..., kind="model")
        return model, model.names
    except Exception as e:
        err = str(e)`, 9);
code(s, 7.95, 1.5, 4.55, "put_latest", "dual_inference.py", "L145–155",
`def put_latest(q, item):
    # 队列满时丢弃最旧的元素
    while True:
        try:
            q.put_nowait(item)
            return
        except queue.Full:
            try:
                q.get_nowait()
            except queue.Empty:
                pass`, 10);
kv(s, 7.95, 4.6, 4.55, [["NPU 单帧推理", "人员 120 ms / 器皿 116 ms"], ["版本一致", "导出工具、板上运行时均为 2.3.2"], ["输入尺寸", "导出时固定 640"]], 1.35, 12);
T(s, "RK3588 实测，FP16；tools/check_npu.py 对比 NPU 与 .pt 的检测结果一致。NPU 加载失败时改用 .pt（CPU），并写一条事件。", { x: 0.83, y: 5.35, w: 6.85, h: 0.6, fontSize: 11, color: MUTE });
orb(s, 1760, 216, 0.2, "g");

s = slide("CONTENT", "识别", "从检测框到事件：时间窗口投票", "单帧检测结果不直接报警：3 s 窗口内命中帧占比 ≥60% 才确认，≤20% 才解除，有滞回。人员在场用装备检出代替 person 类，连续 15 s 无检出才算无人。");
code(s, 0.83, px(260), 6.25, "TemporalVoter.update", "LabSafetyMonitor/dual_inference.py", "L169–180",
`for kind in kinds:
    d = self.hist.setdefault(kind, deque())
    d.append((now, kind in hits))
    while d and now - d[0][0] > self.window:
        d.popleft()
    if len(d) < self.min_frames:
        continue
    ratio = sum(1 for _, h in d if h) / len(d)
    if not self.active.get(kind) and ratio >= self.on_ratio:
        self.active[kind] = True
    elif self.active.get(kind) and ratio <= self.off_ratio:
        self.active[kind] = False`, 10);
kv(s, px(1130), px(260), 4.35, [["窗口", "window_s = 3.0 s", 1], ["确认", "命中帧占比 ≥ 60%"], ["解除", "命中帧占比 ≤ 20%"], ["最少帧数", "4"]]);
T(s, "确认和解除用两个阈值，形成滞回，单帧误检不会触发提醒，事件也不会在边界上反复跳变。", { x: px(1130), y: px(560), w: 4.35, h: 1, fontSize: 16 });
kv(s, px(1130), px(700), 4.35, [["人员在场", "人员模型任一类检出即视为有人"], ["无人值守", "连续 15 s 无检出"], ["画面无效", "黑屏、无摄像头、演示数据时不判断无人"]], 1.3, 14);
orb(s, 1060, 260, 0.2, "g");


// ---------------- 面向学生 ----------------
s = slide("CONTENT", "面向学生", "演示：吃苹果的同学", "演示：摘下头罩、护目镜、口罩吃苹果。检测框经投票确认，events.update 在上升沿播语音，曲目号来自 config.yaml，经串口 PLAY_VOICE 让控制盒播放。分数叠加后小屏和信号灯变红。");
{
  let cx = 0.83;
  ["检测框 no googles", "TemporalVoter 确认", "events.update 上升沿", "_play_voice 选语气", "PLAY_VOICE 0x03，曲目 1"].forEach((t, i, arr) => {
    const w = 0.3 + [...t].reduce((a, ch) => a + (ch.charCodeAt(0) > 255 ? 0.15 : 0.083), 0);
    card(s, cx, 1.5, w, 0.4, { rectRadius: 0.06 });
    T(s, t, { x: cx, y: 1.5, w, h: 0.4, fontSize: 11, color: INK, align: "center", valign: "middle", fontFace: MONO });
    cx += w;
    if (i < arr.length - 1) { s.addShape(pres.shapes.LINE, { x: cx + 0.06, y: 1.7, w: 0.2, h: 0, line: { color: MUTE, width: 1, endArrowType: "triangle" } }); cx += 0.32; }
  });
}
card(s, px(140), px(360), px(880), px(528), { rectRadius: 0.3, fill: { color: "F7F8FC" } });
const kx = px(166), ky = px(386), kw = px(828), kh = px(476);
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: kx, y: ky, w: kw, h: kh, rectRadius: 0.14, fill: { color: WHITE }, line: { color: INK, width: 1.5 } });
s.addShape(pres.shapes.RECTANGLE, { x: kx, y: ky + px(76), w: kw, h: 0, line: { color: INK, width: 1.5 } });
s.addShape(pres.shapes.RECTANGLE, { x: kx, y: ky + kh - px(72), w: kw, h: 0, line: { color: INK, width: 1.5 } });
T(s, "高危", { x: kx + px(86), y: ky, w: 2, h: px(76), fontSize: 20, bold: true, color: INK, valign: "middle" });
T(s, "实验台小屏", { x: kx + kw - 1.6, y: ky, w: 1.45, h: px(76), fontSize: 12, color: INK2, valign: "middle", align: "right" });
T(s, "待处理事项", { x: kx + 0.15, y: ky + px(90), w: 2, h: 0.3, fontSize: 12 });
["停止饮食，到实验区外进食", "佩戴护目镜", "佩戴口罩", "佩戴头罩"].forEach((t, i) => {
  const hi = i === 0; s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: kx + 0.15, y: ky + px(130) + i * 0.4, w: 2.35, h: 0.33, rectRadius: 0.06, fill: { color: hi ? R : Y, transparency: 88 }, line: { type: "none" } });
  T(s, t, { x: kx + 0.25, y: ky + px(130) + i * 0.4, w: 2.2, h: 0.33, fontSize: 12, color: hi ? "A3221B" : "6E4300", valign: "middle" });
});
T(s, "热源", { x: kx + 2.75, y: ky + px(90), w: 1.5, h: 0.3, fontSize: 12 });
T(s, "未加热", { x: kx + 2.75, y: ky + px(130), w: 1.8, h: 0.5, fontSize: 24, bold: true, color: INK });
T(s, "防护", { x: kx + 4.3, y: ky + px(90), w: 1.5, h: 0.3, fontSize: 12 });
[["护目镜", 1], ["实验服", 0], ["手套", 0], ["口罩", 1]].forEach((p, i) => {
  const bx = kx + 4.3 + (i % 2) * 0.82, by = ky + px(130) + Math.floor(i / 2) * 0.4;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: bx, y: by, w: 0.75, h: 0.32, rectRadius: 0.06, fill: { color: p[1] ? R : G, transparency: 88 }, line: { type: "none" } });
  T(s, p[0], { x: bx, y: by, w: 0.75, h: 0.32, fontSize: 11, color: p[1] ? "A3221B" : "0C6B42", align: "center", valign: "middle" });
});
["状态", "画面", "记录", "静音 60s", "呼叫教师", "断电"].forEach((t, i) => T(s, t, { x: kx + i * kw / 6, y: ky + kh - px(72), w: kw / 6, h: px(72), fontSize: 12, color: i === 5 ? "A3221B" : INK, align: "center", valign: "middle" }));
orb(s, 213, 424, 0.24, "r");
T(s, "小屏界面示意，按当前小屏布局绘制", { x: px(166), y: px(900), w: 5, h: 0.3, fontSize: 11, color: MUTE });
[[400, "同学，记得戴好护目镜哦，眼睛只有一双。", "ppe_goggles，曲目 1"], [640, "实验区不能吃东西喝水哦，请到室外再吃。", "eating，曲目 6"]].forEach((b) => {
  card(s, px(1080), px(b[0]), px(700), 1.25, { shadow: { type: "outer", color: "262E6E", blur: 16, offset: 5, angle: 90, opacity: 0.16 } });
  level(s, px(1080) + 0.25, px(b[0]) + 0.18, "y", "温和语气", 1.35);
  T(s, b[2], { x: px(1080) + 1.7, y: px(b[0]) + 0.18, w: 2.6, h: 0.38, fontSize: 11, color: MUTE, valign: "middle", fontFace: MONO });
  T(s, "「" + b[1] + "」", { x: px(1080) + 0.25, y: px(b[0]) + 0.62, w: px(700) - 0.5, h: 0.55, fontSize: 18, color: INK });
});

T(s, "语气由 events._play_voice() 决定：紧急事件或交叉验证为高危时用严厉语气，其余温和；事件解除后 10 s 内再出现算同一次，不重复播报。", { x: px(1080), y: px(880), w: px(700), h: 0.6, fontSize: 11, color: MUTE });
s = slide("CONTENT", "面向学生", "学生是第一用户", "学生是第一用户：提醒先发给台前的学生。每桌一台终端，断网也照常判断；小屏按现场设计，不做动画，不和识别抢 CPU。");
T(s, "系统的首要目标是减少火灾和人身伤害，而不是记录违规。所以提醒先发给台前的学生，管理端只接收需要处理的事件。", { x: 0.83, y: 1.6, w: 6.6, h: 1.5, fontSize: 20 });
shot(s, "kiosk-warning.png", 8.1, 1.4, 4.4, 0.6, "实机截图：实验台小屏，加热中无人值守、预测即将干烧");
orb(s, 230, 860, 0.62, "g");
[["每张实验桌一台终端", "RK3588 开发板、两路 USB 摄像头、控制盒与传感器、小屏；硬件采购估算 1000–1350 元"],
 ["断网照常工作", "识别、打分和断电都在本机；连不上总后台只记一条，恢复后自动重新上报"],
 ["小屏按现场设计", "800×480 基准自适应，按钮 ≥ 64 px；0.5 s 刷新、不做动画，不和识别抢 CPU"]].forEach((f, i) => {
  const x = px(330) + i * 3.3; s.addShape(pres.shapes.LINE, { x, y: 4.6, w: 3.1, h: 0, line: { color: "DDE0EA", width: 0.75 } });
  T(s, f[0], { x, y: 4.6 + 0.2, w: 3.05, h: 0.5, fontSize: 20, bold: true, color: INK });
  T(s, f[1], { x, y: 4.6 + 0.75, w: 3.05, h: 1.3, fontSize: 15 });
});

s = slide("CONTENT", "面向学生", "第一个分叉：交叉验证打分，分三级", "第一个分叉：交叉验证是多源规则打分，不是机器学习里的交叉验证。每条因子带来源和分值，相加封顶 100，30 分中危、70 分高危。三个例子的分数都能从代码里逐项算出来。");
code(s, 0.83, 1.4, 7.0, "assess()", "src/core/cross_check.py", "L92–127 节选",
`elif "WARNING" in ev_levels:
    add("规则引擎", "存在警告事件", 40)
if heating and present is False:
    add("人员 × 传感器", "正在加热但台前无人", 70, ...)
for k in missing:
    name = PPE_NAMES[k]
    if heating and k in ("ppe_goggles", "ppe_gloves"):
        add("人员 × 传感器", f"加热中未佩戴{name}…", 35 if boiling else 30, ...)
    elif items and k in ("ppe_goggles", "ppe_gloves", "ppe_coat"):
        add("人员 × 器皿", f"台面有器皿时未佩戴{name}", 15, ...)
if heating and non_heatable:
    add("器皿 × 传感器", "加热时台面有不可加热量器…", 35, ...)
if wm_risk >= 0.6:
    add("温度预测", f"干烧风险分 {wm_risk:.2f}", 70, ...)
score = min(100, sum(f["points"] for f in factors))
level = "high" if score >= high_score else "mid" if score >= mid_score else "low"`, 8.5);
kv(s, 8.1, 1.4, 4.4, [["输入", "人员、器皿、温度预测、事件等级合成的字典"], ["输出", "level、score、scene、每条依据"], ["性质", "纯函数，不参与断电"], ["分界", "30 / 70，可按区域调整"]], 0.8, 12);
{
  const ax = px(240), aw = px(1440), ay = 5.0;
  [[0, 0.3, G], [0.3, 0.7, Y], [0.7, 1, R]].forEach((seg) => s.addShape(pres.shapes.RECTANGLE, { x: ax + aw * seg[0], y: ay, w: aw * (seg[1] - seg[0]), h: 0.05, fill: { color: seg[2], transparency: 45 }, line: { type: "none" } }));
  [[0, "0"], [0.3, "30"], [0.7, "70"], [1, "100"]].forEach((t) => T(s, t[1], { x: ax + aw * t[0] - 0.4, y: ay + 0.1, w: 0.8, h: 0.25, fontSize: 11, color: MUTE, align: "center", fontFace: MONO }));
  orb(s, 456, 723, 0.24, "g"); orb(s, 1176, 723, 0.24, "y"); orb(s, 1680, 723, 0.24, "r");
  [[240, "g", "低危　15 分", "未加热，整理器皿时未戴手套", "15 台面有器皿时未佩戴手套"], [740, "y", "中危　65 分", "加热中有量筒，未戴护目镜", "35 量器被加热 + 30 未戴护目镜"],
   [1240, "r", "高危　100 分", "越过沸点仍在升温", "70 干烧风险 + 40 警告，封顶 100"]].forEach((c) => {
    card(s, px(c[0]), 5.45, px(440), 1.3); level(s, px(c[0]) + 0.18, 5.58, c[1], c[2], 1.7);
    T(s, c[3], { x: px(c[0]) + 0.18, y: 6.02, w: px(440) - 0.36, h: 0.35, fontSize: 14, color: INK });
    T(s, c[4], { x: px(c[0]) + 0.18, y: 6.38, w: px(440) - 0.36, h: 0.3, fontSize: 10, color: INK2, fontFace: MONO });
  });
}

s = slide("CONTENT", "面向学生", "断电只看规则；温度预测只负责提前预警", "断电只看 R1 到 R9 这组确定的规则，只有 cut=True 的才下发断电。温度预测用一阶热平衡拟合，低于沸点只给沸腾时间；越过沸点还在升温，才给干烧倒计时，触发 R9 预警，不断电。");
{
  const cx = [0.83, 1.4, 5.4], cw = [0.55, 3.95, 1.5];
  ["编号", "条件（config.yaml → rules）", "结果"].forEach((h, k) => T(s, h, { x: cx[k], y: 1.45, w: cw[k], h: 0.3, fontSize: 11, color: MUTE }));
  [["R1", "热源 ≥ 120℃", "紧急，断电", "r"], ["R2", "≥ 80℃ 且升温 ≥ 2℃/s", "警告", "y"], ["R3", "加热中（≥ 50℃）无人，持续 60 s", "警告 → 断电", "r"], ["R4", "无测温 + 可加热器皿 + 无人 + 环境 > 55℃", "紧急，断电", "r"],
   ["R5", "烟雾读数 ≥ 1800", "紧急，断电", "r"], ["R6", "湿度 > 80%", "警告", "y"], ["R7", "环境温度 > 40℃", "警告", "y"], ["R8", "加热中台面有容量瓶、量筒等量器", "提醒", "n"], ["R9", "越过沸点仍升温，预计 ≤ 90 s 到 120℃", "警告，不断电", "y"]].forEach((r, i) => {
    const y = 1.8 + i * 0.43;
    s.addShape(pres.shapes.LINE, { x: 0.83, y, w: 6.1, h: 0, line: { color: "DDE0EA", width: 0.5 } });
    T(s, r[0], { x: cx[0], y, w: cw[0], h: 0.43, fontSize: 12, bold: true, color: INK, valign: "middle", fontFace: MONO });
    T(s, r[1], { x: cx[1], y, w: cw[1], h: 0.43, fontSize: 13, color: INK, valign: "middle" });
    T(s, r[2], { x: cx[2], y, w: cw[2], h: 0.43, fontSize: 13, bold: r[3] === "r", color: { r: "A3221B", y: "8A5200", n: INK2 }[r[3]], valign: "middle" });
  });
}
T(s, "每条规则写成 add(kind, level, title, message, cut=…)，只有 cut=True 的规则会下发断电。", { x: 0.83, y: 5.8, w: 6.1, h: 0.5, fontSize: 11, color: MUTE });
code(s, 7.15, 1.45, 5.35, "_predict", "src/core/world_model.py", "L130–176 节选",
`# 一阶模型 dT/dt = α + β·T，β = -1/τ，T∞ = -α/β
# 2 秒分箱后差分求导，抑制噪声
if len(d_t) >= 4 and slope > 0.02 and not beyond_boil:
    lf = self._linfit(d_t, d_v)
    if lf is not None:
        beta, alpha = lf
        if beta < -1e-4:
            t_inf_c = -alpha / beta
            tau_c = -1.0 / beta
...
if temp < boil_hi:   # 低于沸点：液体还在
    eta_boil = time_to(boil_lo) if temp < boil_lo else None
else:                # 越过沸点仍升温：可能已烧干
    eta = time_to(dry_c)`, 9);
kv(s, 7.15, 4.95, 5.35, [["拟合窗口", "最近 60 s；越过沸点后只用最近 15 s 外推"], ["沸腾平台", "92–104℃ 且 15 s 斜率 < 0.05℃/s"]], 1.1, 12);
orb(s, 1070, 209, 0.2, "y");

s = slide("CONTENT", "面向学生", "第二个分叉：同一事件，三层各自定级", "第二个分叉：同一事件三层各自定级。吃苹果对学生是高危，对老师只记知会，对实验楼不打扰；断电锁定三层都是最高。");
[[880, "学生端", "语音提示、小屏", "r"], [1233, "实验室老师", "处置队列、群消息", "y"], [1586, "实验楼", "处置队列", "g"]].forEach((h) => {
  orb(s, h[0], 262, 0.26, h[3]);
  T(s, h[1], { x: px(h[0]) - 1.2, y: px(300), w: 2.4, h: 0.4, fontSize: 17, color: INK, align: "center" });
  T(s, h[2], { x: px(h[0]) - 1.2, y: px(300) + 0.38, w: 2.4, h: 0.3, fontSize: 12, color: MUTE, align: "center" });
});
[["摘口罩、吃苹果", [["r", "严厉干预"], ["g", "仅记录"], ["g", "无需介入"]]], ["加热时台面有量筒", [["y", "温和提醒"], ["y", "需关注"], ["g", "无需介入"]]],
 ["越过沸点仍升温", [["r", "严厉干预"], ["r", "立即处置"], ["y", "关注"]]], ["断电锁定、烟雾超标", [["r", "严厉干预"], ["r", "立即处置"], ["r", "需介入"]]]].forEach((row, i) => {
  const y = px(400) + i * 0.75; card(s, 0.83, y, 3.5, 0.6);
  T(s, row[0], { x: 1.05, y, w: 3.2, h: 0.6, fontSize: 18, color: INK, valign: "middle" });
  row[1].forEach((c, k) => level(s, px([880, 1233, 1586][k]) - 0.72, y + 0.11, c[0], c[1], 1.45));
});
T(s, "学生端计入全部因子；实验室老师只计入加热、温度、烟雾、断电和学生呼叫，行为违规仅作知会；实验楼只计入断电锁定和紧急事件。", { x: 0.83, y: px(910), w: 11.6, h: 0.7, fontSize: 16, color: INK });

s = slide("CONTENT", "面向学生", "分层上报的实现：同一份打分，三次过滤", "实现上就是在同一份打分上做三次过滤：老师层去掉行为因子，实验楼层只看断电锁定和紧急事件。等级随快照字段 risk.tiers 上报，不参与断电。");
code(s, 0.83, 1.6, 7.45, "tiers()", "src/core/cross_check.py", "L166–191 节选",
`# ---- 实验室老师 ----
reasons = [
    {"text": f["text"], "points": f["points"]} for f in r["factors"]
    if f["source"] not in BEHAVIOR_SOURCES and f["source"] != "规则引擎"]
if latched:
    reasons.append({"text": "已断电锁定，需到场排查", "points": 100})
elif "CRITICAL" in hz: ...
elif "WARNING" in hz: ...
if d.get("called"):
    reasons.append({"text": "学生在终端上呼叫教师", "points": 40})
t_level = _level(t_score, mid_score, high_score)
notes = [f["text"] for f in r["factors"] if f["source"] in BEHAVIOR_SOURCES]

# ---- 实验楼 ----
if latched or "CRITICAL" in hz:
    b_level = "high"
elif t_level == "high":
    b_level = "mid"`, 10);
kv(s, 8.5, 1.6, 4.0, [["学生端", "全部因子，即 risk.level"], ["实验室", "去掉行为因子；hz 只含安全规则事件"], ["实验楼", "只看断电锁定与紧急事件"]], 1.1, 14);
T(s, "三层等级随快照字段 risk.tiers 上报；总后台按账号角色选默认视角，旧版终端没有该字段时有兜底。分层只影响上报，不参与断电。", { x: 8.5, y: 3.3, w: 4.0, h: 1.8, fontSize: 15 });
orb(s, 1160, 240, 0.2, "y");

s = slide("CONTENT", "面向学生", "安全助手：只读，只建议", "安全助手的工具表只有 5 个只读工具，测试会扫描工具名，不允许出现电源、继电器类工具。线路自动选择，都不可用时用规则模板，截图里这条建议就是规则模板生成的。");
shot(s, "advice-card.png", 0.83, 1.55, 4.75, 346 / 370, "实机截图：本机控制台事件卡片，处理建议由规则模板生成", "事件卡片：预测即将干烧，附处理建议的原因、处置和手册依据");
orb(s, 900, 230, 0.2, "y");
T(s, "读取交叉验证结果和安全手册（BM25 检索），生成原因、步骤和条款引用。工具表只有 5 个只读工具，没有任何电源控制接口。", { x: 6.4, y: 1.65, w: 6.1, h: 1.3, fontSize: 18 });
code(s, 6.4, 3.0, 6.1, "TOOLS", "src/agent/agent.py", "L47–66 节选",
`TOOLS = [                       # 全部只读
    {"name": "get_status", ...},           # 状态、遥测、锁定
    {"name": "get_risk_assessment", ...},  # 交叉验证结果
    {"name": "get_recent_events", ...},
    {"name": "get_forecast", ...},         # 温度预测
    {"name": "search_manual", ...},        # 手册检索
]`, 10);
T(s, "线路 agent.route = auto：远程通义千问 → 本地 Ollama；都不可用时退回规则模板。", { x: 6.4, y: 5.25, w: 6.1, h: 0.4, fontSize: 12, color: MUTE });

// ---------------- 断电 ----------------
s = slide("CONTENT", "断电", "最后一道防线：只断不通", "断电链路：开发板发 POWER_OFF，控制盒断继电器回 ACK，0.25 s 超时重发，最多发送 3 次，往返中位 4.9 ms。控制盒另有固件硬规则。软件和总后台都没有通电接口。");
[["开发板", "规则判定需断电", 160], ["控制盒", "ESP32-S3", 810], ["加热电源", "已断开", 1460]].forEach((nd, i) => {
  card(s, px(nd[2]), px(300), px(300), 0.95);
  T(s, nd[0], { x: px(nd[2]), y: px(300) + 0.12, w: px(300), h: 0.4, fontSize: 19, color: INK, align: "center" });
  T(s, nd[1], { x: px(nd[2]), y: px(300) + 0.52, w: px(300), h: 0.3, fontSize: 12, color: MUTE, align: "center" });
  if (i < 2) { const x0 = px(nd[2] + 320), x1 = px([810, 1460][i] - 20); s.addShape(pres.shapes.LINE, { x: x0, y: px(300) + 0.48, w: x1 - x0, h: 0, line: { color: MUTE, width: 1.25, endArrowType: "triangle" } });
    T(s, ["POWER_OFF 0x02", "断开继电器"][i], { x: x0, y: px(300) + 0.08, w: x1 - x0, h: 0.3, fontSize: 12, align: "center", fontFace: MONO }); }
});
T(s, "控制盒回 ACK；0.25 s 未收到则重发，最多发送 3 次。真机实测 ACK 往返时延中位数 4.9 ms。", { x: 0.83, y: px(440), w: 11, h: 0.35, fontSize: 13, color: MUTE });
shot(s, "kiosk-locked.png", px(160), px(540), 3.4, 0.6, "实机截图：小屏断电锁定页");
orb(s, 1610, 300, 0.22, "n", "加热电源指示");
[["开发板规则（可按区域调整）", "R1 热源 ≥ 120℃\nR3 加热中无人 60 s\nR5 烟雾读数 ≥ 1800", 720], ["控制盒本地硬规则（写在固件里）", "热源 ≥ 150℃\n烟雾读数 ≥ 2500\n心跳中断 30 s 且热源 > 60℃", 1260]].forEach((r) => {
  s.addShape(pres.shapes.LINE, { x: px(r[2]), y: px(540), w: 3.5, h: 0, line: { color: "DDE0EA", width: 0.75 } });
  T(s, r[0], { x: px(r[2]), y: px(540) + 0.15, w: 3.5, h: 0.3, fontSize: 12, color: MUTE });
  T(s, r[1], { x: px(r[2]), y: px(540) + 0.48, w: 3.5, h: 1.1, fontSize: 16, color: INK, lineSpacingMultiple: 1.2 });
});
s.addShape(pres.shapes.LINE, { x: px(720), y: px(800), w: 7.2, h: 0, line: { color: "DDE0EA", width: 0.75 } });
T(s, "恢复供电", { x: px(720), y: px(800) + 0.2, w: 1.4, h: 0.45, fontSize: 20, bold: true, color: INK });
T(s, "软件和总后台都没有通电接口。复电只能在现场长按控制键 2 秒，控制盒先复查温度和烟雾，超标则拒绝。", { x: px(720) + 1.5, y: px(800) + 0.2, w: 5.7, h: 0.8, fontSize: 15 });

s = slide("CONTENT", "断电", "程序卡死也能断电：心跳由安全判断驱动", "心跳不是定时器发的：只有安全判断每次跑完调用 feed()，发送线程才发心跳。程序卡死 5 s 心跳就停，控制盒 30 s 收不到心跳、继电器闭合且热源高于 60℃（测不到温度也算）就本地断电。");
code(s, 0.83, 1.52, 6.15, "① R3 加热中无人值守", "src/core/state_machine.py", "L250–260 节选",
`cut_s = rules("unattended_heating_cut_s", 60.0)
if heating and macro_unattended:
    if self._unattended_heat_since is None:
        self._unattended_heat_since = now
    dur = now - self._unattended_heat_since
    if dur >= cut_s:
        add("unattended_heating", "CRITICAL",
            "加热中无人值守超时", ..., cut=True)
    else:
        add("unattended_heating", "WARNING",
            "加热中无人值守", ...)`, 11);
code(s, 7.2, 1.52, 5.3, "② 只有判断跑完才喂心跳", "serial_comm.py", "L375–381 节选",
`def feed(self):
    self._last_feed = time.time()

@property
def engine_alive(self) -> bool:
    return time.time() - self._last_feed \\
        < self.engine_stale_s        # 5 s

# 发送线程（L421）
if self.engine_alive and (...):
    # 发出 HEARTBEAT`, 11);
code(s, 0.83, 4.95, 11.67, "③ 控制盒：心跳中断 30 s 且热源 > 60℃，本地断电", "firmware/lab_guard_esp32/lab_guard_esp32.ino", "L254–257",
`if (mlxOk && !isnan(objC) && objC >= HARD_LIMIT_C) cutPower(CUT_OVERTEMP, EV_LOCAL_OVERTEMP);
if (smokeReady() && smokeRaw >= SMOKE_LIMIT_RAW)   cutPower(CUT_SMOKE, EV_LOCAL_SMOKE);
bool hot = !mlxOk || isnan(objC) || objC > WATCHDOG_HOT_C;   // 测不到温度时按"可能很热"保守处理
if (relayOn && millis() - lastHb > WATCHDOG_CUT_MS && hot) cutPower(CUT_WATCHDOG, EV_WATCHDOG);`, 11);
orb(s, 160, 722, 0.2, "r");

s = slide("CONTENT", "断电", "串口协议：定长帧头 + CRC16 + ACK 重发", "帧格式：AA 55 帧头、长度、序号、命令、负载、CRC16-CCITT 小端。断电指令要 ACK，0.25 s 超时重发，最多发送 3 次。固件和仿真下位机共用这一协议，测试不需要硬件。");
T(s, "示例：POWER_OFF 指令，原因码 4（执行上位机断电），115200 波特", { x: 0.83, y: 1.4, w: 10, h: 0.3, fontSize: 12, color: MUTE });
let bx = 0.83;
[["AA", "帧头", 0.97, "hdr"], ["55", "帧头", 0.97, "hdr"], ["01", "LEN", 0.97], ["2A", "SEQ", 0.97], ["02", "CMD", 0.97, "cmd"], ["04", "PAYLOAD", 1.53], ["95", "CRC 低字节", 0.97, "crc"], ["95", "CRC 高字节", 0.97, "crc"]].forEach((b) => {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: bx, y: 1.82, w: b[2], h: 0.83, rectRadius: 0.08, fill: { color: b[3] === "hdr" ? "F4F6FB" : b[3] === "crc" ? "EBEDF7" : WHITE }, line: b[3] === "cmd" ? { color: R, width: 1.75 } : { color: "DDE0EA", width: 0.75 } });
  T(s, b[0], { x: bx, y: 1.86, w: b[2], h: 0.45, fontSize: 22, bold: true, color: INK, align: "center", fontFace: MONO });
  T(s, b[1], { x: bx, y: 2.3, w: b[2], h: 0.28, fontSize: 10, color: MUTE, align: "center" });
  bx += b[2] + 0.083;
});
s.addShape(pres.shapes.LINE, { x: 0.83 + 2 * 1.053, y: 2.78, w: 3 * 1.053 + 1.53, h: 0, line: { color: MUTE, width: 1 } });
T(s, "CRC16-CCITT 覆盖范围", { x: 0.83 + 2 * 1.053, y: 2.85, w: 3 * 1.053 + 1.53, h: 0.28, fontSize: 12, align: "center" });
orb(s, 838, 262, 0.2, "r");
code(s, 0.83, 3.35, 6.25, "帧构造与校验", "LabSafetyMonitor/serial_comm.py", "L105–118",
`def crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int:
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc

def build_frame(seq: int, cmd: int, payload: bytes = b"") -> bytes:
    body = bytes([len(payload), seq & 0xFF, cmd]) + payload
    return HEADER + body + struct.pack("<H", crc16_ccitt(body))`, 10);
kv(s, 7.45, 3.35, 5.05, [["ACK 超时", "ACK_TIMEOUT_S = 0.25", 1], ["最多发送", "ACK_MAX_TRIES = 3", 1], ["结果", "power_off_state 记录是否被确认"], ["一致性", "固件与 tests/fake_mcu.py 用同一协议"]], 1.35, 15);
T(s, "接收端按帧头重新同步：长度非法或 CRC 错误的帧直接丢弃，不完整的帧留到下一次读取再拼接。", { x: 7.45, y: 5.4, w: 5.05, h: 0.7, fontSize: 12, color: MUTE });


// ---------------- 总后台 ----------------
s = slide("CONTENT", "总后台", "总后台：同一栋楼，三个视角", "总后台三个视角自动轮换：学生端视角吃苹果那张桌是红的；实验室视角变绿；实验楼视角只剩断电锁定那张红。视角就是接口参数 tier。");
const DESKS = [["A01", 140, 330, "ggg"], ["A02", 280, 330, "ygg"], ["A03", 140, 430, "ggg"], ["A04", 280, 430, "ooo"], ["B01", 450, 330, "rry"], ["B02", 450, 430, "ggg"],
  ["C01", 660, 330, "yyg"], ["C02", 800, 330, "ygg"], ["C03", 660, 430, "rrr"], ["D01", 980, 330, "ggg"], ["D02", 980, 430, "ggg"], ["E02", 1250, 568, "ggg"], ["E01", 1450, 568, "rgg"]];
[["学生端视角", "与实验台上的提醒一致"], ["实验室视角", "只显示需要教师处置的实验桌"], ["实验楼视角", "只显示断电锁定与紧急事件"]].forEach((v, t) => {
  const ox = 0.83 + t * 3.95, oy = 1.7, f = 3.75 / 1600;
  card(s, ox, oy, 3.75, 4.9);
  T(s, v[0], { x: ox + 0.2, y: oy + 0.18, w: 3.3, h: 0.4, fontSize: 18, bold: true, color: INK });
  T(s, v[1], { x: ox + 0.2, y: oy + 0.58, w: 3.3, h: 0.3, fontSize: 11, color: MUTE });
  const hi = DESKS.filter((d) => d[3][t] === "r").length, mi = DESKS.filter((d) => d[3][t] === "y").length;
  level(s, ox + 0.2, oy + 0.98, "r", "高危 " + hi, 1.05); level(s, ox + 1.35, oy + 0.98, "y", "中危 " + mi, 1.05);
  [["一楼", 40, 500], ["二楼", 560, 520], ["三楼", 1100, 500]].forEach((fl) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: ox + fl[1] * f, y: oy + 1.6, w: fl[2] * f - 0.03, h: 2.9, rectRadius: 0.05, fill: { color: "F4F6FB" }, line: { color: "DDE0EA", width: 0.5 } });
    T(s, fl[0], { x: ox + fl[1] * f + 0.04, y: oy + 1.64, w: 0.6, h: 0.22, fontSize: 9, color: MUTE });
  });
  DESKS.forEach((d) => {
    const lv = d[3][t], dx = ox + d[1] * f - 0.15, dy = oy + 1.6 + (d[2] - 220) * 0.0072;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: dx, y: dy, w: 0.3, h: 0.42, rectRadius: 0.04,
      fill: lv === "o" ? { type: "none" } : { color: { g: G, y: Y, r: R }[lv], transparency: lv === "g" ? 85 : 0 }, line: lv === "o" ? { color: MUTE, width: 0.75, dashType: "dash" } : { type: "none" } });
    T(s, d[0], { x: dx - 0.05, y: dy, w: 0.4, h: 0.42, fontSize: 7, bold: true, color: lv === "g" ? "0C6B42" : lv === "o" ? MUTE : WHITE, align: "center", valign: "middle", fontFace: MONO });
  });
});
T(s, "演示数据：tools/center_demo.py，13 台模拟终端。视角即接口参数 GET /api/overview?tier=…", { x: 0.83, y: 6.68, w: 11, h: 0.3, fontSize: 12, color: MUTE });

s = slide("CONTENT", "总后台", "终端接入：一个上报接口，指令只有断电和静音", "终端每 2 秒调一次上报接口，带上快照和上次指令的执行结果；总后台返回区域阈值、待执行指令和语音包版本。指令白名单只有断电和静音。");
[[0.83, "实验台终端", "center_link.py"], [10.1, "总后台", "center/app.py"]].forEach((n) => {
  card(s, n[0], 1.45, 2.4, 1.05);
  T(s, n[1], { x: n[0] + 0.22, y: 1.58, w: 2.0, h: 0.45, fontSize: 20, bold: true, color: INK });
  T(s, n[2], { x: n[0] + 0.22, y: 2.05, w: 2.0, h: 0.3, fontSize: 11, color: MUTE, fontFace: MONO });
});
s.addShape(pres.shapes.LINE, { x: 3.4, y: 1.8, w: 6.55, h: 0, line: { color: MUTE, width: 1.25, endArrowType: "triangle" } });
T(s, "POST /api/node/report　X-Node-Token　每 2 s：snapshot、meta、acks", { x: 3.4, y: 1.5, w: 6.55, h: 0.28, fontSize: 11, align: "center", fontFace: MONO });
s.addShape(pres.shapes.LINE, { x: 3.4, y: 2.3, w: 6.55, h: 0, line: { color: MUTE, width: 1.25, beginArrowType: "triangle" } });
T(s, "返回 profile（区域阈值）、commands、voice（语音包版本）", { x: 3.4, y: 2.0, w: 6.55, h: 0.28, fontSize: 11, align: "center", fontFace: MONO });
code(s, 0.83, 2.85, 6.2, "node_report", "center/app.py", "L449–461 节选",
`@app.post("/api/node/report")
async def node_report(request: Request, n=Depends(node_auth)):
    data = await body(request)
    store.ack_commands(n["id"], data.get("acks") or {})
    store.record_report(n["id"], ..., snap, meta)
    prof = _resolved_rules(n["area_id"])
    cmds = store.pending_commands(n["id"])
    return {"profile": prof, "commands": [...],
            "voice": _voice_pack(n["area_id"]), ...}`, 9.5);
code(s, 7.25, 2.85, 5.25, "指令白名单", "center_link.py", "L145–155 节选",
`COMMANDS = ("cut_power", "mute")

def run_command(self, c):
    cmd, args = c.get("cmd"), c.get("args") or {}
    if cmd == "cut_power":
        return self.engine.cut_power(f"总后台·{who}")
    if cmd == "mute":
        until = self.engine.mute(...)
        return ...
    return "不支持的指令"   # 没有上电 / 解锁指令`, 9.5);
T(s, "执行结果在下一次上报的 acks 里回写；上报失败只记录，终端本机判断不受影响。", { x: 0.83, y: 5.75, w: 11.6, h: 0.35, fontSize: 12, color: MUTE });
orb(s, 500, 222, 0.2, "g");

s = slide("CONTENT", "总后台", "分层管理；下发的阈值在终端再校验一次", "账号、授权、阈值方案、语音包、审计都在总后台的 SQLite 里。阈值下发到终端后，终端按本机控制盒的硬上限重建白名单，超限项不生效并回报原因。");
[["账号与授权", "管理员和教师两种角色；教师只能看、管被授权的楼栋、房间或实验桌", "users、grants"], ["阈值方案", "出厂预设打底，按区域逐级覆盖", "profiles"],
 ["语音包", "每类提示温和、严厉两种语气；TTS 或教师本人录音", "voice_assets、voice_map"], ["复核与审计", "报警复核汇总现场准确率；所有操作写入审计", "audit"]].forEach((m, i) => {
  const x = 0.83 + (i % 2) * 3.1, y = 1.45 + Math.floor(i / 2) * 1.45;
  s.addShape(pres.shapes.LINE, { x, y, w: 2.9, h: 0, line: { color: "DDE0EA", width: 0.75 } });
  T(s, m[0], { x, y: y + 0.12, w: 2.9, h: 0.4, fontSize: 18, bold: true, color: INK });
  T(s, m[1], { x, y: y + 0.52, w: 2.9, h: 0.6, fontSize: 12 });
  T(s, m[2], { x, y: y + 1.1, w: 2.9, h: 0.25, fontSize: 9, color: MUTE, fontFace: MONO });
});
code(s, 0.83, 4.45, 6.0, "tunable_spec()", "src/core/tunable.py", "L38–44 节选",
`spec = dict(TUNABLE)
typ, lo, _, label, grp = spec["rules.dry_burn_c"]
spec["rules.dry_burn_c"] = (typ, lo, float(hard_limit_c) - 5, ...)
typ, lo, _, label, grp = spec["rules.smoke_raw"]
spec["rules.smoke_raw"] = (typ, lo, int(smoke_limit_raw) - 100, ...)`, 9.5);
s.addImage({ path: IMG, x: 7.2, y: 1.45, w: 5.3, h: 5.3 * 1000 / 1440, altText: "总后台总览页：处置队列与按楼层排布的实验桌平面图" });
T(s, "总后台总览页截图（演示数据）", { x: 7.2, y: 1.45 + 5.3 * 1000 / 1440 + 0.08, w: 5.3, h: 0.3, fontSize: 11, color: MUTE });
T(s, "终端 apply_profile() 按本机控制盒硬上限（150℃ / 2500）重建白名单，超限项不生效，原因写进事件，并在下一次上报的 profile_errors 里回报。", { x: 7.2, y: 5.6, w: 5.3, h: 0.8, fontSize: 12 });
orb(s, 1060, 641, 0.2, "g");

// ---------------- 验证 ----------------
s = slide("CONTENT", "验证", "设计约束写进自动测试", "只断不通、大模型不碰电闸，这些约束都写成了测试：扫描路由和工具名。三套测试共 212 个用例，用仿真下位机，不需要硬件。");
code(s, 0.83, 1.6, 7.0, "只断不通、大模型不碰电闸", "tests/test_platform.py", "L173, L231",
`names = {t["function"]["name"] for t in TOOLS}
check(not any(k in n for n in names for k in
              ("power", "relay", "reset", "unlock", "cut")),
      "Agent 工具表中没有任何电源 / 继电器 / 解锁类工具")

routes = {getattr(rt, "path", "") for rt in client.app.routes}
check(not any(k in p for p in routes for k in
              ("power/on", "power/restore", "unlock", "reset", "release")),
      "不存在任何上电 / 解锁接口")`, 10);
[["87", "test_backend", "安全核心、协议、控制键"], ["44", "test_platform", "控制台、助手、约束"], ["81", "test_center", "总后台、接入、分层"]].forEach((c, i) => {
  const x = 8.3 + i * 1.42; s.addShape(pres.shapes.LINE, { x, y: 1.6, w: 1.3, h: 0, line: { color: "DDE0EA", width: 0.75 } });
  T(s, c[0], { x, y: 1.75, w: 1.3, h: 0.6, fontSize: 32, bold: true, color: INK, fontFace: MONO });
  T(s, c[1] + "\n" + c[2], { x, y: 2.4, w: 1.35, h: 0.9, fontSize: 11, color: MUTE });
});
T(s, "测试用 tests/fake_mcu.py 模拟控制盒，数据库建在临时目录，不需要摄像头、控制盒和大模型。", { x: 8.3, y: 3.5, w: 4.2, h: 1.1, fontSize: 15 });
T(s, "用例数为仓库文档记录；答辩前请在比赛电脑上重跑一遍。", { x: 8.3, y: 4.7, w: 4.2, h: 0.6, fontSize: 12, color: MUTE });
orb(s, 1160, 240, 0.2, "g");

s = slide("CONTENT", "验证", "实物运行", "实物运行照片。");
[[0.83, 1.67, 5.83, 4.9, 1, "照片 1：实验台终端整机运行"], [7.0, 1.67, 5.5, 2.35, 2, "照片 2：控制盒与传感器接线"], [7.0, 4.22, 5.5, 2.35, 3, "照片 3：小屏提醒或总后台联调"]].forEach((p) =>
  s.addImage({ path: path.join(__dirname, "photo-" + p[4] + ".png"), x: p[0], y: p[1], w: p[2], h: p[3], altText: p[5], objectName: p[5] }));
orb(s, 160, 240, 0.2, "g");


// ---------------- 结尾 ----------------
s = slide("CONTENT", "结尾", null, "总结：需求落成三条工程约束，判断在本机、断电在硬件、提醒按三层分级、总后台管全楼。出发点是让做实验的同学在出事之前就被提醒。");
card(s, 5.6, 2.35, 2.13, 1.3, { rectRadius: 0.2, fill: { color: "F7F8FC" }, shadow: { type: "outer", color: "262E6E", blur: 18, offset: 6, angle: 90, opacity: 0.2 } });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.38, y: 2.72, w: 0.58, h: 0.58, rectRadius: 0.08, fill: { color: INK }, line: { type: "none" } });
T(s, "RK3588", { x: 6.28, y: 2.72, w: 0.78, h: 0.58, fontSize: 8, bold: true, color: "CBD1EE", align: "center", valign: "middle", fontFace: MONO });
orb(s, 1096, 399, 0.18, "g");
[["双摄识别", "YOLO11n，人员 12 类，器皿 14 类", 220, 150], ["交叉验证", "多源规则打分，分低、中、高三级", 780, 110], ["三层分级上报", "学生端、实验室老师、实验楼各自定级", 1340, 150],
 ["语音提示", "温和与严厉两种语气，可用教师本人录音", 1420, 420], ["总后台", "平面图、处置队列、阈值方案、授权", 1340, 690], ["控制盒断电", "固件硬规则与心跳看门狗，只断不通", 780, 700],
 ["安全助手", "只读工具，引用手册条款", 220, 690], ["温度预测", "一阶热平衡拟合；越过沸点才给干烧倒计时", 140, 420]].forEach((r) => {
  card(s, px(r[2]), px(r[3]), px(360), 0.95, { shadow: { type: "outer", color: "262E6E", blur: 14, offset: 4, angle: 90, opacity: 0.14 } });
  T(s, r[0], { x: px(r[2]) + 0.18, y: px(r[3]) + 0.12, w: px(360) - 0.36, h: 0.38, fontSize: 17, bold: true, color: INK });
  T(s, r[1], { x: px(r[2]) + 0.18, y: px(r[3]) + 0.5, w: px(360) - 0.36, h: 0.4, fontSize: 11 });
});
s.addText("防患于未然", { isTextBox: true, x: 1, y: px(872), w: 11.33, h: 0.6, fontSize: 30, bold: true, fontFace: HEAD, color: INK, align: "center", margin: 0 });
T(s, "基于双摄协同的实验室安全事前干预监测系统", { x: 1, y: px(872) + 0.6, w: 11.33, h: 0.3, fontSize: 13, color: MUTE, align: "center" });

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("written", OUT, n, "slides");
})();
