# 答辩网页演示

浏览器打开 `index.html` 即可（断网可用，字体在 `fonts/`）。

- 翻页：→ / 空格 / 点击画面右侧；← / 点击画面左侧返回；底部章节栏可跳转
- `N` 显示 / 隐藏提词，`F` 全屏
- 网址末尾加 `#b9` 可直接打开第 9 拍
- 8 章 24 拍，从第 2 拍起每页都对应仓库里的具体模块和代码；平面图等级来自 `labguard/tools/center_demo.py` 的演示场景，模型曲线来自 `labguard/models/model_card.json`

## 字体

- 标题：思源宋体（SemiBold）；正文：更纱黑体；代码：等距更纱黑体，没有时用 JetBrains Mono
- 电脑上装了思源宋体 / 更纱黑体会直接用本机字体；没装时用 `fonts/` 里的子集：
  `serif-sc-600.woff` 是 Noto Serif CJK SC（与思源宋体同一套字形），
  `sans-sc-*.woff` 是 Noto Sans CJK SC（更纱黑体的中文字形取自思源黑体，二者中文一致，西文字母略有差别）
- 子集只含页面里用到的字。改了页面文字后，新加的字如果显示成别的字体，重新生成子集：
  `pyftsubset NotoSerifCJK-SemiBold.ttc --font-number=2 --text-file=字表.txt --flavor=woff --layout-features='*' --output-file=fonts/serif-sc-600.woff`
  （正文两个文件同理，用 NotoSansCJK-Regular / Medium）。字体均为 SIL OFL 开源协议

## 图片

- `img/kiosk-warning.png`、`img/kiosk-locked.png`、`img/advice-card.png` 取自 `docs/上手指南图片/`（实机程序截图，像素风格界面）
- `img/center-floorplan.png` 取自 `docs/截图/`（总后台演示数据）
- 第 23 拍「实物运行」：把照片放成 `img/photo-1.jpg`、`photo-2.jpg`、`photo-3.jpg`，占位框会自动换成照片
