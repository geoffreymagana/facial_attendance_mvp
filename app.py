"""Facial Recognition Class Attendance System - Tkinter GUI.

Three screens in one window:
  1. Register Student  (details + face capture + retrain)
  2. Start Session     (live recognition)
  3. View Attendance   (filter by date/course, export CSV)

Run:  python app.py
"""

import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date

import database
import register
import train
import recognize


class AttendanceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Facial Recognition Class Attendance System")
        self.geometry("760x520")
        database.init_db()

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

        self.btn_capture = ttk.Button(
            frame, text="Register + Capture Faces (webcam)",
            command=self.on_register)
        self.btn_capture.grid(row=4, column=0, columnspan=2, **pad)

        self.lbl_reg_status = ttk.Label(frame, text="", foreground="green")
        self.lbl_reg_status.grid(row=5, column=0, columnspan=2, **pad)

        ttk.Separator(frame, orient="horizontal").grid(
            row=6, column=0, columnspan=2, sticky="ew", padx=10, pady=10)

        ttk.Label(frame, text="Registered students:").grid(
            row=7, column=0, columnspan=2, sticky="w", padx=10)
        self.students_list = tk.Listbox(frame, width=70, height=8)
        self.students_list.grid(row=8, column=0, columnspan=2, padx=10, pady=4)
        self.refresh_students()

    def refresh_students(self):
        self.students_list.delete(0, tk.END)
        for s in database.list_students():
            self.students_list.insert(
                tk.END,
                f"#{s['student_id']}  {s['name']}  |  {s['registration_no']}  |  {s['course']}")

    def on_register(self):
        name = self.var_name.get().strip()
        regno = self.var_regno.get().strip()
        course = self.var_course.get().strip()
        if not (name and regno and course):
            messagebox.showwarning("Missing details",
                                   "Fill in name, registration number and course.")
            return

        self.btn_capture.config(state="disabled")
        self.lbl_reg_status.config(text="Capturing faces... look at the camera.")

        def work():
            try:
                student_id = database.add_student(name, regno, course)
                register.capture_faces(student_id)
                train.train()
                msg = f"Registered {name} and retrained model."
            except Exception as e:
                msg = f"Error: {e}"
            self.after(0, lambda: self._register_done(msg))

        threading.Thread(target=work, daemon=True).start()

    def _register_done(self, msg):
        self.lbl_reg_status.config(text=msg)
        self.btn_capture.config(state="normal")
        self.refresh_students()
        for v in (self.var_name, self.var_regno, self.var_course):
            v.set("")

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

        self.btn_session = ttk.Button(frame, text="Start Camera Session",
                                      command=self.on_session)
        self.btn_session.pack(**pad)

        ttk.Label(frame, text="A camera window will open. Recognized students are\n"
                              "marked present automatically (once per course per day).\n"
                              "Press q in the camera window to end the session.",
                  justify="center").pack(**pad)

    def on_session(self):
        course = self.var_session.get().strip() or "GENERAL"
        self.btn_session.config(state="disabled")

        def work():
            try:
                recognize.run_session(course)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Session error", str(e)))
            self.after(0, lambda: self.btn_session.config(state="normal"))
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
