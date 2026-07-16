# database.py
import sqlite3
from datetime import datetime


class Database:
    def __init__(self, path: str = "english_school.db"):
        self.path = path

    def _conn(self):
        return sqlite3.connect(self.path)

    def init(self):
        with self._conn() as conn:
            # Ученики
            conn.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    user_id     INTEGER PRIMARY KEY,
                    username    TEXT,
                    full_name   TEXT,
                    joined_at   TEXT
                )
            """)
            # Рефералы
            conn.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    new_user_id  INTEGER PRIMARY KEY,
                    referrer_id  INTEGER,
                    created_at   TEXT
                )
            """)
            # Speaking Club
            conn.execute("""
                CREATE TABLE IF NOT EXISTS clubs (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    date       TEXT,
                    time       TEXT,
                    topic      TEXT,
                    level      TEXT,
                    meet_link  TEXT,
                    max_spots  INTEGER DEFAULT 8,
                    active     INTEGER DEFAULT 1,
                    created_at TEXT
                )
            """)
            # Записи на клуб
            conn.execute("""
                CREATE TABLE IF NOT EXISTS registrations (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER,
                    username   TEXT,
                    full_name  TEXT,
                    club_id    INTEGER,
                    created_at TEXT,
                    UNIQUE(user_id, club_id)
                )
            """)

    # ── Ученики ──
    def add_student(self, user_id, username, full_name):
        with self._conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO students (user_id, username, full_name, joined_at)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, full_name, datetime.now().isoformat()))

    def count_students(self):
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]

    def get_all_students(self):
        with self._conn() as conn:
            return conn.execute("SELECT user_id, username, full_name FROM students").fetchall()

    # ── Рефералы ──
    def add_referral(self, new_user_id, referrer_id):
        with self._conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO referrals (new_user_id, referrer_id, created_at)
                VALUES (?, ?, ?)
            """, (new_user_id, referrer_id, datetime.now().isoformat()))

    def referral_exists(self, user_id):
        with self._conn() as conn:
            return conn.execute(
                "SELECT 1 FROM referrals WHERE new_user_id=?", (user_id,)
            ).fetchone() is not None

    def get_referral_count(self, referrer_id):
        with self._conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (referrer_id,)
            ).fetchone()[0]

    # ── Speaking Club ──
    def create_club(self, date, time, topic, level, meet_link, max_spots=8):
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO clubs (date, time, topic, level, meet_link, max_spots, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (date, time, topic, level, meet_link, max_spots, datetime.now().isoformat()))
            return cur.lastrowid

    def get_active_clubs(self):
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT c.*,
                       (SELECT COUNT(*) FROM registrations r WHERE r.club_id = c.id) as registered
                FROM clubs c WHERE c.active = 1
                ORDER BY c.created_at DESC
            """).fetchall()
            return [dict(r) for r in rows]

    def get_club(self, club_id):
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("""
                SELECT c.*,
                       (SELECT COUNT(*) FROM registrations r WHERE r.club_id = c.id) as registered
                FROM clubs c WHERE c.id = ?
            """, (club_id,)).fetchone()
            return dict(row) if row else None

    def get_spots_left(self, club_id):
        club = self.get_club(club_id)
        return club["max_spots"] - club["registered"] if club else 0

    def is_registered(self, user_id, club_id):
        with self._conn() as conn:
            return conn.execute(
                "SELECT 1 FROM registrations WHERE user_id=? AND club_id=?",
                (user_id, club_id)
            ).fetchone() is not None

    def register(self, user_id, username, full_name, club_id):
        with self._conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO registrations (user_id, username, full_name, club_id, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, full_name, club_id, datetime.now().isoformat()))

    def unregister(self, user_id, club_id):
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM registrations WHERE user_id=? AND club_id=?",
                (user_id, club_id)
            )

    def get_registered_count(self, club_id):
        with self._conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM registrations WHERE club_id=?", (club_id,)
            ).fetchone()[0]

    def get_club_members(self, club_id):
        with self._conn() as conn:
            return conn.execute(
                "SELECT user_id, username, full_name FROM registrations WHERE club_id=?",
                (club_id,)
            ).fetchall()

    def deactivate_club(self, club_id: int):
        with self._conn() as conn:
            conn.execute("UPDATE clubs SET active=0 WHERE id=?", (club_id,))

    def get_stats(self) -> dict:
        with self._conn() as conn:
            students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
            active_clubs = conn.execute("SELECT COUNT(*) FROM clubs WHERE active=1").fetchone()[0]
            total_reg = conn.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
            referrals = conn.execute("SELECT COUNT(*) FROM referrals").fetchone()[0]
            return {
                "students": students,
                "active_clubs": active_clubs,
                "total_registrations": total_reg,
                "referrals": referrals
            }
