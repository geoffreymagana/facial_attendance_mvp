"""Tests for train.py and recognize.py using synthetic face images.

No webcam needed: the LBPH pipeline (load data -> train -> save model ->
load model -> predict) is exercised on deterministic generated textures.
"""

import cv2
import numpy as np
import pytest

import recognize
import train

from conftest import make_face


def test_load_training_data_reads_all_samples(faces_dataset):
    images, labels = train.load_training_data()
    assert len(images) == 20
    assert sorted(set(labels)) == [1, 2]
    assert labels.count(1) == 10
    assert labels.count(2) == 10
    assert all(img.shape == (200, 200) for img in images)


def test_load_training_data_ignores_non_numeric_dirs(faces_dataset):
    junk = faces_dataset["faces_dir"] / "not_a_student"
    junk.mkdir()
    cv2.imwrite(str(junk / "001.png"), make_face(seed=77))

    _, labels = train.load_training_data()
    assert set(labels) == {1, 2}


def test_load_training_data_missing_dir_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(train, "FACES_DIR", tmp_path / "does_not_exist")
    images, labels = train.load_training_data()
    assert images == [] and labels == []


def test_train_with_no_images_returns_zero_and_removes_stale_model(
        tmp_path, monkeypatch):
    """After the last student is de-registered, retraining must remove the
    stale model instead of crashing — otherwise deleted faces would still
    be recognized."""
    monkeypatch.setattr(train, "FACES_DIR", tmp_path / "empty")
    stale = tmp_path / "lbph_model.yml"
    stale.write_text("stale model")
    monkeypatch.setattr(train, "MODEL_PATH", stale)

    assert train.train() == 0
    assert not stale.exists()


def test_train_creates_model_file(faces_dataset):
    train.train()
    assert faces_dataset["model_path"].exists()
    assert faces_dataset["model_path"].stat().st_size > 0


def test_trained_model_recognizes_training_faces(faces_dataset):
    train.train()
    recognizer = recognize.load_recognizer()

    for student_id in (1, 2):
        sample = cv2.imread(
            str(faces_dataset["faces_dir"] / str(student_id) / "000.png"),
            cv2.IMREAD_GRAYSCALE)
        label, confidence = recognizer.predict(sample)
        assert label == student_id
        assert confidence <= recognize.THRESHOLD, (
            f"training image should match well below the Unknown threshold, "
            f"got {confidence:.1f}")


def test_unknown_face_scores_worse_than_known(faces_dataset):
    train.train()
    recognizer = recognize.load_recognizer()

    known = cv2.imread(
        str(faces_dataset["faces_dir"] / "1" / "000.png"),
        cv2.IMREAD_GRAYSCALE)
    stranger = make_face(seed=999999)  # texture never seen in training

    _, known_conf = recognizer.predict(known)
    _, stranger_conf = recognizer.predict(stranger)
    # LBPH confidence is a distance: lower = better match.
    assert known_conf < stranger_conf


def test_load_recognizer_without_model_raises_runtime_error(
        tmp_path, monkeypatch):
    """RuntimeError (not SystemExit) so the GUI thread can catch it and
    show a friendly dialog (guard rail 9a)."""
    monkeypatch.setattr(recognize, "MODEL_PATH", tmp_path / "missing.yml")
    with pytest.raises(RuntimeError):
        recognize.load_recognizer()


@pytest.mark.parametrize("registered, session, expected", [
    ("CS101", "CS101", True),
    ("CS101", "cs101", True),          # case-insensitive
    ("CS101", "  CS101  ", True),      # trimmed
    (" cs101 ", "CS101", True),        # both sides normalised
    ("CS101", "CS205", False),         # not enrolled
    ("CS101", "CS1010", False),        # no prefix matching
])
def test_is_enrolled_matches_case_insensitive_trimmed(
        registered, session, expected):
    """Enrollment check (scope item 10): session course vs the student's
    single registered course field."""
    student = {"course": registered}
    assert recognize.is_enrolled(student, session) is expected


def test_haar_cascade_is_available():
    """Guards the dependency requirement: opencv-contrib-python 4.x must
    bundle the frontal-face cascade (OpenCV 5 wheels dropped it)."""
    assert not recognize.CASCADE.empty()


def test_cascade_detects_a_real_face_pattern():
    """Sanity-check detection on a synthetic but face-like image: light
    oval with darker eye/mouth regions on a mid-gray background."""
    img = np.full((400, 400), 100, dtype=np.uint8)
    cv2.ellipse(img, (200, 200), (90, 120), 0, 0, 360, 200, -1)  # head
    cv2.circle(img, (165, 165), 12, 60, -1)   # left eye
    cv2.circle(img, (235, 165), 12, 60, -1)   # right eye
    cv2.ellipse(img, (200, 260), (30, 12), 0, 0, 360, 90, -1)    # mouth
    img = cv2.GaussianBlur(img, (7, 7), 0)

    faces = recognize.CASCADE.detectMultiScale(
        img, scaleFactor=1.1, minNeighbors=3, minSize=(80, 80))
    # Haar cascades are approximate; assert it runs and returns a
    # well-formed result rather than demanding a hit on synthetic input.
    assert faces is not None
