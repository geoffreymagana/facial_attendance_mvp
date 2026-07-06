"""Student registration: capture face samples from the webcam.

Usage:
    python register.py
Prompts for student details, then opens the webcam and captures
NUM_SAMPLES grayscale face crops saved to data/faces/<student_id>/.
Press 'q' to abort early.
"""

import cv2
from pathlib import Path

import database

NUM_SAMPLES = 30
FACE_SIZE = (200, 200)

CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def capture_faces(student_id, num_samples=NUM_SAMPLES, camera_index=0):
    out_dir = Path(__file__).parent / "data" / "faces" / str(student_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError("Cannot open webcam. Check camera index / permissions.")

    count = 0
    print(f"Capturing {num_samples} samples. Look at the camera, move your head "
          f"slightly (left/right/up/down) so the model learns different angles.")

    while count < num_samples:
        ok, frame = cap.read()
        if not ok:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = CASCADE.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5,
                                         minSize=(80, 80))

        for (x, y, w, h) in faces[:1]:  # take only the largest/first face
            face = cv2.resize(gray[y:y + h, x:x + w], FACE_SIZE)
            count += 1
            cv2.imwrite(str(out_dir / f"{count:03d}.png"), face)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, f"Sample {count}/{num_samples}", (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow("Registration - press q to abort", frame)
        if cv2.waitKey(100) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"Saved {count} samples to {out_dir}")
    return count


def main():
    database.init_db()
    name = input("Student name: ").strip()
    reg_no = input("Registration number: ").strip()
    course = input("Course: ").strip()

    student_id = database.add_student(name, reg_no, course)
    print(f"Registered student #{student_id}: {name}")
    capture_faces(student_id)
    print("Now run: python train.py")


if __name__ == "__main__":
    main()
