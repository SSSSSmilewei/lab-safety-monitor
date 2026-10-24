// 生成答辩 PPT：node slides/pptx/build.js  →  slides/实验室安全答辩.pptx
// 内容与 slides/web/index.html 一一对应（7 章 22 页）；照片页为图片占位符，在 PowerPoint 里点图标即可插入。
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.PPTX_SKILL_DIR ? path.join(process.env.PPTX_SKILL_DIR, "scripts/apply_theme.js") : "/mnt/skills/public/pptx/scripts/apply_theme.js");

const OUT = path.join(__dirname, "..", "实验室安全答辩.pptx");
const IMG = path.join(__dirname, "..", "web", "img", "center-floorplan.png");
const THEME = {
  name: "LabGuard",
  headFontFace: "Microsoft YaHei",
  bodyFontFace: "Microsoft YaHei",
  colors: { dk1: "1A1F3D", lt1: "FFFFFF", dk2: "4E5577", lt2: "F1F3F8", accent1: "16A362", accent2: "EC9808", accent3: "E03A32", accent4: "5C6BC0", accent5: "171B33", accent6: "7F86A3", hlink: "5C6BC0", folHlink: "4E5577" },
};
const HEX = { ink: "1A1F3D", g: "16A362", y: "EC9808", r: "E03A32", n: "969DB8", code: "171B33" };
const MONO = "Consolas";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 × 7.5 in；1 in = 144 px（与网页 1920×1080 舞台同比例）
pres.title = "基于双摄协同的实验室安全事前干预监测系统";
pres.author = "湖南涉外经济学院 3 队";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const INK = C.text1, INK2 = C.text2, BG = C.background2, WHITE = C.background1;
const G = C.accent1, Y = C.accent2, R = C.accent3, IND = C.accent4, CODE = C.accent5, MUTE = C.accent6;
const px = (v) => v / 144;

// ---------------- 版式 ----------------
const footer = { text: { text: "基于双摄协同的实验室安全事前干预监测系统", options: { x: 0.83, y: 7.05, w: 7, h: 0.3, fontSize: 10, color: MUTE, margin: 0 } } };
pres.defineSlideMaster({
  title: "TITLE", background: { color: BG },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 1, y: 3.4, w: 11.33, h: 1.8, fontSize: 48, bold: true, color: INK, align: "center", valign: "middle" }, text: "" } },
            { placeholder: { options: { name: "body", type: "body", x: 1, y: 5.35, w: 11.33, h: 0.6, fontSize: 18, color: MUTE, align: "center" }, text: "" } }],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: BG },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.83, y: 0.55, w: 11.6, h: 0.8, fontSize: 32, bold: true, color: INK, valign: "middle", align: "left", margin: 0 }, text: "" } }, footer],
  slideNumber: { x: 12.2, y: 7.05, w: 0.5, h: 0.3, fontSize: 10, color: MUTE, align: "right" },
});
pres.defineSlideMaster({
  title: "PHOTO3", background: { color: BG },
  objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.83, y: 0.55, w: 11.6, h: 0.8, fontSize: 32, bold: true, color: INK, valign: "middle", margin: 0 }, text: "" } },
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
const T = (s, text, o) => s.addText(text, Object.assign({ isTextBox: true, margin: 0, color: INK2, fontSize: 16, valign: "top", paraSpaceAfter: 4 }, o));
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
let s = slide("TITLE", "片头", null, "开场：不是又一套天花板监控，而是放在每张实验桌上的安全终端：识别风险、现场提醒、必要时由硬件断电。");
s.addText("基于双摄协同的实验室安全\n事前干预监测系统", { placeholder: "title" });
s.addText("放在每一张实验桌上的安全终端", { placeholder: "body" });
orb(s, 960, 400, 0.85, "g", "信号灯（片头）");

// ---------------- 需求 ----------------
function camera(s) {
  s.addShape(pres.shapes.RECTANGLE, { x: px(296), y: 0, w: px(8), h: px(175), fill: { color: "CDD2E3" }, line: { type: "none" } });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: px(180), y: px(170), w: px(250), h: px(120), rectRadius: px(60), fill: { color: WHITE }, line: { color: "DDE0EA", width: 0.75 }, shadow: { type: "outer", color: "262E6E", blur: 18, offset: 6, angle: 90, opacity: 0.18 } });
  orb(s, 362, 230, 0.52, "n", "监控镜头");
}
s = slide("CONTENT", "需求", null, "现有监控只记录已发生的事：事故发生时不能干预，事故发生前不能预警。");
camera(s);
s.addText("监控只能事后回看", { isTextBox: true, x: px(760), y: px(230), w: 7, h: 0.9, fontSize: 40, bold: true, color: INK, margin: 0 });
T(s, "天花板监控记录的是已经发生的事。事故发生时它不能干预，事故发生前它也不能预警。", { x: px(760), y: px(360), w: 6.8, h: 1, fontSize: 20 });
steps(s, px(760), px(520), ["事故发生", "录像存档", "事后调取"]);

s = slide("CONTENT", "需求", null, "俯拍看不清台面细节：器皿种类、离桌边距离、温度都分辨不出；几十路画面也不可能有人实时盯守。");
camera(s);
s.addShape(pres.shapes.RIGHT_TRIANGLE, { x: px(362), y: px(262), w: px(398), h: px(638), fill: { color: IND, transparency: 92 }, line: { type: "none" }, flipH: false });
s.addText("看得到人，\n看不清台面", { isTextBox: true, x: 0.83, y: px(380), w: 3.9, h: 1.3, fontSize: 30, bold: true, color: INK, margin: 0 });
T(s, "俯拍画面里分辨不出器皿种类、离桌边的距离和温度。一间实验室几十路画面，也不可能有人实时盯守。", { x: 0.83, y: px(560), w: 3.75, h: 1.6, fontSize: 16 });
card(s, px(760), px(320), px(1020), px(580), { fill: { color: "E8EBF4" } });
[[80, 120], [400, 120], [720, 120], [80, 360], [400, 360], [720, 360]].forEach((d) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: px(760 + d[0]), y: px(320 + d[1]), w: px(210), h: px(90), rectRadius: 0.08, fill: { color: IND, transparency: 80 }, line: { type: "none" } }));
s.addShape(pres.shapes.OVAL, { x: px(1290), y: px(520), w: px(340), h: px(340), fill: { color: WHITE }, line: { color: "DDE0EA", width: 0.75 }, shadow: { type: "outer", color: "262E6E", blur: 18, offset: 6, angle: 90, opacity: 0.2 } });
T(s, "烧杯还是量筒？\n离桌边多远？\n热源多少度？", { x: px(1290), y: px(520), w: px(340), h: px(340), fontSize: 17, align: "center", valign: "middle", lineSpacingMultiple: 1.4 });

s = slide("CONTENT", "需求", null, "防患于未然：先识别风险并现场提醒；风险继续升级，由控制盒直接切断加热电源。");
orb(s, 250, 250, 0.62, "g");
s.addText("防患于未然", { isTextBox: true, x: px(200), y: px(330), w: 10, h: 1.9, fontSize: 96, bold: true, color: INK, margin: 0 });
T(s, "在事故发生之前识别风险：先在现场提醒操作者；风险继续升级，由控制盒直接切断加热电源。", { x: px(200), y: px(640), w: 10.5, h: 0.9, fontSize: 20 });
steps(s, px(200), px(820), ["1  识别风险", "2  现场提醒", "3  硬件断电"]);

// ---------------- 识别 ----------------
s = slide("CONTENT", "识别", "两路摄像头分工：全景看人，台面看器皿", "全景摄像头跑人员模型（12 类：五类防护及其未佩戴类、进食、饮水），台面摄像头跑器皿模型（14 类）。");
[[160, "全景摄像头", "人员模型，12 类", ["护目镜", "手套", "实验服", "口罩", "头罩", "以上五项的未佩戴类", "进食", "饮水"]],
 [980, "台面摄像头", "器皿模型，14 类", ["烧杯", "锥形瓶", "圆底烧瓶", "平底烧瓶", "梨形瓶", "试管", "量筒", "容量瓶", "滴定管", "移液管", "试剂瓶", "洗瓶", "漏斗", "滴定装置"]]].forEach((col, ci) => {
  const x = px(col[0]); card(s, x, px(270), px(780), px(640));
  T(s, col[1], { x: x + 0.24, y: px(270) + 0.22, w: 3, h: 0.45, fontSize: 22, bold: true, color: INK });
  T(s, col[2], { x: x + 2.6, y: px(270) + 0.26, w: 2.55, h: 0.4, fontSize: 13, color: MUTE, align: "right" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.24, y: px(270) + 0.82, w: px(780) - 0.48, h: 1.85, rectRadius: 0.12, fill: { color: "EEF1F8" }, line: { color: "DDE0EA", width: 0.75 } });
  if (ci === 0) {
    s.addShape(pres.shapes.OVAL, { x: x + 2.1, y: px(270) + 1.0, w: 0.62, h: 0.62, fill: { color: "C9CEE2" }, line: { type: "none" } });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 1.83, y: px(270) + 1.68, w: 1.17, h: 0.9, rectRadius: 0.3, fill: { color: "D7DBEA" }, line: { type: "none" } });
    s.addShape(pres.shapes.RECTANGLE, { x: x + 2.04, y: px(270) + 1.05, w: 0.74, h: 0.3, fill: { type: "none" }, line: { color: R, width: 1.5, dashType: "dash" } });
    T(s, "No googles", { x: x + 2.04, y: px(270) + 0.78, w: 1.2, h: 0.24, fontSize: 11, bold: true, color: R });
  } else {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 1.5, y: px(270) + 1.3, w: 0.8, h: 1.0, rectRadius: 0.08, fill: { color: IND, transparency: 70 }, line: { color: "9AA4D6", width: 1.5 } });
    s.addShape(pres.shapes.RECTANGLE, { x: x + 1.42, y: px(270) + 1.2, w: 0.96, h: 1.2, fill: { type: "none" }, line: { color: G, width: 1.5, dashType: "dash" } });
    T(s, "Beaker", { x: x + 1.42, y: px(270) + 0.96, w: 1, h: 0.24, fontSize: 11, bold: true, color: G });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 3.4, y: px(270) + 1.0, w: 0.36, h: 1.3, rectRadius: 0.05, fill: { color: IND, transparency: 80 }, line: { color: "9AA4D6", width: 1.5 } });
    s.addShape(pres.shapes.RECTANGLE, { x: x + 3.32, y: px(270) + 0.94, w: 0.52, h: 1.42, fill: { type: "none" }, line: { color: Y, width: 1.5, dashType: "dash" } });
    T(s, "Measuring Cylinder", { x: x + 2.6, y: px(270) + 0.7, w: 1.8, h: 0.24, fontSize: 11, bold: true, color: Y, align: "right" });
  }
  T(s, col[3].join("　"), { x: x + 0.24, y: px(270) + 2.85, w: px(780) - 0.48, h: 1.3, fontSize: 15, color: INK, lineSpacingMultiple: 1.5 });
});
T(s, "检测框标签为模型原始类别名。两个模型共享一套推理线程，按配置的帧率轮流推理。", { x: 0.83, y: px(935), w: 11, h: 0.35, fontSize: 12, color: MUTE });
orb(s, 1756, 274, 0.22, "g");

s = slide("CONTENT", "识别", "YOLO11n 微调，各约 2.59 M 参数", "人员模型 80 轮，mAP@0.5 为 89.0%；器皿模型 50 轮，mAP@0.5 为 89.3%，mAP@0.5:0.95 为 73.7%。这是验证集上的检测指标，不是事故识别准确率。");
const CUR = require("./curves.json");
[[160, "人员模型", "全景摄像头，12 类，80 epoch", "ppe", [["mAP@0.5", "89.0%"], ["Precision", "83.4%"], ["Recall", "87.7%"], ["mAP@0.5:0.95", "64.3%"]]],
 [980, "器皿模型", "台面摄像头，14 类，50 epoch", "chem", [["mAP@0.5", "89.3%"], ["Precision", "86.7%"], ["Recall", "85.1%"], ["mAP@0.5:0.95", "73.7%"]]]].forEach((m) => {
  const x = px(m[0]); card(s, x, px(270), px(780), px(660));
  T(s, m[1], { x: x + 0.24, y: px(270) + 0.22, w: 2, h: 0.45, fontSize: 22, bold: true, color: INK });
  T(s, m[2], { x: x + 2.2, y: px(270) + 0.27, w: 2.95, h: 0.4, fontSize: 13, color: MUTE, align: "right" });
  m[4].forEach((v, i) => {
    T(s, v[1], { x: x + 0.24 + i * 1.24, y: px(270) + 0.8, w: 1.2, h: 0.5, fontSize: 24, bold: true, color: INK, fontFace: MONO });
    T(s, v[0], { x: x + 0.24 + i * 1.24, y: px(270) + 1.3, w: 1.2, h: 0.3, fontSize: 11, color: MUTE });
  });
  const c = CUR[m[3]], labels = c.a.map((_, i) => String(i + 1));
  s.addChart(pres.charts.LINE, [{ name: "mAP@0.5", labels, values: c.a }, { name: "mAP@0.5:0.95", labels, values: c.b }], {
    x: x + 0.15, y: px(270) + 1.7, w: px(780) - 0.3, h: 2.7, chartColors: [HEX.ink, "9AA4D6"], lineSize: 2, lineDataSymbol: "none",
    valAxisMinVal: 0, valAxisMaxVal: 1, valAxisMajorUnit: 0.25, valAxisLabelFormatCode: "0.00", catAxisLabelFrequency: 10,
    valAxisLabelColor: "7F86A3", catAxisLabelColor: "7F86A3", valAxisLabelFontSize: 10, catAxisLabelFontSize: 10, valAxisLabelFontFace: "+mn-lt", catAxisLabelFontFace: "+mn-lt",
    valGridLine: { color: "E3E6EF", size: 0.75 }, catGridLine: { style: "none" }, catAxisLabelRotate: 0, showLegend: true, legendPos: "b", legendFontSize: 11, legendColor: "4E5577", legendFontFace: "+mn-lt",
    showTitle: true, title: "验证集指标随 epoch 变化", titleFontSize: 12, titleColor: "4E5577", titleFontFace: "+mn-lt" });
});
T(s, "指标为训练结束时验证集上的目标检测指标，数据来自 models/model_card.json", { x: 0.83, y: px(212), w: 10, h: 0.3, fontSize: 12, color: MUTE });
orb(s, 1760, 150, 0.2, "g");

s = slide("CONTENT", "识别", "从检测框到事件：时间窗口投票", "检测结果先过时间窗口投票：3 s 窗口内命中帧占比 ≥60% 才确认，≤20% 才解除，单帧误检不会触发提醒。NPU 单帧推理人员 120 ms、器皿 116 ms。");
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
kv(s, px(1130), px(700), 4.35, [["NPU 单帧推理", "人员 120 ms / 器皿 116 ms"], ["模型格式", "RKNN → ONNX → .pt 依次回退"]], 1.6, 15);
T(s, "RK3588 实测，rknn-toolkit2 2.3.2，FP16；tools/check_npu.py 对比检测结果与 .pt 一致", { x: px(1130), y: px(860), w: 4.35, h: 0.6, fontSize: 12, color: MUTE });
orb(s, 1060, 260, 0.2, "g");

// ---------------- 面向学生 ----------------
s = slide("CONTENT", "面向学生", "演示：吃苹果的同学", "演示：摘下护目镜时温和提示；咬一口苹果再提示，小屏逐条列出要做的事；分数叠加后信号灯变红。");
T(s, "摘下头罩、护目镜、口罩，在实验台前吃苹果。", { x: 0.83, y: px(232) - 0.1, w: 8, h: 0.5, fontSize: 20 });
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
[[400, "同学，记得戴好护目镜哦，眼睛只有一双。"], [640, "实验区不能吃东西喝水哦，请到室外再吃。"]].forEach((b) => {
  card(s, px(1080), px(b[0]), px(700), 1.25, { shadow: { type: "outer", color: "262E6E", blur: 16, offset: 5, angle: 90, opacity: 0.16 } });
  level(s, px(1080) + 0.25, px(b[0]) + 0.18, "y", "温和语气", 1.35);
  T(s, "语音提示", { x: px(1080) + 1.7, y: px(b[0]) + 0.18, w: 1.5, h: 0.38, fontSize: 12, color: MUTE, valign: "middle" });
  T(s, "「" + b[1] + "」", { x: px(1080) + 0.25, y: px(b[0]) + 0.62, w: px(700) - 0.5, h: 0.55, fontSize: 18, color: INK });
});

s = slide("CONTENT", "面向学生", "学生是第一用户", "学生是第一用户：目标是减少火灾和伤害。每张实验桌一台终端，判断在本机完成，断网也照常工作。");
T(s, "系统的首要目标是减少火灾和人身伤害，而不是记录违规。所以提醒先发给台前的学生，管理端只接收需要处理的事件。", { x: 0.83, y: 1.6, w: 10.5, h: 1, fontSize: 20 });
orb(s, 230, 860, 0.62, "g");
[["每张实验桌一台终端", "RK3588 开发板、两路 USB 摄像头、控制盒与传感器、小屏；硬件采购估算 1000–1350 元"],
 ["判断在本机完成", "识别、打分和断电不依赖网络；与总后台断开时终端照常工作，恢复后自动重连"],
 ["小屏按现场设计", "按钮不小于 64 px，戴手套可操作；状态同时用颜色、形状和文字表示"]].forEach((f, i) => {
  const x = px(330) + i * 3.3; s.addShape(pres.shapes.LINE, { x, y: px(620), w: 3.1, h: 0, line: { color: "DDE0EA", width: 0.75 } });
  T(s, f[0], { x, y: px(620) + 0.2, w: 3.05, h: 0.5, fontSize: 20, bold: true, color: INK });
  T(s, f[1], { x, y: px(620) + 0.75, w: 3.05, h: 1.3, fontSize: 15 });
});

s = slide("CONTENT", "面向学生", "第一个分叉：风险分三级", "第一个分叉：交叉验证是多源规则打分，不是机器学习里的交叉验证。30 分以下低危，70 分以上高危，低中危温和语气，高危严厉语气。");
T(s, "交叉验证（多源规则打分）：人员模型、器皿模型、传感器和温度预测的结果合在一起计分，30 分为中危界，70 分为高危界，可按区域调整。", { x: 0.83, y: 1.5, w: 11.6, h: 0.8, fontSize: 17 });
const ax = px(240), aw = px(1440), ay = px(556);
[[0, 0.3, G], [0.3, 0.7, Y], [0.7, 1, R]].forEach((seg) => s.addShape(pres.shapes.RECTANGLE, { x: ax + aw * seg[0], y: ay, w: aw * (seg[1] - seg[0]), h: 0.06, fill: { color: seg[2], transparency: 45 }, line: { type: "none" } }));
[[0, "0"], [0.3, "30"], [0.7, "70"], [1, "100"]].forEach((t) => { s.addShape(pres.shapes.LINE, { x: ax + aw * t[0], y: ay + 0.12, w: 0, h: 0.12, line: { color: MUTE, width: 1 } }); T(s, t[1], { x: ax + aw * t[0] - 0.4, y: ay + 0.28, w: 0.8, h: 0.3, fontSize: 13, color: MUTE, align: "center", fontFace: MONO }); });
orb(s, 456, 560, 0.3, "g"); orb(s, 1176, 560, 0.3, "y"); orb(s, 1680, 560, 0.3, "r");
[[240, "g", "低危　15 分", "未加热，整理器皿时未戴手套", "温和提示：佩戴手套"], [740, "y", "中危　65 分", "加热中台面有量筒，且未戴护目镜", "移出量器，改用烧杯或锥形瓶加热"],
 [1240, "r", "高危　100 分", "越过沸点仍在升温，液体可能已烧干", "严厉语气：立即降低火力或补充液体"]].forEach((c) => {
  card(s, px(c[0]), px(680), px(440), 1.75); level(s, px(c[0]) + 0.2, px(680) + 0.2, c[1], c[2], 1.7);
  T(s, c[3], { x: px(c[0]) + 0.2, y: px(680) + 0.7, w: px(440) - 0.4, h: 0.6, fontSize: 16, color: INK });
  T(s, c[4], { x: px(c[0]) + 0.2, y: px(680) + 1.25, w: px(440) - 0.4, h: 0.4, fontSize: 13 });
});

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

s = slide("CONTENT", "面向学生", "安全助手：只读，只建议", "安全助手读取打分结果和安全手册，写原因、步骤和条款；三条线路：通义千问、本地 Ollama、离线规则模板。工具表只有 4 个只读工具。");
card(s, 0.83, 1.65, 6.25, 3.55);
T(s, "处置建议", { x: 1.75, y: 1.85, w: 3, h: 0.45, fontSize: 22, bold: true, color: INK });
T(s, "警告与紧急事件自动生成", { x: 4.3, y: 1.9, w: 2.55, h: 0.35, fontSize: 12, color: MUTE, align: "right" });
orb(s, 226, 300, 0.2, "r");
kv(s, 1.13, 2.5, 5.7, [["风险等级", "高危"], ["当前工况", "加热中（沸腾 / 高温阶段）"], ["主要依据", "越过沸点仍在升温；干烧风险分 0.70"], ["处置步骤", "1. 立即降低火力或补充液体；2. 回到实验台查看液面"], ["手册条款", "《实验室安全手册》1.3 沸腾阶段的注意事项"]], 1.4, 14);
T(s, "读取交叉验证结果和安全手册（BM25 检索），生成原因、步骤和条款引用。工具表只有 4 个只读工具，没有任何电源控制接口。", { x: 7.6, y: 1.65, w: 4.9, h: 1.6, fontSize: 17 });
kv(s, 7.6, 3.5, 4.9, [["远程通义千问", "联网"], ["本地 Ollama", "局域网"], ["规则模板", "离线兜底"]], 2.6, 17);

s = slide("CONTENT", "面向学生", "最后一道防线：只断不通", "断电链路：开发板发 POWER_OFF，控制盒断继电器回 ACK，0.25 s 超时重发最多 3 次，往返中位 4.9 ms。控制盒另有 150℃、烟雾 2500、心跳 30 s 的本地硬规则。只断不通。");
[["开发板", "规则判定需断电", 160], ["控制盒", "ESP32-S3", 810], ["加热电源", "已断开", 1460]].forEach((nd, i) => {
  card(s, px(nd[2]), px(300), px(300), 0.95);
  T(s, nd[0], { x: px(nd[2]), y: px(300) + 0.12, w: px(300), h: 0.4, fontSize: 19, color: INK, align: "center" });
  T(s, nd[1], { x: px(nd[2]), y: px(300) + 0.52, w: px(300), h: 0.3, fontSize: 12, color: MUTE, align: "center" });
  if (i < 2) { const x0 = px(nd[2] + 320), x1 = px([810, 1460][i] - 20); s.addShape(pres.shapes.LINE, { x: x0, y: px(300) + 0.48, w: x1 - x0, h: 0, line: { color: MUTE, width: 1.25, endArrowType: "triangle" } });
    T(s, ["POWER_OFF 0x02", "断开继电器"][i], { x: x0, y: px(300) + 0.08, w: x1 - x0, h: 0.3, fontSize: 12, align: "center", fontFace: MONO }); }
});
T(s, "控制盒回 ACK；0.25 s 未收到则重发，最多 3 次。真机实测 ACK 往返时延中位数 4.9 ms。", { x: 0.83, y: px(440), w: 11, h: 0.35, fontSize: 13, color: MUTE });
card(s, px(160), px(560), px(480), px(330), { rectRadius: 0.22 });
[0, 1, 2].forEach((k) => s.addShape(pres.shapes.OVAL, { x: px(210) + k * 0.35, y: px(610), w: 0.21, h: 0.21, fill: { color: "E3E6EF" }, line: { type: "none" } }));
orb(s, 225, 625, 0.22, "r");
s.addShape(pres.shapes.OVAL, { x: px(160 + 480 - 56 - 92), y: px(560 + 330 - 56 - 92), w: px(92), h: px(92), fill: { color: WHITE }, line: { color: "DDE0EA", width: 1.5 } });
T(s, "长按 2 秒", { x: px(160 + 480 - 56 - 92), y: px(560 + 330 - 56 - 92), w: px(92), h: px(92), fontSize: 10, align: "center", valign: "middle" });
T(s, "控制盒", { x: px(210), y: px(820), w: 1.5, h: 0.3, fontSize: 13, color: MUTE });
[["开发板规则（可按区域调整）", "R1 热源 ≥ 120℃\nR3 加热中无人 60 s\nR5 烟雾读数 ≥ 1800", 720], ["控制盒本地硬规则（写在固件里）", "热源 ≥ 150℃\n烟雾读数 ≥ 2500\n心跳中断 30 s 且仍在加热", 1260]].forEach((r) => {
  s.addShape(pres.shapes.LINE, { x: px(r[2]), y: px(540), w: 3.5, h: 0, line: { color: "DDE0EA", width: 0.75 } });
  T(s, r[0], { x: px(r[2]), y: px(540) + 0.15, w: 3.5, h: 0.3, fontSize: 12, color: MUTE });
  T(s, r[1], { x: px(r[2]), y: px(540) + 0.48, w: 3.5, h: 1.1, fontSize: 16, color: INK, lineSpacingMultiple: 1.2 });
});
s.addShape(pres.shapes.LINE, { x: px(720), y: px(800), w: 7.2, h: 0, line: { color: "DDE0EA", width: 0.75 } });
T(s, "恢复供电", { x: px(720), y: px(800) + 0.2, w: 1.4, h: 0.45, fontSize: 20, bold: true, color: INK });
T(s, "软件和总后台都没有通电接口。复电只能在现场长按控制键 2 秒，控制盒先复查温度和烟雾，超标则拒绝。", { x: px(720) + 1.5, y: px(800) + 0.2, w: 5.7, h: 0.8, fontSize: 15 });

// ---------------- 总后台 ----------------
s = slide("CONTENT", "总后台", "总后台：同一栋楼，三个视角", "总后台三个视角：学生端视角吃苹果那张桌是红的；实验室视角变绿；实验楼视角只剩断电锁定那张红、加热无人那张标关注。");
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
T(s, "演示数据：tools/center_demo.py，一栋三层楼、13 台模拟终端；E01 为「摘防护吃苹果」场景", { x: 0.83, y: 6.68, w: 11, h: 0.3, fontSize: 12, color: MUTE });

s = slide("CONTENT", "总后台", "一套后台，分层管理", "管理员对应实验楼，教师只管被授权的区域；阈值按区域下发，终端按硬上限再校验；语音包、复核、审计都在总后台。");
[["账号与授权", "管理员管理整栋楼；教师只能查看和管理被授权的楼栋、房间或实验桌。"], ["阈值方案", "按区域下发规则阈值；终端再按本机控制盒硬上限校验，超限项不生效并回报原因。"],
 ["语音包", "每类提示配温和、严厉两种语气；可用 TTS 生成，也可上传教师本人录音（需本人同意）。"], ["复核与审计", "教师在终端标注报警是否正确，总后台汇总现场准确率；所有操作写入审计记录。"]].forEach((m, i) => {
  const x = 0.83 + (i % 2) * 3.25, y = 1.75 + Math.floor(i / 2) * 2.35;
  s.addShape(pres.shapes.LINE, { x, y, w: 2.95, h: 0, line: { color: "DDE0EA", width: 0.75 } });
  T(s, m[0], { x, y: y + 0.18, w: 2.95, h: 0.45, fontSize: 20, bold: true, color: INK });
  T(s, m[1], { x, y: y + 0.7, w: 2.95, h: 1.4, fontSize: 15 });
});
s.addImage({ path: IMG, x: 7.75, y: 1.75, w: 4.75, h: 4.75 * 1000 / 1440, rounding: false, altText: "总后台总览页：处置队列与按楼层排布的实验桌平面图" });
T(s, "总后台总览页截图（演示数据）", { x: 7.75, y: 1.75 + 4.75 * 1000 / 1440 + 0.1, w: 4.75, h: 0.3, fontSize: 12, color: MUTE });
orb(s, 1752, 948, 0.2, "g");

// ---------------- 工程实现 ----------------
s = slide("CONTENT", "工程实现", "系统组成：三个独立程序", "三个独立程序：控制盒固件、实验台终端 run_app.py、总后台 run_center.py。安全判断在 SafetyEngine 里，所有界面只读快照。");
function mod(s, x, y, w, h, t, sub, core) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.07, fill: { color: core ? INK : "F4F6FB" }, line: core ? { type: "none" } : { color: "DDE0EA", width: 0.5 } });
  s.addText([{ text: t, options: { fontSize: 13, color: core ? WHITE : INK, breakLine: !!sub } }].concat(sub ? [{ text: sub, options: { fontSize: 9, color: core ? "A9B0D3" : MUTE, fontFace: MONO } }] : []),
    { isTextBox: true, x: x + 0.1, y, w: w - 0.2, h, margin: 0, valign: "middle" });
}
card(s, 0.83, 1.7, 2.7, 3.95); T(s, "控制盒", { x: 1.0, y: 1.85, w: 2.4, h: 0.4, fontSize: 20, bold: true, color: INK }); T(s, "ESP32-S3 · Arduino 固件", { x: 1.0, y: 2.25, w: 2.4, h: 0.25, fontSize: 10, color: MUTE, fontFace: MONO });
mod(s, 1.0, 2.6, 2.36, 0.85, "SHT30 温湿度\nMLX90614 红外测温\nMQ-2 烟雾"); mod(s, 1.0, 3.55, 2.36, 0.65, "继电器（加热电源）\n控制键、信号灯、蜂鸣器"); mod(s, 1.0, 4.3, 2.36, 0.6, "本地硬规则", "150℃ / 2500 / 心跳 30 s", true);
card(s, 4.72, 1.7, 4.6, 3.95); T(s, "实验台终端", { x: 4.9, y: 1.85, w: 3, h: 0.4, fontSize: 20, bold: true, color: INK }); T(s, "RK3588 · Python · run_app.py", { x: 4.9, y: 2.25, w: 3.5, h: 0.25, fontSize: 10, color: MUTE, fontFace: MONO });
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

s = slide("CONTENT", "工程实现", "程序卡死也能断电：心跳由安全判断驱动", "心跳不是定时器发的：只有安全判断每次跑完调用 feed()，发送线程才发心跳。程序卡死 5 s 心跳就停，控制盒 30 s 收不到心跳且仍在加热就本地断电。");
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
code(s, 0.83, 4.95, 11.67, "③ 控制盒：心跳中断 30 s 且仍在加热，本地断电", "firmware/lab_guard_esp32/lab_guard_esp32.ino", "L254–257",
`if (mlxOk && !isnan(objC) && objC >= HARD_LIMIT_C) cutPower(CUT_OVERTEMP, EV_LOCAL_OVERTEMP);
if (smokeReady() && smokeRaw >= SMOKE_LIMIT_RAW)   cutPower(CUT_SMOKE, EV_LOCAL_SMOKE);
bool hot = !mlxOk || isnan(objC) || objC > WATCHDOG_HOT_C;   // 测不到温度时按"可能很热"保守处理
if (relayOn && millis() - lastHb > WATCHDOG_CUT_MS && hot) cutPower(CUT_WATCHDOG, EV_WATCHDOG);`, 11);
orb(s, 160, 722, 0.2, "r");

s = slide("CONTENT", "工程实现", "串口协议：定长帧头 + CRC16 + ACK 重发", "帧格式：AA 55 帧头、长度、序号、命令、负载、CRC16-CCITT 小端。断电指令要 ACK，0.25 s 超时重发，最多 3 次。固件和仿真下位机共用这一协议。");
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
T(s, "接收端按帧头重新同步，半个包头会保留到下一次读取；CRC 错误计数可在控制台查看。", { x: 7.45, y: 5.4, w: 5.05, h: 0.7, fontSize: 12, color: MUTE });

s = slide("CONTENT", "工程实现", "分层上报的实现：同一份打分，三次过滤", "分层上报只是在同一份打分上做三次过滤：老师层去掉行为因子，实验楼层只看断电锁定和紧急事件。等级随快照上报，不参与断电。");
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

s = slide("CONTENT", "工程实现", "设计约束写进自动测试", "只断不通、大模型不碰电闸，这些约束都写成了测试：扫描路由和工具名。三套测试共 212 个用例，不需要硬件。");
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

s = slide("CONTENT", "工程实现", "实物运行", "实物运行照片：整机、控制盒接线、现场提醒。在 PowerPoint 里右键占位图 → 更改图片，位置和尺寸会保留。");
[[0.83, 1.67, 5.83, 4.9, 1, "照片 1：实验台终端整机运行"], [7.0, 1.67, 5.5, 2.35, 2, "照片 2：控制盒与传感器接线"], [7.0, 4.22, 5.5, 2.35, 3, "照片 3：小屏提醒或总后台联调"]].forEach((p) =>
  s.addImage({ path: path.join(__dirname, "photo-" + p[4] + ".png"), x: p[0], y: p[1], w: p[2], h: p[3], altText: p[5], objectName: p[5] }));
orb(s, 160, 240, 0.2, "g");

// ---------------- 结尾 ----------------
s = slide("CONTENT", "结尾", null, "总结：看清台面、按风险分级提醒、三层各自定级、危险时硬件断电、总后台管全楼。出发点是让做实验的同学在出事之前就被提醒。");
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
s.addText("防患于未然", { isTextBox: true, x: 1, y: px(872), w: 11.33, h: 0.6, fontSize: 30, bold: true, color: INK, align: "center", margin: 0 });
T(s, "基于双摄协同的实验室安全事前干预监测系统", { x: 1, y: px(872) + 0.6, w: 11.33, h: 0.3, fontSize: 13, color: MUTE, align: "center" });

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("written", OUT, n, "slides");
})();
