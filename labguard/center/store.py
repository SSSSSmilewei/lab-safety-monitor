"""
总后台数据层（SQLite，只用标准库）
center/store.py

表：
  users      账号：admin（全部）/ teacher（只看被授权的区域）
  sessions   登录会话（只存令牌的哈希）
  areas      区域树：任意层级，如 楼 → 房间 → 实验桌；kind 只是显示用（group / room / desk）
  grants     授权：用户 ↔ 区域，授权一个区域即包含它下面的所有区域（可混合：整间房间 + 别的房间的一张桌）
  nodes      实验桌终端（开发板）：节点密钥只存哈希；最近一次上报的状态
  profiles   区域的规则阈值（主控决策）：下级覆盖上级，下发给节点前在节点本地再校验一次
  commands   发给节点的指令队列：只有 cut_power / mute 两种，没有任何上电指令
  voice_*    语音素材与「事件 × 语气」映射
  demo_frames 演示画面：每张实验桌的全景 / 台面各一张图片，终端无法提供实时画面时显示（标明「演示画面」）
  audit      操作记录
"""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Set

ROLES = ("admin", "teacher")
UI_STYLES = ("standard", "pixel")       # 界面风格：standard 新版字体（默认）；pixel 旧版 Zpix 像素字体
AREA_KINDS = ("group", "room", "desk")
COMMANDS = ("cut_power", "mute")          # 只能断电、静音；不存在上电 / 解锁指令
SESSION_TTL_S = 12 * 3600
PBKDF2_ROUNDS = 200_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, display_name TEXT NOT NULL,
  role TEXT NOT NULL, pw_hash TEXT NOT NULL, salt TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1, must_change INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created REAL NOT NULL, expires REAL NOT NULL, ip TEXT);
CREATE TABLE IF NOT EXISTS areas (
  id INTEGER PRIMARY KEY, parent_id INTEGER, name TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'group',
  sort INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '', created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS grants (
  user_id INTEGER NOT NULL, area_id INTEGER NOT NULL, PRIMARY KEY (user_id, area_id));
CREATE TABLE IF NOT EXISTS nodes (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, area_id INTEGER UNIQUE, token_hash TEXT NOT NULL,
  token_hint TEXT NOT NULL, created REAL NOT NULL, last_seen REAL, last_ip TEXT, web_port INTEGER,
  hard_limit_c REAL, smoke_limit_raw INTEGER, snapshot TEXT, applied_profile TEXT, report_count INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS profiles (
  area_id INTEGER PRIMARY KEY, preset TEXT NOT NULL DEFAULT '', rules TEXT NOT NULL DEFAULT '{}',
  updated REAL NOT NULL, updated_by TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS commands (
  id INTEGER PRIMARY KEY, node_id INTEGER NOT NULL, cmd TEXT NOT NULL, args TEXT NOT NULL DEFAULT '{}',
  created REAL NOT NULL, created_by TEXT NOT NULL, delivered REAL, result TEXT);
CREATE TABLE IF NOT EXISTS voice_assets (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, source TEXT NOT NULL, filename TEXT NOT NULL,
  voice TEXT NOT NULL DEFAULT '', text TEXT NOT NULL DEFAULT '', consent INTEGER NOT NULL DEFAULT 0,
  created REAL NOT NULL, created_by TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS voice_map (
  area_id INTEGER NOT NULL DEFAULT 0, kind TEXT NOT NULL, tone TEXT NOT NULL, asset_id INTEGER NOT NULL,
  PRIMARY KEY (area_id, kind, tone));
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY, ts REAL NOT NULL, user TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS demo_frames (
  area_id INTEGER NOT NULL, which TEXT NOT NULL, mime TEXT NOT NULL, data BLOB NOT NULL,
  updated REAL NOT NULL, updated_by TEXT NOT NULL DEFAULT '', PRIMARY KEY (area_id, which));
"""


def _hash_pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ROUNDS).hex()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class StoreError(ValueError):
    pass


class Store:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.RLock()
        with self._lock:
            self._db.executescript(SCHEMA)
            cols = {r[1] for r in self._db.execute("PRAGMA table_info(users)")}
            if "ui_style" not in cols:     # 旧数据库升级
                self._db.execute("ALTER TABLE users ADD COLUMN ui_style TEXT NOT NULL DEFAULT 'standard'")
            if "layout" not in {r[1] for r in self._db.execute("PRAGMA table_info(areas)")}:
                self._db.execute("ALTER TABLE areas ADD COLUMN layout TEXT NOT NULL DEFAULT ''")
            self._db.commit()

    # ------------------------------------------------------------------
    def _q(self, sql: str, args: Iterable = ()) -> List[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, tuple(args)).fetchall()

    def _x(self, sql: str, args: Iterable = ()) -> int:
        with self._lock:
            cur = self._db.execute(sql, tuple(args))
            self._db.commit()
            return cur.lastrowid

    def audit(self, user: str, action: str, detail: Any = ""):
        if not isinstance(detail, str):
            detail = json.dumps(detail, ensure_ascii=False, default=str)
        self._x("INSERT INTO audit (ts, user, action, detail) VALUES (?,?,?,?)",
                (time.time(), user, action, detail[:2000]))

    def audit_log(self, n: int = 100) -> List[Dict[str, Any]]:
        return [dict(r) for r in self._q("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (int(n),))]

    def meta(self, k: str, default: str = "") -> str:
        r = self._q("SELECT v FROM meta WHERE k=?", (k,))
        return r[0]["v"] if r else default

    def set_meta(self, k: str, v: str):
        self._x("INSERT INTO meta (k, v) VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))

    # ------------------------------------------------------------------
    # 账号
    # ------------------------------------------------------------------
    @staticmethod
    def check_password_strength(password: str):
        if len(password or "") < 8:
            raise StoreError("密码至少 8 位")
        if password.isdigit() or password.isalpha():
            raise StoreError("密码需同时包含字母和数字")

    def create_user(self, username: str, display_name: str, role: str, password: str,
                    must_change: bool = True) -> int:
        username = (username or "").strip()
        if not (2 <= len(username) <= 32) or not username.replace("_", "").replace(".", "").isalnum():
            raise StoreError("用户名 2–32 位，只能用字母、数字、下划线和点")
        if role not in ROLES:
            raise StoreError("角色只能是 admin 或 teacher")
        self.check_password_strength(password)
        if self._q("SELECT 1 FROM users WHERE username=?", (username,)):
            raise StoreError("用户名已存在")
        salt = secrets.token_hex(16)
        return self._x("INSERT INTO users (username, display_name, role, pw_hash, salt, must_change, created) "
                       "VALUES (?,?,?,?,?,?,?)",
                       (username, (display_name or username).strip()[:32], role, _hash_pw(password, salt), salt,
                        1 if must_change else 0, time.time()))

    def user(self, user_id: int) -> Optional[Dict[str, Any]]:
        r = self._q("SELECT id, username, display_name, role, active, must_change, ui_style, created FROM users WHERE id=?",
                    (user_id,))
        return dict(r[0]) if r else None

    def users(self) -> List[Dict[str, Any]]:
        out = []
        for r in self._q("SELECT id, username, display_name, role, active, must_change, ui_style, created FROM users ORDER BY id"):
            u = dict(r)
            u["grants"] = self.grants_of(u["id"])
            out.append(u)
        return out

    def update_user(self, user_id: int, display_name: Optional[str] = None, role: Optional[str] = None,
                    active: Optional[bool] = None, ui_style: Optional[str] = None):
        u = self.user(user_id)
        if u is None:
            raise StoreError("用户不存在")
        if role is not None and role not in ROLES:
            raise StoreError("角色只能是 admin 或 teacher")
        if ui_style is not None and ui_style not in UI_STYLES:
            raise StoreError("界面风格只能是 standard 或 pixel")
        if ui_style is not None:
            self._x("UPDATE users SET ui_style=? WHERE id=?", (ui_style, user_id))
        demote = (role is not None and role != "admin") or active is False
        if u["role"] == "admin" and demote and self._admin_count(exclude=user_id) == 0:
            raise StoreError("至少保留一个启用的管理员")
        if display_name is not None:
            self._x("UPDATE users SET display_name=? WHERE id=?", (display_name.strip()[:32] or u["username"], user_id))
        if role is not None:
            self._x("UPDATE users SET role=? WHERE id=?", (role, user_id))
        if active is not None:
            self._x("UPDATE users SET active=? WHERE id=?", (1 if active else 0, user_id))
            if not active:
                self._x("DELETE FROM sessions WHERE user_id=?", (user_id,))

    def delete_user(self, user_id: int):
        u = self.user(user_id)
        if u is None:
            raise StoreError("用户不存在")
        if u["role"] == "admin" and self._admin_count(exclude=user_id) == 0:
            raise StoreError("至少保留一个启用的管理员")
        self._x("DELETE FROM sessions WHERE user_id=?", (user_id,))
        self._x("DELETE FROM grants WHERE user_id=?", (user_id,))
        self._x("DELETE FROM users WHERE id=?", (user_id,))

    def _admin_count(self, exclude: int = 0) -> int:
        return self._q("SELECT COUNT(*) c FROM users WHERE role='admin' AND active=1 AND id<>?", (exclude,))[0]["c"]

    def set_password(self, user_id: int, password: str, must_change: bool = False):
        self.check_password_strength(password)
        salt = secrets.token_hex(16)
        self._x("UPDATE users SET pw_hash=?, salt=?, must_change=? WHERE id=?",
                (_hash_pw(password, salt), salt, 1 if must_change else 0, user_id))
        self._x("DELETE FROM sessions WHERE user_id=?", (user_id,))

    def verify(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        r = self._q("SELECT * FROM users WHERE username=?", ((username or "").strip(),))
        if not r:
            _hash_pw(password or "", "00" * 16)   # 用户不存在时也算一次哈希，避免通过耗时猜用户名
            return None
        row = r[0]
        if not hmac.compare_digest(_hash_pw(password or "", row["salt"]), row["pw_hash"]) or not row["active"]:
            return None
        return self.user(row["id"])

    def ensure_admin(self) -> Optional[str]:
        """首次启动：没有任何账号时创建 admin，返回随机初始密码（要求首次登录修改）"""
        if self._q("SELECT 1 FROM users LIMIT 1"):
            return None
        pw = secrets.token_urlsafe(9) + "7a"
        self.create_user("admin", "系统管理员", "admin", pw, must_change=True)
        self.audit("system", "创建初始管理员", "admin")
        return pw

    # ------------------------------------------------------------------
    # 会话
    # ------------------------------------------------------------------
    def new_session(self, user_id: int, ip: str = "") -> str:
        token = secrets.token_urlsafe(32)
        now = time.time()
        self._x("DELETE FROM sessions WHERE expires < ?", (now,))
        self._x("INSERT INTO sessions (token_hash, user_id, created, expires, ip) VALUES (?,?,?,?,?)",
                (_hash_token(token), user_id, now, now + SESSION_TTL_S, ip))
        return token

    def session_user(self, token: str) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        r = self._q("SELECT user_id, expires FROM sessions WHERE token_hash=?", (_hash_token(token),))
        if not r or r[0]["expires"] < time.time():
            return None
        u = self.user(r[0]["user_id"])
        return u if u and u["active"] else None

    def end_session(self, token: str):
        self._x("DELETE FROM sessions WHERE token_hash=?", (_hash_token(token or ""),))

    # ------------------------------------------------------------------
    # 区域树
    # ------------------------------------------------------------------
    @staticmethod
    def _area_dict(r: sqlite3.Row) -> Dict[str, Any]:
        a = dict(r)
        try:
            a["layout"] = json.loads(a.get("layout") or "null")
        except ValueError:
            a["layout"] = None
        return a

    def areas(self) -> List[Dict[str, Any]]:
        return [self._area_dict(r) for r in self._q("SELECT * FROM areas ORDER BY sort, id")]

    def area(self, area_id: int) -> Optional[Dict[str, Any]]:
        r = self._q("SELECT * FROM areas WHERE id=?", (area_id,))
        return self._area_dict(r[0]) if r else None

    def create_area(self, name: str, parent_id: Optional[int], kind: str = "group", note: str = "") -> int:
        name = (name or "").strip()
        if not name or len(name) > 40:
            raise StoreError("名称 1–40 个字")
        if kind not in AREA_KINDS:
            raise StoreError("类型只能是 group / room / desk")
        if parent_id is not None:
            parent = self.area(parent_id)
            if parent is None:
                raise StoreError("上级区域不存在")
            if parent["kind"] == "desk":
                raise StoreError("实验桌下面不能再建区域")
        if self._q("SELECT 1 FROM areas WHERE name=? AND parent_id IS ?", (name, parent_id)):
            raise StoreError("同一层级下已有同名区域")
        sort = self._q("SELECT COALESCE(MAX(sort), 0) + 1 s FROM areas WHERE parent_id IS ?", (parent_id,))[0]["s"]
        return self._x("INSERT INTO areas (parent_id, name, kind, sort, note, created) VALUES (?,?,?,?,?,?)",
                       (parent_id, name, kind, sort, (note or "")[:200], time.time()))

    def update_area(self, area_id: int, name: Optional[str] = None, parent_id: Any = "keep",
                    note: Optional[str] = None, layout: Any = "keep"):
        a = self.area(area_id)
        if a is None:
            raise StoreError("区域不存在")
        if name is not None:
            name = name.strip()
            if not name or len(name) > 40:
                raise StoreError("名称 1–40 个字")
            self._x("UPDATE areas SET name=? WHERE id=?", (name, area_id))
        if parent_id != "keep":
            if parent_id is not None:
                if parent_id == area_id or parent_id in self.descendants([area_id]):
                    raise StoreError("不能移到自己或自己的下级里")
                p = self.area(parent_id)
                if p is None or p["kind"] == "desk":
                    raise StoreError("上级区域无效")
            self._x("UPDATE areas SET parent_id=? WHERE id=?", (parent_id, area_id))
        if note is not None:
            self._x("UPDATE areas SET note=? WHERE id=?", (note[:200], area_id))
        if layout != "keep":
            self.set_layout(area_id, layout)

    def set_layout(self, area_id: int, layout: Optional[Dict[str, Any]]):
        """区域在上级平面图里的位置：{x, y, w, h}，单位是上级宽 / 高的百分比；None = 自动排布"""
        if layout is None:
            self._x("UPDATE areas SET layout='' WHERE id=?", (area_id,))
            return
        try:
            box = {k: round(float(layout[k]), 2) for k in ("x", "y", "w", "h")}
        except (KeyError, TypeError, ValueError):
            raise StoreError("位置需要 x、y、w、h 四个数")
        if not (0 <= box["x"] < 100 and 0 <= box["y"] < 100 and 1 <= box["w"] <= 100 and 1 <= box["h"] <= 100
                and box["x"] + box["w"] <= 100.01 and box["y"] + box["h"] <= 100.01):
            raise StoreError("位置超出上级范围（0–100%）")
        self._x("UPDATE areas SET layout=? WHERE id=?", (json.dumps(box), area_id))

    def delete_area(self, area_id: int):
        if self._q("SELECT 1 FROM areas WHERE parent_id=?", (area_id,)):
            raise StoreError("请先删除或移走下级区域")
        if self._q("SELECT 1 FROM nodes WHERE area_id=?", (area_id,)):
            raise StoreError("这张实验桌还绑定着终端，请先在节点管理里解绑")
        self._x("DELETE FROM grants WHERE area_id=?", (area_id,))
        self._x("DELETE FROM profiles WHERE area_id=?", (area_id,))
        self._x("DELETE FROM voice_map WHERE area_id=?", (area_id,))
        self._x("DELETE FROM demo_frames WHERE area_id=?", (area_id,))
        self._x("DELETE FROM areas WHERE id=?", (area_id,))

    def _children_map(self) -> Dict[Optional[int], List[int]]:
        m: Dict[Optional[int], List[int]] = {}
        for r in self._q("SELECT id, parent_id FROM areas"):
            m.setdefault(r["parent_id"], []).append(r["id"])
        return m

    def descendants(self, roots: Iterable[int]) -> Set[int]:
        """roots 及其所有下级"""
        m = self._children_map()
        out, stack = set(), list(roots)
        while stack:
            a = stack.pop()
            if a in out:
                continue
            out.add(a)
            stack.extend(m.get(a, []))
        return out

    def ancestors(self, area_id: int) -> List[int]:
        """从根到 area_id 的路径（含自身）"""
        parent = {r["id"]: r["parent_id"] for r in self._q("SELECT id, parent_id FROM areas")}
        path, cur, seen = [], area_id, set()
        while cur is not None and cur in parent and cur not in seen:
            seen.add(cur)
            path.append(cur)
            cur = parent[cur]
        return list(reversed(path))

    def path_name(self, area_id: int) -> str:
        names = {r["id"]: r["name"] for r in self._q("SELECT id, name FROM areas")}
        return " / ".join(names.get(a, "?") for a in self.ancestors(area_id))

    # ------------------------------------------------------------------
    # 授权（RBAC）
    # ------------------------------------------------------------------
    def grants_of(self, user_id: int) -> List[int]:
        return [r["area_id"] for r in self._q("SELECT area_id FROM grants WHERE user_id=? ORDER BY area_id", (user_id,))]

    def set_grants(self, user_id: int, area_ids: Iterable[int]):
        ids = sorted(set(int(a) for a in area_ids))
        known = {r["id"] for r in self._q("SELECT id FROM areas")}
        bad = [a for a in ids if a not in known]
        if bad:
            raise StoreError(f"区域不存在：{bad}")
        with self._lock:
            self._db.execute("DELETE FROM grants WHERE user_id=?", (user_id,))
            self._db.executemany("INSERT INTO grants (user_id, area_id) VALUES (?,?)", [(user_id, a) for a in ids])
            self._db.commit()

    def scope(self, user: Dict[str, Any]) -> Optional[Set[int]]:
        """用户能管理的区域集合；None 表示全部（管理员）"""
        if user["role"] == "admin":
            return None
        return self.descendants(self.grants_of(user["id"]))

    def can(self, user: Dict[str, Any], area_id: Optional[int]) -> bool:
        if user["role"] == "admin":
            return True
        return area_id is not None and area_id in self.scope(user)

    def visible_tree(self, user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """用户看得到的区域：可管理的区域 + 它们的上级（上级只用来显示路径，标记 managed=False）"""
        areas = self.areas()
        sc = self.scope(user)
        if sc is None:
            return [dict(a, managed=True) for a in areas]
        show = set(sc)
        for a in sc:
            show.update(self.ancestors(a))
        return [dict(a, managed=a["id"] in sc) for a in areas if a["id"] in show]

    # ------------------------------------------------------------------
    # 节点（实验桌终端）
    # ------------------------------------------------------------------
    def create_node(self, name: str, area_id: Optional[int]) -> Dict[str, Any]:
        name = (name or "").strip()
        if not name or len(name) > 40:
            raise StoreError("名称 1–40 个字")
        if area_id is not None:
            self._check_desk_free(area_id)
        token = "lg_" + secrets.token_urlsafe(24)
        nid = self._x("INSERT INTO nodes (name, area_id, token_hash, token_hint, created) VALUES (?,?,?,?,?)",
                      (name, area_id, _hash_token(token), token[-4:], time.time()))
        return {"id": nid, "token": token}

    def _check_desk_free(self, area_id: int, node_id: int = 0):
        a = self.area(area_id)
        if a is None:
            raise StoreError("区域不存在")
        if a["kind"] != "desk":
            raise StoreError("终端只能绑定到「实验桌」类型的区域")
        if self._q("SELECT 1 FROM nodes WHERE area_id=? AND id<>?", (area_id, node_id)):
            raise StoreError("这张实验桌已经绑定了别的终端")

    def update_node(self, node_id: int, name: Optional[str] = None, area_id: Any = "keep"):
        if self.node(node_id) is None:
            raise StoreError("节点不存在")
        if name is not None:
            if not name.strip() or len(name.strip()) > 40:
                raise StoreError("名称 1–40 个字")
            self._x("UPDATE nodes SET name=? WHERE id=?", (name.strip(), node_id))
        if area_id != "keep":
            if area_id is not None:
                self._check_desk_free(area_id, node_id)
            self._x("UPDATE nodes SET area_id=? WHERE id=?", (area_id, node_id))

    def rotate_node_token(self, node_id: int) -> str:
        token = "lg_" + secrets.token_urlsafe(24)
        self._x("UPDATE nodes SET token_hash=?, token_hint=? WHERE id=?", (_hash_token(token), token[-4:], node_id))
        return token

    def delete_node(self, node_id: int):
        self._x("DELETE FROM commands WHERE node_id=?", (node_id,))
        self._x("DELETE FROM nodes WHERE id=?", (node_id,))

    def node(self, node_id: int) -> Optional[Dict[str, Any]]:
        r = self._q("SELECT * FROM nodes WHERE id=?", (node_id,))
        return self._node_dict(r[0]) if r else None

    def node_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        r = self._q("SELECT * FROM nodes WHERE token_hash=?", (_hash_token(token),))
        return self._node_dict(r[0]) if r else None

    def node_by_area(self, area_id: int) -> Optional[Dict[str, Any]]:
        r = self._q("SELECT * FROM nodes WHERE area_id=?", (area_id,))
        return self._node_dict(r[0]) if r else None

    def nodes(self) -> List[Dict[str, Any]]:
        return [self._node_dict(r) for r in self._q("SELECT * FROM nodes ORDER BY id")]

    @staticmethod
    def _node_dict(r: sqlite3.Row) -> Dict[str, Any]:
        d = dict(r)
        d.pop("token_hash", None)
        for k in ("snapshot", "applied_profile"):
            try:
                d[k] = json.loads(d[k]) if d.get(k) else None
            except ValueError:
                d[k] = None
        return d

    def record_report(self, node_id: int, ip: str, snapshot: Dict[str, Any], meta: Dict[str, Any]):
        self._x("UPDATE nodes SET last_seen=?, last_ip=?, web_port=?, hard_limit_c=?, smoke_limit_raw=?, "
                "snapshot=?, applied_profile=?, report_count=report_count+1 WHERE id=?",
                (time.time(), ip, meta.get("web_port"), meta.get("hard_limit_c"), meta.get("smoke_limit_raw"),
                 json.dumps(snapshot, ensure_ascii=False, default=str),
                 json.dumps(meta.get("applied_profile") or {}, ensure_ascii=False), node_id))

    # ------------------------------------------------------------------
    # 规则阈值（主控决策）：下级覆盖上级
    # ------------------------------------------------------------------
    def profile(self, area_id: int) -> Dict[str, Any]:
        r = self._q("SELECT * FROM profiles WHERE area_id=?", (area_id,))
        if not r:
            return {"area_id": area_id, "preset": "", "rules": {}, "updated": None, "updated_by": ""}
        d = dict(r[0])
        d["rules"] = json.loads(d["rules"] or "{}")
        return d

    def set_profile(self, area_id: int, preset: str, rules: Dict[str, Any], by: str):
        self._x("INSERT INTO profiles (area_id, preset, rules, updated, updated_by) VALUES (?,?,?,?,?) "
                "ON CONFLICT(area_id) DO UPDATE SET preset=excluded.preset, rules=excluded.rules, "
                "updated=excluded.updated, updated_by=excluded.updated_by",
                (area_id, preset or "", json.dumps(rules, ensure_ascii=False), time.time(), by))

    def resolved_profile(self, area_id: Optional[int]) -> Dict[str, Any]:
        """从根到实验桌逐级合并；返回 {rules, sources{key: 区域名}, version}"""
        rules, sources, stamps = {}, {}, []
        if area_id is not None:
            for a in self.ancestors(area_id):
                p = self.profile(a)
                for k, v in p["rules"].items():
                    rules[k] = v
                    sources[k] = self.area(a)["name"]
                stamps.append(f"{a}:{p['updated'] or 0}")
        version = hashlib.sha1("|".join(stamps).encode()).hexdigest()[:12]
        return {"rules": rules, "sources": sources, "version": version}

    # ------------------------------------------------------------------
    # 指令队列（只断电 / 静音）
    # ------------------------------------------------------------------
    def queue_command(self, node_id: int, cmd: str, args: Dict[str, Any], by: str) -> int:
        if cmd not in COMMANDS:
            raise StoreError("只支持断电与静音指令")
        return self._x("INSERT INTO commands (node_id, cmd, args, created, created_by) VALUES (?,?,?,?,?)",
                       (node_id, cmd, json.dumps(args or {}, ensure_ascii=False), time.time(), by))

    def pending_commands(self, node_id: int, max_age_s: float = 120.0) -> List[Dict[str, Any]]:
        """未送达且不太旧的指令（断电指令过时就不该再执行，交给现场判断）"""
        rows = self._q("SELECT * FROM commands WHERE node_id=? AND delivered IS NULL AND created > ? ORDER BY id",
                       (node_id, time.time() - max_age_s))
        return [dict(r, args=json.loads(r["args"] or "{}")) for r in rows]

    def ack_commands(self, node_id: int, results: Dict[str, str]):
        for cid, res in (results or {}).items():
            self._x("UPDATE commands SET delivered=?, result=? WHERE id=? AND node_id=?",
                    (time.time(), str(res)[:300], int(cid), node_id))

    def commands_of(self, node_id: int, n: int = 20) -> List[Dict[str, Any]]:
        return [dict(r) for r in self._q("SELECT * FROM commands WHERE node_id=? ORDER BY id DESC LIMIT ?",
                                         (node_id, n))]

    # ------------------------------------------------------------------
    # 演示画面
    # ------------------------------------------------------------------
    def set_demo_frame(self, area_id: int, which: str, mime: str, data: bytes, by: str):
        self._x("INSERT INTO demo_frames (area_id, which, mime, data, updated, updated_by) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(area_id, which) DO UPDATE SET mime=excluded.mime, data=excluded.data, "
                "updated=excluded.updated, updated_by=excluded.updated_by",
                (area_id, which, mime, sqlite3.Binary(data), time.time(), by))

    def demo_frame(self, area_id: int, which: str) -> Optional[Dict[str, Any]]:
        r = self._q("SELECT * FROM demo_frames WHERE area_id=? AND which=?", (area_id, which))
        return dict(r[0]) if r else None

    def demo_frame_info(self) -> Dict[int, Dict[str, float]]:
        """{area_id: {which: 更新时间}}，不带图片内容"""
        out: Dict[int, Dict[str, float]] = {}
        for r in self._q("SELECT area_id, which, updated FROM demo_frames"):
            out.setdefault(r["area_id"], {})[r["which"]] = r["updated"]
        return out

    def delete_demo_frame(self, area_id: int, which: str):
        self._x("DELETE FROM demo_frames WHERE area_id=? AND which=?", (area_id, which))

    # ------------------------------------------------------------------
    # 语音素材
    # ------------------------------------------------------------------
    def add_voice_asset(self, name: str, source: str, filename: str, by: str, voice: str = "", text: str = "",
                        consent: bool = False) -> int:
        return self._x("INSERT INTO voice_assets (name, source, filename, voice, text, consent, created, created_by) "
                       "VALUES (?,?,?,?,?,?,?,?)",
                       (name[:40], source, filename, voice, text[:200], 1 if consent else 0, time.time(), by))

    def voice_assets(self) -> List[Dict[str, Any]]:
        return [dict(r) for r in self._q("SELECT * FROM voice_assets ORDER BY id DESC")]

    def voice_asset(self, asset_id: int) -> Optional[Dict[str, Any]]:
        r = self._q("SELECT * FROM voice_assets WHERE id=?", (asset_id,))
        return dict(r[0]) if r else None

    def delete_voice_asset(self, asset_id: int):
        self._x("DELETE FROM voice_map WHERE asset_id=?", (asset_id,))
        self._x("DELETE FROM voice_assets WHERE id=?", (asset_id,))

    def set_voice_map(self, area_id: int, kind: str, tone: str, asset_id: Optional[int]):
        if asset_id is None:
            self._x("DELETE FROM voice_map WHERE area_id=? AND kind=? AND tone=?", (area_id, kind, tone))
            return
        if self.voice_asset(asset_id) is None:
            raise StoreError("语音素材不存在")
        self._x("INSERT INTO voice_map (area_id, kind, tone, asset_id) VALUES (?,?,?,?) "
                "ON CONFLICT(area_id, kind, tone) DO UPDATE SET asset_id=excluded.asset_id",
                (area_id, kind, tone, asset_id))

    def voice_map(self, area_id: int) -> List[Dict[str, Any]]:
        return [dict(r) for r in self._q("SELECT * FROM voice_map WHERE area_id=?", (area_id,))]

    def resolved_voice(self, area_id: Optional[int]) -> Dict[str, Dict[str, int]]:
        """全局（area_id=0）→ 根 → 实验桌逐级覆盖：{kind: {tone: asset_id}}"""
        chain = [0] + (self.ancestors(area_id) if area_id is not None else [])
        out: Dict[str, Dict[str, int]] = {}
        for a in chain:
            for m in self.voice_map(a):
                out.setdefault(m["kind"], {})[m["tone"]] = m["asset_id"]
        return out
