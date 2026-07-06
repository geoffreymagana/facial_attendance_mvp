# CLAUDE.md — project rules for Claude Code

Read README.md before doing anything. It is the single source of truth for
scope, known issues, edge-case behaviors, and the acceptance test checklist.

Hard rules:

1. **Scope is frozen.** Build or fix only items listed under IN SCOPE in
   README.md. Never add anything from OUT OF SCOPE, even if asked-adjacent
   or "quick". This is a graded diploma project due in under 2 weeks;
   scope creep is the primary risk.
2. **Stack is fixed**: Python, OpenCV Haar cascade + LBPH
   (opencv-contrib-python), SQLite, Tkinter. Do not introduce new
   dependencies, ML models, frameworks, or databases.
3. **Never delete attendance history.** De-registration deactivates the
   student and removes face images only.
4. **Keep it simple.** Prefer the smallest change that passes the test
   checklist. No refactors unless a bug requires it. No new files unless
   necessary.
5. **Current priority order**: fix Known Issue #1 (unknown-face feedback +
   prediction logging), implement the enrollment check (IN SCOPE item 10 —
   recognized ≠ enrolled; match session course against the student's
   existing `course` field, no new tables), implement de-registration, add
   the three GUI guard rails, then support the user through the test
   checklist.
6. LBPH confidence is a DISTANCE: lower = better match. Faces with
   confidence ABOVE the threshold are rejected as Unknown. Do not invert
   this.
7. Before claiming a fix works, state which checklist item(s) it satisfies
   and how the user should verify with the physical webcam (this
   environment has no camera).

Project files: app.py (GUI), database.py, register.py, train.py,
recognize.py. Data lives in data/ (gitignore-style: never commit face
images or the .db).
