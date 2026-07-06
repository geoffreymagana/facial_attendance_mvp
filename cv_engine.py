"""Fault-tolerant access to the OpenCV (cv2) runtime.

Importing cv2 loads native DLLs that can be missing or broken on a fresh
Windows machine — most often a missing Microsoft Visual C++ redistributable,
or an opencv wheel whose DLLs fail to load. If that happens at import time it
takes the whole GUI down before the user can reach the screen that would let
them fix it (or plug in an external camera).

So nothing here imports cv2 at module load. Callers ask for it on demand;
the first failure is cached and surfaced as a readable status the UI can
show instead of a traceback. After the user installs the runtime, reset()
lets the next call try again without restarting the app.
"""

import importlib

_cv2 = None
_cascade = None
_error = None
_loaded = False


def load_cv2():
    """Return the cv2 module, or None if it cannot be loaded. Never raises;
    call error_message() for the reason it failed."""
    global _cv2, _error, _loaded
    if _loaded:
        return _cv2
    _loaded = True
    try:
        _cv2 = importlib.import_module("cv2")
    except Exception as e:
        # ImportError for a missing wheel; OSError/ImportError with a DLL
        # load message on Windows. A broken native import can surface in
        # several ways, so catch broadly and keep the reason for the UI.
        _cv2 = None
        _error = e
    return _cv2


def available():
    """True if the OpenCV runtime can be loaded."""
    return load_cv2() is not None


def error_message():
    """Human-readable reason cv2 could not load, or '' if it loaded fine."""
    load_cv2()
    if _error is None:
        return ""
    return f"{type(_error).__name__}: {_error}"


def require_cv2():
    """Return the cv2 module, or raise a RuntimeError that explains what to
    install. Use this in code paths that cannot proceed without OpenCV."""
    cv2 = load_cv2()
    if cv2 is None:
        raise RuntimeError(
            "OpenCV (cv2) is not available, so camera features are disabled.\n"
            f"Reason: {error_message()}\n\n"
            "On Windows this is usually a missing Microsoft Visual C++ "
            "redistributable. Install it (or reinstall opencv-contrib-python), "
            "then click 'Retry camera engine'.")
    return cv2


def face_cascade():
    """The Haar frontal-face detector, built on first use. Raises via
    require_cv2() if OpenCV is unavailable."""
    global _cascade
    cv2 = require_cv2()
    if _cascade is None:
        _cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    return _cascade


def reset():
    """Forget a previous (failed) load so the next call retries — call after
    the user has installed the missing runtime."""
    global _cv2, _cascade, _error, _loaded
    _cv2 = None
    _cascade = None
    _error = None
    _loaded = False
