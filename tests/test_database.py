"""Tests for database.py: students, attendance marking, filtering, export."""

import csv
import sqlite3

import pytest


def test_init_db_creates_tables(db):
    conn = db.get_connection()
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {"students", "attendance"} <= tables


def test_add_student_returns_id_and_sets_face_dir(db):
    sid = db.add_student("Alice Wanjiku", "CS/001/2026", "CS101")
    assert sid == 1
    student = db.get_student(sid)
    assert student["name"] == "Alice Wanjiku"
    assert student["registration_no"] == "CS/001/2026"
    assert student["course"] == "CS101"
    assert student["face_dir"] == "data/faces/1"


def test_add_student_strips_whitespace(db):
    sid = db.add_student("  Bob  ", " CS/002/2026 ", " CS101 ")
    student = db.get_student(sid)
    assert student["name"] == "Bob"
    assert student["registration_no"] == "CS/002/2026"
    assert student["course"] == "CS101"


def test_registration_no_must_be_unique(db):
    db.add_student("Alice", "CS/001/2026", "CS101")
    with pytest.raises(sqlite3.IntegrityError):
        db.add_student("Impostor", "CS/001/2026", "CS102")


def test_get_student_missing_returns_none(db):
    assert db.get_student(999) is None


def test_list_students_ordered_by_id(db):
    db.add_student("Alice", "R1", "CS101")
    db.add_student("Bob", "R2", "CS101")
    db.add_student("Carol", "R3", "CS102")
    names = [s["name"] for s in db.list_students()]
    assert names == ["Alice", "Bob", "Carol"]


def test_deactivate_student_hides_from_list_but_keeps_history(db):
    sid = db.add_student("Alice", "R1", "CS101")
    db.mark_attendance(sid, "CS101")

    db.deactivate_student(sid)

    assert db.list_students() == []
    inactive = db.list_students(include_inactive=True)
    assert len(inactive) == 1 and inactive[0]["active"] == 0
    assert len(db.get_attendance()) == 1  # history preserved


def test_remove_student_rollback_frees_registration_no(db):
    sid = db.add_student("Alice", "R1", "CS101")
    assert db.remove_student_if_no_attendance(sid) is True
    assert db.get_student(sid) is None
    # The registration number can be used again after the rollback.
    db.add_student("Alice", "R1", "CS101")


def test_remove_student_refuses_when_history_exists(db):
    sid = db.add_student("Alice", "R1", "CS101")
    db.mark_attendance(sid, "CS101")
    assert db.remove_student_if_no_attendance(sid) is False
    assert db.get_student(sid) is not None
    assert len(db.get_attendance()) == 1


def test_init_db_migrates_pre_active_schema(tmp_path, monkeypatch):
    """Databases created before de-registration existed gain the active
    column (defaulting to 1) instead of breaking."""
    import database
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE students ("
        "student_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, "
        "registration_no TEXT NOT NULL UNIQUE, course TEXT NOT NULL, "
        "face_dir TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    conn.execute(
        "INSERT INTO students (name, registration_no, course) "
        "VALUES ('Old Alice', 'R1', 'CS101')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(database, "DB_PATH", path)
    database.init_db()

    students = database.list_students()
    assert len(students) == 1
    assert students[0]["active"] == 1


def test_mark_attendance_first_time_returns_true(db):
    sid = db.add_student("Alice", "R1", "CS101")
    assert db.mark_attendance(sid, "CS101", confidence=42.5) is True
    records = db.get_attendance()
    assert len(records) == 1
    assert records[0]["status"] == "Present"
    assert records[0]["confidence"] == 42.5


def test_mark_attendance_duplicate_same_day_returns_false(db):
    sid = db.add_student("Alice", "R1", "CS101")
    assert db.mark_attendance(sid, "CS101") is True
    assert db.mark_attendance(sid, "CS101") is False
    assert len(db.get_attendance()) == 1


def test_mark_attendance_different_course_same_day_allowed(db):
    sid = db.add_student("Alice", "R1", "CS101")
    assert db.mark_attendance(sid, "CS101") is True
    assert db.mark_attendance(sid, "CS205") is True
    assert len(db.get_attendance()) == 2


def test_get_attendance_filters_by_date_and_course(db):
    from datetime import date
    today = date.today().isoformat()
    a = db.add_student("Alice", "R1", "CS101")
    b = db.add_student("Bob", "R2", "CS101")
    db.mark_attendance(a, "CS101")
    db.mark_attendance(b, "CS205")

    assert len(db.get_attendance(on_date=today)) == 2
    assert len(db.get_attendance(on_date="1999-01-01")) == 0

    cs101 = db.get_attendance(course="CS101")
    assert len(cs101) == 1
    assert cs101[0]["name"] == "Alice"

    both = db.get_attendance(on_date=today, course="CS205")
    assert len(both) == 1
    assert both[0]["name"] == "Bob"


def test_export_attendance_csv(db, tmp_path):
    sid = db.add_student("Alice", "R1", "CS101")
    db.mark_attendance(sid, "CS101")
    out = tmp_path / "export.csv"

    n = db.export_attendance_csv(str(out))

    assert n == 1
    with open(out, newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["Name", "Reg No", "Course", "Date", "Time", "Status"]
    assert rows[1][0] == "Alice"
    assert rows[1][2] == "CS101"
    assert rows[1][5] == "Present"


def test_export_attendance_csv_empty(db, tmp_path):
    out = tmp_path / "empty.csv"
    n = db.export_attendance_csv(str(out))
    assert n == 0
    with open(out, newline="") as f:
        rows = list(csv.reader(f))
    assert len(rows) == 1  # header only
