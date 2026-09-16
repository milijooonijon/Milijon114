import sqlite3
import datetime
import uuid
import hashlib
import json
from typing import List, Optional, Dict, Any
from app.config import DB_PATH

def get_db():
    global DB_PATH
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # verify connection works without locking error
        cursor = conn.cursor()
        conn.execute("CREATE TABLE IF NOT EXISTS _lock_test (id INT)")
        return conn
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        # Fallback to local /tmp path on non-POSIX locking mounts
        DB_PATH = "/tmp/milijon.db"
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                uuid TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                is_active INTEGER DEFAULT 1,
                upload_bytes INTEGER DEFAULT 0,
                download_bytes INTEGER DEFAULT 0,
                country_preset TEXT DEFAULT 'iran',
                notes TEXT DEFAULT ''
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        # Public Nodes table for harvested global nodes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS public_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                protocol TEXT NOT NULL,
                server TEXT NOT NULL,
                port INTEGER NOT NULL,
                uuid_or_key TEXT NOT NULL,
                security TEXT DEFAULT 'tls',
                network TEXT DEFAULT 'ws',
                path TEXT DEFAULT '',
                sni TEXT DEFAULT '',
                host TEXT DEFAULT '',
                country_code TEXT DEFAULT 'XX',
                flag TEXT DEFAULT '🌐',
                ping_ms INTEGER DEFAULT 9999,
                is_alive INTEGER DEFAULT 1,
                last_checked TEXT NOT NULL,
                raw_link TEXT NOT NULL,
                details_json TEXT DEFAULT '{}',
                UNIQUE(server, port, protocol)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_alive_ping ON public_nodes(is_alive, ping_ms)")
        conn.commit()

        # Create default admin user if none exists
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            default_uuid = str(uuid.uuid4())
            default_pass = "milijon_user"
            p_hash = hashlib.sha224(default_pass.encode('utf-8')).hexdigest()
            now_iso = datetime.datetime.utcnow().isoformat()
            cursor.execute("""
                INSERT INTO users (username, uuid, password, password_hash, created_at, is_active, country_preset, notes)
                VALUES (?, ?, ?, ?, ?, 1, 'iran', 'Default VIP User')
            """, ("DefaultUser", default_uuid, default_pass, p_hash, now_iso))
            conn.commit()

def get_all_users() -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY id DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_user_by_uuid(user_uuid: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE uuid = ? AND is_active = 1", (user_uuid.strip().lower(),))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_user_by_password_hash(p_hash: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE password_hash = ? AND is_active = 1", (p_hash.strip().lower(),))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None

def create_user(username: str, user_uuid: Optional[str] = None, password: Optional[str] = None,
                expires_at: Optional[str] = None, country_preset: str = 'iran', notes: str = '') -> Dict[str, Any]:
    if not user_uuid:
        user_uuid = str(uuid.uuid4())
    else:
        user_uuid = user_uuid.strip().lower()

    if not password:
        password = str(uuid.uuid4())[:12]
    
    p_hash = hashlib.sha224(password.encode('utf-8')).hexdigest()
    created_at = datetime.datetime.utcnow().isoformat()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (username, uuid, password, password_hash, created_at, expires_at, is_active, country_preset, notes)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (username.strip(), user_uuid, password, p_hash, created_at, expires_at, country_preset, notes))
        conn.commit()
        user_id = cursor.lastrowid
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return dict(cursor.fetchone())

def delete_user(user_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount > 0

def toggle_user_status(user_id: int) -> Optional[int]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_active FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        new_status = 0 if row["is_active"] == 1 else 1
        cursor.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
        conn.commit()
        return new_status

def add_traffic(user_id: int, up: int, down: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET upload_bytes = upload_bytes + ?, download_bytes = download_bytes + ?
            WHERE id = ?
        """, (up, down, user_id))
        conn.commit()

# --- PUBLIC NODE HARVESTER DATABASE OPERATIONS ---

def upsert_public_node(node: Dict[str, Any]) -> int:
    """Insert or update a harvested public node with health and geo info."""
    now_iso = datetime.datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO public_nodes (
                name, protocol, server, port, uuid_or_key, security,
                network, path, sni, host, country_code, flag, ping_ms,
                is_alive, last_checked, raw_link, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(server, port, protocol) DO UPDATE SET
                name = excluded.name,
                uuid_or_key = excluded.uuid_or_key,
                security = excluded.security,
                network = excluded.network,
                path = excluded.path,
                sni = excluded.sni,
                host = excluded.host,
                country_code = excluded.country_code,
                flag = excluded.flag,
                ping_ms = excluded.ping_ms,
                is_alive = excluded.is_alive,
                last_checked = excluded.last_checked,
                raw_link = excluded.raw_link,
                details_json = excluded.details_json
        """, (
            node["name"],
            node["protocol"],
            node["server"],
            int(node["port"]),
            node["uuid_or_key"],
            node.get("security", "tls"),
            node.get("network", "ws"),
            node.get("path", ""),
            node.get("sni", ""),
            node.get("host", ""),
            node.get("country_code", "XX"),
            node.get("flag", "🌐"),
            int(node.get("ping_ms", 9999)),
            int(node.get("is_alive", 1)),
            now_iso,
            node["raw_link"],
            json.dumps(node.get("details", {}), ensure_ascii=False)
        ))
        conn.commit()
        return cursor.lastrowid

def get_active_public_nodes(limit: int = 30, max_ping: int = 1500) -> List[Dict[str, Any]]:
    """Retrieve verified healthy public nodes sorted by lowest latency."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM public_nodes
            WHERE is_alive = 1 AND ping_ms <= ?
            ORDER BY ping_ms ASC
            LIMIT ?
        """, (max_ping, limit))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["details"] = json.loads(d.get("details_json") or "{}")
            except Exception:
                d["details"] = {}
            result.append(d)
        return result

def get_all_public_nodes(limit: int = 100) -> List[Dict[str, Any]]:
    """Get all public nodes for admin panel view."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM public_nodes
            ORDER BY is_alive DESC, ping_ms ASC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def update_public_node_health(node_id: int, is_alive: int, ping_ms: int):
    """Update ping and status for a specific node."""
    now_iso = datetime.datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE public_nodes
            SET is_alive = ?, ping_ms = ?, last_checked = ?
            WHERE id = ?
        """, (is_alive, ping_ms, now_iso, node_id))
        conn.commit()

def get_public_nodes_stats() -> Dict[str, Any]:
    """Retrieve statistical summary of public nodes."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM public_nodes")
        total_nodes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM public_nodes WHERE is_alive = 1")
        alive_nodes = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(ping_ms) FROM public_nodes WHERE is_alive = 1 AND ping_ms < 9000")
        avg_ping_row = cursor.fetchone()
        avg_ping = int(avg_ping_row[0]) if (avg_ping_row and avg_ping_row[0]) else 0

        cursor.execute("""
            SELECT flag, country_code, COUNT(*) as cnt
            FROM public_nodes
            WHERE is_alive = 1
            GROUP BY country_code, flag
            ORDER BY cnt DESC
            LIMIT 10
        """)
        countries = [{"flag": r[0], "code": r[1], "count": r[2]} for r in cursor.fetchall()]

        return {
            "total_nodes": total_nodes,
            "alive_nodes": alive_nodes,
            "avg_ping_ms": avg_ping,
            "countries": countries
        }

def cleanup_old_dead_nodes(max_count: int = 200):
    """Prune excessive dead nodes to keep SQLite database lean."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM public_nodes WHERE id IN (
                SELECT id FROM public_nodes
                WHERE is_alive = 0
                ORDER BY last_checked ASC
                LIMIT (SELECT MAX(0, COUNT(*) - ?) FROM public_nodes WHERE is_alive = 0)
            )
        """, (max_count,))
        conn.commit()
