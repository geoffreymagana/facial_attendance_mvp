# Facial Recognition Class Attendance System (MVP)

Python + OpenCV (Haar cascade detection, LBPH recognition) + SQLite + Tkinter.
Matches the architecture in the project proposal: three tiers (GUI /
recognition logic / database), enrollment phase + recognition phase.

## 1. Setup (once)

Requires Python 3.10+ and a webcam.

```bash
pip install opencv-contrib-python numpy
```

Important: it must be **opencv-contrib-python** (not plain opencv-python) —
LBPH lives in the contrib module. If both are installed, uninstall both and
reinstall only contrib.

Verify:
```bash
python -c "import cv2; cv2.face.LBPHFaceRecognizer_create(); print('OK')"
```

## 2. Run it

Everything through the GUI:
```bash
python app.py
```

Or via the individual scripts (useful for testing/debugging):
```bash
python register.py    # enroll a student: details + 30 face samples via webcam
python train.py       # retrain LBPH model (run after every registration)
python recognize.py   # start a live attendance session
```

## 3. Workflow

1. **Register** each student: enter name/reg no/course, the webcam opens and
   captures 30 grayscale face crops. Move your head slightly during capture
   (left, right, up, down, glasses on/off) — variety makes the model robust.
2. **Train** happens automatically after GUI registration (or run train.py).
3. **Start Session**: enter the course name. Recognized students are marked
   Present once per course per day (duplicates blocked at the database level).
   Unknown faces show a red box and are ignored.
4. **View Attendance**: filter by date/course, export to CSV.

## 4. Threshold tuning (the key testing task)

LBPH confidence is a distance: **lower = better match**. The cutoff is
`THRESHOLD` in recognize.py (default 65).

- Registered students being shown as Unknown → raise it (70–80).
- Strangers being recognized as students → lower it (50–60).

Test procedure for the report (Chapter 4):
1. Register 3–5 real people.
2. Each person stands in front of the camera 10 times; record how many times
   they are correctly recognized → recognition accuracy.
3. Have 2–3 unregistered people try; record how often they are wrongly
   accepted → False Acceptance Rate (FAR).
4. Count how often registered people are rejected → False Rejection Rate (FRR).
5. Repeat under two lighting conditions (window light vs artificial light).
6. Screenshot everything as you go — those are your report figures.

## 5. Can I use a pre-made face dataset?

Yes, for development: drop grayscale 200x200 face crops into
`data/faces/<student_id>/` and run train.py. But register real people (you
and friends) for the demo — live enrollment is part of what will be examined.

## 6. Troubleshooting

- **"Cannot open webcam"** — another app is using it, or change
  `camera_index=0` to 1 in register.py / recognize.py.
- **`cv2.face` AttributeError** — you have plain opencv-python installed;
  see Setup above.
- **Poor recognition** — recapture samples with better lighting; make sure
  faces fill a good portion of the frame during registration.
- **Camera window frozen on Linux** — use `opencv-contrib-python` (GUI
  build), not the headless variant.

## Files

- `app.py` — Tkinter GUI (register / session / view+export)
- `database.py` — SQLite schema and queries
- `register.py` — face capture / enrollment
- `train.py` — LBPH training
- `recognize.py` — live recognition + attendance marking
