"""
src/ui/tabs/failures_tab.py
===========================
Print failure log tab for Abaad 3D Print Manager v5.0.

Features:
- Chronological failure log with filtering by reason / source
- Add failure dialog: reason, source, filament wasted, time, cost calc
- Summary stats: count, total cost, filament wasted
- Optional filament deduction from spool
"""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from src.auth.permissions import Permission
from src.core.config import (FAILURE_REASONS, FAILURE_SOURCES,
                              ELECTRICITY_RATE, DEFAULT_COST_PER_GRAM)
from src.services.finance_service import FinanceService
from src.services.inventory_service import InventoryService
from src.ui.theme import Colors, Fonts
from src.utils.helpers import format_currency, format_time_minutes, safe_float
from src.ui.context_menu import bind_treeview_menu



class FailuresTab(ttk.Frame):
    """Print failure log tab.

    Args:
        parent:            ttk.Notebook parent.
        finance_service:   FinanceService instance.
        inventory_service: InventoryService instance (for spool deduction).
        user:              Currently logged-in User object.
    """

    def __init__(self, parent, finance_service: FinanceService,
                 inventory_service: InventoryService, user,
                 on_status_change=None) -> None:
        super().__init__(parent, padding=10)
        self._fin    = finance_service
        self._inv    = inventory_service
        self._user   = user
        self._notify = on_status_change or (lambda: None)
        self._selected_id: Optional[str] = None

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._load_failures()
        self._update_summary()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self._build_toolbar()
        self._build_list()
        self._build_summary()

    def _build_toolbar(self) -> None:
        tb = ttk.Frame(self)
        tb.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        can_manage = self._user.has_permission(Permission.VIEW_FINANCIAL)

        ttk.Button(tb, text="➕ Log Failure",
                   command=self._add_failure,
                   state="normal" if can_manage else "disabled").pack(
            side=tk.LEFT, padx=2)

        self._btn_del = ttk.Button(tb, text="🗑 Delete",
                                   command=self._delete_failure,
                                   state="disabled")
        self._btn_del.pack(side=tk.LEFT, padx=2)

        ttk.Separator(tb, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8)

        # Reason filter
        ttk.Label(tb, text="Reason:").pack(side=tk.LEFT)
        self._reason_filter = tk.StringVar(value="All")
        ttk.Combobox(tb, textvariable=self._reason_filter,
                     values=["All"] + FAILURE_REASONS, width=18,
                     state="readonly").pack(side=tk.LEFT, padx=4)

        # Source filter
        ttk.Label(tb, text="Source:").pack(side=tk.LEFT)
        self._source_filter = tk.StringVar(value="All")
        ttk.Combobox(tb, textvariable=self._source_filter,
                     values=["All"] + FAILURE_SOURCES, width=16,
                     state="readonly").pack(side=tk.LEFT, padx=4)

        ttk.Button(tb, text="🔍 Filter",
                   command=self.refresh).pack(side=tk.LEFT, padx=2)
        ttk.Button(tb, text="🔄 Reset",
                   command=self._reset_filter).pack(side=tk.LEFT, padx=2)

    def _build_list(self) -> None:
        lf = ttk.Frame(self)
        lf.grid(row=1, column=0, sticky="nsew")
        lf.rowconfigure(0, weight=1)
        lf.columnconfigure(0, weight=1)

        cols = ("date", "reason", "source", "filament", "time",
                "mat_cost", "elec_cost", "total_cost", "notes")
        self._tree = ttk.Treeview(lf, columns=cols, show="headings",
                                  selectmode="browse")
        headers = [
            ("date",       "Date",          100),
            ("reason",     "Reason",        130),
            ("source",     "Source",        110),
            ("filament",   "Filament (g)",   85),
            ("time",       "Time",           70),
            ("mat_cost",   "Mat. Cost",      80),
            ("elec_cost",  "Elec. Cost",     80),
            ("total_cost", "Total Cost",     80),
            ("notes",      "Notes",         150),
        ]
        for col, text, width in headers:
            self._tree.heading(col, text=text)
            anchor = "e" if col in ("filament", "mat_cost", "elec_cost",
                                    "total_cost") else "w"
            self._tree.column(col, width=width, anchor=anchor)

        vsb = ttk.Scrollbar(lf, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        bind_treeview_menu(self._tree, actions=[
            ("🗑 Delete", self._delete_failure),
        ])

    def _build_summary(self) -> None:
        sf = ttk.LabelFrame(self, text="📊 Failure Summary", padding=8)
        sf.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        cards = [
            ("Total Failures",  "_sum_count",    Colors.DANGER),
            ("Filament Wasted", "_sum_filament",  Colors.WARNING),
            ("Time Wasted",     "_sum_time",      Colors.INFO),
            ("Total Cost",      "_sum_cost",      Colors.PRIMARY),
        ]
        for i, (label, attr, color) in enumerate(cards):
            card = tk.Frame(sf, bg=color, padx=14, pady=8)
            card.grid(row=0, column=i, padx=4, sticky="ew")
            sf.columnconfigure(i, weight=1)
            tk.Label(card, text=label, bg=color, fg="white",
                     font=Fonts.SMALL).pack()
            val = tk.Label(card, text="—", bg=color, fg="white",
                           font=Fonts.BIG_NUMBER)
            val.pack()
            setattr(self, attr, val)

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _load_failures(self) -> None:
        reason = self._reason_filter.get()
        source = self._source_filter.get()
        failures = self._fin.get_all_failures(
            reason_filter=None if reason == "All" else reason,
            source_filter=None if source == "All" else source,
        )
        self._tree.delete(*self._tree.get_children())
        for fl in failures:
            self._tree.insert("", "end", iid=fl.id, values=(
                fl.date[:10] if fl.date else "—",
                fl.reason,
                fl.source,
                f"{fl.filament_wasted_grams:.1f}",
                format_time_minutes(fl.time_wasted_minutes),
                format_currency(fl.filament_cost),
                format_currency(fl.electricity_cost),
                format_currency(fl.total_loss),
                fl.description or "—",
            ))
        self._selected_id = None
        self._btn_del.config(state="disabled")

    def _update_summary(self) -> None:
        stats = self._fin.get_failure_stats()
        self._sum_count.config(text=str(stats.get("total_failures", 0)))
        self._sum_filament.config(
            text=f"{stats.get('total_filament_wasted', 0):.1f} g")
        self._sum_time.config(
            text=format_time_minutes(int(stats.get("total_time_wasted", 0))))
        self._sum_cost.config(
            text=format_currency(stats.get("total_cost", 0)))

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _on_select(self, _event=None) -> None:
        sel = self._tree.selection()
        if not sel:
            self._selected_id = None
            self._btn_del.config(state="disabled")
            return
        self._selected_id = sel[0]
        can = self._user.has_permission(Permission.VIEW_FINANCIAL)
        self._btn_del.config(state="normal" if can else "disabled")

    def _reset_filter(self) -> None:
        self._reason_filter.set("All")
        self._source_filter.set("All")
        self.refresh()

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

    def _add_failure(self) -> None:
        colors = self._inv.get_colors()
        spools = self._inv.get_active_spools()
        dlg = _FailureDialog(self, colors=colors, spools=spools)
        if dlg.result:
            data     = dlg.result.copy()
            spool_id = data.pop("spool_id", None)
            deduct   = data.pop("deduct_from_spool", False)
            self._fin.log_failure(**data)
            if deduct and spool_id:
                grams = data.get("filament_wasted_grams", 0)
                self._inv.commit_filament(spool_id, grams)
            self.refresh()
            self._notify()

    def _delete_failure(self) -> None:
        if not self._selected_id:
            return
        if not messagebox.askyesno("Confirm Delete",
                                   "Delete this failure record?"):
            return
        ok = self._fin.delete_failure(self._selected_id)
        if ok:
            self.refresh()
        else:
            messagebox.showerror("Error", "Could not delete failure record.")


# ---------------------------------------------------------------------------
# Failure dialog
# ---------------------------------------------------------------------------

class _FailureDialog:
    def __init__(self, parent, colors: list, spools: list) -> None:
        self.result = None
        self._win = tk.Toplevel(parent)
        self._win.title("Log Print Failure")
        self._win.resizable(False, False)
        self._win.grab_set()
        self._colors = colors
        self._spools = spools
        self._build()
        self._win.wait_window()

    def _build(self) -> None:
        f = ttk.Frame(self._win, padding=16)
        f.pack(fill=tk.BOTH, expand=True)
        f.columnconfigure(1, weight=1)
        pad = dict(padx=8, pady=4)

        # Reason
        ttk.Label(f, text="Reason *").grid(row=0, column=0, sticky="w", **pad)
        self._reason_var = tk.StringVar()
        ttk.Combobox(f, textvariable=self._reason_var,
                     values=FAILURE_REASONS, state="readonly",
                     width=24).grid(row=0, column=1, sticky="ew", **pad)

        # Source
        ttk.Label(f, text="Source *").grid(row=1, column=0, sticky="w", **pad)
        self._source_var = tk.StringVar(value=FAILURE_SOURCES[0])
        ttk.Combobox(f, textvariable=self._source_var,
                     values=FAILURE_SOURCES, state="readonly",
                     width=24).grid(row=1, column=1, sticky="ew", **pad)

        # Filament wasted
        ttk.Label(f, text="Filament Wasted (g)").grid(
            row=2, column=0, sticky="w", **pad)
        self._filament_var = tk.StringVar(value="0")
        self._filament_var.trace_add("write", self._recalc)
        ttk.Entry(f, textvariable=self._filament_var).grid(
            row=2, column=1, sticky="ew", **pad)

        # Time wasted
        ttk.Label(f, text="Time Wasted (min)").grid(
            row=3, column=0, sticky="w", **pad)
        self._time_var = tk.StringVar(value="0")
        self._time_var.trace_add("write", self._recalc)
        ttk.Entry(f, textvariable=self._time_var).grid(
            row=3, column=1, sticky="ew", **pad)

        # Cost preview
        cost_row = ttk.LabelFrame(f, text="Estimated Cost", padding=8)
        cost_row.grid(row=4, column=0, columnspan=2, sticky="ew", **pad)
        cost_row.columnconfigure((0, 1, 2), weight=1)

        for i, (lbl, attr) in enumerate([
            ("Material", "_calc_mat"),
            ("Electricity", "_calc_elec"),
            ("Total", "_calc_total"),
        ]):
            tk.Frame(cost_row).grid(row=0, column=i)
            ttk.Label(cost_row, text=lbl).grid(row=0, column=i, padx=8)
            val_lbl = ttk.Label(cost_row, text="0.00 EGP",
                                style="Section.TLabel")
            val_lbl.grid(row=1, column=i, padx=8, pady=4)
            setattr(self, attr, val_lbl)

        # Spool deduction
        ttk.Separator(f, orient="horizontal").grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=8)

        self._deduct_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Deduct from spool",
                        variable=self._deduct_var,
                        command=self._toggle_spool).grid(
            row=6, column=0, columnspan=2, sticky="w", **pad)

        # Color / Spool selector (shown when deduct checked)
        self._spool_frame = ttk.Frame(f)
        self._spool_frame.grid(row=7, column=0, columnspan=2, sticky="ew")
        self._spool_frame.columnconfigure(1, weight=1)

        ttk.Label(self._spool_frame, text="Color").grid(
            row=0, column=0, sticky="w", padx=8, pady=2)
        self._color_var = tk.StringVar()
        self._color_var.trace_add("write", self._update_spools)
        self._color_cb = ttk.Combobox(self._spool_frame,
                                       textvariable=self._color_var,
                                       values=self._colors, state="readonly",
                                       width=20)
        self._color_cb.grid(row=0, column=1, sticky="ew", padx=8, pady=2)

        ttk.Label(self._spool_frame, text="Spool").grid(
            row=1, column=0, sticky="w", padx=8, pady=2)
        self._spool_var = tk.StringVar()
        self._spool_cb = ttk.Combobox(self._spool_frame,
                                       textvariable=self._spool_var,
                                       state="readonly", width=28)
        self._spool_cb.grid(row=1, column=1, sticky="ew", padx=8, pady=2)
        self._spool_frame.grid_remove()

        # Notes
        ttk.Label(f, text="Notes").grid(row=8, column=0, sticky="w", **pad)
        self._notes_var = tk.StringVar()
        ttk.Entry(f, textvariable=self._notes_var, width=32).grid(
            row=8, column=1, sticky="ew", **pad)

        btn_row = ttk.Frame(f)
        btn_row.grid(row=9, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_row, text="💾 Save",
                   command=self._save).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="Cancel",
                   command=self._win.destroy).pack(side=tk.LEFT, padx=4)

        self._recalc()

    def _recalc(self, *_) -> None:
        g   = safe_float(self._filament_var.get())
        min_ = safe_float(self._time_var.get())
        mat  = g * DEFAULT_COST_PER_GRAM
        elec = (min_ / 60) * ELECTRICITY_RATE
        total = mat + elec
        self._calc_mat.config(text=f"{mat:.2f} EGP")
        self._calc_elec.config(text=f"{elec:.2f} EGP")
        self._calc_total.config(text=f"{total:.2f} EGP")

    def _toggle_spool(self) -> None:
        if self._deduct_var.get():
            self._spool_frame.grid()
        else:
            self._spool_frame.grid_remove()

    def _update_spools(self, *_) -> None:
        color = self._color_var.get()
        filtered = [s for s in self._spools if s.color == color]
        labels = [f"{s.color} — {s.available_weight:.0f}g avail (id:{s.id[:6]})"
                  for s in filtered]
        self._spool_cb["values"] = labels
        self._spool_map = {lbl: s.id for lbl, s in zip(labels, filtered)}
        if labels:
            self._spool_cb.current(0)

    def _save(self) -> None:
        if not self._reason_var.get():
            messagebox.showwarning("Required", "Please select a reason.",
                                   parent=self._win)
            return
        g    = safe_float(self._filament_var.get())
        min_ = safe_float(self._time_var.get())
        mat  = g * DEFAULT_COST_PER_GRAM
        elec = (min_ / 60) * ELECTRICITY_RATE

        spool_id = None
        if self._deduct_var.get():
            lbl = self._spool_var.get()
            spool_id = getattr(self, "_spool_map", {}).get(lbl)

        self.result = {
            "reason":                self._reason_var.get(),
            "source":                self._source_var.get(),
            "item_name":             "",
            "filament_wasted_grams": g,
            "time_wasted_minutes":   int(min_),
            "description":           self._notes_var.get().strip(),
            "spool_id":              spool_id,
            "deduct_from_spool":     self._deduct_var.get(),
        }
        self._win.destroy()