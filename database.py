# database.py
import sqlite3
from datetime import datetime, date, timedelta


def get_next_friday(from_date=None):
    d = from_date or date.today()
    days_ahead = 4 - d.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (d + timedelta(days=days_ahead)).strftime("%d.%m.%Y")


def get_week_start():
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


class Database:
    def __init__(self, path: str = "english_school.db"):
        self.path = path

    def _conn(self):
        return sqlite3.connect(self.path)

    def init(self):
        with self._conn() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS students (
                user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT,
                joined_at TEXT, cohort TEXT)""")
            try:
                conn.execute("ALTER TABLE students ADD COLUMN cohort TEXT")
            except Exception:
                pass
            conn.execute("""CREATE TABLE IF NOT EXISTS student_profiles (
                user_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT,
                phone TEXT, email TEXT, how_found TEXT, registered_at TEXT)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS clubs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, time TEXT,
                topic TEXT, level TEXT, meet_link TEXT, max_spots INTEGER DEFAULT 8,
                active INTEGER DEFAULT 1, created_at TEXT)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
                full_name TEXT, club_id INTEGER, attended INTEGER DEFAULT 0,
                created_at TEXT, UNIQUE(user_id, club_id))""")
            try:
                conn.execute("ALTER TABLE registrations ADD COLUMN attended INTEGER DEFAULT 0")
            except Exception:
                pass
            conn.execute("""CREATE TABLE IF NOT EXISTS topic_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
                full_name TEXT, thread_id INTEGER, week_start TEXT, count INTEGER DEFAULT 1,
                UNIQUE(user_id, thread_id, week_start))""")

    def add_student(self, user_id, username, full_name):
        """Добавляет студента БЕЗ cohort. Cohort только после регистрации."""
        with self._conn() as conn:
            conn.execute("""INSERT OR IGNORE INTO students (user_id, username, full_name, joined_at, cohort)
                VALUES (?, ?, ?, ?, NULL)""", (user_id, username, full_name, datetime.now().isoformat()))

    def assign_cohort(self, user_id):
        """Назначает cohort. Вызывается только после заполнения анкеты."""
        cohort = get_next_friday()
        with self._conn() as conn:
            conn.execute("UPDATE students SET cohort=? WHERE user_id=? AND cohort IS NULL", (cohort, user_id))
        return cohort

    def count_students(self):
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]

    def get_all_students(self):
        with self._conn() as conn:
            return conn.execute("SELECT user_id, username, full_name FROM students").fetchall()

    def get_unregistered_students(self):
        """Холодные клиенты - в боте но без анкеты."""
        with self._conn() as conn:
            return conn.execute("""SELECT s.user_id, s.username, s.full_name, s.joined_at
                FROM students s LEFT JOIN student_profiles p ON s.user_id = p.user_id
                WHERE p.user_id IS NULL""").fetchall()

    def get_students_older_than_days(self, days: int):
        """Холодные клиенты N+ дней без анкеты."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with self._conn() as conn:
            return conn.execute("""SELECT s.user_id, s.username, s.full_name
                FROM students s LEFT JOIN student_profiles p ON s.user_id = p.user_id
                WHERE p.user_id IS NULL AND s.joined_at < ?""", (cutoff,)).fetchall()

    def get_student_by_username(self, username):
        with self._conn() as conn:
            return conn.execute(
                "SELECT user_id, username, full_name, cohort FROM students WHERE username=?",
                (username.lstrip("@"),)).fetchone()

    def get_cohorts(self):
        """Только потоки зарегистрированных студентов."""
        with self._conn() as conn:
            rows = conn.execute("""SELECT DISTINCT s.cohort FROM students s
                JOIN student_profiles p ON s.user_id = p.user_id
                WHERE s.cohort IS NOT NULL ORDER BY s.cohort""").fetchall()
            return [r[0] for r in rows]

    def get_students_by_cohort(self, cohort):
        """Только зарегистрированные в потоке."""
        with self._conn() as conn:
            return conn.execute("""SELECT s.user_id, s.username, s.full_name FROM students s
                JOIN student_profiles p ON s.user_id = p.user_id WHERE s.cohort=?""", (cohort,)).fetchall()

    def has_profile(self, user_id):
        with self._conn() as conn:
            return conn.execute("SELECT 1 FROM student_profiles WHERE user_id=?", (user_id,)).fetchone() is not None

    def add_profile(self, user_id, first_name, last_name, phone, email, how_found):
        with self._conn() as conn:
            conn.execute("""INSERT OR IGNORE INTO student_profiles
                (user_id, first_name, last_name, phone, email, how_found, registered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, first_name, last_name, phone, email, how_found, datetime.now().isoformat()))

    def count_profiles(self):
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM student_profiles").fetchone()[0]

    def get_all_profiles(self):
        with self._conn() as conn:
            return conn.execute("SELECT user_id, first_name, last_name, phone, email, how_found, registered_at FROM student_profiles").fetchall()

    def create_club(self, date, time, topic, level, meet_link, max_spots=8):
        with self._conn() as conn:
            cur = conn.execute("""INSERT INTO clubs (date, time, topic, level, meet_link, max_spots, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (date, time, topic, level, meet_link, max_spots, datetime.now().isoformat()))
            return cur.lastrowid

    def get_active_clubs(self):
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""SELECT c.*,
                (SELECT COUNT(*) FROM registrations r WHERE r.club_id = c.id) as registered
                FROM clubs c WHERE c.active = 1 ORDER BY c.created_at DESC""").fetchall()
            return [dict(r) for r in rows]

    def get_club(self, club_id):
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("""SELECT c.*,
                (SELECT COUNT(*) FROM registrations r WHERE r.club_id = c.id) as registered
                FROM clubs c WHERE c.id = ?""", (club_id,)).fetchone()
            return dict(row) if row else None

    def get_spots_left(self, club_id):
        club = self.get_club(club_id)
        return club["max_spots"] - club["registered"] if club else 0

    def is_registered(self, user_id, club_id):
        with self._conn() as conn:
            return conn.execute("SELECT 1 FROM registrations WHERE user_id=? AND club_id=?",
                (user_id, club_id)).fetchone() is not None

    def register(self, user_id, username, full_name, club_id):
        with self._conn() as conn:
            conn.execute("""INSERT OR IGNORE INTO registrations (user_id, username, full_name, club_id, created_at)
                VALUES (?, ?, ?, ?, ?)""", (user_id, username, full_name, club_id, datetime.now().isoformat()))

    def unregister(self, user_id, club_id):
        with self._conn() as conn:
            conn.execute("DELETE FROM registrations WHERE user_id=? AND club_id=?", (user_id, club_id))

    def get_registered_count(self, club_id):
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM registrations WHERE club_id=?", (club_id,)).fetchone()[0]

    def get_club_members(self, club_id):
        with self._conn() as conn:
            return conn.execute("SELECT user_id, username, full_name FROM registrations WHERE club_id=?", (club_id,)).fetchall()

    def get_user_registrations(self, user_id):
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""SELECT c.*,
                (SELECT COUNT(*) FROM registrations r2 WHERE r2.club_id = c.id) as registered
                FROM clubs c JOIN registrations r ON r.club_id = c.id
                WHERE r.user_id = ? AND c.active = 1 ORDER BY c.created_at DESC""", (user_id,)).fetchall()
            return [dict(r) for r in rows]

    def mark_attended(self, user_id, club_id):
        with self._conn() as conn:
            conn.execute("UPDATE registrations SET attended=1 WHERE user_id=? AND club_id=?", (user_id, club_id))

    def get_not_attended(self, club_id):
        with self._conn() as conn:
            return conn.execute("SELECT user_id, username, full_name FROM registrations WHERE club_id=? AND attended=0", (club_id,)).fetchall()

    def deactivate_club(self, club_id):
        with self._conn() as conn:
            conn.execute("UPDATE clubs SET active=0 WHERE id=?", (club_id,))

    def record_topic_activity(self, user_id, username, full_name, thread_id):
        week_start = get_week_start()
        with self._conn() as conn:
            existing = conn.execute("SELECT id FROM topic_activity WHERE user_id=? AND thread_id=? AND week_start=?",
                (user_id, thread_id, week_start)).fetchone()
            if existing:
                conn.execute("UPDATE topic_activity SET count=count+1 WHERE user_id=? AND thread_id=? AND week_start=?",
                    (user_id, thread_id, week_start))
            else:
                conn.execute("INSERT INTO topic_activity (user_id, username, full_name, thread_id, week_start, count) VALUES (?, ?, ?, ?, ?, 1)",
                    (user_id, username, full_name, thread_id, week_start))

    def get_active_in_topics_this_week(self, thread_ids):
        week_start = get_week_start()
        placeholders = ",".join("?" * len(thread_ids))
        with self._conn() as conn:
            rows = conn.execute(f"SELECT DISTINCT user_id FROM topic_activity WHERE thread_id IN ({placeholders}) AND week_start=?",
                (*thread_ids, week_start)).fetchall()
            return [r[0] for r in rows]

    def get_clubs_this_week(self):
        week_start = get_week_start()
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""SELECT c.*,
                (SELECT COUNT(*) FROM registrations r WHERE r.club_id = c.id) as registered
                FROM clubs c WHERE c.created_at >= ? ORDER BY c.created_at""", (week_start,)).fetchall()
            return [dict(r) for r in rows]

    def get_stats(self):
        with self._conn() as conn:
            students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
            profiles = conn.execute("SELECT COUNT(*) FROM student_profiles").fetchone()[0]
            active_clubs = conn.execute("SELECT COUNT(*) FROM clubs WHERE active=1").fetchone()[0]
            total_reg = conn.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
            return {"students": students, "profiles": profiles, "cold_leads": students - profiles,
                    "active_clubs": active_clubs, "total_registrations": total_reg}
