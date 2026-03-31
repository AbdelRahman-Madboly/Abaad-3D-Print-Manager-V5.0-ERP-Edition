"""
src/ui/dialogs/login_dialog.py
==============================
Login dialog for Abaad ERP v5.0.
Shows on startup. Returns a User object on success or None on cancel.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from src.auth.auth_manager import get_auth_manager
from src.core.config import APP_TITLE, LOGO_PATH
from src.ui.theme import Colors, Fonts


class LoginDialog:
    """Modal login window.

    Args:
        parent: Root Tk window (should be withdrawn before showing this).

    Attributes:
        result: The authenticated User object, or None if cancelled.
    """

    def __init__(self, parent: tk.Tk) -> None:
        self.result = None
        self._auth  = get_auth_manager()

        self._win = tk.Toplevel(parent)
        self._win.title(APP_TITLE)
        self._win.resizable(False, False)
        self._win.grab_set()
        self._win.protocol("WM_DELETE_WINDOW", self._cancel)

        self._build()
        self._centre(parent)
        self._win.wait_window()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build(self) -> None:
        outer = tk.Frame(self._win, bg=Colors.BG_DARK)
        outer.pack(fill=tk.BOTH, expand=True)

        # Header
        header = tk.Frame(outer, bg=Colors.BG_DARK, pady=24)
        header.pack(fill=tk.X)

        try:
            from PIL import Image, ImageTk
            img = Image.open(str(LOGO_PATH)).resize((64, 64), Image.LANCZOS)
            self._logo = ImageTk.PhotoImage(img)
            tk.Label(header, image=self._logo,
                     bg=Colors.BG_DARK).pack()
        except Exception:
            tk.Label(header, text="🖨", font=("Segoe UI", 32),
                     bg=Colors.BG_DARK, fg="white").pack()

        tk.Label(header, text="Abaad ERP", bg=Colors.BG_DARK, fg="white",
                 font=Fonts.TITLE).pack()
        tk.Label(header, text="3D Printing Management System",
                 bg=Colors.BG_DARK, fg=Colors.TEXT_LIGHT,
                 font=Fonts.SMALL).pack()

        # Card
        card = tk.Frame(outer, bg=Colors.CARD, padx=32, pady=28)
        card.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 24))
        card.columnconfigure(0, weight=1)

        tk.Label(card, text="Sign In", bg=Colors.CARD,
                 font=Fonts.HEADER, fg=Colors.TEXT).grid(
            row=0, column=0, sticky="w", pady=(0, 16))

        # Username
        tk.Label(card, text="Username", bg=Colors.CARD,
                 font=Fonts.SMALL, fg=Colors.TEXT_SECONDARY).grid(
            row=1, column=0, sticky="w")
        self._user_var = tk.StringVar()
        self._user_entry = ttk.Entry(card, textvariable=self._user_var,
                                     font=Fonts.DEFAULT, width=26)
        self._user_entry.grid(row=2, column=0, sticky="ew", pady=(2, 12))

        # Password
        tk.Label(card, text="Password", bg=Colors.CARD,
                 font=Fonts.SMALL, fg=Colors.TEXT_SECONDARY).grid(
            row=3, column=0, sticky="w")
        self._pass_var = tk.StringVar()
        self._pass_entry = ttk.Entry(card, textvariable=self._pass_var,
                                     show="●", font=Fonts.DEFAULT, width=26)
        self._pass_entry.grid(row=4, column=0, sticky="ew", pady=(2, 4))

        # Show password toggle
        self._show_pw = tk.BooleanVar(value=False)
        ttk.Checkbutton(card, text="Show password",
                        variable=self._show_pw,
                        command=self._toggle_pw).grid(
            row=5, column=0, sticky="w", pady=(0, 16))

        # Error label
        self._error_lbl = tk.Label(card, text="", bg=Colors.CARD,
                                    fg=Colors.DANGER, font=Fonts.SMALL,
                                    wraplength=280)
        self._error_lbl.grid(row=6, column=0, sticky="w", pady=(0, 8))

        # Login button
        login_btn = tk.Button(
            card, text="Sign In", bg=Colors.PRIMARY, fg="white",
            font=Fonts.BUTTON_BOLD, relief=tk.FLAT, cursor="hand2",
            padx=12, pady=8, width=24,
            command=self._login,
            activebackground=Colors.PRIMARY_DARK, activeforeground="white",
        )
        login_btn.grid(row=7, column=0, sticky="ew")

        # Quick-access user buttons
        users = self._auth.get_all_users() if self._auth.is_admin else []
        if not users:
            # pre-login: show quick-select if we can list them
            try:
                users = list(self._auth._users.values())
            except Exception:
                users = []

        if users:
            sep = ttk.Separator(card, orient="horizontal")
            sep.grid(row=8, column=0, sticky="ew", pady=12)
            tk.Label(card, text="Quick select:", bg=Colors.CARD,
                     fg=Colors.TEXT_SECONDARY, font=Fonts.SMALL).grid(
                row=9, column=0, sticky="w")
            btn_row = tk.Frame(card, bg=Colors.CARD)
            btn_row.grid(row=10, column=0, sticky="w", pady=(4, 0))
            for u in users[:4]:
                role_color = (Colors.ADMIN if u.role == "Admin"
                              else Colors.INFO)
                tk.Button(
                    btn_row,
                    text=f"{u.display_name or u.username}\n({u.role})",
                    bg=role_color, fg="white",
                    font=Fonts.TINY, relief=tk.FLAT, cursor="hand2",
                    padx=8, pady=4,
                    command=lambda n=u.username: self._quick_select(n),
                ).pack(side=tk.LEFT, padx=3)

        # Bindings
        self._user_entry.bind("<Return>", lambda _: self._pass_entry.focus())
        self._pass_entry.bind("<Return>", lambda _: self._login())
        self._user_entry.focus_set()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _toggle_pw(self) -> None:
        self._pass_entry.config(show="" if self._show_pw.get() else "●")

    def _quick_select(self, username: str) -> None:
        self._user_var.set(username)
        self._pass_entry.focus()

    def _login(self) -> None:
        username = self._user_var.get().strip()
        password = self._pass_var.get()

        if not username:
            self._error_lbl.config(text="Please enter your username.")
            return

        ok, msg, user = self._auth.login(username, password)
        if ok:
            self.result = user
            self._win.destroy()
        else:
            self._error_lbl.config(text=f"⚠ {msg}")
            self._pass_var.set("")
            self._pass_entry.focus()

    def _cancel(self) -> None:
        self.result = None
        self._win.destroy()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _centre(self, parent: tk.Tk) -> None:
        self._win.update_idletasks()
        w = self._win.winfo_width()
        h = self._win.winfo_height()
        sw = parent.winfo_screenwidth()
        sh = parent.winfo_screenheight()
        self._win.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")