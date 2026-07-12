"""Locate the application's data directory in both run modes.

As a normal ``python app.py`` run, data/ lives next to the source files.
As a PyInstaller onefile exe, ``__file__`` points inside the temporary
directory the exe unpacks itself into (deleted when the app closes), so
anything written there would be lost on exit. In that case data/ must live
next to the .exe itself (``sys.executable``), where it survives restarts
and can be backed up by copying the folder.
"""

import sys
from pathlib import Path


def app_dir():
    """Directory the application runs from: the folder containing the .exe
    when frozen by PyInstaller, else the folder containing the source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def data_dir():
    """The data/ directory (database, face images, model, logs)."""
    return app_dir() / "data"
