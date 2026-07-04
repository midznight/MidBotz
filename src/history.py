"""
Simpan histori chat per user di SQLite. File DB otomatis dibuat kalau belum ada.

Catatan skala: sqlite3 bawaan Python (blocking) dipakai langsung di sini karena
untuk bot personal/kelas kecil ini lebih dari cukup dan lebih simpel buat belajar.
Kalau nanti usernya banyak & mau full non-blocking, ganti ke aiosqlite atau
pindah ke Postgres -- struktur tabelnya tidak perlu berubah banyak.
"""

import sqlite3
from pathlib import Path

MAX_TURNS_DEFAULT = 12  # jumlah pesan terakhir yang dikirim balik sebagai konteks


class HistoryStore:
    def __init__(self, db_path: str = "data/history.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                agent_name TEXT NOT NULL DEFAULT 'default'
            )
            """
        )
        self.conn.commit()

    def add_message(self, user_id: int, role: str, content: str):
        self.conn.execute(
            "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content),
        )
        self.conn.commit()

    def get_recent(self, user_id: int, max_turns: int = MAX_TURNS_DEFAULT) -> list[dict]:
        """Ambil N pesan terakhir user ini, urut lama->baru, siap dipakai jadi messages[]."""
        rows = self.conn.execute(
            "SELECT role, content FROM messages WHERE user_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (user_id, max_turns),
        ).fetchall()
        rows.reverse()
        return [{"role": r, "content": c} for r, c in rows]

    def clear(self, user_id: int):
        self.conn.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def get_agent(self, user_id: int) -> str:
        row = self.conn.execute(
            "SELECT agent_name FROM user_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row[0] if row else "default"

    def set_agent(self, user_id: int, agent_name: str):
        self.conn.execute(
            "INSERT INTO user_settings (user_id, agent_name) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET agent_name = excluded.agent_name",
            (user_id, agent_name),
        )
        self.conn.commit()
