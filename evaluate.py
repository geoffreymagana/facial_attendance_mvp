"""Offline evaluation of the recognition pipeline — error rates on demand.

Uses the face samples already saved under data/faces/ (no webcam needed):

1. Splits each active student's samples into a training part and a held-out
   test part, trains a temporary LBPH model, and predicts the held-out
   images. Reports per student: correct, falsely rejected (own face shown
   as Unknown -> FRR) and misidentified (accepted as someone else — the
   worst error).
2. Estimates the False Acceptance Rate (FAR) by leave-one-student-out:
   each student's test images are predicted against a model trained
   WITHOUT them; a well-tuned threshold rejects all of them.
3. Prints the genuine/impostor confidence ranges and a suggested THRESHOLD.

Every run appends one summary row to data/evaluation_log.csv, so error
rates can be compared across changes (recaptured samples, new threshold,
more students) — evidence of whether the system is improving.

Usage:
    python evaluate.py
"""

import csv
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

import database
import recognize
import train

LOG_PATH = Path(__file__).parent / "data" / "evaluation_log.csv"
TEST_FRACTION = 0.2  # hold out the last 20% of each student's samples


def load_samples():
    """Preprocessed samples per active student: {student_id: [images]}."""
    database.init_db()
    students = {s["student_id"]: s for s in database.list_students()}
    samples = {}
    for sid in students:
        imgs = []
        for p in sorted((train.FACES_DIR / str(sid)).glob("*.png")):
            img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                imgs.append(recognize.preprocess(
                    cv2.resize(img, recognize.FACE_SIZE)))
        if imgs:
            samples[sid] = imgs
    return samples, students


def _train_model(images, labels):
    model = cv2.face.LBPHFaceRecognizer_create(
        radius=1, neighbors=8, grid_x=8, grid_y=8)
    model.train(images, np.array(labels))
    return model


def _split(samples):
    train_set, test_set = {}, {}
    for sid, imgs in samples.items():
        n_test = max(1, int(len(imgs) * TEST_FRACTION))
        train_set[sid] = imgs[:-n_test]
        test_set[sid] = imgs[-n_test:]
    return train_set, test_set


def evaluate(threshold=None):
    """Run the evaluation; returns a metrics dict and appends to the log."""
    if threshold is None:
        threshold = recognize.THRESHOLD
    samples, students = load_samples()
    if len(samples) < 2:
        raise SystemExit(
            "Need at least 2 registered students with saved samples.")
    train_set, test_set = _split(samples)

    # --- Identification on held-out images (accuracy / FRR / confusion) ---
    images, labels = [], []
    for sid, imgs in train_set.items():
        images += imgs
        labels += [sid] * len(imgs)
    model = _train_model(images, labels)

    genuine_confs = []
    correct = rejected = misidentified = total = 0
    print(f"\nPer-student results (threshold {threshold:.0f}):")
    for sid, imgs in test_set.items():
        c = r = m = 0
        for img in imgs:
            label, conf = model.predict(img)
            genuine_confs.append(conf)
            if conf > threshold:
                r += 1
            elif label == sid:
                c += 1
            else:
                m += 1
                other = students.get(label, {}).get("name", f"id {label}")
                print(f"  MISIDENTIFIED: {students[sid]['name']} -> {other} "
                      f"(confidence {conf:.1f})")
        print(f"  {students[sid]['name']:<24} correct {c}/{len(imgs)}  "
              f"rejected {r}  misidentified {m}")
        correct += c
        rejected += r
        misidentified += m
        total += len(imgs)

    # --- FAR: each student as an impostor against a model without them ---
    impostor_confs = []
    far_accepts = 0
    for sid in samples:
        images, labels = [], []
        for other, imgs in train_set.items():
            if other != sid:
                images += imgs
                labels += [other] * len(imgs)
        loo_model = _train_model(images, labels)
        for img in test_set[sid]:
            _, conf = loo_model.predict(img)
            impostor_confs.append(conf)
            if conf <= threshold:
                far_accepts += 1

    accuracy = correct / total
    frr = rejected / total
    misid_rate = misidentified / total
    far = far_accepts / len(impostor_confs)

    print(f"\nOverall on {total} held-out images, {len(samples)} students:")
    print(f"  Recognition accuracy : {accuracy:.0%}")
    print(f"  False rejection (FRR): {frr:.0%}")
    print(f"  Misidentification    : {misid_rate:.0%}")
    print(f"  False acceptance(FAR): {far:.0%}  "
          f"({far_accepts}/{len(impostor_confs)} impostor images accepted)")
    print(f"  Genuine confidence   : {min(genuine_confs):.0f}-"
          f"{max(genuine_confs):.0f} (lower = better)")
    print(f"  Impostor confidence  : {min(impostor_confs):.0f}-"
          f"{max(impostor_confs):.0f}")

    suggested = (max(genuine_confs) + min(impostor_confs)) / 2
    if max(genuine_confs) < min(impostor_confs):
        print(f"  Suggested THRESHOLD  : {suggested:.0f} "
              f"(genuine and impostor ranges are separated)")
    else:
        print("  WARNING: genuine and impostor confidences overlap — "
              "recapture samples with more head movement/better light.")

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    is_new = not LOG_PATH.exists()
    with open(LOG_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["timestamp", "students", "test_images",
                             "threshold", "accuracy", "frr",
                             "misidentification", "far"])
        writer.writerow([datetime.now().isoformat(timespec="seconds"),
                         len(samples), total, threshold,
                         f"{accuracy:.3f}", f"{frr:.3f}",
                         f"{misid_rate:.3f}", f"{far:.3f}"])
    print(f"\nSummary appended to {LOG_PATH}")

    return {"accuracy": accuracy, "frr": frr, "misidentification": misid_rate,
            "far": far, "suggested_threshold": suggested}


if __name__ == "__main__":
    evaluate()
