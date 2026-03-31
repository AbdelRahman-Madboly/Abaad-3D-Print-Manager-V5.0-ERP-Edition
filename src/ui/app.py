"""
src/ui/app.py
=============
Main application window for Abaad 3D Print Manager v5.0.
Assembles all tabs, header bar, and status bar.
Must stay under 200 lines — all business logic lives in services.

Usage (from main.py):
    root = tk.Tk()
    app = App(root, user, db, services)
    root.mainloop()
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime
from typing import Optional

from src.auth.auth_manager import User
from src.auth.permissions import Permission
from src.core.config import APP_TITLE, APP_VERSION, LOGO_PATH, ICON_PATH
from src.ui.theme import Colors, Fonts, setup_styles

# Tab imports
from src.ui.tabs.orders_tab    import OrdersTab
from src.ui.tabs.customers_tab import CustomersTab
from src.ui.tabs.filament_tab  import FilamentTab
from src.ui.tabs.printers_tab  import PrintersTab
from src.ui.tabs.failures_tab  import FailuresTab
from src.ui.tabs.expenses_tab  import ExpensesTab
from src.ui.tabs.stats_tab     import StatsTab
from src.ui.tabs.analytics_tab import AnalyticsTab
from src.ui.tabs.settings_tab  import SettingsTab


class App:
    """Main application window.

    Args:
        root:     The root ``tk.Tk()`` instance.
        user:     The currently authenticated ``User``.
        db:       ``DatabaseManager`` instance.
        services: Dict of instantiated service objects:
                  ``order``, ``customer``, ``inventory``,
                  ``printer``, ``finance``.
        on_logout: Callable — called when the user switches accounts.
    """

    def __init__(self, root: tk.Tk, user: User, db,
                 services: dict, on_logout=None) -> None:
        self._root     = root
        self._user     = user
        self._db       = db
        self._svc      = services
        self._on_logout = on_logout or (lambda: None)

        self._setup_window()
        setup_styles(root)
        self._build_header()
        self._build_notebook()
        self._build_status_bar()
        self._update_status_bar()
        self._start_clock()

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self._root.title(APP_TITLE)
        self._root.state("zoomed")          # maximised on Windows
        self._root.configure(bg=Colors.BG)
        self._root.minsize(1100, 650)

        # Icon
        try:
            self._root.iconbitmap(str(ICON_PATH))
        except Exception:
            pass

        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Header bar
    # ------------------------------------------------------------------

    def _build_header(self) -> None:
        hdr = tk.Frame(self._root, bg=Colors.BG_DARK, pady=8, padx=16)
        hdr.pack(fill=tk.X)

        # Logo + title
        try:
            from PIL import Image, ImageTk  # type: ignore
            img = Image.open(str(LOGO_PATH)).resize((36, 36), Image.LANCZOS)
            self._logo_img = ImageTk.PhotoImage(img)
            tk.Label(hdr, image=self._logo_img,
                     bg=Colors.BG_DARK).pack(side=tk.LEFT, padx=(0, 8))
        except Exception:
            pass

        tk.Label(hdr, text="Abaad ERP", bg=Colors.BG_DARK, fg="white",
                 font=Fonts.TITLE).pack(side=tk.LEFT)
        tk.Label(hdr, text=f"v{APP_VERSION}", bg=Colors.BG_DARK,
                 fg=Colors.TEXT_LIGHT, font=Fonts.SMALL).pack(
            side=tk.LEFT, padx=(4, 0), pady=(8, 0))

        # Right side — user info + logout
        role_color = Colors.ADMIN if self._user.role == "Admin" else Colors.USER
        tk.Label(hdr, text=self._user.role, bg=role_color, fg="white",
                 font=Fonts.SMALL, padx=8, pady=2).pack(
            side=tk.RIGHT, padx=(4, 0))
        tk.Label(hdr,
                 text=self._user.display_name or self._user.username,
                 bg=Colors.BG_DARK, fg="white",
                 font=Fonts.BUTTON_BOLD).pack(side=tk.RIGHT, padx=(16, 4))
        tk.Label(hdr, text="👤", bg=Colors.BG_DARK,
                 fg=Colors.TEXT_LIGHT).pack(side=tk.RIGHT)

        tk.Button(hdr, text="⇄ Switch User", bg=Colors.BG_DARK,
                  fg=Colors.TEXT_LIGHT, font=Fonts.SMALL,
                  relief=tk.FLAT, cursor="hand2",
                  command=self._logout).pack(side=tk.RIGHT, padx=16)

    # ------------------------------------------------------------------
    # Notebook (tabs)
    # ------------------------------------------------------------------

    def _build_notebook(self) -> None:
        self._nb = ttk.Notebook(self._root)
        self._nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 0))

        notify = self._update_status_bar
        svc    = self._svc
        user   = self._user

        # Always-visible tabs
        self._orders_tab = OrdersTab(
            self._nb, svc["order"], user, on_status_change=notify)
        self._nb.add(self._orders_tab, text="📦 Orders")

        if user.can_access_tab("customers"):
            tab = CustomersTab(self._nb, svc["customer"], user,
                               on_status_change=notify)
            self._nb.add(tab, text="👥 Customers")

        if user.can_access_tab("filament"):
            tab = FilamentTab(self._nb, svc["inventory"], user,
                              on_status_change=notify)
            self._nb.add(tab, text="🧵 Filament")

        if user.can_access_tab("printers"):
            tab = PrintersTab(self._nb, svc["printer"], user,
                              on_status_change=notify)
            self._nb.add(tab, text="🖨 Printers")

        if user.can_access_tab("failures"):
            tab = FailuresTab(self._nb, svc["finance"], svc["inventory"],
                              user, on_status_change=notify)
            self._nb.add(tab, text="❌ Failures")

        if user.can_access_tab("expenses"):
            tab = ExpensesTab(self._nb, svc["finance"], user,
                              on_status_change=notify)
            self._nb.add(tab, text="🧾 Expenses")

        if user.can_access_tab("stats"):
            tab = StatsTab(self._nb, svc["finance"], svc["customer"],
                           svc["inventory"], user, on_status_change=notify)
            self._nb.add(tab, text="📊 Statistics")

        if user.can_access_tab("analytics"):
            tab = AnalyticsTab(self._nb, svc["finance"], user,
                               on_status_change=notify)
            self._nb.add(tab, text="📈 Analytics")

        if user.can_access_tab("settings"):
            self._settings_tab = SettingsTab(
                self._nb, svc["finance"], self._db, user,
                on_status_change=notify)
            self._nb.add(self._settings_tab, text="⚙️ Settings")

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _build_status_bar(self) -> None:
        bar = tk.Frame(self._root, bg=Colors.BG_DARK, pady=3)
        bar.pack(fill=tk.X, side=tk.BOTTOM)

        self._status_orders   = tk.Label(bar, bg=Colors.BG_DARK,
                                          fg=Colors.TEXT_LIGHT,
                                          font=Fonts.SMALL, padx=10)
        self._status_spools   = tk.Label(bar, bg=Colors.BG_DARK,
                                          fg=Colors.TEXT_LIGHT,
                                          font=Fonts.SMALL, padx=10)
        self._status_revenue  = tk.Label(bar, bg=Colors.BG_DARK,
                                          fg=Colors.TEXT_LIGHT,
                                          font=Fonts.SMALL, padx=10)
        self._status_clock    = tk.Label(bar, bg=Colors.BG_DARK,
                                          fg=Colors.TEXT_LIGHT,
                                          font=Fonts.SMALL, padx=10)
        self._status_version  = tk.Label(
            bar, text=f"Abaad ERP v{APP_VERSION}",
            bg=Colors.BG_DARK, fg=Colors.TEXT_MUTED,
            font=Fonts.SMALL, padx=10)

        self._status_orders.pack(side=tk.LEFT)
        tk.Label(bar, text="|", bg=Colors.BG_DARK,
                 fg=Colors.BORDER_DARK).pack(side=tk.LEFT)
        self._status_spools.pack(side=tk.LEFT)
        tk.Label(bar, text="|", bg=Colors.BG_DARK,
                 fg=Colors.BORDER_DARK).pack(side=tk.LEFT)
        if self._user.has_permission(Permission.VIEW_FINANCIAL):
            self._status_revenue.pack(side=tk.LEFT)
            tk.Label(bar, text="|", bg=Colors.BG_DARK,
                     fg=Colors.BORDER_DARK).pack(side=tk.LEFT)
        self._status_version.pack(side=tk.RIGHT)
        self._status_clock.pack(side=tk.RIGHT)

    def _update_status_bar(self) -> None:
        """Refresh quick stats shown in the status bar."""
        try:
            orders = self._svc["order"].get_all_orders()
            active = sum(1 for o in orders
                         if o.status not in ("Delivered", "Cancelled"))
            self._status_orders.config(
                text=f"📦 {len(orders)} orders ({active} active)")

            inv = self._svc["inventory"].get_inventory_summary()
            self._status_spools.config(
                text=f"🧵 {inv.get('active_spools', 0)} spools / "
                     f"{inv.get('total_available', 0):.0f}g avail")

            if self._user.has_permission(Permission.VIEW_FINANCIAL):
                stats = self._svc["finance"].get_full_statistics()
                from src.utils.helpers import format_currency
                self._status_revenue.config(
                    text=f"💰 {format_currency(stats.get('total_revenue', 0))} revenue")
        except Exception:
            pass

    def _start_clock(self) -> None:
        def _tick():
            self._status_clock.config(
                text=datetime.now().strftime("%H:%M  %d/%m/%Y"))
            self._root.after(30_000, _tick)
        _tick()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _logout(self) -> None:
        self._root.destroy()
        self._on_logout()

    def _on_close(self) -> None:
        self._root.destroy()