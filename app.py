"""Facial Recognition Class Attendance System - Tkinter GUI.

Three screens in one window:
  1. Register Student  (details + face capture + retrain)
  2. Start Session     (live recognition)
  3. View Attendance   (filter by date/course, export CSV)

Run:  python app.py
"""

import shutil
import sqlite3
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date
from pathlib import Path

import database
import register
import train
import recognize


class AttendanceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Facial Recognition Class Attendance System")
        self.geometry("760x560")
        database.init_db()

        # Camera device shared by registration and sessions: 0 is usually
        # the built-in webcam; a USB webcam or a phone running a webcam
        # app appears as a higher index. "Detect cameras" fills the list.
        self.var_camera = tk.StringVar(value="0")
        self.camera_choices = ["0"]
        self._camera_boxes = []

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_register = ttk.Frame(notebook)
        self.tab_session = ttk.Frame(notebook)
        self.tab_view = ttk.Frame(notebook)
        notebook.add(self.tab_register, text="  Register Student  ")
        notebook.add(self.tab_session, text="  Start Session  ")
        notebook.add(self.tab_view, text="  View Attendance  ")

        self._build_register_tab()
        self._build_session_tab()
        self._build_view_tab()

    # ---------------- Register tab ----------------
    def _build_register_tab(self):
        frame = self.tab_register
        pad = {"padx": 10, "pady": 6}

        ttk.Label(frame, text="Register a New Student",
                  font=("Segoe UI", 13, "bold")).grid(row=0, column=0,
                                                      columnspan=2, **pad)

        self.var_name = tk.StringVar()
        self.var_regno = tk.StringVar()
        self.var_course = tk.StringVar()

        for i, (label, var) in enumerate([
            ("Full Name", self.var_name),
            ("Registration No", self.var_regno),
            ("Course", self.var_course),
        ], start=1):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="e", **pad)
            ttk.Entry(frame, textvariable=var, width=34).grid(
                row=i, column=1, sticky="w", **pad)

        self._build_camera_row(frame).grid(row=4, column=0, columnspan=2, **pad)

        self.btn_capture = ttk.Button(
            frame, text="Register + Capture Faces (webcam)",
            command=self.on_register)
        self.btn_capture.grid(row=5, column=0, columnspan=2, **pad)

        self.lbl_reg_status = ttk.Label(frame, text="", foreground="green")
        self.lbl_reg_status.grid(row=6, column=0, columnspan=2, **pad)

        ttk.Separator(frame, orient="horizontal").grid(
            row=7, column=0, columnspan=2, sticky="ew", padx=10, pady=10)

        ttk.Label(frame, text="Registered students:").grid(
            row=8, column=0, columnspan=2, sticky="w", padx=10)
        self.students_list = tk.Listbox(frame, width=70, height=8)
        self.students_list.grid(row=9, column=0, columnspan=2, padx=10, pady=4)

        self.btn_deregister = ttk.Button(
            frame, text="De-register Selected", command=self.on_deregister)
        self.btn_deregister.grid(row=10, column=0, columnspan=2, **pad)

        self.refresh_students()

    # ---------------- Camera selection ----------------
    def _build_camera_row(self, parent):
        """Camera picker; one shared variable, so the selection made on one
        tab follows the user to the other."""
        row = ttk.Frame(parent)
        ttk.Label(row, text="Camera device:").pack(side="left", padx=6)
        box = ttk.Combobox(row, textvariable=self.var_camera, width=4,
                           values=self.camera_choices, state="readonly")
        box.pack(side="left")
        ttk.Button(row, text="Detect cameras",
                   command=self.on_detect_cameras).pack(side="left", padx=8)
        self._camera_boxes.append(box)
        return row

    def _camera_index(self):
        try:
            return int(self.var_camera.get())
        except ValueError:
            return 0

    def on_detect_cameras(self):
        self._set_busy(True)

        def work():
            found = register.detect_cameras()
            self.after(0, lambda: self._cameras_detected(found))

        threading.Thread(target=work, daemon=True).start()

    def _cameras_detected(self, found):
        self._set_busy(False)
        if not found:
            messagebox.showerror(
                "No camera found",
                "No working camera detected. Plug in a USB webcam, or start "
                "the webcam app on your phone (e.g. DroidCam or Iriun), "
                "then click Detect cameras again.")
            return
        self.camera_choices = [str(i) for i in found]
        for box in self._camera_boxes:
            box.config(values=self.camera_choices)
        if self.var_camera.get() not in self.camera_choices:
            self.var_camera.set(self.camera_choices[0])
        messagebox.showinfo(
            "Cameras detected",
            f"Found camera device(s): {', '.join(self.camera_choices)}.\n\n"
            f"Device 0 is usually the built-in webcam; higher numbers are "
            f"USB webcams or phone cameras. Pick one in the dropdown.")

    def refresh_students(self):
        self.students_list.delete(0, tk.END)
        self._listed_students = database.list_students()
        for s in self._listed_students:
            self.students_list.insert(
                tk.END,
                f"#{s['student_id']}  {s['name']}  |  {s['registration_no']}  |  {s['course']}")

    def _set_busy(self, busy):
        """Disable register/de-register/session buttons while any webcam or
        retrain job runs — retraining during a live session is unsupported."""
        state = "disabled" if busy else "normal"
        for btn in (self.btn_capture, self.btn_deregister, self.btn_session):
            btn.config(state=state)

    def on_register(self):
        name = self.var_name.get().strip()
        regno = self.var_regno.get().strip()
        course = self.var_course.get().strip()
        if not (name and regno and course):
            messagebox.showwarning("Missing details",
                                   "Fill in name, registration number and course.")
            return

        self._set_busy(True)
        self.lbl_reg_status.config(text="Capturing faces... look at the camera.")
        camera_index = self._camera_index()

        def work():
            student_id = None
            try:
                student_id = database.add_student(name, regno, course)
                count = register.capture_faces(student_id,
                                               camera_index=camera_index)
                face_dir = Path(__file__).parent / "data" / "faces" / str(student_id)
                dup = recognize.match_existing_student(face_dir,
                                                       exclude_id=student_id)
                if dup:
                    self.after(0, lambda: self._confirm_duplicate_face(
                        student_id, name, count, dup))
                    return
                train.train()
                self.after(0, lambda: self._register_done(name, count))
            except sqlite3.IntegrityError:
                self.after(0, lambda: self._register_failed(
                    "Duplicate registration number",
                    f"A student with registration number '{regno}' already "
                    f"exists. Use a different number."))
            except Exception as e:
                # Roll back the half-created student only if no face sample
                # was saved (e.g. webcam unavailable), so the registration
                # number can be retried.
                face_dir = Path(__file__).parent / "data" / "faces" / str(student_id)
                if student_id is not None and not any(face_dir.glob("*.png")):
                    database.remove_student_if_no_attendance(student_id)
                self.after(0, lambda: self._register_failed(
                    "Registration failed", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _register_done(self, name, count):
        self.lbl_reg_status.config(text=f"Registered {name} and retrained model.")
        self._set_busy(False)
        self.refresh_students()
        for v in (self.var_name, self.var_regno, self.var_course):
            v.set("")
        if count < 10:
            messagebox.showwarning(
                "Few samples captured",
                f"Only {count} face sample(s) were captured (10+ needed for "
                f"reliable recognition). De-register and register again with "
                f"the face clearly visible.")

    def _register_failed(self, title, msg):
        self.lbl_reg_status.config(text="")
        self._set_busy(False)
        self.refresh_students()
        messagebox.showerror(title, msg)

    def _confirm_duplicate_face(self, student_id, name, count, dup):
        """The captured face matched an already-registered student; let the
        lecturer decide (e.g. twins) or cancel the duplicate registration."""
        existing, fraction, mean_conf = dup
        keep = messagebox.askyesno(
            "Possible duplicate face",
            f"The captured face matches already-registered student "
            f"{existing['name']} ({existing['registration_no']}) on "
            f"{fraction:.0%} of samples (mean confidence {mean_conf:.0f}).\n\n"
            f"The same person may be registering under a second registration "
            f"number.\n\nRegister '{name}' anyway?")
        if keep:
            def finish():
                try:
                    train.train()
                    self.after(0, lambda: self._register_done(name, count))
                except Exception as e:
                    self.after(0, lambda: self._register_failed(
                        "Training failed", str(e)))
            threading.Thread(target=finish, daemon=True).start()
            return

        shutil.rmtree(Path(__file__).parent / "data" / "faces" / str(student_id),
                      ignore_errors=True)
        database.remove_student_if_no_attendance(student_id)
        self.lbl_reg_status.config(
            text=f"Registration of {name} cancelled (duplicate face).")
        self._set_busy(False)
        self.refresh_students()

    def on_deregister(self):
        sel = self.students_list.curselection()
        if not sel:
            messagebox.showwarning("No selection",
                                   "Select a student in the list first.")
            return
        student = self._listed_students[sel[0]]
        if not messagebox.askyesno(
                "De-register student",
                f"De-register {student['name']} ({student['registration_no']})?\n\n"
                f"Their face images are deleted and they will no longer be "
                f"recognized. Attendance history is kept."):
            return

        self._set_busy(True)
        self.lbl_reg_status.config(text="De-registering and retraining...")

        def work():
            try:
                database.deactivate_student(student["student_id"])
                face_dir = (Path(__file__).parent / "data" / "faces"
                            / str(student["student_id"]))
                shutil.rmtree(face_dir, ignore_errors=True)
                train.train()  # removes the model file if no students remain
                msg = f"De-registered {student['name']} and retrained model."
                self.after(0, lambda: self._deregister_done(msg))
            except Exception as e:
                self.after(0, lambda: self._register_failed(
                    "De-registration failed", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _deregister_done(self, msg):
        self.lbl_reg_status.config(text=msg)
        self._set_busy(False)
        self.refresh_students()

    # ---------------- Session tab ----------------
    def _build_session_tab(self):
        frame = self.tab_session
        pad = {"padx": 10, "pady": 8}

        ttk.Label(frame, text="Start an Attendance Session",
                  font=("Segoe UI", 13, "bold")).pack(**pad)

        row = ttk.Frame(frame)
        row.pack(**pad)
        ttk.Label(row, text="Course / session name:").pack(side="left", padx=6)
        self.var_session = tk.StringVar(value="CS101")
        ttk.Entry(row, textvariable=self.var_session, width=20).pack(side="left")

        self._build_camera_row(frame).pack(**pad)

        self.btn_session = ttk.Button(frame, text="Start Camera Session",
                                      command=self.on_session)
        self.btn_session.pack(**pad)

        ttk.Label(frame, text="A camera window will open. Recognized students are\n"
                              "marked present automatically (once per course per day).\n"
                              "Press q in the camera window to end the session.",
                  justify="center").pack(**pad)

    def on_session(self):
        if not recognize.MODEL_PATH.exists():
            messagebox.showerror(
                "No trained model",
                "No trained model found. Register at least one student "
                "first — training runs automatically after registration.")
            return

        course = self.var_session.get().strip() or "GENERAL"
        camera_index = self._camera_index()
        self._set_busy(True)

        def work():
            try:
                recognize.run_session(course, camera_index=camera_index)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Session error", str(e)))
            self.after(0, lambda: self._set_busy(False))
            self.after(0, self.refresh_attendance)

        threading.Thread(target=work, daemon=True).start()

    # ---------------- View tab ----------------
    def _build_view_tab(self):
        frame = self.tab_view
        pad = {"padx": 8, "pady": 6}

        controls = ttk.Frame(frame)
        controls.pack(fill="x", **pad)

        ttk.Label(controls, text="Date (YYYY-MM-DD):").pack(side="left", padx=4)
        self.var_fdate = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(controls, textvariable=self.var_fdate, width=12).pack(side="left")

        ttk.Label(controls, text="Course:").pack(side="left", padx=4)
        self.var_fcourse = tk.StringVar()
        ttk.Entry(controls, textvariable=self.var_fcourse, width=12).pack(side="left")

        ttk.Button(controls, text="Filter",
                   command=self.refresh_attendance).pack(side="left", padx=6)
        ttk.Button(controls, text="Show All",
                   command=self.show_all_attendance).pack(side="left")
        ttk.Button(controls, text="Export CSV",
                   command=self.on_export).pack(side="right", padx=4)

        cols = ("name", "regno", "course", "date", "time", "status")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", height=16)
        headings = ["Name", "Reg No", "Course", "Date", "Time", "Status"]
        widths = [160, 110, 90, 90, 80, 80]
        for c, h, w in zip(cols, headings, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, **pad)

        self.refresh_attendance()

    def _load_rows(self, on_date=None, course=None):
        self.tree.delete(*self.tree.get_children())
        for r in database.get_attendance(on_date, course):
            self.tree.insert("", tk.END, values=(
                r["name"], r["registration_no"], r["session_course"],
                r["date"], r["time"], r["status"]))

    def refresh_attendance(self):
        d = self.var_fdate.get().strip() or None
        c = self.var_fcourse.get().strip() or None
        self._load_rows(d, c)

    def show_all_attendance(self):
        self._load_rows(None, None)

    def on_export(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"attendance_{date.today().isoformat()}.csv")
        if not path:
            return
        d = self.var_fdate.get().strip() or None
        c = self.var_fcourse.get().strip() or None
        n = database.export_attendance_csv(path, d, c)
        messagebox.showinfo("Export complete", f"Exported {n} records to:\n{path}")


if __name__ == "__main__":
    AttendanceApp().mainloop()
