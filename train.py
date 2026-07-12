"""Train the LBPH face recognizer on all captured face samples.

Reads data/faces/<student_id>/*.png, trains LBPH with student_id as the
label, and saves the model to data/lbph_model.yml.
Run this after every new registration.
"""

import numpy as np

import cv_engine
import paths

DATA_DIR = paths.data_dir()
FACES_DIR = DATA_DIR / "faces"
MODEL_PATH = DATA_DIR / "lbph_model.yml"


def load_training_data():
    images, labels = [], []
    if not FACES_DIR.exists():
        return images, labels
    # Load cv2 only once we know there is at least one sample to decode, so
    # the "no samples -> remove stale model" path in train() still works when
    # OpenCV is unavailable (e.g. de-registering the last student).
    cv2 = None
    for student_dir in sorted(FACES_DIR.iterdir()):
        if not student_dir.is_dir():
            continue
        try:
            label = int(student_dir.name)
        except ValueError:
            continue
        for img_path in student_dir.glob("*.png"):
            if cv2 is None:
                cv2 = cv_engine.require_cv2()
            img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                # Equalize lighting; must match recognize.preprocess().
                images.append(cv2.equalizeHist(img))
                labels.append(label)
    return images, labels


def train():
    """Train on all face samples. Returns the number of students trained.

    With zero samples (e.g. the last student was de-registered) any existing
    model file is removed — a stale model would keep recognizing deleted
    faces — and 0 is returned instead of raising.
    """
    images, labels = load_training_data()
    if not images:
        if MODEL_PATH.exists():
            MODEL_PATH.unlink()
            print(f"No training images; removed stale model {MODEL_PATH}")
        else:
            print("No training images found.")
        return 0

    cv2 = cv_engine.require_cv2()
    recognizer = cv2.face.LBPHFaceRecognizer_create(
        radius=1, neighbors=8, grid_x=8, grid_y=8
    )
    recognizer.train(images, np.array(labels))
    recognizer.write(str(MODEL_PATH))

    n_students = len(set(labels))
    print(f"Trained on {len(images)} images across {n_students} student(s).")
    print(f"Model saved to {MODEL_PATH}")
    return n_students


if __name__ == "__main__":
    if train() == 0:
        raise SystemExit("Run register.py first.")
