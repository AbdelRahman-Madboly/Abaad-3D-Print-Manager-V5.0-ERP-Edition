"""
src/ui/tabs/settings_tab.py
===========================
Settings and system management tab for Abaad 3D Print Manager v5.0.
Admin-only tab.

Sections:
  1. Company Information — saved to settings table
  2. Pricing Defaults — rate per gram, spool price, currency symbol
  3. Quote / Invoice — deposit %, validity days
  4. Data Management — backup, export CSV
  5. About — app version, DB stats

Phase 2 changes:
  - Removed "📥 Import / Migrate v4" button and _import_v4() method (Task 5)
  - Added currency_symbol field to Pricing section (Task 2)
  - Added company_logo_path picker and app_subtitle to Company section (Tasks 3 & 4)
  - _save_all() now batches into one save_all_settings() call (Task 7)
  - Currency cache invalidated on save so format_currency() picks up new symbol
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import shutil

from src.core.config import (
    APP_NAME, APP_VERSION,
    DEFAULT_RATE_PER_GRAM, SPOOL_PRICE_FIXED,
    DB_PATH, ASSETS_DIR, PROJECT_ROOT, DEFAULT_SETTINGS,
)
from src.services.finance_service import FinanceService
from src.ui.theme import Colors, Fonts
from src.utils.helpers import format_currency, safe_float
from src.ui.context_menu import bind_treeview_menu


class SettingsTab(ttk.Frame):
    """Settings and system management tab (admin-only).

    Args:
        parent:          ttk.Notebook parent.
        finance_service: FinanceService instance (for DB stats).
        db:              DatabaseManager instance (backup / export).
        user:            Currently logged-in User object.
    """

    def __init__(self, parent, finance_service: FinanceService,
                 db, user, on_status_change=None) -> None:
        super().__init__(parent, padding=10)
        self._fin    = finance_service
        self._db     = db
        self._user   = user
        self._notify = on_status_change or (lambda: None)
        self._pending_logo: Path | None = None   # user-picked logo path

        self._build_ui()
        self._load_settings()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._load_settings()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        canvas = tk.Canvas(self, bg=Colors.BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self._inner = ttk.Frame(canvas)
        self._inner.columnconfigure(0, weight=1)
        win = canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        self._build_company_section()
        self._build_pricing_section()
        self._build_quote_section()
        self._build_data_section()
        self._build_about_section()

        ttk.Button(self._inner, text="💾 Save All Settings",
                   command=self._save_all,
                   style="Accent.TButton").grid(
            row=99, column=0, pady=16, padx=4, sticky="w")

    # -- Company --

    def _build_company_section(self) -> None:
        sec = ttk.LabelFrame(self._inner,
                             text="🏢 Company Information", padding=12)
        sec.grid(row=0, column=0, sticky="ew", pady=(0, 10), padx=4)
        sec.columnconfigure(1, weight=1)

        text_fields = [
            ("Company Name",   "company_name",     DEFAULT_SETTINGS["company_name"]),
            ("App Subtitle",   "app_subtitle",     DEFAULT_SETTINGS["app_subtitle"]),
            ("Subtitle",       "company_subtitle", DEFAULT_SETTINGS["company_subtitle"]),
            ("Phone",          "company_phone",    DEFAULT_SETTINGS["company_phone"]),
            ("Address",        "company_address",  DEFAULT_SETTINGS["company_address"]),
            ("Tagline",        "company_tagline",  DEFAULT_SETTINGS["company_tagline"]),
            ("Social Handle",  "company_social",   DEFAULT_SETTINGS["company_social"]),
        ]
        self._company_vars: dict = {}
        for r, (label, key, default) in enumerate(text_fields):
            ttk.Label(sec, text=f"{label}:").grid(
                row=r, column=0, sticky="w", padx=(0, 12), pady=3)
            var = tk.StringVar()
            ttk.Entry(sec, textvariable=var, width=40).grid(
                row=r, column=1, sticky="ew", pady=3)
            self._company_vars[key] = (var, default)

        # Logo picker row
        logo_row = len(text_fields)
        ttk.Label(sec, text="Logo File:").grid(
            row=logo_row, column=0, sticky="w", padx=(0, 12), pady=3)
        logo_frame = ttk.Frame(sec)
        logo_frame.grid(row=logo_row, column=1, sticky="ew", pady=3)
        self._logo_path_var = tk.StringVar()
        ttk.Entry(logo_frame, textvariable=self._logo_path_var,
                  width=30, state="readonly").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(logo_frame, text="📂 Browse…",
                   command=self._pick_logo).pack(side=tk.LEFT)

    # -- Pricing --

    def _build_pricing_section(self) -> None:
        sec = ttk.LabelFrame(self._inner,
                             text="💰 Pricing Defaults", padding=12)
        sec.grid(row=1, column=0, sticky="ew", pady=(0, 10), padx=4)
        sec.columnconfigure(1, weight=1)

        currency_default = DEFAULT_SETTINGS["currency_symbol"]
        fields = [
            ("Currency Symbol",         "currency_symbol",
             currency_default),
            ("Rate per gram",           "default_rate_per_gram",
             str(DEFAULT_RATE_PER_GRAM)),
            ("Spool price",             "spool_price",
             str(SPOOL_PRICE_FIXED)),
            ("Cost per gram",           "default_cost_per_gram",   "0.84"),
            ("Electricity rate (/ hr)", "electricity_rate",        "0.31"),
        ]
        self._pricing_vars: dict = {}
        for r, (label, key, default) in enumerate(fields):
            ttk.Label(sec, text=f"{label}:").grid(
                row=r, column=0, sticky="w", padx=(0, 12), pady=3)
            var = tk.StringVar()
            ttk.Entry(sec, textvariable=var, width=14).grid(
                row=r, column=1, sticky="w", pady=3)
            ttk.Label(sec, text=f"(default: {default})",
                      style="Muted.TLabel").grid(
                row=r, column=2, sticky="w", padx=(8, 0), pady=3)
            self._pricing_vars[key] = (var, default)

    # -- Quote / Invoice --

    def _build_quote_section(self) -> None:
        sec = ttk.LabelFrame(self._inner,
                             text="📄 Quote & Invoice", padding=12)
        sec.grid(row=2, column=0, sticky="ew", pady=(0, 10), padx=4)
        sec.columnconfigure(1, weight=1)

        fields = [
            ("Deposit %",             "quote_deposit_pct",   "30"),
            ("Quote validity (days)", "quote_validity_days", "7"),
            ("Invoice footer note",   "invoice_footer",
             "Thank you for your business!"),
        ]
        self._quote_vars: dict = {}
        for r, (label, key, default) in enumerate(fields):
            ttk.Label(sec, text=f"{label}:").grid(
                row=r, column=0, sticky="w", padx=(0, 12), pady=3)
            var = tk.StringVar()
            width = 40 if "footer" in key else 14
            ttk.Entry(sec, textvariable=var, width=width).grid(
                row=r, column=1, sticky="ew" if "footer" in key else "w",
                pady=3)
            self._quote_vars[key] = (var, default)

    # -- Data Management --

    def _build_data_section(self) -> None:
        sec = ttk.LabelFrame(self._inner,
                             text="🗄 Data Management", padding=12)
        sec.grid(row=3, column=0, sticky="ew", pady=(0, 10), padx=4)

        btn_row = ttk.Frame(sec)
        btn_row.pack(fill=tk.X, pady=4)

        ttk.Button(btn_row, text="💾 Backup Database",
                   command=self._backup_db).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="📤 Export to CSV",
                   command=self._export_csv).pack(side=tk.LEFT, padx=4)
        # NOTE: "📥 Import / Migrate v4" button removed in Phase 2 (Task 5)

        self._data_status = ttk.Label(sec, text="", style="Muted.TLabel")
        self._data_status.pack(anchor="w", pady=(6, 0))

        ttk.Label(sec,
                  text=f"Database: {DB_PATH}",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

    # -- About --

    def _build_about_section(self) -> None:
        sec = ttk.LabelFrame(self._inner, text="ℹ About", padding=12)
        sec.grid(row=4, column=0, sticky="ew", pady=(0, 10), padx=4)
        sec.columnconfigure(1, weight=1)

        about_rows = [
            ("App",      f"{APP_NAME} v{APP_VERSION}"),
            ("Database", "SQLite (WAL mode)"),
            ("Python",   self._python_version()),
        ]
        for r, (label, value) in enumerate(about_rows):
            ttk.Label(sec, text=f"{label}:",
                      style="Section.TLabel").grid(
                row=r, column=0, sticky="w", padx=(0, 12), pady=3)
            ttk.Label(sec, text=value).grid(
                row=r, column=1, sticky="w", pady=3)

        # DB stats
        stats_frame = ttk.Frame(sec)
        stats_frame.grid(row=len(about_rows), column=0,
                         columnspan=2, sticky="ew", pady=(10, 0))

        self._stat_labels: dict = {}
        stat_items = [
            ("Orders",    "db_orders",    Colors.PRIMARY),
            ("Customers", "db_customers", Colors.SUCCESS),
            ("Spools",    "db_spools",    Colors.INFO),
            ("Expenses",  "db_expenses",  Colors.WARNING),
            ("Failures",  "db_failures",  Colors.DANGER),
        ]
        for i, (label, key, color) in enumerate(stat_items):
            card = tk.Frame(stats_frame, bg=color, padx=12, pady=6)
            card.grid(row=0, column=i, padx=3, sticky="ew")
            stats_frame.columnconfigure(i, weight=1)
            tk.Label(card, text=label, bg=color, fg="white",
                     font=Fonts.SMALL).pack()
            val = tk.Label(card, text="—", bg=color, fg="white",
                           font=Fonts.BIG_NUMBER)
            val.pack()
            self._stat_labels[key] = val

        ttk.Button(sec, text="🔄 Refresh Stats",
                   command=self._refresh_db_stats).grid(
            row=len(about_rows)+1, column=0, pady=(8, 0), sticky="w")

    # ------------------------------------------------------------------
    # Settings load / save
    # ------------------------------------------------------------------

    def _load_settings(self) -> None:
        """Load all settings from the DB into form fields."""
        all_vars = {
            **self._company_vars,
            **self._pricing_vars,
            **self._quote_vars,
        }
        for key, (var, default) in all_vars.items():
            value = self._db_get(key) or default
            var.set(value)

        # Load logo path display
        logo_rel = self._db_get("company_logo_path") or ""
        self._logo_path_var.set(logo_rel)
        self._pending_logo = None

        self._refresh_db_stats()

    def _save_all(self) -> None:
        """Batch-save all settings to the settings table in one transaction."""
        all_vars = {
            **self._company_vars,
            **self._pricing_vars,
            **self._quote_vars,
        }

        settings_dict: dict = {}
        for key, (var, _) in all_vars.items():
            settings_dict[key] = var.get().strip()

        # Handle pending logo file copy
        if self._pending_logo and self._pending_logo.exists():
            try:
                ASSETS_DIR.mkdir(parents=True, exist_ok=True)
                dest = ASSETS_DIR / f"logo_custom{self._pending_logo.suffix}"
                shutil.copy2(self._pending_logo, dest)
                logo_rel = str(Path("assets") / dest.name)
                settings_dict["company_logo_path"] = logo_rel
                self._logo_path_var.set(logo_rel)
                self._pending_logo = None
            except Exception as exc:
                messagebox.showwarning(
                    "Logo", f"Could not copy logo:\n{exc}")

        try:
            ok = self._db.save_all_settings(settings_dict)
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc))
            return

        if not ok:
            messagebox.showerror("Save Error",
                                 "save_all_settings() returned False.")
            return

        # Invalidate currency cache so format_currency picks up new symbol
        try:
            from src.utils.helpers import invalidate_currency_cache
            invalidate_currency_cache()
        except Exception:
            pass

        messagebox.showinfo("Saved",
                            f"✅ {len(settings_dict)} settings saved successfully.")
        self._notify()

    def _db_get(self, key: str) -> str:
        try:
            return self._db.get_setting(key, default="")
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Logo picker
    # ------------------------------------------------------------------

    def _pick_logo(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose a logo image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.ico"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self._pending_logo = Path(path)
        self._logo_path_var.set(self._pending_logo.name + " (pending save)")

    # ------------------------------------------------------------------
    # Data actions
    # ------------------------------------------------------------------

    def _backup_db(self) -> None:
        try:
            path = self._db.backup_database()
            self._data_status.config(
                text=f"✅ Backup created: {path}",
                foreground=Colors.SUCCESS)
        except Exception as exc:
            self._data_status.config(
                text=f"❌ Backup failed: {exc}",
                foreground=Colors.DANGER)

    def _export_csv(self) -> None:
        try:
            export_dir = self._db.export_to_csv()
            self._data_status.config(
                text=f"✅ CSV files exported to: {export_dir}",
                foreground=Colors.SUCCESS)
            import os, subprocess, sys
            if sys.platform == "win32":
                os.startfile(str(export_dir))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(export_dir)])
            else:
                subprocess.run(["xdg-open", str(export_dir)])
        except Exception as exc:
            self._data_status.config(
                text=f"❌ Export failed: {exc}",
                foreground=Colors.DANGER)

    # ------------------------------------------------------------------
    # DB stats
    # ------------------------------------------------------------------

    def _refresh_db_stats(self) -> None:
        table_map = {
            "db_orders":    "orders",
            "db_customers": "customers",
            "db_spools":    "filament_spools",
            "db_expenses":  "expenses",
            "db_failures":  "print_failures",
        }
        for key, table in table_map.items():
            lbl = self._stat_labels.get(key)
            if not lbl:
                continue
            try:
                count = self._db.get_table_count(table)
                lbl.config(text=str(count))
            except Exception:
                lbl.config(text="—")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _python_version() -> str:
        import sys
        v = sys.version_info
        return f"{v.major}.{v.minor}.{v.micro}"
