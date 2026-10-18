"""
在开发板上检查 NPU：版本是否一致、RKNN 模型能否加载、推理多快、结果和 .pt 是否一致。
    conda activate lab_safety
    python tools/check_npu.py                  # 用 ultralytics 自带的两张测试图
    python tools/check_npu.py 照片1.jpg ...      # 用自己拍的实验台照片（推荐，更有说服力）
    python tools/check_npu.py --camera 0       # 用摄像头现拍一张（也可以写 /dev/video0）
最后一行显示"全部通过"才算 NPU 可用；推理速度可以直接写进答辩材料。
"""
import argparse
import glob
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
STEMS = ("ppe_best", "chem_best")
RUNTIME_LIB = "/usr/lib/librknnrt.so"

problems = []


def bad(msg):
    problems.append(msg)
    print(f"  !! {msg}")


def read_text(path):
    try:
        with open(path, "rb") as f:
            return f.read().replace(b"\x00", b" ").decode(errors="replace").strip()
    except OSError:
        return ""


def runtime_version():
    try:
        with open(RUNTIME_LIB, "rb") as f:
            m = re.search(rb"librknnrt version: ([0-9.]+)", f.read())
        return m.group(1).decode() if m else "看不出版本"
    except OSError:
        return ""


def check_board():
    print("== 1. 芯片")
    print(f"  型号：{read_text('/proc/device-tree/model') or '读不到'}")
    print(f"  compatible：{read_text('/proc/device-tree/compatible') or '读不到'}")
    from ultralytics.utils.checks import is_rockchip
    if is_rockchip():
        print("  ultralytics 认出这是 Rockchip 芯片，可以用 NPU")
    else:
        bad("ultralytics 没认出 Rockchip 芯片（看 compatible 最后一项是不是 rk3588），RKNN 模型会加载失败")


def check_versions():
    print("== 2. 版本（三处必须一致）")
    from importlib.metadata import version, PackageNotFoundError
    try:
        lite = version("rknn-toolkit-lite2")
    except PackageNotFoundError:
        lite = ""
    rt = runtime_version()
    model_ver = {s: read_text(os.path.join(ROOT, "models", f"{s}_rknn_model", "RKNN_VERSION")) for s in STEMS}
    print(f"  rknn-toolkit-lite2（Python 包）：{lite or '没装'}")
    print(f"  {RUNTIME_LIB}：{rt or '没有这个文件'}")
    for s, v in model_ver.items():
        print(f"  models/{s}_rknn_model 导出时的版本：{v or '未知'}")
    drv = read_text("/sys/kernel/debug/rknpu/version")
    print(f"  NPU 驱动：{drv or '看不到（用 sudo cat /sys/kernel/debug/rknpu/version 查看）'}")
    if not lite:
        bad("没装 rknn-toolkit-lite2：重新跑 deploy/orangepi/setup.sh")
    if not rt:
        bad(f"没有 {RUNTIME_LIB}：重新跑 deploy/orangepi/setup.sh")
    wanted = {v for v in model_ver.values() if v}
    if wanted and lite and rt and (lite not in wanted or rt not in wanted):
        bad(f"版本不一致：模型是 {'/'.join(sorted(wanted))}，请重新跑 deploy/orangepi/setup.sh 统一版本")


def grab_camera(src):
    import cv2
    cap = cv2.VideoCapture(int(src) if str(src).isdigit() else src)
    ok, frame = False, None
    for _ in range(10):   # 前几帧常常是黑的
        ok, frame = cap.read()
    cap.release()
    if not ok:
        sys.exit(f"摄像头 {src} 读不到画面")
    os.makedirs(os.path.join(ROOT, "runtime"), exist_ok=True)
    path = os.path.join(ROOT, "runtime", "npu_check.jpg")
    cv2.imwrite(path, frame)
    print(f"  已拍照：{path}")
    return path


def classes(model, img, imgsz):
    r = model.predict(img, imgsz=imgsz, conf=0.35, iou=0.45, verbose=False)[0]
    return sorted(r.names[int(c)] for c in r.boxes.cls.tolist())


def timed(model, img, imgsz, n):
    for _ in range(3):   # 预热
        model.predict(img, imgsz=imgsz, verbose=False)
    t = time.perf_counter()
    for _ in range(n):
        model.predict(img, imgsz=imgsz, verbose=False)
    return (time.perf_counter() - t) / n * 1000


def check_models(images):
    print("== 3. 模型")
    from ultralytics import YOLO
    from src.config import cfg
    imgsz = int(cfg("vision.imgsz", 640))
    order = cfg("vision.prefer_format", ["rknn", "onnx", "pt"])
    print(f"  config.yaml 的模型优先顺序：{order}（第一个是 rknn，程序就会自动用 NPU）")
    for stem in STEMS:
        rknn_dir = os.path.join(ROOT, "models", f"{stem}_rknn_model")
        pt = os.path.join(ROOT, "models", f"{stem}.pt")
        print(f"  -- {stem}")
        if not os.path.isdir(rknn_dir):
            bad(f"没有 {rknn_dir}")
            continue
        try:
            npu = YOLO(rknn_dir, task="detect")
            npu.predict(images[0], imgsz=imgsz, verbose=False)
        except Exception as e:
            bad(f"{stem} 的 RKNN 模型加载 / 推理失败：{e}")
            continue
        cpu = YOLO(pt, task="detect") if os.path.isfile(pt) else None
        for img in images:
            c_npu = classes(npu, img, imgsz)
            line = f"  {os.path.basename(img)}：NPU {c_npu}"
            if cpu is not None:
                c_cpu = classes(cpu, img, imgsz)
                line += f"   .pt(CPU) {c_cpu}"
                if c_npu != c_cpu:
                    line += "   ← 不一致"
                    bad(f"{stem} 在 {os.path.basename(img)} 上 NPU 和 .pt 结果不一致")
            print(line)
        ms = timed(npu, images[0], imgsz, 20)
        msg = f"  速度：NPU 每张 {ms:.0f} ms（约 {1000 / ms:.1f} 帧/秒，含前后处理）"
        if cpu is not None:
            ms_cpu = timed(cpu, images[0], imgsz, 5)
            msg += f"；.pt 在 CPU 上每张 {ms_cpu:.0f} ms，NPU 快 {ms_cpu / ms:.1f} 倍"
        print(msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="*", help="用来对比的图片")
    ap.add_argument("--camera", default=None, help="用摄像头现拍一张，填编号或设备路径")
    args = ap.parse_args()

    check_board()
    check_versions()
    import ultralytics
    images = list(args.images)
    if args.camera is not None:
        images.append(grab_camera(args.camera))
    if not images:
        images = sorted(glob.glob(os.path.join(os.path.dirname(ultralytics.__file__), "assets", "*.jpg")))
    check_models(images)

    print()
    if problems:
        print(f"有 {len(problems)} 个问题：")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print("全部通过：NPU 可用，程序启动时会自动使用 RKNN 模型")


if __name__ == "__main__":
    main()
