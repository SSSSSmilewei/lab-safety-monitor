"""
把 models/*.pt 导出为 RK3588 NPU 可用的 RKNN 模型（视美泰 AIOT-3588A、香橙派 5 通用）。

运行环境：x86_64 Linux（Ubuntu 20.04/22.04，或 Windows 的 WSL2），Python 3.8–3.12
    pip install "ultralytics>=8.3.0" "rknn-toolkit2==2.3.2" "onnxslim>=0.1.82" "numpy<2" "setuptools<81"
    python tools/export_rknn.py              # 导出 + 在模拟器里和原模型对比
    python tools/export_rknn.py --no-check   # 只导出
    python tools/export_rknn.py --check 图1.jpg 图2.jpg   # 额外用自己的图片对比

输出：models/ppe_best_rknn_model/、models/chem_best_rknn_model/（仓库里已有一份导出好的）
程序会自动优先使用（config.yaml → vision.prefer_format）。

版本必须三处一致，否则板子上加载模型会失败或结果错乱：
    这里的 rknn-toolkit2  ==  板子上的 rknn-toolkit-lite2  ==  板子上 /usr/lib/librknnrt.so
    三者都定为 RKNN_VERSION；deploy/orangepi/setup.sh 会在板子上装同一版本。
    不用 2.5.0：它转换 YOLO11 时会报 IndexError（Ultralytics 也限制了 <2.5）。
    numpy 必须 <2：装 onnxslim 等包时可能被顺带升到 2.x，转换会报 TypeError。

注意：导出尺寸固定为 imgsz，板子上推理时也会使用同样的尺寸（config.yaml → vision.imgsz）。
"""
import argparse
import glob
import os
import sys

RKNN_VERSION = "2.3.2"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STEMS = ("ppe_best", "chem_best")


def check_toolkit():
    from importlib.metadata import version, PackageNotFoundError
    try:
        v = version("rknn-toolkit2")
    except PackageNotFoundError:
        sys.exit(f"没装 rknn-toolkit2：pip install \"rknn-toolkit2=={RKNN_VERSION}\" \"setuptools<81\"")
    if v != RKNN_VERSION:
        sys.exit(f"rknn-toolkit2 版本是 {v}，需要 {RKNN_VERSION}（要和板子上的运行库一致）：\n"
                 f"  pip install \"rknn-toolkit2=={RKNN_VERSION}\"")
    import numpy
    if int(numpy.__version__.split(".")[0]) >= 2:
        sys.exit(f"numpy 是 {numpy.__version__}，rknn-toolkit2 {RKNN_VERSION} 要求 numpy<2：pip install \"numpy<2\"")


def export(stem, imgsz):
    from ultralytics import YOLO
    pt = os.path.join(ROOT, "models", f"{stem}.pt")
    if not os.path.isfile(pt):
        print(f"跳过：未找到 {pt}")
        return None
    print(f"导出 {pt} → RKNN (rk3588, imgsz={imgsz}, FP16)")
    out = YOLO(pt).export(format="rknn", name="rk3588", imgsz=imgsz)
    with open(os.path.join(out, "RKNN_VERSION"), "w") as f:
        f.write(RKNN_VERSION + "\n")
    print(f"完成：{out}")
    return out


def compare(onnx, imgsz, images):
    """在 rknn-toolkit2 自带的模拟器里跑同一张图，和 ONNX（与 .pt 等价）的结果对比"""
    import cv2
    import numpy as np
    import onnxruntime as ort
    import torch
    from rknn.api import RKNN
    from ultralytics.data.augment import LetterBox
    from ultralytics.utils.nms import non_max_suppression

    r = RKNN(verbose=False)
    r.config(mean_values=[[0, 0, 0]], std_values=[[255, 255, 255]], target_platform="rk3588")
    r.load_onnx(model=onnx)
    r.build(do_quantization=False)
    r.init_runtime()   # 不指定 target = 在电脑上模拟 NPU
    sess = ort.InferenceSession(onnx)
    same, max_diff = 0, 0.0
    for p in images:
        im = cv2.imread(p)
        if im is None:
            print(f"  读不了图片：{p}")
            continue
        x = np.ascontiguousarray(LetterBox((imgsz, imgsz), auto=False)(image=im[:, :, ::-1]))[None]
        y_npu = r.inference(inputs=[x], data_format="nhwc")[0].astype(np.float32)
        y_ref = sess.run(None, {sess.get_inputs()[0].name: x.transpose(0, 3, 1, 2).astype(np.float32) / 255})[0]
        max_diff = max(max_diff, float(np.abs(y_npu[:, 4:] - y_ref[:, 4:]).max()))
        c_npu = sorted(non_max_suppression(torch.from_numpy(y_npu), 0.35, 0.45)[0][:, 5].int().tolist())
        c_ref = sorted(non_max_suppression(torch.from_numpy(y_ref), 0.35, 0.45)[0][:, 5].int().tolist())
        same += c_npu == c_ref
        print(f"  {os.path.basename(p)}：原模型 {c_ref}  NPU 模型 {c_npu}")
    r.release()
    print(f"  类别分数最大差 {max_diff:.4f}；{same}/{len(images)} 张图检测出的类别完全一致")
    return same == len(images)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--no-check", action="store_true", help="不在模拟器里对比")
    ap.add_argument("--check", nargs="*", default=[], metavar="IMG", help="额外用来对比的图片")
    args = ap.parse_args()
    check_toolkit()

    import ultralytics
    images = sorted(glob.glob(os.path.join(os.path.dirname(ultralytics.__file__), "assets", "*.jpg"))) + args.check
    ok = True
    for stem in STEMS:
        onnx = os.path.join(ROOT, "models", f"{stem}.onnx")   # 导出过程中生成的中间文件
        try:
            if export(stem, args.imgsz) and not args.no_check:
                print(f"对比 {stem}（模拟器）")
                ok = compare(onnx, args.imgsz, images) and ok
        finally:
            if os.path.isfile(onnx):
                os.remove(onnx)   # 不留 .onnx，免得电脑上被 prefer_format 优先选中
    if not ok:
        sys.exit("!! 有图片的结果不一致，先别拷到板子上，把上面的输出发给队友看看")


if __name__ == "__main__":
    main()
