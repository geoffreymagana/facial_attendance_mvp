"""Smoke tests: every module imports cleanly with the installed deps."""

import importlib

import pytest


@pytest.mark.parametrize("module_name", [
    "database", "register", "train", "recognize", "app",
])
def test_module_imports(module_name):
    assert importlib.import_module(module_name) is not None


def test_cv2_face_module_present():
    """README requirement: opencv-contrib-python, not plain opencv-python."""
    import cv2
    assert cv2.face.LBPHFaceRecognizer_create() is not None
