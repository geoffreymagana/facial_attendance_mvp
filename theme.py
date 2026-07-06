"""Visual theme for the Tkinter GUI.

A small self-contained design system — colour palette, fonts and ttk style
configuration — so the app has a consistent, modern look without pulling in a
third-party UI toolkit (which matters here: the OpenCV DLL problems show the
runtime environment is fragile, so we avoid extra native dependencies).

Everything is built on ttk's "clam" theme, which is the most style-able of the
built-in themes. Structural containers in app.py use plain ``tk`` widgets so we
control background colour precisely; interactive widgets (Entry, Combobox,
Button, Treeview) are ttk and styled here.
"""

import tkinter as tk  # noqa: F401  (kept for callers importing tk via theme)
from tkinter import ttk

# --- Palette -------------------------------------------------------------
# Light content area with a dark slate sidebar and an indigo accent.
PALETTE = {
    "bg":             "#eef1f6",  # app / content background
    "surface":        "#ffffff",  # cards
    "surface_alt":    "#f5f7fb",  # zebra rows, subtle fills
    "sidebar":        "#0f172a",  # slate-900
    "sidebar_hover":  "#1e293b",
    "sidebar_active": "#4f46e5",  # accent — current page
    "sidebar_text":   "#cbd5e1",
    "sidebar_muted":  "#64748b",
    "text":           "#0f172a",
    "muted":          "#64748b",
    "border":         "#e2e8f0",
    "accent":         "#4f46e5",  # indigo-600
    "accent_hover":   "#4338ca",
    "accent_active":  "#3730a3",
    "danger":         "#e11d48",  # rose-600
    "danger_hover":   "#be123c",
    "danger_active":  "#9f1239",
    "success":        "#15803d",
    "warn_bg":        "#b91c1c",  # banner
    "on_accent":      "#ffffff",
    "disabled_bg":    "#cbd1dc",
    "disabled_fg":    "#8b94a3",
    "field_bg":       "#ffffff",
    "field_border":   "#cbd5e1",
    "pill_ok":        "#4ade80",
    "pill_off":       "#f87171",
}

FONTS = {
    "brand":      ("Segoe UI Semibold", 14),
    "title":      ("Segoe UI Semibold", 20),
    "h2":         ("Segoe UI Semibold", 13),
    "body":       ("Segoe UI", 10),
    "body_bold":  ("Segoe UI Semibold", 10),
    "small":      ("Segoe UI", 9),
    "small_bold": ("Segoe UI Semibold", 9),
    "nav":        ("Segoe UI", 11),
}


def apply_styles(root):
    """Configure ttk styles on ``root``. Call once, before building widgets."""
    p = PALETTE
    style = ttk.Style(root)
    style.theme_use("clam")

    # Combobox drop-down is a classic tk Listbox reached only via option db.
    root.option_add("*TCombobox*Listbox.background", p["surface"])
    root.option_add("*TCombobox*Listbox.foreground", p["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", p["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", p["on_accent"])

    style.configure("TFrame", background=p["bg"])
    style.configure("TSeparator", background=p["border"])

    # --- Entry ---
    style.configure(
        "TEntry", fieldbackground=p["field_bg"], background=p["field_bg"],
        foreground=p["text"], insertcolor=p["text"], bordercolor=p["field_border"],
        lightcolor=p["field_border"], darkcolor=p["field_border"],
        borderwidth=1, relief="flat", padding=7)
    style.map("TEntry",
              bordercolor=[("focus", p["accent"])],
              lightcolor=[("focus", p["accent"])],
              darkcolor=[("focus", p["accent"])])

    # --- Combobox ---
    style.configure(
        "TCombobox", fieldbackground=p["field_bg"], background=p["field_bg"],
        foreground=p["text"], arrowcolor=p["muted"], bordercolor=p["field_border"],
        lightcolor=p["field_border"], darkcolor=p["field_border"],
        borderwidth=1, padding=6)
    style.map("TCombobox",
              fieldbackground=[("readonly", p["field_bg"])],
              selectbackground=[("readonly", p["field_bg"])],
              selectforeground=[("readonly", p["text"])],
              bordercolor=[("focus", p["accent"])])

    # --- Buttons ---
    def _solid(name, bg, hover, active):
        style.configure(name, background=bg, foreground=p["on_accent"],
                        font=FONTS["body_bold"], borderwidth=0, relief="flat",
                        focuscolor=bg, padding=(16, 9), anchor="center")
        style.map(name,
                  background=[("disabled", p["disabled_bg"]),
                              ("pressed", active), ("active", hover)],
                  foreground=[("disabled", p["disabled_fg"])])

    _solid("Primary.TButton", p["accent"], p["accent_hover"], p["accent_active"])
    _solid("Danger.TButton", p["danger"], p["danger_hover"], p["danger_active"])

    # Secondary: subtle bordered chip on a card.
    style.configure("Secondary.TButton", background=p["surface_alt"],
                    foreground=p["text"], font=FONTS["body_bold"], borderwidth=1,
                    relief="flat", padding=(14, 8), bordercolor=p["border"],
                    lightcolor=p["border"], darkcolor=p["border"],
                    focuscolor=p["surface_alt"])
    style.map("Secondary.TButton",
              background=[("disabled", p["surface_alt"]),
                          ("pressed", "#e2e8f0"), ("active", "#e9edf4")],
              foreground=[("disabled", p["disabled_fg"])],
              bordercolor=[("focus", p["accent"])])

    # Ghost: text-only accent button.
    style.configure("Ghost.TButton", background=p["surface"],
                    foreground=p["accent"], font=FONTS["body_bold"],
                    borderwidth=0, relief="flat", padding=(12, 8),
                    focuscolor=p["surface"])
    style.map("Ghost.TButton",
              background=[("active", p["surface_alt"]), ("pressed", p["surface_alt"])],
              foreground=[("disabled", p["disabled_fg"])])

    # --- Scrollbar ---
    style.configure("Vertical.TScrollbar", background=p["surface_alt"],
                    troughcolor=p["surface"], bordercolor=p["surface"],
                    arrowcolor=p["muted"], relief="flat", borderwidth=0)
    style.map("Vertical.TScrollbar", background=[("active", p["border"])])

    # --- Treeview ---
    style.configure("Treeview", background=p["surface"], fieldbackground=p["surface"],
                    foreground=p["text"], rowheight=30, borderwidth=0,
                    relief="flat", font=FONTS["body"])
    style.configure("Treeview.Heading", background=p["surface_alt"],
                    foreground=p["muted"], font=FONTS["small_bold"],
                    relief="flat", borderwidth=0, padding=(10, 10))
    style.map("Treeview.Heading", background=[("active", p["border"])])
    style.map("Treeview",
              background=[("selected", p["accent"])],
              foreground=[("selected", p["on_accent"])])

    return style
