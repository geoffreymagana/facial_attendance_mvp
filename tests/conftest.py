"""Shared fixtures: isolate every test from the real data/ directory.

The app stores its SQLite DB and model under <project>/data. Tests must
never touch that, so these fixtures repoint the module-level path
constants at a pytest tmp_path.
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

# Make the project importable when pytest is run from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import train  # noqa: E402
import recognize  # noqa: E402

FACE_SIZE = (200, 200)


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Fresh empty database in a temp directory."""
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "attendance.db")
    database.init_db()
    return database


def make_face(seed, size=FACE_SIZE):
    """Deterministic synthetic grayscale 'face' image.

    Each seed produces a distinct texture, which is what LBPH actually
    discriminates on — good enough to exercise train/predict end to end
    without a webcam.
    """
    rng = np.random.default_rng(seed)
    img = rng.integers(0, 256, size=size, dtype=np.uint8)
    # Smooth a little so the texture is stable rather than pure noise.
    return cv2.GaussianBlur(img, (5, 5), 0)


@pytest.fixture
def faces_dataset(tmp_path, monkeypatch):
    """Synthetic training set for two students (ids 1 and 2), with
    train.py and recognize.py repointed at the temp directory."""
    faces_dir = tmp_path / "faces"
    model_path = tmp_path / "lbph_model.yml"
    monkeypatch.setattr(train, "FACES_DIR", faces_dir)
    monkeypatch.setattr(train, "MODEL_PATH", model_path)
    monkeypatch.setattr(recognize, "MODEL_PATH", model_path)

    for student_id in (1, 2):
        student_dir = faces_dir / str(student_id)
        student_dir.mkdir(parents=True)
        for i in range(10):
            # Same base seed per student, tiny per-sample variation.
            img = make_face(seed=student_id * 1000)
            noise = np.random.default_rng(i).integers(
                0, 8, size=img.shape, dtype=np.uint8)
            img = cv2.add(img, noise)
            cv2.imwrite(str(student_dir / f"{i:03d}.png"), img)

    return {"faces_dir": faces_dir, "model_path": model_path}
