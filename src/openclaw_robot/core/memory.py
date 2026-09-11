"""持久记忆：SQLite 存储，按 channel+user 维度隔离会话历史。"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

_DEFAULT_DB = Path.home() / ".openclaw" / "memory.db"


class Memory:
    """线程安全的 SQLite 记忆存储。

    scope: (channel, user_id) 二元组隔离不同渠道不同用户的对话历史。
    """

    def __init__(self, db_path: str | Path = _DEFAULT_DB) -> None:
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    ts INTEGER NOT NULL
                )"""
            )
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_scope ON messages(channel, user_id, ts)"
            )
            self._db.commit()

    def append(self, channel: str, user_id: str, role: str, content: str, ts: int) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO messages(channel, user_id, role, content, ts) VALUES(?,?,?,?,?)",
                (channel, user_id, role, content, ts),
            )
            self._db.commit()

    def history(self, channel: str, user_id: str, limit: int = 20) -> list[dict]:
        with self._lock:
            cur = self._db.execute(
                """SELECT role, content FROM messages
                   WHERE channel=? AND user_id=?
                   ORDER BY ts DESC LIMIT ?""",
                (channel, user_id, limit),
            )
            rows = cur.fetchall()
        # 倒序读出后翻转为时间正序
        return [{"role": r, "content": c} for r, c in reversed(rows)]

    def clear(self, channel: str, user_id: str) -> None:
        with self._lock:
            self._db.execute(
                "DELETE FROM messages WHERE channel=? AND user_id=?",
                (channel, user_id),
            )
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()
