#!/usr/bin/env bash
# 启动监测系统（开机自启也调用这个脚本）
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$APP_DIR"
mkdir -p runtime
export DISPLAY="${DISPLAY:-:0}"
# 大模型 API Key 等私密环境变量：开机自启不经过登录 shell，读不到 ~/.bashrc 里的 export。
# 放在仓库外的 ~/.config/labguard/env（每行 KEY=值，chmod 600），这里加载成环境变量；不写进 config.yaml
LABGUARD_ENV_FILE="${LABGUARD_ENV_FILE:-$HOME/.config/labguard/env}"
if [ -f "$LABGUARD_ENV_FILE" ]; then set -a; . "$LABGUARD_ENV_FILE"; set +a; fi
# 路演 / 值守场景：关闭屏保与息屏
xset s off -dpms 2>/dev/null || true
# CPU 调度设为性能模式（需要 sudo 免密时才会生效，失败不影响运行）
echo performance | sudo -n tee /sys/devices/system/cpu/cpufreq/policy*/scaling_governor >/dev/null 2>&1 || true
# 找 Python：优先 conda 环境 lab_safety（setup.sh 默认），其次 .venv，最后系统 python3
PY=python3
for d in "$LABGUARD_CONDA_DIR" /userdata/miniforge3 "$HOME/miniforge3" "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/.conda"; do
  if [ -n "$d" ] && [ -x "$d/envs/lab_safety/bin/python" ]; then PY="$d/envs/lab_safety/bin/python"; break; fi
done
if [ "$PY" = python3 ] && [ -x .venv/bin/python ]; then PY=.venv/bin/python; fi
# 正式部署：小屏 + 网页大屏。没接屏幕时自动改为 headless（只跑安全核心和网页）
MODE=edge
if [ -z "$(ls /sys/class/drm/*/status 2>/dev/null | xargs grep -l '^connected' 2>/dev/null)" ]; then
  MODE=headless
fi
exec "$PY" run_app.py --mode "${LABGUARD_MODE:-$MODE}" >> runtime/app.log 2>&1
