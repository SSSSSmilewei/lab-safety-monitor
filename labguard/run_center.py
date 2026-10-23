#!/usr/bin/env python3
"""
总后台（多实验室管理中心）入口 —— 和 run_app.py 是两个独立程序，一般装在老师办公室的电脑或服务器上

  python run_center.py                    # 默认 0.0.0.0:8200，数据放在 runtime/center.db
  python run_center.py --port 8300 --db D:/labguard/center.db

首次启动会创建 admin 账号，随机初始密码打印在终端，并写入 runtime/center_initial_password.txt；
首次登录必须修改密码，改完后请删掉这个文件。
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def main():
    ap = argparse.ArgumentParser(description="实验室安全 · 总后台")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8200)
    ap.add_argument("--db", default=os.path.join(ROOT, "runtime", "center.db"))
    args = ap.parse_args()

    os.makedirs(os.path.dirname(os.path.abspath(args.db)), exist_ok=True)
    import uvicorn
    from center.app import create_app

    app = create_app(args.db)
    pw = app.state.initial_password
    if pw:
        path = os.path.join(os.path.dirname(os.path.abspath(args.db)), "center_initial_password.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"用户名 admin\n初始密码 {pw}\n首次登录后必须修改密码，改完请删除本文件。\n")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        print(f"\n[总后台] 已创建管理员账号 admin，初始密码：{pw}（也写在 {path}）\n")
    print(f"[总后台] 打开 http://127.0.0.1:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
