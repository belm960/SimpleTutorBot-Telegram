# --- database.py ---
import sqlite3
from typing import Optional, Any, List, Dict

from constants import DB_PATH

def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                role TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS students (
                telegram_id INTEGER PRIMARY KEY,
                full_name TEXT,
                phone TEXT,
                city TEXT,
                grade TEXT,
                subject_needed TEXT,
                mode TEXT,
                notes TEXT,
                FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS tutors (
                telegram_id INTEGER PRIMARY KEY,
                full_name TEXT,
                phone TEXT,
                city TEXT,
                subjects TEXT,
                grades TEXT,
                experience_years INTEGER,
                mode TEXT,
                hourly_rate TEXT,
                bio TEXT,
                test_score INTEGER DEFAULT 0,
                FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                tutor_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def upsert_user(telegram_id: int, role: str, status: str):
    with db() as conn:
        conn.execute("""
        INSERT INTO users(telegram_id, role, status) VALUES(?,?,?)
        ON CONFLICT(telegram_id) DO UPDATE SET role=excluded.role, status=excluded.status
        """, (telegram_id, role, status))
        conn.commit()

def get_user(telegram_id: int) -> Optional[sqlite3.Row]:
    with db() as conn:
        cur = conn.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        return cur.fetchone()

def save_student(telegram_id: int, data: Dict[str, Any]):
    with db() as conn:
        conn.execute("""
        INSERT INTO students(telegram_id, full_name, phone, city, grade, subject_needed, mode, notes)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(telegram_id) DO UPDATE SET
          full_name=excluded.full_name,
          phone=excluded.phone,
          city=excluded.city,
          grade=excluded.grade,
          subject_needed=excluded.subject_needed,
          mode=excluded.mode,
          notes=excluded.notes
        """, (
            telegram_id,
            data.get("full_name"),
            data.get("phone"),
            data.get("city"),
            data.get("grade"),
            data.get("subject_needed"),
            data.get("mode"),
            data.get("notes"),
        ))
        conn.commit()

def save_tutor(telegram_id: int, data: Dict[str, Any], test_score: int, status: str):
    with db() as conn:
        conn.execute("""
        INSERT INTO tutors(telegram_id, full_name, phone, city, subjects, grades, experience_years, mode, hourly_rate, bio, test_score)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            full_name=excluded.full_name,
            phone=excluded.phone,
            city=excluded.city,
            subjects=excluded.subjects,
            grades=excluded.grades,
            experience_years=excluded.experience_years,
            mode=excluded.mode,
            hourly_rate=excluded.hourly_rate,
            bio=excluded.bio,
            test_score=excluded.test_score
        """, (
            telegram_id,
            data.get("full_name"),
            data.get("phone"),
            data.get("city"),
            data.get("subjects"),
            data.get("grades"),
            int(data.get("experience_years") or 0),
            data.get("mode"),
            data.get("hourly_rate"),
            data.get("bio"),
            test_score
        ))
        # update user status
        conn.execute("UPDATE users SET status=? WHERE telegram_id=?", (status, telegram_id))
        conn.commit()

def search_tutors(subject: str, grade: Optional[str] = None, city: Optional[str] = None) -> List[sqlite3.Row]:
    q = """
    SELECT u.status, t.*
    FROM tutors t
    JOIN users u ON u.telegram_id = t.telegram_id
    WHERE u.role='tutor' AND u.status='approved'
      AND lower(t.subjects) LIKE lower(?)
    """
    params: List[Any] = [f"%{subject}%"]

    if grade:
        q += " AND lower(t.grades) LIKE lower(?)"
        params.append(f"%{grade}%")
    if city:
        q += " AND lower(t.city) LIKE lower(?)"
        params.append(f"%{city}%")

    q += " ORDER BY t.experience_years DESC"

    with db() as conn:
        cur = conn.execute(q, params)
        return cur.fetchall()

def create_request(student_id: int, tutor_id: int, message: str):
    with db() as conn:
        conn.execute(
            "INSERT INTO requests(student_id, tutor_id, message) VALUES (?,?,?)",
            (student_id, tutor_id, message),
        )
        conn.commit()