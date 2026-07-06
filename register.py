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


def detect_cameras(max_devices=5):
    """Indices of camera devices OpenCV can currently open and read from:
    the built-in webcam, a USB webcam, or a phone exposed as a camera by a
    webcam app (DroidCam, Iriun, EpocCam, ...). Returns e.g. [0, 1];
    empty list means no working camera was found."""
    found = []
    for index in range(max_devices):
        cap = cv2.VideoCapture(index)
        if cap.isOpened():
            ok, _ = cap.read()
            if ok:
                found.append(index)
        cap.release()
    return found


def capture_faces(student_id, num_samples=NUM_SAMPLES, camera_index=0):
    out_dir = Path(__file__).parent / "data" / "faces" / str(student_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(
            f"Cannot open camera {camera_index}. Close other apps using it, "
            f"or select a different camera device.")

    # Let the camera auto-expose/auto-focus before sampling; the first
    # frames are often too dark and poison the training set.
    for _ in range(10):
        cap.read()

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
        # 200ms between samples (~6s total): near-duplicate burst frames
        # teach LBPH the lighting of the moment, not the face.
        if cv2.waitKey(200) & 0xFF == ord("q"):
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

    cam = input("Camera index (Enter for 0): ").strip()

    student_id = database.add_student(name, reg_no, course)
    print(f"Registered student #{student_id}: {name}")
    capture_faces(student_id, camera_index=int(cam) if cam.isdigit() else 0)
    print("Now run: python train.py")


if __name__ == "__main__":
    main()
