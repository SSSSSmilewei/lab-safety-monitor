#!/usr/bin/env bash
# RK3588 开发板一键部署脚本
# 适用：视美泰 AIOT-3588A（厂家 Ubuntu 22.04 镜像）、香橙派 5（官方 Ubuntu 22.04 Desktop 镜像）
# 用法：bash deploy/orangepi/setup.sh
#   默认用 conda（Miniforge）建 Python 环境，和电脑上的 environment.yml 是同一份；
#   想用系统 Python + venv 的老办法：LABGUARD_USE_VENV=1 bash deploy/orangepi/setup.sh
#   conda 装在哪：LABGUARD_CONDA_DIR 指定；不指定时，有可写的 /userdata（视美泰系统盘只有约 6GB）
#   就装到 /userdata/miniforge3，否则装到 ~/miniforge3
#   NPU 运行库下载不了时：从 rknn-toolkit2 仓库 v2.3.2 标签下载 librknnrt.so，
#   用 LABGUARD_RKNNRT=/路径/librknnrt.so 指定，或放到 deploy/orangepi/librknnrt.so
set -e
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$APP_DIR"
echo "==> 项目目录: $APP_DIR"

echo "==> 1/6 安装系统依赖"
sudo apt update
sudo apt install -y libgl1 libglib2.0-0 libegl1 libxkbcommon-x11-0 libxcb-cursor0 \
    v4l-utils fonts-wqy-microhei x11-xserver-utils wget
if [ -n "$LABGUARD_USE_VENV" ]; then
  sudo apt install -y python3-venv python3-pip python3-dev python3-pyqt6
fi

echo "==> 2/6 串口与摄像头权限（重新登录后生效）"
sudo usermod -aG dialout,video "$USER"
sudo cp deploy/orangepi/99-labguard.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger

if [ -n "$LABGUARD_USE_VENV" ]; then
  echo "==> 3/6 创建虚拟环境（复用系统的 PyQt6，避免在 ARM 上编译 Qt）"
  python3 -m venv --system-site-packages .venv
  source .venv/bin/activate
  pip install -U pip
  grep -v -i "^PySide6" requirements.txt > /tmp/labguard_req.txt
  pip install -r /tmp/labguard_req.txt
else
  echo "==> 3/6 用 conda 创建 Python 环境 lab_safety（第一次要下载约 1–2 GB，耐心等）"
  if [ -n "$LABGUARD_CONDA_DIR" ]; then
    CONDA_DIR="$LABGUARD_CONDA_DIR"
  elif [ -d /userdata ] && [ -w /userdata ]; then
    CONDA_DIR=/userdata/miniforge3
  else
    CONDA_DIR="$HOME/miniforge3"
  fi
  echo "   conda 安装位置：$CONDA_DIR"
  # pip 的缓存和临时文件也放到 conda 旁边，免得把小的系统盘写满（不能放进 $CONDA_DIR，安装器要求它不存在）
  WORK_DIR="$(dirname "$CONDA_DIR")/.labguard-cache"
  export PIP_CACHE_DIR="$WORK_DIR/pip" TMPDIR="$WORK_DIR/tmp"
  mkdir -p "$PIP_CACHE_DIR" "$TMPDIR"
  if ! command -v conda >/dev/null 2>&1 && [ ! -x "$CONDA_DIR/bin/conda" ]; then
    INSTALLER=/tmp/Miniforge3-Linux-aarch64.sh
    wget -q -O "$INSTALLER" https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh \
      || wget -q -O "$INSTALLER" https://mirrors.tuna.tsinghua.edu.cn/github-release/conda-forge/miniforge/LatestRelease/Miniforge3-Linux-aarch64.sh
    bash "$INSTALLER" -b -p "$CONDA_DIR"
  fi
  if [ -x "$CONDA_DIR/bin/conda" ]; then CONDA="$CONDA_DIR/bin/conda"; else CONDA="$(command -v conda)"; fi
  if "$CONDA" env list | grep -q "^lab_safety "; then
    "$CONDA" env update -n lab_safety -f environment.yml --prune
  else
    "$CONDA" env create -f environment.yml
  fi
  eval "$("$CONDA" shell.bash hook)"
  conda activate lab_safety
fi
echo "==> 4/6 NPU 推理运行库（RKNN）"
# 版本必须和导出模型用的 rknn-toolkit2 一致（见 tools/export_rknn.py 的 RKNN_VERSION、models/*_rknn_model/RKNN_VERSION）
RKNN_VERSION=2.3.2
RT=/usr/lib/librknnrt.so
RT_URL="https://github.com/airockchip/rknn-toolkit2/raw/v$RKNN_VERSION/rknpu2/runtime/Linux/librknn_api/aarch64/librknnrt.so"
rt_ver() { grep -a -o -m1 "librknnrt version: [0-9.]*" "$1" 2>/dev/null | head -1 | awk '{print $3}'; }
pip install "rknn-toolkit-lite2==$RKNN_VERSION" \
  || echo "!! rknn-toolkit-lite2 安装失败：请从 github.com/airockchip/rknn-toolkit2 的 v$RKNN_VERSION 标签 rknn-toolkit-lite2/packages 下载对应 Python 版本（conda 环境是 cp312）的 whl 手动安装"
CUR_RT="$(rt_ver "$RT")"
if [ "$CUR_RT" = "$RKNN_VERSION" ]; then
  echo "   $RT 已是 $RKNN_VERSION"
else
  echo "   $RT 当前版本：${CUR_RT:-没有}，需要 $RKNN_VERSION，开始更换"
  NEW_RT=""
  for f in "$LABGUARD_RKNNRT" deploy/orangepi/librknnrt.so; do
    if [ -n "$f" ] && [ "$(rt_ver "$f")" = "$RKNN_VERSION" ]; then NEW_RT="$f"; break; fi
  done
  if [ -z "$NEW_RT" ]; then
    DL="$(mktemp)"   # 先下到临时文件，确认版本对了才替换，下载失败不会弄坏原来的
    if wget -q -O "$DL" "$RT_URL" && [ "$(rt_ver "$DL")" = "$RKNN_VERSION" ]; then NEW_RT="$DL"; fi
  fi
  if [ -n "$NEW_RT" ]; then
    # 只在第一次备份，保留的是系统原装的那份；想还原：sudo mv $RT.bak $RT && sudo ldconfig
    if [ -f "$RT" ] && [ ! -f "$RT.bak" ]; then sudo cp -a "$RT" "$RT.bak"; fi
    sudo install -m 0644 "$NEW_RT" "$RT" && sudo ldconfig
    echo "   已换成 $(rt_ver "$RT")"
  else
    echo "!! librknnrt.so $RKNN_VERSION 下载失败，$RT 保持原样（${CUR_RT:-没有}），NPU 模型会加载失败、程序自动改用 CPU。"
    echo "   请在电脑上下载 $RT_URL"
    echo "   拷到板子的 $APP_DIR/deploy/orangepi/librknnrt.so 后重新运行本脚本"
  fi
  rm -f "$DL"
fi
echo "   NPU 驱动版本：$(sudo cat /sys/kernel/debug/rknpu/version 2>/dev/null || echo 读不到)"
if ls models/*_rknn_model >/dev/null 2>&1; then
  echo "   已找到 RKNN 模型：$(ls -d models/*_rknn_model | tr '\n' ' ')"
  echo "   检查 NPU 能否使用：python tools/check_npu.py"
else
  echo "!! models/ 下没有 RKNN 模型，将使用 .pt 在 CPU 上推理（较慢）。请在 x86 Linux / WSL2 上运行 tools/export_rknn.py 导出后拷过来"
fi

echo "==> 5/6 开机自启"
mkdir -p ~/.config/autostart runtime
sed "s#__APP_DIR__#$APP_DIR#g" deploy/orangepi/labguard.desktop > ~/.config/autostart/labguard.desktop
chmod +x deploy/orangepi/start.sh

echo "==> 6/6 摄像头列表（把 by-id 路径填进 config.yaml 的 camera.pano / camera.desk，插拔后编号不会变）"
ls -l /dev/v4l/by-id/ 2>/dev/null || v4l2-ctl --list-devices
echo
echo "完成。重新登录（或重启）后生效；手动启动：bash deploy/orangepi/start.sh"
