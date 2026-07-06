"""Database module for the Facial Recognition Class Attendance System.

Uses SQLite. Tables: students, attendance.
Facial data is stored on disk under data/faces/<student_id>/ and the
trained LBPH model maps directly to student_id labels.
"""

import sqlite3
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "attendance.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS students (
            student_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            registration_no TEXT NOT NULL UNIQUE,
            course TEXT NOT NULL,
            face_dir TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS attendance (
            attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            session_course TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Present',
            confidence REAL,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            UNIQUE (student_id, session_course, date)
        );
        """
    )
    conn.commit()
    conn.close()


def add_student(name, registration_no, course):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO students (name, registration_no, course) VALUES (?, ?, ?)",
        (name.strip(), registration_no.strip(), course.strip()),
    )
    student_id = cur.lastrowid
    face_dir = f"data/faces/{student_id}"
    conn.execute(
        "UPDATE students SET face_dir = ? WHERE student_id = ?",
        (face_dir, student_id),
    )
    conn.commit()
    conn.close()
    return student_id


def get_student(student_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM students WHERE student_id = ?", (student_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_students():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM students ORDER BY student_id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_attendance(student_id, session_course, confidence=None):
    """Mark a student present. Returns True if newly marked,
    False if already marked for this course today (duplicate prevention)."""
    now = datetime.now()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO attendance (student_id, session_course, date, time, status, confidence) "
            "VALUES (?, ?, ?, ?, 'Present', ?)",
            (student_id, session_course, now.date().isoformat(),
             now.strftime("%H:%M:%S"), confidence),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # already marked today for this course
    finally:
        conn.close()


def get_attendance(on_date=None, course=None):
    query = (
        "SELECT a.attendance_id, s.name, s.registration_no, a.session_course, "
        "a.date, a.time, a.status, a.confidence "
        "FROM attendance a JOIN students s ON s.student_id = a.student_id WHERE 1=1"
    )
    params = []
    if on_date:
        query += " AND a.date = ?"
        params.append(on_date)
    if course:
        query += " AND a.session_course = ?"
        params.append(course)
    query += " ORDER BY a.date DESC, a.time DESC"
    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def export_attendance_csv(filepath, on_date=None, course=None):
    import csv
    records = get_attendance(on_date, course)
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Reg No", "Course", "Date", "Time", "Status"])
        for r in records:
            writer.writerow([r["name"], r["registration_no"], r["session_course"],
                             r["date"], r["time"], r["status"]])
    return len(records)


if __name__ == "__main__":
    init_db()
    print(f"Database initialised at {DB_PATH}")
