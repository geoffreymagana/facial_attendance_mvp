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

import cv2
from pathlib import Path

import database

THRESHOLD = 65.0  # tune this during testing
FACE_SIZE = (200, 200)
MODEL_PATH = Path(__file__).parent / "data" / "lbph_model.yml"

CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def is_enrolled(student, session_course):
    """Enrollment check (scope item 10): the student's single registered
    course must match the session course, case-insensitive and trimmed."""
    return student["course"].strip().lower() == session_course.strip().lower()


def load_recognizer():
    if not MODEL_PATH.exists():
        raise RuntimeError(
            "No trained model found. Register at least one student first.")
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(str(MODEL_PATH))
    return recognizer


def run_session(session_course, camera_index=0):
    database.init_db()
    recognizer = load_recognizer()
    students = {s["student_id"]: s for s in database.list_students()}
    marked_this_session = set()

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(
            "Cannot open webcam. Close other apps using the camera, "
            "or try camera_index=1.")

    print(f"Session '{session_course}' started. Press q to end.")

    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # More sensitive than registration (1.2 / 80px): a session face may
        # be further from the camera; see Known Issue #1 in README.md.
        faces = CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                         minSize=(60, 60))

        for (x, y, w, h) in faces:
            face = cv2.resize(gray[y:y + h, x:x + w], FACE_SIZE)
            label, confidence = recognizer.predict(face)

            accepted = confidence <= THRESHOLD and label in students
            print(f"[predict] label={label} confidence={confidence:.1f} -> "
                  f"{'ACCEPT' if accepted else 'REJECT'}")

            if accepted and is_enrolled(students[label], session_course):
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
                # orange box, no attendance row (scope item 10).
                student = students[label]
                color = (0, 165, 255)
                text = "Recognized - not enrolled"
                print(f"[enroll] {student['name']} registered course="
                      f"'{student['course']}' session='{session_course}' "
                      f"-> NOT MARKED")
            else:
                color = (0, 0, 255)
                text = f"Unknown ({confidence:.0f})"

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
    print(f"Session ended. {len(marked_this_session)} student(s) recognized.")


if __name__ == "__main__":
    course = input("Course / session name (e.g. CS101): ").strip() or "GENERAL"
    try:
        run_session(course)
    except RuntimeError as e:
        raise SystemExit(str(e))
