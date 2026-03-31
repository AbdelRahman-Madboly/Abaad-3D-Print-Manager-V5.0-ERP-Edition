"""
src/ui/theme.py
===============
Single source of truth for all UI colors, fonts, and ttk style configuration.
Abaad 3D Print Manager — v5.0

Usage:
    from src.ui.theme import Colors, Fonts, setup_styles

    # In App.__init__:
    setup_styles(self.root)
    self.root.configure(bg=Colors.BG)
"""

import tkinter as tk
from tkinter import ttk


# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

class Colors:
    """Full color palette for Abaad ERP.

    Replaces the duplicated Colors class that existed in login.py
    and admin_panel.py.
    """

    # Primary (Blue)
    PRIMARY         = "#1e3a8a"
    PRIMARY_DARK    = "#1d4ed8"
    PRIMARY_LIGHT   = "#3b82f6"
    PRIMARY_LIGHTER = "#60a5fa"

    # Status — Success (Green)
    SUCCESS       = "#10b981"
    SUCCESS_DARK  = "#059669"
    SUCCESS_LIGHT = "#34d399"

    # Status — Danger (Red)
    DANGER       = "#ef4444"
    DANGER_DARK  = "#dc2626"
    DANGER_LIGHT = "#f87171"

    # Status — Warning (Amber)
    WARNING       = "#f59e0b"
    WARNING_DARK  = "#d97706"
    WARNING_LIGHT = "#fbbf24"

    # Status — Info (Cyan)
    INFO       = "#06b6d4"
    INFO_DARK  = "#0891b2"
    INFO_LIGHT = "#22d3ee"

    # Purple (also used for Admin role)
    PURPLE       = "#7c3aed"
    PURPLE_DARK  = "#6d28d9"
    PURPLE_LIGHT = "#a78bfa"

    # Misc accents
    CYAN   = "#06b6d4"
    ORANGE = "#f97316"
    PINK   = "#ec4899"

    # Backgrounds
    BG        = "#f8fafc"
    BG_DARK   = "#1e293b"
    BG_DARKER = "#0f172a"

    # Cards / surfaces
    CARD       = "#ffffff"
    CARD_HOVER = "#f1f5f9"
    CARD_DARK  = "#334155"

    # Text
    TEXT           = "#0f172a"
    TEXT_SECONDARY = "#64748b"
    TEXT_LIGHT     = "#94a3b8"
    TEXT_MUTED     = "#cbd5e1"

    # Borders
    BORDER      = "#e2e8f0"
    BORDER_DARK = "#475569"

    # Role shortcuts (used by login dialog & admin panel)
    ADMIN      = PURPLE
    ADMIN_DARK = PURPLE_DARK
    USER       = INFO
    USER_DARK  = INFO_DARK


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

class Fonts:
    """Font tuples for all text elements in the application."""

    DEFAULT     = ("Segoe UI", 10)
    TITLE       = ("Segoe UI", 16, "bold")
    SUBTITLE    = ("Segoe UI", 12)
    HEADER      = ("Segoe UI", 13, "bold")
    SECTION     = ("Segoe UI", 11, "bold")
    SMALL       = ("Segoe UI", 9)
    TINY        = ("Segoe UI", 8)
    BUTTON      = ("Segoe UI", 10)
    BUTTON_BOLD = ("Segoe UI", 10, "bold")
    MONO        = ("Consolas", 10)
    BIG_NUMBER  = ("Segoe UI", 14, "bold")


# ---------------------------------------------------------------------------
# TTK Style Setup
# ---------------------------------------------------------------------------

def setup_styles(root: tk.Tk) -> None:
    """Configure all ttk styles for the application.

    Call once in App.__init__ after the root window is created.
    Moves all style logic out of App._setup_styles() in main.py.

    Args:
        root: The application root Tk window (needed for ttk.Style()).
    """
    style = ttk.Style(root)
    style.theme_use("clam")

    # --- Base widgets ---
    style.configure(
        "TFrame",
        background=Colors.BG,
    )
    style.configure(
        "TLabel",
        background=Colors.BG,
        font=Fonts.DEFAULT,
        foreground=Colors.TEXT,
    )
    style.configure(
        "TButton",
        font=Fonts.BUTTON,
        padding=6,
    )
    style.configure(
        "TEntry",
        padding=5,
    )
    style.configure(
        "TCombobox",
        padding=5,
    )
    style.configure(
        "TCheckbutton",
        background=Colors.BG,
        font=Fonts.DEFAULT,
    )
    style.configure(
        "TRadiobutton",
        background=Colors.BG,
        font=Fonts.DEFAULT,
    )
    style.configure(
        "TSpinbox",
        padding=5,
    )

    # --- Notebook tabs ---
    style.configure(
        "TNotebook",
        background=Colors.BG,
        borderwidth=0,
    )
    style.configure(
        "TNotebook.Tab",
        padding=[20, 10],
        font=Fonts.SECTION,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", Colors.PRIMARY), ("!selected", Colors.CARD)],
        foreground=[("selected", "white"),        ("!selected", Colors.TEXT)],
    )

    # --- LabelFrame ---
    style.configure(
        "TLabelframe",
        background=Colors.BG,
        borderwidth=1,
        relief="groove",
    )
    style.configure(
        "TLabelframe.Label",
        font=Fonts.DEFAULT + ("bold",) if len(Fonts.DEFAULT) == 2 else Fonts.SECTION,
        foreground=Colors.PRIMARY,
        background=Colors.BG,
    )

    # --- Treeview ---
    style.configure(
        "Treeview",
        font=Fonts.DEFAULT,
        rowheight=28,
        background=Colors.CARD,
        fieldbackground=Colors.CARD,
        foreground=Colors.TEXT,
        borderwidth=0,
    )
    style.configure(
        "Treeview.Heading",
        font=Fonts.BUTTON_BOLD,
        background=Colors.PRIMARY,
        foreground="white",
        relief="flat",
    )
    style.map(
        "Treeview",
        background=[("selected", Colors.PRIMARY_LIGHT)],
        foreground=[("selected", "white")],
    )
    style.map(
        "Treeview.Heading",
        background=[("active", Colors.PRIMARY_DARK)],
    )

    # --- Scrollbar ---
    style.configure(
        "TScrollbar",
        background=Colors.BG,
        troughcolor=Colors.BORDER,
        arrowcolor=Colors.TEXT_SECONDARY,
    )

    # --- Separator ---
    style.configure(
        "TSeparator",
        background=Colors.BORDER,
    )

    # --- Progressbar ---
    style.configure(
        "TProgressbar",
        background=Colors.PRIMARY,
        troughcolor=Colors.BORDER,
        thickness=8,
    )

    # --- Custom label styles ---
    style.configure(
        "Title.TLabel",
        font=Fonts.TITLE,
        foreground=Colors.TEXT,
        background=Colors.BG,
    )
    style.configure(
        "Subtitle.TLabel",
        font=Fonts.SUBTITLE,
        foreground=Colors.TEXT_SECONDARY,
        background=Colors.BG,
    )
    style.configure(
        "Header.TLabel",
        font=Fonts.HEADER,
        foreground=Colors.PRIMARY,
        background=Colors.BG,
    )
    style.configure(
        "Section.TLabel",
        font=Fonts.SECTION,
        foreground=Colors.TEXT,
        background=Colors.BG,
    )
    style.configure(
        "Muted.TLabel",
        font=Fonts.SMALL,
        foreground=Colors.TEXT_MUTED,
        background=Colors.BG,
    )

    # --- Custom button styles ---
    style.configure(
        "Accent.TButton",
        font=Fonts.BUTTON_BOLD,
    )
    style.configure(
        "Success.TButton",
        font=Fonts.BUTTON,
    )
    style.configure(
        "Danger.TButton",
        font=Fonts.BUTTON,
    )

    # --- Card frame (white surface) ---
    style.configure(
        "Card.TFrame",
        background=Colors.CARD,
        relief="flat",
    )
    style.configure(
        "Card.TLabel",
        background=Colors.CARD,
        font=Fonts.DEFAULT,
        foreground=Colors.TEXT,
    )

    # --- Status bar ---
    style.configure(
        "StatusBar.TLabel",
        background=Colors.BG_DARK,
        foreground=Colors.TEXT_LIGHT,
        font=Fonts.SMALL,
        padding=[8, 4],
    )