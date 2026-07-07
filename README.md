# Facial Recognition Class Attendance System

A desktop application that automates class attendance using facial
recognition. A lecturer registers students by capturing their face with a
webcam; during a lecture, the system watches the camera feed, recognizes
registered students in real time, and marks them present automatically —
removing the need for manual roll calls or sign-in sheets that can be
forged or consume lecture time.

Built with Python, OpenCV (Haar cascade face detection + LBPH face
recognition), SQLite, and Tkinter.

---

## System architecture

The system follows a three-tier architecture:

| Tier | Component | Files |
| --- | --- | --- |
| Presentation | Tkinter GUI (registration, live session, reports) | `app.py` |
| Application logic | Face capture, model training, live recognition | `register.py`, `train.py`, `recognize.py` |
| Data | SQLite database and file storage for face images and the trained model | `database.py`, `data/` |

Operation is split into two phases:

1. **Enrollment phase** — a student's details are stored in the database
   and 30 grayscale face samples are captured from the webcam and saved to
   `data/faces/<student_id>/`. The LBPH model is then (re)trained on all
   registered students' samples, using the student's database ID as the
   training label.
2. **Recognition phase** — during a session, each video frame is converted
   to grayscale, faces are detected with a Haar cascade classifier, and
   each detected face is passed to the trained LBPH recognizer, which
   returns the closest matching student label and a confidence score.

## Features

- **Student registration** — personal details (name, registration number,
  course) plus 30 webcam face samples per student, spaced ~200 ms apart
  (after a short camera warm-up) so the model learns pose variety rather
  than 30 copies of one frame. Registration numbers are unique (enforced
  by a database constraint, with a friendly error dialog on duplicates).
- **Duplicate-face check** — after capture, the new samples are compared
  against the existing model; if most of them strongly match an
  already-registered student, the lecturer is warned that the same person
  may be enrolling under a second registration number and can cancel the
  registration.
- **Automatic model training** — the LBPH recognizer is retrained after
  every registration and de-registration.
- **Live attendance sessions** — the lecturer enters the course name and
  starts the camera. Recognized, enrolled students are marked Present
  automatically. The session runs until the lecturer presses `q`.
- **Unknown-face rejection** — faces that do not match any registered
  student closely enough are shown with a red "Unknown" box and are not
  marked. Every prediction is also logged to the console with its
  confidence score so the rejection threshold can be tuned with evidence.
- **Enrollment check** — a recognized student is only marked Present if
  the session course matches their registered course (case-insensitive,
  whitespace-trimmed). Otherwise the face is shown with an orange
  "Recognized - not enrolled" box and no attendance record is created.
- **Duplicate prevention** — a student can be marked at most once per
  course per calendar day, enforced by a database UNIQUE constraint.
  Running two sessions for the same course on the same day never
  double-marks anyone.
- **Absentee marking (by inference)** — when a session ends, every enrolled
  student (active, and registered for that course) who was never recognized
  is recorded **Absent** for that course and day. Recognized students stay
  Present, and a latecomer who appears in a later same-day session for the
  same course is upgraded from Absent back to Present. The GUI shows a
  present/absent summary at session end and colours the status column.
- **Attendance reports** — view attendance filtered by date, course and/or
  status (Present/Absent) in the GUI, and export the filtered view to CSV.
- **De-registration** — removes a student from recognition: the student is
  marked inactive, their face images are deleted, and the model is
  retrained. Their attendance history is deliberately preserved so past
  reports remain accurate.
- **External camera support** — any camera OpenCV can open works as the
  video source: the built-in webcam, a USB webcam, or a phone used as a
  camera. A "Detect cameras" button scans for connected devices and the
  lecturer picks one from a dropdown (shared by registration and
  sessions), so the system is not tied to the laptop's own camera.
- **Error handling** — friendly dialogs (no crashes) when a session is
  started before any student is registered, when a registration number is
  already taken, or when the webcam is unavailable or in use. If the
  webcam fails before any face sample is saved, the half-created student
  record is rolled back so the registration number can be reused.

## How recognition works

**Face detection** uses OpenCV's pre-trained Haar cascade
(`haarcascade_frontalface_default.xml`) on each grayscale frame. The live
session uses a more sensitive configuration (`scaleFactor=1.1`,
`minSize=(60, 60)`) than registration, because during a session students
may be further from the camera.

**Face recognition** uses LBPH (Local Binary Patterns Histograms), which
describes each face as a histogram of local texture patterns and compares
histograms between the detected face and the training data.

**Preprocessing**: every face crop is histogram-equalized
(`cv2.equalizeHist`) before both training and prediction. LBPH is
sensitive to overall brightness, so without this step the model tends to
match on lighting conditions instead of facial features — typically
predicting whichever student was registered most recently, since their
samples best match the current camera exposure. Equalization normalizes
the lighting so the comparison is about the face.

**The confidence score is a distance: lower means a better match.** A
detected face is accepted as a registered student only when its confidence
is at or below the threshold (`THRESHOLD` in `recognize.py`, default 65);
anything above the threshold is rejected as Unknown. This threshold is the
key tuning parameter:

- Registered students frequently shown as Unknown → raise it (70–80).
- Strangers accepted as registered students → lower it (50–60).

To make tuning evidence-based rather than guesswork, every prediction is
logged to the console as:

```text
[predict] label=<student_id> confidence=<value> -> ACCEPT/REJECT/NOT_ENROLLED
```

and appended to `data/predictions_log.csv` with a timestamp and the
session course, so error rates during real sessions can be analyzed after
the fact.

A known limitation of LBPH: with only one registered student the model has
no negative examples, so rejection of strangers is unreliable. Rejection
quality improves noticeably once three or more students are registered,
which is why testing is done with at least three people.

## Database design

Two tables in a single SQLite file (`data/attendance.db`):

- **students** — `student_id` (primary key, doubles as the model's
  training label), `name`, `registration_no` (UNIQUE), `course`,
  `face_dir`, `active` (set to 0 on de-registration), `created_at`.
- **attendance** — `attendance_id`, `student_id` (foreign key),
  `session_course`, `date`, `time`, `status`, `confidence`, with
  `UNIQUE (student_id, session_course, date)` providing the
  once-per-course-per-day guarantee at the database level.

### Storage growth

For a realistic deployment (50 students, 5 sessions/day, 15-week
semester):

- Attendance rows are ~100 bytes each → roughly 19,000 rows ≈ 2 MB per
  semester. SQLite comfortably handles millions of rows, so no archiving
  or purging mechanism is required at this scale.
- Face images: 30 PNGs × ~50 KB ≈ 1.5 MB per student ≈ 75 MB for 50
  students, removed automatically on de-registration.
- The trained model (`data/lbph_model.yml`) grows linearly with the number
  of students and stays within a few megabytes.

CSV export doubles as the long-term archive: export at the end of each
semester and keep the file.

## Defined behaviors (edge cases)

| Case | Behavior |
| --- | --- |
| Session started with no trained model | Error dialog, no crash |
| Duplicate registration number | Error dialog (database UNIQUE constraint) |
| Webcam busy or absent | Error dialog with a camera-index hint |
| OpenCV runtime fails to load (e.g. missing DLL on Windows) | GUI still opens; a banner explains camera features are disabled and offers **Retry camera engine**. Viewing/exporting attendance keeps working |
| Webcam fails during registration before any sample is saved | Student record rolled back so the registration number can be retried |
| Multiple faces in frame during a session | All faces are processed |
| Multiple faces in frame during registration | Only the first face is sampled |
| Same student, same course, same day | Marked once; silently ignored afterwards |
| Same student, different course, same day | Marked separately per course — only for the course they are enrolled in |
| Session ends with enrolled students unseen | Each unseen enrolled student is recorded Absent for that course and day |
| Latecomer appears in a later same-day session | Their Absent record is upgraded to Present (no duplicate row) |
| Status filter set to Present or Absent in the View tab | Only rows with that status are shown and exported; "All" (the default) shows both |
| Recognized student, session course ≠ their registered course | Orange "Recognized - not enrolled" box, console log, no attendance row |
| Session course typed with different casing/spacing (e.g. " cs101 ") | Still matches — comparison is case-insensitive and trimmed |
| De-registered student appears in a session | Shown as Unknown (excluded from the model after retraining) |
| Last remaining student de-registered | Model file removed; the no-model guard then applies |
| Registration aborted early (`q`) with fewer than 30 samples | Model still trains on what exists; the GUI warns if fewer than 10 samples were captured |
| Registering or de-registering while a session is running | Prevented — those buttons are disabled during a session (retraining mid-session is unsupported) |

A session has no fixed or minimum duration: it starts when the lecturer
clicks Start and ends when they press `q` in the camera window. Attendance
uniqueness is per (student, course, calendar date), not per session.

## Setup

Requires Python 3.10+ and a webcam.

```bash
pip install -r requirements.txt
python -c "import cv2; cv2.face.LBPHFaceRecognizer_create(); print('OK')"
python app.py
```

The dependency must be **opencv-contrib-python** (the LBPH recognizer
lives in the contrib module). If plain opencv-python is also installed,
uninstall both and reinstall only contrib. The version is pinned below 5
in `requirements.txt` because the OpenCV 5 wheels no longer bundle the
Haar cascade XML files this project loads from `cv2.data.haarcascades`.

## Usage

Everything is available through the GUI (`python app.py`), which has three
tabs:

1. **Register Student** — enter name, registration number, and course,
   then click the capture button. The webcam opens and captures 30 face
   samples; moving the head slightly during capture (left, right, up,
   down) makes the model more robust. Training runs automatically
   afterwards. The same tab lists registered students and provides
   de-registration.
2. **Start Session** — enter the course name and start the camera.
   Recognized enrolled students are marked Present; press `q` in the
   camera window to end the session.
3. **View Attendance** — filter records by date, course and/or status
   (Present/Absent), and export the current view to CSV.

### Using an external camera (USB webcam or phone)

Both webcam tabs have a **Camera device** dropdown with a **Detect
cameras** button:

- **USB webcam** — plug it in, click Detect cameras, and pick its number
  (device 0 is usually the built-in webcam; the USB camera appears as 1
  or higher).
- **Phone as camera** — install a webcam app such as DroidCam or Iriun
  (phone app + free Windows client), connect via USB cable or Wi-Fi, and
  the phone shows up as an extra camera device; click Detect cameras and
  select it. Phone cameras are usually sharper than laptop webcams, which
  helps recognition accuracy.

The standalone scripts ask for the camera index on start; the default
(Enter) is device 0.

The underlying scripts also run standalone, which is useful for testing
and debugging: `python register.py`, `python train.py`,
`python recognize.py`.

## Project structure

```text
app.py            Tkinter GUI (all three tabs)
database.py       SQLite schema and queries
register.py       Face sample capture (enrollment)
train.py          LBPH model training
recognize.py      Live recognition and attendance marking
evaluate.py       Offline error-rate measurement (accuracy, FRR, FAR)
tests/            Automated unit tests (pytest)
requirements.txt  Dependencies
data/             Runtime data: face images, database, trained model
                  (created automatically; not committed to version control)
```

## Testing

### Automated tests

Unit tests cover the database layer (registration, duplicate prevention,
attendance marking and filtering, de-registration, CSV export, schema
migration) and the full LBPH pipeline (load data → train → save → load →
predict) using synthetic face images, so no webcam is needed:

```bash
python -m pytest tests -v
```

### Error-rate measurement (no webcam needed)

`evaluate.py` measures the recognizer on the face samples already saved
under `data/faces/`: it holds out 20% of each student's images, trains on
the rest, and reports per-student accuracy, false rejections (FRR) and
misidentifications; it then estimates the False Acceptance Rate (FAR) by
predicting each student against a model trained without them. It also
prints the genuine vs impostor confidence ranges and a suggested
`THRESHOLD`.

```bash
python evaluate.py
```

Each run appends a summary row to `data/evaluation_log.csv`, so error
rates can be compared across changes (recaptured samples, threshold
adjustments, more students) — this is the quantitative evidence for the
project report.

### Acceptance tests (manual, with webcam)

Run in order; screenshots of each double as evaluation evidence for the
project report.

1. **Fresh start** — delete `data/`, launch `app.py` → no crash, empty
   lists.
2. **No-model guard** — start a session before registering → friendly
   error dialog.
3. **Registration** — register 3 people (real faces, good light) → each
   gets 30 samples, the model retrains, all appear in the registered list.
4. **Recognition accuracy** — each registered person attempts recognition
   10 times → expect at least 8/10 correct; the recorded number is the
   recognition accuracy.
5. **Unknown rejection** — 2 unregistered people, 5 attempts each → red
   "Unknown" box every time and zero attendance rows. Failures here
   measure the False Acceptance Rate (FAR); rejections of registered
   people in test 4 measure the False Rejection Rate (FRR).
6. **Duplicate block** — a recognized person stays in frame for 30
   seconds → exactly one attendance row.
7. **Enrollment block** — a recognized person in a session for a course
   they are not registered in → orange "Recognized - not enrolled" box and
   zero attendance rows; a session for their own course then marks them
   normally.
8. **De-registration** — de-register one person → they now show as
   Unknown, while their old attendance rows remain visible in reports.
9. **Report and export** — filter by today's date and course, export CSV,
   open it → rows match the on-screen view. Set the status filter to
   Absent, then Present → the table narrows to only those rows, and an
   export while filtered writes only the shown rows.
10. **Lighting variation** — repeat test 4 under window light and under
    artificial light, recording both accuracy numbers.
11. **Absentee marking** — with 3 students enrolled in a course, run a
    session where only some appear, then press `q` → the session-end summary
    reports the present/absent split, and the unseen enrolled students show
    as **Absent** in the report. Re-run the session and let a previously
    absent student appear → their row flips to Present (no duplicate).

The recognition threshold used in the final system is documented together
with the measurements above that justify it.

## Troubleshooting

- **"Cannot open camera"** — another application is using the camera;
  close it, or click **Detect cameras** and select a different device.
- **Phone doesn't appear as a camera** — make sure the webcam app is
  running on the phone *and* its Windows client is installed and
  connected, then click Detect cameras again.
- **`cv2.face` AttributeError** — plain opencv-python is installed instead
  of opencv-contrib-python; see Setup.
- **"Camera engine unavailable" banner / `DLL load failed while importing
  cv2`** — the OpenCV native libraries could not load. On Windows this is
  usually a missing Microsoft Visual C++ redistributable; install it (or
  reinstall `opencv-contrib-python`), then click **Retry camera engine**.
  The rest of the app (viewing and exporting attendance) works meanwhile.
- **Poor recognition** — recapture samples in better lighting and make
  sure the face fills a good portion of the frame during registration.
- **Camera window frozen on Linux** — install `opencv-contrib-python`
  (the GUI build), not the headless variant.

## Limitations and possible future work

- LBPH is a classical texture-based method: it is fast and works offline
  on modest hardware, but is sensitive to lighting and pose, and its
  stranger-rejection depends on a manually tuned threshold. Deep-learning
  embeddings (e.g. FaceNet-style models) would improve accuracy at the
  cost of heavier dependencies.
- There is no liveness detection, so a printed photo could in principle
  spoof the camera.
- Each student is associated with a single course; supporting multiple
  enrollments per student would require an enrollments table.
- The system is single-camera and single-machine by design, matching the
  scale of one classroom.
