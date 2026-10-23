"""
从训练好的 YOLO 权重里导出"模型档案"（总后台「模型看板」的数据来源）
    python tools/export_model_card.py            # 读 models/*.pt，写 models/model_card.json

只导出权重文件里真实保存的内容：训练参数、最终验证指标、逐轮训练曲线、类别、参数量。
训练集图片数量等权重里没有的信息，请在总后台「模型看板 → 编辑数据集信息」里如实填写，不要编。
需要 torch + ultralytics（在电脑上运行即可，开发板和总后台都不需要）。
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = {
    "ppe_best.pt": {"role": "人员模型（全景摄像头）", "use": "识别防护装备佩戴情况、饮食行为，判断是否有人在台前"},
    "chem_best.pt": {"role": "器皿模型（台面摄像头）", "use": "识别台面器皿种类，区分可加热器皿与量器，判断是否靠近桌边"},
}
METRIC_KEYS = {"metrics/precision(B)": "precision", "metrics/recall(B)": "recall",
               "metrics/mAP50(B)": "map50", "metrics/mAP50-95(B)": "map50_95"}
CURVE_KEYS = ["epoch", "metrics/precision(B)", "metrics/recall(B)", "metrics/mAP50(B)", "metrics/mAP50-95(B)",
              "train/box_loss", "train/cls_loss", "val/box_loss", "val/cls_loss"]


def card(path: str, info: dict) -> dict:
    import torch
    ck = torch.load(path, map_location="cpu", weights_only=False)
    model = ck.get("model") or ck.get("ema")
    args = ck.get("train_args") or {}
    tm = ck.get("train_metrics") or {}
    tr = ck.get("train_results") or {}
    names = getattr(model, "names", {}) or {}
    yaml = getattr(model, "yaml", {}) or {}
    # 训练时的路径可能是 Windows 路径，统一成 / 再取文件名
    data_path = str(args.get("data", "")).replace("\\", "/")
    base_weights = os.path.basename(str(args.get("model", "")).replace("\\", "/"))
    return {
        "file": os.path.basename(path),
        "role": info["role"], "use": info["use"],
        "architecture": f"YOLO11{yaml.get('scale', '')}（{base_weights} 预训练权重微调）",
        "params": int(sum(p.numel() for p in model.parameters())) if model is not None else None,
        "classes": [names[k] for k in sorted(names)] if isinstance(names, dict) else list(names),
        "train_args": {k: args.get(k) for k in ("epochs", "imgsz", "batch", "optimizer", "patience", "lr0")},
        "dataset_name": os.path.basename(os.path.dirname(data_path)) or None,
        "trained_at": ck.get("date"), "ultralytics": ck.get("version"),
        "final": {v: round(float(tm[k]), 4) for k, v in METRIC_KEYS.items() if k in tm},
        "curves": {k: [round(float(x), 5) for x in tr[k]] for k in CURVE_KEYS if k in tr},
    }


def main():
    out = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "models": []}
    for fname, info in MODELS.items():
        path = os.path.join(ROOT, "models", fname)
        if not os.path.isfile(path):
            print(f"跳过（不存在）：{path}")
            continue
        out["models"].append(card(path, info))
        print(f"已读取：{fname}")
    dst = os.path.join(ROOT, "models", "model_card.json")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"已写入：{dst}")


if __name__ == "__main__":
    sys.exit(main())
