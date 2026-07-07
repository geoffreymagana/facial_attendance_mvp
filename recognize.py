"""Live attendance session: recognize faces and mark attendance.

Usage:
    python recognize.py
Prompts for the course/session name, opens the webcam, and marks each
recognized registered student present (once per course per day) — but only
if the session course matches their registered course (enrollment check).
Unknown faces are labelled Unknown and ignored. Press 'q' to end session.

LBPH confidence: LOWER is BETTER (it is a distance). Faces with
confidence above THRESHOLD are treated as Unknown. Tune THRESHOLD
during testing — typical working range is 50-80.
"""

import csv
from datetime import datetime
from pathlib import Path

import cv_engine
import database

THRESHOLD = 65.0  # tune this during testing (evaluate.py suggests a value)
DUPLICATE_THRESHOLD = 55.0  # stricter: same-face matches are strong
FACE_SIZE = (200, 200)
MODEL_PATH = Path(__file__).parent / "data" / "lbph_model.yml"
PREDICTIONS_LOG = Path(__file__).parent / "data" / "predictions_log.csv"


def preprocess(gray_face):
    """Histogram-equalize a grayscale face crop so LBPH compares facial
    texture rather than overall lighting. Must stay identical to the
    preprocessing applied at training time (train.py)."""
    return cv_engine.require_cv2().equalizeHist(gray_face)


def is_enrolled(student, session_course):
    """Enrollment check (scope item 10): the student's single registered
    course must match the session course, case-insensitive and trimmed."""
    return student["course"].strip().lower() == session_course.strip().lower()


def load_recognizer():
    if not MODEL_PATH.exists():
        raise RuntimeError(
            "No trained model found. Register at least one student first.")
    recognizer = cv_engine.require_cv2().face.LBPHFaceRecognizer_create()
    recognizer.read(str(MODEL_PATH))
    return recognizer


def match_existing_student(face_dir, exclude_id=None):
    """Duplicate-registration check: predict newly captured samples against
    the current model (trained before this student was added). Returns
    (student, match_fraction, mean_confidence) if at least half the samples
    match one existing active student below DUPLICATE_THRESHOLD, else None.
    """
    if not MODEL_PATH.exists():
        return None
    cv2 = cv_engine.require_cv2()
    recognizer = load_recognizer()
    students = {s["student_id"]: s for s in database.list_students()}
    students.pop(exclude_id, None)
    if not students:
        return None

    votes, confs, total = {}, {}, 0
    for img_path in sorted(Path(face_dir).glob("*.png")):
        img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        total += 1
        label, conf = recognizer.predict(
            preprocess(cv2.resize(img, FACE_SIZE)))
        if label in students and conf <= DUPLICATE_THRESHOLD:
            votes[label] = votes.get(label, 0) + 1
            confs.setdefault(label, []).append(conf)

    if not votes:
        return None
    best = max(votes, key=votes.get)
    if votes[best] * 2 >= total:
        mean_conf = sum(confs[best]) / len(confs[best])
        return students[best], votes[best] / total, mean_conf
    return None


def _open_predictions_log():
    """Append-mode CSV of every prediction — the evidence base for
    threshold tuning and error-rate reporting."""
    PREDICTIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
    is_new = not PREDICTIONS_LOG.exists()
    f = open(PREDICTIONS_LOG, "a", newline="")
    writer = csv.writer(f)
    if is_new:
        writer.writerow(["timestamp", "session_course", "label",
                         "confidence", "decision"])
    return f, writer


def run_session(session_course, camera_index=0):
    cv2 = cv_engine.require_cv2()
    cascade = cv_engine.face_cascade()
    database.init_db()
    recognizer = load_recognizer()
    students = {s["student_id"]: s for s in database.list_students()}
    marked_this_session = set()

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(
            f"Cannot open camera {camera_index}. Close other apps using it, "
            f"or select a different camera device.")

    print(f"Session '{session_course}' started. Press q to end.")
    log_file, log = _open_predictions_log()

    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # More sensitive than registration (1.2 / 80px): a session face may
        # be further from the camera.
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                         minSize=(60, 60))

        for (x, y, w, h) in faces:
            face = preprocess(cv2.resize(gray[y:y + h, x:x + w], FACE_SIZE))
            label, confidence = recognizer.predict(face)

            accepted = confidence <= THRESHOLD and label in students

            if accepted and is_enrolled(students[label], session_course):
                decision = "ACCEPT"
                student = students[label]
                name = student["name"]
                color = (0, 255, 0)
                text = f"{name} ({confidence:.0f})"

                if label not in marked_this_session:
                    newly = database.mark_attendance(label, session_course,
                                                     confidence)
                    marked_this_session.add(label)
                    if newly:
                        print(f"  MARKED PRESENT: {name} "
                              f"(confidence {confidence:.1f})")
                    else:
                        print(f"  {name} already marked today.")
            elif accepted:
                # Recognized but not enrolled in this session's course:
                # orange box, no attendance row.
                decision = "NOT_ENROLLED"
                student = students[label]
                color = (0, 165, 255)
                text = "Recognized - not enrolled"
                print(f"[enroll] {student['name']} registered course="
                      f"'{student['course']}' session='{session_course}' "
                      f"-> NOT MARKED")
            else:
                decision = "REJECT"
                color = (0, 0, 255)
                text = f"Unknown ({confidence:.0f})"

            print(f"[predict] label={label} confidence={confidence:.1f} -> "
                  f"{decision}")
            log.writerow([datetime.now().isoformat(timespec="seconds"),
                          session_course, label, f"{confidence:.1f}", decision])

            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, text, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        cv2.putText(frame, f"Session: {session_course}  |  q = end",
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        cv2.imshow("Attendance Session", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    log_file.close()

    # Attendance is now marked by inference too: everyone enrolled in this
    # course who was never recognized is recorded Absent for today.
    absent = database.mark_session_absentees(session_course)
    present = len(marked_this_session)
    print(f"Session ended. {present} student(s) recognized and marked present.")
    print(f"Marked {absent} enrolled student(s) absent for '{session_course}'.")
    print(f"Predictions logged to {PREDICTIONS_LOG}")
    return {"present": present, "absent": absent}


if __name__ == "__main__":
    course = input("Course / session name (e.g. CS101): ").strip() or "GENERAL"
    cam = input("Camera index (Enter for 0): ").strip()
    try:
        run_session(course, camera_index=int(cam) if cam.isdigit() else 0)
    except RuntimeError as e:
        raise SystemExit(str(e))
