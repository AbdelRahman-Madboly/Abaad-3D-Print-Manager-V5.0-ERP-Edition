"""
src/ui/tabs/settings_tab.py
===========================
Settings and system management tab for Abaad 3D Print Manager v5.0.
Admin-only tab.

Sections:
  1. Company Information — saved to settings table
  2. Pricing Defaults — rate per gram, spool price
  3. Quote / Invoice — deposit %, validity days
  4. Data Management — backup, export CSV, import
  5. About — app version, DB stats
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime

from src.core.config import (
    APP_NAME, APP_VERSION,
    DEFAULT_RATE_PER_GRAM, SPOOL_PRICE_FIXED,
    DB_PATH,
)
from src.services.finance_service import FinanceService
from src.ui.theme import Colors, Fonts
from src.utils.helpers import format_currency, safe_float


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

        # Scrollable canvas
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

        # Save button (sticky at bottom of inner)
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

        fields = [
            ("Company Name",   "company_name",    "Abaad"),
            ("Subtitle",       "company_subtitle","3D Printing Services"),
            ("Phone",          "company_phone",   "01070750477"),
            ("Address",        "company_address", "Ismailia, Egypt"),
            ("Tagline",        "company_tagline", "Quality 3D Printing Solutions"),
            ("Social Handle",  "company_social",  "@abaad3d"),
        ]
        self._company_vars: dict = {}
        for r, (label, key, default) in enumerate(fields):
            ttk.Label(sec, text=f"{label}:").grid(
                row=r, column=0, sticky="w", padx=(0, 12), pady=3)
            var = tk.StringVar()
            ttk.Entry(sec, textvariable=var, width=40).grid(
                row=r, column=1, sticky="ew", pady=3)
            self._company_vars[key] = (var, default)

    # -- Pricing --

    def _build_pricing_section(self) -> None:
        sec = ttk.LabelFrame(self._inner,
                             text="💰 Pricing Defaults", padding=12)
        sec.grid(row=1, column=0, sticky="ew", pady=(0, 10), padx=4)
        sec.columnconfigure(1, weight=1)

        fields = [
            ("Rate per gram (EGP)",    "default_rate_per_gram",
             str(DEFAULT_RATE_PER_GRAM)),
            ("Spool price (EGP)",      "spool_price",
             str(SPOOL_PRICE_FIXED)),
            ("Cost per gram (EGP)",    "default_cost_per_gram",   "0.84"),
            ("Electricity rate (EGP/hr)", "electricity_rate",     "0.31"),
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
            ("Deposit %",         "quote_deposit_pct",      "30"),
            ("Quote validity (days)", "quote_validity_days","7"),
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
        ttk.Button(btn_row, text="📥 Import / Migrate v4",
                   command=self._import_v4).pack(side=tk.LEFT, padx=4)

        self._data_status = ttk.Label(sec, text="", style="Muted.TLabel")
        self._data_status.pack(anchor="w", pady=(6, 0))

        # DB path info
        ttk.Label(sec,
                  text=f"Database: {DB_PATH}",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

    # -- About --

    def _build_about_section(self) -> None:
        sec = ttk.LabelFrame(self._inner, text="ℹ About", padding=12)
        sec.grid(row=4, column=0, sticky="ew", pady=(0, 10), padx=4)
        sec.columnconfigure(1, weight=1)

        about_rows = [
            ("App",         f"{APP_NAME} v{APP_VERSION}"),
            ("Database",    "SQLite (WAL mode)"),
            ("Python",      self._python_version()),
            ("Built for",   "Abaad 3D Printing Services, Ismailia, Egypt"),
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

        self._refresh_db_stats()

    def _save_all(self) -> None:
        """Save all settings to the settings table."""
        all_vars = {
            **self._company_vars,
            **self._pricing_vars,
            **self._quote_vars,
        }
        saved = 0
        for key, (var, _) in all_vars.items():
            value = var.get().strip()
            self._db_set(key, value)
            saved += 1

        messagebox.showinfo("Saved",
                            f"✅ {saved} settings saved successfully.")
        self._notify()

    def _db_get(self, key: str) -> str:
        """Read a single key from the settings table."""
        try:
            rows = self._db.execute_query(
                "SELECT value FROM settings WHERE key = ?", (key,))
            return rows[0]["value"] if rows else ""
        except Exception:
            return ""

    def _db_set(self, key: str, value: str) -> None:
        """Upsert a key in the settings table."""
        try:
            self._db.execute_update(
                """INSERT INTO settings (key, value)
                   VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (key, value))
        except Exception as exc:
            print(f"Settings save error: {exc}")

    # ------------------------------------------------------------------
    # Data actions
    # ------------------------------------------------------------------

    def _backup_db(self) -> None:
        """Trigger a database backup."""
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
        """Export all tables to CSV files."""
        try:
            export_dir = self._db.export_to_csv()
            self._data_status.config(
                text=f"✅ CSV files exported to: {export_dir}",
                foreground=Colors.SUCCESS)
            # Try to open the folder
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

    def _import_v4(self) -> None:
        """Run the v4 → v5 migration script."""
        if not messagebox.askyesno(
            "Import v4 Data",
            "This will import data from the v4 JSON database "
            "(data/abaad_v4.db.json).\n\n"
            "Existing records will NOT be overwritten unless "
            "you confirm --force mode.\n\n"
            "Continue?",
        ):
            return
        try:
            from src.utils.migration import run_migration
            result = run_migration(force=False)
            self._data_status.config(
                text=f"✅ Migration complete: {result}",
                foreground=Colors.SUCCESS)
        except ImportError:
            self._data_status.config(
                text="❌ Migration module not found. "
                     "Run scripts/migrate_v4_to_v5.py manually.",
                foreground=Colors.DANGER)
        except Exception as exc:
            self._data_status.config(
                text=f"❌ Migration failed: {exc}",
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
                rows = self._db.execute_query(
                    f"SELECT COUNT(*) AS cnt FROM {table}")
                count = rows[0]["cnt"] if rows else 0
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