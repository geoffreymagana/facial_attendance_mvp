"""Facial Recognition Class Attendance System - Tkinter GUI.

A single window with a sidebar navigation and three pages:
  1. Register    (student details + face capture + retrain)
  2. Session     (live recognition)
  3. Attendance  (filter by date/course, export CSV)

The look is defined in theme.py (palette, fonts, ttk styles). Structural
containers use plain tk widgets for precise colour control; interactive
widgets are ttk and themed centrally.

Run:  python app.py
"""

import shutil
import sqlite3
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date
from pathlib import Path

import cv_engine
import database
import register
import train
import recognize
import theme
from theme import PALETTE as C, FONTS as F


class AttendanceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Facial Recognition Class Attendance System")
        self.geometry("1040x720")
        self.minsize(940, 640)
        database.init_db()
        theme.apply_styles(self)
        self.configure(bg=C["bg"])

        # Camera device shared by registration and sessions: 0 is usually
        # the built-in webcam; a USB webcam or a phone running a webcam
        # app appears as a higher index. "Detect cameras" fills the list.
        self.var_camera = tk.StringVar(value="0")
        self.camera_choices = ["0"]
        self._camera_boxes = []

        # Whether the OpenCV runtime loaded. When it did not (e.g. a missing
        # DLL on a fresh Windows box), the window still opens: only the
        # camera-dependent controls are disabled, and a banner offers a retry
        # once the user installs the runtime or plugs in an external device.
        self.camera_ready = cv_engine.available()
        self._camera_buttons = []

        self._active_page = None
        self.nav_buttons = {}
        self.engine_pill = None

        main = tk.Frame(self, bg=C["bg"])
        main.pack(fill="both", expand=True)
        self._build_sidebar(main)

        self.content = tk.Frame(main, bg=C["bg"])
        self.content.pack(side="left", fill="both", expand=True)

        self.pages_container = tk.Frame(self.content, bg=C["bg"])
        self.pages_container.pack(fill="both", expand=True)
        self.pages = {
            "register": tk.Frame(self.pages_container, bg=C["bg"]),
            "session": tk.Frame(self.pages_container, bg=C["bg"]),
            "view": tk.Frame(self.pages_container, bg=C["bg"]),
        }

        self._build_register_page()
        self._build_session_page()
        self._build_view_page()

        # Banner lives in the content column, above the pages.
        self._build_banner()

        self._show_page("register")
        # Reflect the initial engine state onto the camera-dependent buttons.
        self._set_busy(False)

    # ================= Layout scaffolding =================
    def _build_sidebar(self, parent):
        bar = tk.Frame(parent, bg=C["sidebar"], width=248)
        bar.pack(side="left", fill="y")
        bar.pack_propagate(False)

        brand = tk.Frame(bar, bg=C["sidebar"])
        brand.pack(fill="x", padx=20, pady=(24, 20))
        tk.Label(brand, text="\U0001F393  Attendance", bg=C["sidebar"],
                 fg="#ffffff", font=F["brand"]).pack(anchor="w")
        tk.Label(brand, text="Facial Recognition", bg=C["sidebar"],
                 fg=C["sidebar_muted"], font=F["small"]).pack(anchor="w")

        nav = tk.Frame(bar, bg=C["sidebar"])
        nav.pack(fill="x", pady=(4, 0))
        self._nav_button(nav, "register", "Register", "\U0001F9D1")
        self._nav_button(nav, "session", "Session", "\U0001F3A5")
        self._nav_button(nav, "view", "Attendance", "\U0001F4CA")

        footer = tk.Frame(bar, bg=C["sidebar"])
        footer.pack(side="bottom", fill="x", padx=20, pady=20)
        self.engine_pill = tk.Label(footer, bg=C["sidebar"], anchor="w",
                                    font=F["small_bold"])
        self.engine_pill.pack(anchor="w")
        self._update_engine_pill()

    def _nav_button(self, parent, name, label, icon):
        btn = tk.Button(
            parent, text=f"   {icon}    {label}", anchor="w", font=F["nav"],
            bd=0, relief="flat", cursor="hand2", highlightthickness=0,
            bg=C["sidebar"], fg=C["sidebar_text"],
            activebackground=C["sidebar_active"], activeforeground="#ffffff",
            padx=14, pady=11, command=lambda: self._show_page(name))
        btn.pack(fill="x", padx=12, pady=3)
        btn.bind("<Enter>", lambda e: btn.config(
            bg=C["sidebar_hover"]) if self._active_page != name else None)
        btn.bind("<Leave>", lambda e: btn.config(
            bg=C["sidebar_active"] if self._active_page == name else C["sidebar"]))
        self.nav_buttons[name] = btn

    def _show_page(self, name):
        for frame in self.pages.values():
            frame.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        self._active_page = name
        for n, btn in self.nav_buttons.items():
            if n == name:
                btn.config(bg=C["sidebar_active"], fg="#ffffff")
            else:
                btn.config(bg=C["sidebar"], fg=C["sidebar_text"])

    def _card(self, parent):
        """A white panel with a hairline border. Returns (outer, inner);
        pack/grid the outer, put content in the padded inner."""
        outer = tk.Frame(parent, bg=C["surface"], bd=0,
                         highlightbackground=C["border"],
                         highlightcolor=C["border"], highlightthickness=1)
        inner = tk.Frame(outer, bg=C["surface"])
        inner.pack(fill="both", expand=True, padx=20, pady=18)
        return outer, inner

    def _page_header(self, parent, title, subtitle):
        head = tk.Frame(parent, bg=C["bg"])
        tk.Label(head, text=title, bg=C["bg"], fg=C["text"],
                 font=F["title"]).pack(anchor="w")
        tk.Label(head, text=subtitle, bg=C["bg"], fg=C["muted"],
                 font=F["body"]).pack(anchor="w", pady=(3, 0))
        return head

    def _field(self, parent, label, var, width=32):
        wrap = tk.Frame(parent, bg=C["surface"])
        tk.Label(wrap, text=label, bg=C["surface"], fg=C["muted"],
                 font=F["small_bold"]).pack(anchor="w")
        ttk.Entry(wrap, textvariable=var, width=width).pack(
            anchor="w", fill="x", pady=(4, 0))
        return wrap

    # ================= Camera-engine banner / status =================
    def _build_banner(self):
        """A strip shown only when OpenCV failed to load. It explains why
        camera features are off and offers a retry, so a DLL/runtime problem
        degrades the app instead of preventing it from opening."""
        self.banner = tk.Frame(self.content, bg=C["warn_bg"])
        inner = tk.Frame(self.banner, bg=C["warn_bg"])
        inner.pack(fill="x", padx=18, pady=9)
        self.banner_label = tk.Label(inner, bg=C["warn_bg"], fg="#ffffff",
                                     justify="left", anchor="w", font=F["small"])
        self.banner_label.pack(side="left", fill="x", expand=True)
        tk.Button(inner, text="Retry camera engine", command=self.on_retry_engine,
                  bg="#ffffff", fg=C["warn_bg"], bd=0, relief="flat",
                  cursor="hand2", activebackground="#f1f5f9",
                  activeforeground=C["warn_bg"], font=F["small_bold"],
                  padx=12, pady=5).pack(side="right")
        self._update_banner()

    def _update_engine_pill(self):
        if self.engine_pill is None:
            return
        if self.camera_ready:
            self.engine_pill.config(text="●  Camera ready", fg=C["pill_ok"])
        else:
            self.engine_pill.config(text="●  Camera off", fg=C["pill_off"])

    def _update_banner(self):
        self._update_engine_pill()
        if self.camera_ready:
            self.banner.pack_forget()
            return
        self.banner_label.config(
            text="⚠  Camera engine unavailable — registering students and "
                 "live sessions are disabled. Viewing and exporting attendance "
                 "still work.    " + cv_engine.error_message())
        # Keep the banner above the pages even after a failed retry re-packs it.
        self.banner.pack(side="top", fill="x", before=self.pages_container)

    def on_retry_engine(self):
        """Re-attempt the OpenCV load — for after the user installs the missing
        runtime or connects an external camera."""
        cv_engine.reset()
        self.camera_ready = cv_engine.available()
        self._update_banner()
        self._set_busy(False)
        if self.camera_ready:
            messagebox.showinfo(
                "Camera engine ready",
                "OpenCV loaded successfully. Camera features are now enabled. "
                "Use 'Detect cameras' to find a connected device.")
        else:
            messagebox.showerror(
                "Still unavailable",
                "OpenCV still could not be loaded:\n\n"
                f"{cv_engine.error_message()}")

    # ================= Register page =================
    def _build_register_page(self):
        page = self.pages["register"]
        wrap = tk.Frame(page, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=28, pady=24)
        self._page_header(
            wrap, "Register Student",
            "Capture a student's face and add them to the recognition model."
        ).pack(fill="x", anchor="w")

        body = tk.Frame(wrap, bg=C["bg"])
        body.pack(fill="both", expand=True, pady=(18, 0))
        body.columnconfigure(0, weight=3, uniform="cols")
        body.columnconfigure(1, weight=2, uniform="cols")
        body.rowconfigure(0, weight=1)

        # --- Left: details form ---
        left_o, left = self._card(body)
        left_o.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tk.Label(left, text="Student details", bg=C["surface"], fg=C["text"],
                 font=F["h2"]).pack(anchor="w", pady=(0, 14))

        self.var_name = tk.StringVar()
        self.var_regno = tk.StringVar()
        self.var_course = tk.StringVar()
        for label, var in [("FULL NAME", self.var_name),
                           ("REGISTRATION NO", self.var_regno),
                           ("COURSE", self.var_course)]:
            self._field(left, label, var).pack(fill="x", pady=(0, 8))

        self._build_camera_row(left).pack(fill="x", pady=(2, 12))

        self.btn_capture = ttk.Button(
            left, text="Register + Capture Faces", style="Primary.TButton",
            command=self.on_register)
        self.btn_capture.pack(anchor="w")
        self._camera_buttons.append(self.btn_capture)

        self.lbl_reg_status = tk.Label(
            left, text="", bg=C["surface"], fg=C["success"], font=F["small"],
            wraplength=380, justify="left")
        self.lbl_reg_status.pack(anchor="w", pady=(12, 0))

        # --- Right: registered students ---
        right_o, right = self._card(body)
        right_o.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        tk.Label(right, text="Registered students", bg=C["surface"],
                 fg=C["text"], font=F["h2"]).pack(anchor="w", pady=(0, 14))

        listwrap = tk.Frame(right, bg=C["surface"])
        listwrap.pack(fill="both", expand=True)
        self.students_list = tk.Listbox(
            listwrap, activestyle="none", bd=0, highlightthickness=0,
            relief="flat", bg=C["surface_alt"], fg=C["text"], font=F["body"],
            selectbackground=C["accent"], selectforeground=C["on_accent"])
        self.students_list.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(listwrap, orient="vertical",
                           command=self.students_list.yview)
        self.students_list.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        self.btn_deregister = ttk.Button(
            right, text="De-register Selected", style="Danger.TButton",
            command=self.on_deregister)
        self.btn_deregister.pack(anchor="w", pady=(14, 0))

        self.refresh_students()

    # ---------------- Camera selection ----------------
    def _build_camera_row(self, parent):
        """Camera picker; one shared variable, so the selection made on one
        page follows the user to the other."""
        row = tk.Frame(parent, bg=C["surface"])
        tk.Label(row, text="CAMERA DEVICE", bg=C["surface"], fg=C["muted"],
                 font=F["small_bold"]).pack(anchor="w")
        inner = tk.Frame(row, bg=C["surface"])
        inner.pack(anchor="w", fill="x", pady=(4, 0))
        box = ttk.Combobox(inner, textvariable=self.var_camera, width=5,
                           values=self.camera_choices, state="readonly")
        box.pack(side="left")
        detect_btn = ttk.Button(inner, text="Detect cameras",
                                style="Secondary.TButton",
                                command=self.on_detect_cameras)
        detect_btn.pack(side="left", padx=(8, 0))
        self._camera_boxes.append(box)
        self._camera_buttons.append(detect_btn)
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
                f"  #{s['student_id']}   {s['name']}   |   {s['registration_no']}   |   {s['course']}")

    def _set_busy(self, busy):
        """Disable register/de-register/session buttons while any webcam or
        retrain job runs — retraining during a live session is unsupported.
        Camera-dependent buttons stay disabled while the OpenCV engine is
        unavailable, regardless of the busy state."""
        self.btn_deregister.config(state="disabled" if busy else "normal")
        for btn in self._camera_buttons:
            enabled = self.camera_ready and not busy
            btn.config(state="normal" if enabled else "disabled")

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
                if count == 0:
                    # Nothing to train on: cancel instead of saving a ghost
                    # student that the model can never recognize.
                    shutil.rmtree(face_dir, ignore_errors=True)
                    database.remove_student_if_no_attendance(student_id)
                    self.after(0, lambda: self._register_failed(
                        "No face captured",
                        "The camera never detected a face, so the "
                        "registration was cancelled. Make sure the face is "
                        "well lit and fills the frame — and if you are using "
                        "a phone camera, hold it in landscape so the face is "
                        "upright. Then register again."))
                    return
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
                if self.camera_ready:
                    train.train()  # removes the model file if no students remain
                    msg = f"De-registered {student['name']} and retrained model."
                else:
                    # No OpenCV to retrain with. The student is deactivated and
                    # their images gone; the model refreshes on the next
                    # registration (or retry) once the engine is available.
                    msg = (f"De-registered {student['name']}. Model will refresh "
                           f"when the camera engine is available.")
                self.after(0, lambda: self._deregister_done(msg))
            except Exception as e:
                self.after(0, lambda: self._register_failed(
                    "De-registration failed", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _deregister_done(self, msg):
        self.lbl_reg_status.config(text=msg)
        self._set_busy(False)
        self.refresh_students()

    # ================= Session page =================
    def _build_session_page(self):
        page = self.pages["session"]
        wrap = tk.Frame(page, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=28, pady=24)
        self._page_header(
            wrap, "Start Session",
            "Open the camera and mark enrolled students present automatically."
        ).pack(fill="x", anchor="w")

        outer, card = self._card(wrap)
        outer.pack(fill="x", pady=(18, 0))
        tk.Label(card, text="Session details", bg=C["surface"], fg=C["text"],
                 font=F["h2"]).pack(anchor="w", pady=(0, 14))

        self.var_session = tk.StringVar(value="CS101")
        self._field(card, "COURSE / SESSION NAME", self.var_session,
                    width=26).pack(fill="x", pady=(0, 10))

        self._build_camera_row(card).pack(fill="x", pady=(2, 18))

        self.btn_session = ttk.Button(
            card, text="▶   Start Camera Session", style="Primary.TButton",
            command=self.on_session)
        self.btn_session.pack(anchor="w")
        self._camera_buttons.append(self.btn_session)

        tk.Label(
            card,
            text="A camera window opens. Recognized, enrolled students are marked\n"
                 "present once per course per day. Press  q  in the camera window\n"
                 "to end the session.",
            bg=C["surface"], fg=C["muted"], font=F["small"],
            justify="left").pack(anchor="w", pady=(16, 0))

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

    # ================= Attendance (view) page =================
    def _build_view_page(self):
        page = self.pages["view"]
        wrap = tk.Frame(page, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=28, pady=24)
        self._page_header(
            wrap, "Attendance",
            "Filter, review and export attendance records."
        ).pack(fill="x", anchor="w")

        filt_o, filt = self._card(wrap)
        filt_o.pack(fill="x", pady=(18, 0))

        tk.Label(filt, text="DATE", bg=C["surface"], fg=C["muted"],
                 font=F["small_bold"]).pack(side="left", padx=(0, 6))
        self.var_fdate = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(filt, textvariable=self.var_fdate, width=12).pack(side="left")

        tk.Label(filt, text="COURSE", bg=C["surface"], fg=C["muted"],
                 font=F["small_bold"]).pack(side="left", padx=(16, 6))
        self.var_fcourse = tk.StringVar()
        ttk.Entry(filt, textvariable=self.var_fcourse, width=14).pack(side="left")

        ttk.Button(filt, text="Filter", style="Secondary.TButton",
                   command=self.refresh_attendance).pack(side="left", padx=(16, 6))
        ttk.Button(filt, text="Show All", style="Ghost.TButton",
                   command=self.show_all_attendance).pack(side="left")
        ttk.Button(filt, text="Export CSV", style="Primary.TButton",
                   command=self.on_export).pack(side="left", padx=(16, 0))

        table_o, table = self._card(wrap)
        table_o.pack(fill="both", expand=True, pady=(14, 0))

        cols = ("name", "regno", "course", "date", "time", "status")
        self.tree = ttk.Treeview(table, columns=cols, show="headings", height=14)
        headings = ["Name", "Reg No", "Course", "Date", "Time", "Status"]
        widths = [180, 120, 100, 100, 90, 90]
        for c, h, w in zip(cols, headings, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w)
        self.tree.tag_configure("odd", background=C["surface"])
        self.tree.tag_configure("even", background=C["surface_alt"])

        sb = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.refresh_attendance()

    def _load_rows(self, on_date=None, course=None):
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(database.get_attendance(on_date, course)):
            tag = "even" if i % 2 else "odd"
            self.tree.insert("", tk.END, tags=(tag,), values=(
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
