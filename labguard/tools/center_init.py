#!/usr/bin/env python3
"""
总后台初始化：建一套干净的正式数据 —— 一栋楼 / 一层 / 一间实验室 / 一张实验桌，登记一台终端，再建一个教师账号。
不含任何模拟终端和演示画面；实验桌的画面、传感器数据全部来自真实开发板（两路摄像头 + 控制盒）。

  python tools/center_init.py --center-url http://192.168.1.10:8200
  python tools/center_init.py --local                 # 总后台和终端程序在同一台电脑上：节点密钥直接写进本机配置

完成后：
  1. python run_center.py                             # 用同一个数据库启动总后台（默认 runtime/center.db）
  2. 开发板：把打印出来的 center 段写进 labguard/runtime/config_override.yaml，重启终端程序
  3. 用打印出来的教师账号登录，总览里只有这一张实验桌

数据库里已经有区域时拒绝执行（不覆盖正式数据）；确实要重来请加 --reset（会删除旧数据库）。
"""
import argparse
import os
import secrets
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def random_password() -> str:
    while True:
        pw = secrets.token_urlsafe(9)
        if any(c.isdigit() for c in pw) and any(c.isalpha() for c in pw):
            return pw


def main():
    ap = argparse.ArgumentParser(description="总后台初始化：一张实验桌 + 一台终端 + 一个教师账号")
    ap.add_argument("--db", default=os.path.join(ROOT, "runtime", "center.db"))
    ap.add_argument("--building", default="化学楼")
    ap.add_argument("--floor", default="一楼")
    ap.add_argument("--room", default="A实验室")
    ap.add_argument("--desk", default="1号桌")
    ap.add_argument("--terminal", default="LG-A01", help="终端名称")
    ap.add_argument("--user", default="teacher", help="教师账号用户名")
    ap.add_argument("--name", default="实验室教师", help="教师显示名")
    ap.add_argument("--password", default="", help="教师密码（至少 8 位，含字母和数字）；不填则随机生成，首次登录须改密")
    ap.add_argument("--center-url", default="", help="开发板访问总后台用的地址，如 http://192.168.1.10:8200")
    ap.add_argument("--local", action="store_true", help="终端程序也在本机：把 center 段写进本机 runtime/config_override.yaml")
    ap.add_argument("--reset", action="store_true", help="删除旧数据库后重建")
    args = ap.parse_args()

    from center.store import Store, StoreError

    db = os.path.abspath(args.db)
    os.makedirs(os.path.dirname(db), exist_ok=True)
    if args.reset and os.path.exists(db):
        os.remove(db)
    store = Store(db)
    if store.areas():
        sys.exit(f"[初始化] {db} 里已经有区域数据，未做任何修改。确实要重建请加 --reset（会删除旧数据库）。")

    admin_pw = store.ensure_admin()
    if admin_pw:      # 与 run_center.py 相同：初始密码另存一份，首次登录改密后删除
        pw_file = os.path.join(os.path.dirname(db), "center_initial_password.txt")
        with open(pw_file, "w", encoding="utf-8") as fp:
            fp.write(f"用户名 admin\n初始密码 {admin_pw}\n首次登录后必须修改密码，改完请删除本文件。\n")
        try:
            os.chmod(pw_file, 0o600)
        except OSError:
            pass
    b = store.create_area(args.building, None)
    f = store.create_area(args.floor, b)
    r = store.create_area(args.room, f)
    d = store.create_area(args.desk, r, kind="desk")
    node = store.create_node(args.terminal, d)

    pw = args.password or random_password()
    try:
        uid = store.create_user(args.user, args.name, "teacher", pw, must_change=not args.password)
    except StoreError as e:
        sys.exit(f"[初始化] 教师账号创建失败：{e}")
    store.set_grants(uid, [r])
    path = store.path_name(d)
    store.audit("初始化脚本", "初始化总后台", {"desk": path, "node": args.terminal, "user": args.user})

    url = args.center_url.rstrip("/") or "http://127.0.0.1:8200"
    snippet = f"center:\n  url: {url}\n  node_token: {node['token']}\n"
    if args.local:
        from src.config import set_value
        set_value("center.url", url)
        set_value("center.node_token", node["token"])

    print(f"\n[初始化] 数据库：{db}")
    print(f"  实验桌：{path}  ←  终端 {args.terminal}")
    if admin_pw:
        print(f"  管理员：admin / {admin_pw}（首次登录须改密）")
    print(f"  教师：  {args.user} / {pw}" + ("（首次登录须改密）" if not args.password else "") + f"，授权范围 {store.path_name(r)}")
    print("\n终端配置（节点密钥只显示这一次）：")
    if args.local:
        print("  已写入本机 runtime/config_override.yaml，直接启动 python run_app.py 即可接入。")
    else:
        print("  把下面三行写进开发板的 labguard/runtime/config_override.yaml，然后重启终端程序：\n")
        print("  " + snippet.rstrip("\n").replace("\n", "\n  "))
    if not args.center_url and not args.local:
        print("  注意：url 现在是 127.0.0.1，开发板上要换成总后台电脑的局域网 IP。")
    print(f"\n启动总后台：python run_center.py --db {db}")


if __name__ == "__main__":
    main()
