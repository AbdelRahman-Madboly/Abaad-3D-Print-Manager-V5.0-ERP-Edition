"""
src/ui/app.py
=============
Main application window for Abaad ERP v5.0.
Assembles all tabs, header bar, status bar, keyboard shortcuts.

Task 4.3 additions:
  • Global keyboard shortcuts (Ctrl+N, Ctrl+S, Ctrl+F, F5, Escape)
  • Status bar "Saved ✓" flash (2 s green → normal)
  • on_status_change callback now triggers the flash
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime
from typing import Optional

from src.auth.auth_manager import User
from src.auth.permissions import Permission
from src.core.config import APP_TITLE, APP_VERSION, LOGO_PATH, ICON_PATH
from src.ui.theme import Colors, Fonts, setup_styles

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
        root:      Root Tk window.
        user:      Authenticated User object.
        db:        DatabaseManager instance.
        services:  Dict of service instances (order, customer, inventory,
                   printer, finance).
        on_logout: Callable invoked when the user requests a switch.
    """

    def __init__(self, root: tk.Tk, user: User, db,
                 services: dict, on_logout=None) -> None:
        self._root      = root
        self._user      = user
        self._db        = db
        self._svc       = services
        self._on_logout = on_logout or (lambda: None)
        self._flash_job: Optional[str] = None   # after() id for status flash

        self._setup_window()
        setup_styles(root)
        self._build_header()
        self._build_notebook()
        self._build_status_bar()
        self._bind_shortcuts()
        self._update_status_bar()
        self._start_clock()

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self._root.title(APP_TITLE)
        try:
            self._root.state("zoomed")
        except tk.TclError:
            self._root.attributes("-zoomed", True)
        self._root.configure(bg=Colors.BG)
        self._root.minsize(1100, 650)
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

        try:
            from PIL import Image, ImageTk
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
        tk.Button(
            hdr, text="⇄ Switch User", bg=Colors.BG_DARK,
            fg=Colors.TEXT_LIGHT, font=Fonts.SMALL,
            relief=tk.FLAT, cursor="hand2",
            command=self._logout,
        ).pack(side=tk.RIGHT, padx=16)

    # ------------------------------------------------------------------
    # Notebook
    # ------------------------------------------------------------------

    def _build_notebook(self) -> None:
        self._nb = ttk.Notebook(self._root)
        self._nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 0))

        notify = self._on_data_changed
        svc    = self._svc
        user   = self._user

        self._orders_tab = OrdersTab(self._nb, svc["order"], user,
                                     on_status_change=notify)
        self._nb.add(self._orders_tab, text="📦 Orders")

        self._tab_refs: list = [self._orders_tab]

        if user.can_access_tab("customers"):
            t = CustomersTab(self._nb, svc["customer"], user,
                             on_status_change=notify)
            self._nb.add(t, text="👥 Customers")
            self._tab_refs.append(t)

        if user.can_access_tab("filament"):
            t = FilamentTab(self._nb, svc["inventory"], user,
                            on_status_change=notify)
            self._nb.add(t, text="🧵 Filament")
            self._tab_refs.append(t)

        if user.can_access_tab("printers"):
            t = PrintersTab(self._nb, svc["printer"], user,
                            on_status_change=notify)
            self._nb.add(t, text="🖨 Printers")
            self._tab_refs.append(t)

        if user.can_access_tab("failures"):
            t = FailuresTab(self._nb, svc["finance"], svc["inventory"],
                            user, on_status_change=notify)
            self._nb.add(t, text="❌ Failures")
            self._tab_refs.append(t)

        if user.can_access_tab("expenses"):
            t = ExpensesTab(self._nb, svc["finance"], user,
                            on_status_change=notify)
            self._nb.add(t, text="🧾 Expenses")
            self._tab_refs.append(t)

        if user.can_access_tab("stats"):
            t = StatsTab(self._nb, svc["finance"], svc["customer"],
                         svc["inventory"], user, on_status_change=notify)
            self._nb.add(t, text="📊 Statistics")
            self._tab_refs.append(t)

        if user.can_access_tab("analytics"):
            t = AnalyticsTab(self._nb, svc["finance"], user,
                             on_status_change=notify)
            self._nb.add(t, text="📈 Analytics")
            self._tab_refs.append(t)

        if user.can_access_tab("settings"):
            self._settings_tab = SettingsTab(
                self._nb, svc["finance"], self._db, user,
                on_status_change=notify)
            self._nb.add(self._settings_tab, text="⚙️ Settings")
            self._tab_refs.append(self._settings_tab)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _build_status_bar(self) -> None:
        bar = tk.Frame(self._root, bg=Colors.BG_DARK, pady=3)
        bar.pack(fill=tk.X, side=tk.BOTTOM)

        self._status_orders  = tk.Label(bar, bg=Colors.BG_DARK,
                                         fg=Colors.TEXT_LIGHT, font=Fonts.SMALL,
                                         padx=10)
        self._status_spools  = tk.Label(bar, bg=Colors.BG_DARK,
                                         fg=Colors.TEXT_LIGHT, font=Fonts.SMALL,
                                         padx=10)
        self._status_revenue = tk.Label(bar, bg=Colors.BG_DARK,
                                         fg=Colors.TEXT_LIGHT, font=Fonts.SMALL,
                                         padx=10)
        self._status_saved   = tk.Label(bar, bg=Colors.BG_DARK,
                                         fg=Colors.SUCCESS, font=Fonts.SMALL,
                                         padx=10, text="")
        self._status_clock   = tk.Label(bar, bg=Colors.BG_DARK,
                                         fg=Colors.TEXT_LIGHT, font=Fonts.SMALL,
                                         padx=10)
        self._status_version = tk.Label(bar,
                                         text=f"Abaad ERP v{APP_VERSION}",
                                         bg=Colors.BG_DARK, fg=Colors.TEXT_MUTED,
                                         font=Fonts.SMALL, padx=10)

        sep = lambda: tk.Label(bar, text="|", bg=Colors.BG_DARK,
                                fg=Colors.BORDER_DARK)

        self._status_orders.pack(side=tk.LEFT)
        sep().pack(side=tk.LEFT)
        self._status_spools.pack(side=tk.LEFT)
        sep().pack(side=tk.LEFT)
        if self._user.has_permission(Permission.VIEW_FINANCIAL):
            self._status_revenue.pack(side=tk.LEFT)
            sep().pack(side=tk.LEFT)
        self._status_saved.pack(side=tk.LEFT)
        self._status_version.pack(side=tk.RIGHT)
        self._status_clock.pack(side=tk.RIGHT)

    def _update_status_bar(self) -> None:
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
                    text=f"💰 {format_currency(stats.get('total_revenue', 0))}")
        except Exception:
            pass

    def _on_data_changed(self) -> None:
        """Called by every tab after a successful save/delete."""
        self._update_status_bar()
        self._flash_saved()

    def _flash_saved(self) -> None:
        """Show 'Saved ✓' in green for 2 seconds then clear."""
        if self._flash_job:
            self._root.after_cancel(self._flash_job)
        self._status_saved.config(text="✅ Saved")
        self._flash_job = self._root.after(
            2000,
            lambda: self._status_saved.config(text=""))

    # ------------------------------------------------------------------
    # Keyboard shortcuts  (Task 4.3)
    # ------------------------------------------------------------------

    def _bind_shortcuts(self) -> None:
        root = self._root

        # Ctrl+N — new order (switch to Orders tab and call new_order)
        root.bind_all("<Control-n>", self._shortcut_new_order)

        # Ctrl+S — save the current tab (if it exposes a .save() method)
        root.bind_all("<Control-s>", self._shortcut_save)

        # Ctrl+F — focus search on the active tab
        root.bind_all("<Control-f>", self._shortcut_focus_search)

        # F5 — refresh all tabs
        root.bind_all("<F5>", self._shortcut_refresh_all)

        # Escape — clear selection on active tab
        root.bind_all("<Escape>", self._shortcut_escape)

    def _active_tab(self):
        """Return the currently visible tab widget, or None."""
        try:
            idx = self._nb.index("current")
            return self._tab_refs[idx]
        except Exception:
            return None

    def _shortcut_new_order(self, _event=None) -> None:
        # Switch to Orders tab and start a new order
        self._nb.select(0)
        if hasattr(self._orders_tab, "new_order"):
            self._orders_tab.new_order()

    def _shortcut_save(self, _event=None) -> None:
        tab = self._active_tab()
        if tab and hasattr(tab, "save"):
            tab.save()
        elif tab and hasattr(tab, "_save_order"):
            tab._save_order()

    def _shortcut_focus_search(self, _event=None) -> None:
        tab = self._active_tab()
        if tab and hasattr(tab, "_search_var"):
            # Focus the search Entry widget on this tab
            for child in tab.winfo_children():
                self._find_and_focus_search(child)

    def _find_and_focus_search(self, widget) -> bool:
        """Recursively find the first search Entry and focus it."""
        if isinstance(widget, ttk.Entry):
            widget.focus_set()
            return True
        for child in widget.winfo_children():
            if self._find_and_focus_search(child):
                return True
        return False

    def _shortcut_refresh_all(self, _event=None) -> None:
        for tab in self._tab_refs:
            if hasattr(tab, "refresh"):
                try:
                    tab.refresh()
                except Exception:
                    pass
        self._update_status_bar()

    def _shortcut_escape(self, _event=None) -> None:
        tab = self._active_tab()
        if tab and hasattr(tab, "_clear_detail"):
            tab._clear_detail()
        elif tab and hasattr(tab, "_tree"):
            tab._tree.selection_remove(tab._tree.selection())

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

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