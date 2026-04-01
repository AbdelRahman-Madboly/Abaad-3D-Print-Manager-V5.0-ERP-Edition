"""
src/ui/tabs/printers_tab.py
===========================
Printer management tab for Abaad 3D Print Manager v5.0.

Features:
- Printer list with key metrics
- Detail panel: depreciation, nozzle wear, electricity, cost totals
- Add / Edit printer
- Reset nozzle counter
- Cost report per printer
"""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from src.auth.permissions import Permission
from src.services.printer_service import PrinterService
from src.ui.theme import Colors, Fonts
from src.utils.helpers import format_currency, format_time_minutes
from src.ui.context_menu import bind_treeview_menu



class PrintersTab(ttk.Frame):
    """Printer management tab.

    Args:
        parent:          ttk.Notebook parent.
        printer_service: PrinterService instance.
        user:            Currently logged-in User object.
    """

    def __init__(self, parent, printer_service: PrinterService, user,
                 on_status_change=None) -> None:
        super().__init__(parent, padding=10)
        self._svc    = printer_service
        self._user   = user
        self._notify = on_status_change or (lambda: None)
        self._selected_id: Optional[str] = None

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._load_printers()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_left()
        self._build_right()

    def _build_left(self) -> None:
        left = ttk.Frame(self, width=280)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_propagate(False)

        ttk.Label(left, text="🖨 Printers",
                  style="Header.TLabel").pack(pady=(0, 6))

        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("name", "model", "printed", "status")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  selectmode="browse")
        self._tree.heading("name",    text="Name")
        self._tree.heading("model",   text="Model")
        self._tree.heading("printed", text="Printed (kg)")
        self._tree.heading("status",  text="Status")
        self._tree.column("name",    width=80)
        self._tree.column("model",   width=100)
        self._tree.column("printed", width=80, anchor="e")
        self._tree.column("status",  width=60, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                             command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        bind_treeview_menu(self._tree, actions=[
            ("✏️ Edit",          self._edit_printer),
            ("🔧 Reset Nozzle",  self._reset_nozzle),
        ])
        btn_row = ttk.Frame(left)
        btn_row.pack(fill=tk.X, pady=(6, 0))
        can_manage = self._user.has_permission(Permission.MANAGE_PRINTERS)
        ttk.Button(btn_row, text="➕ Add",
                   command=self._add_printer,
                   state="normal" if can_manage else "disabled").pack(
            side=tk.LEFT, padx=2)
        self._btn_edit = ttk.Button(btn_row, text="✏️ Edit",
                                    command=self._edit_printer,
                                    state="disabled")
        self._btn_edit.pack(side=tk.LEFT, padx=2)
        self._btn_nozzle = ttk.Button(btn_row, text="🔧 Reset Nozzle",
                                      command=self._reset_nozzle,
                                      state="disabled")
        self._btn_nozzle.pack(side=tk.LEFT, padx=2)

    def _build_right(self) -> None:
        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(2, weight=1)
        right.columnconfigure(0, weight=1)

        # Info card
        info = ttk.LabelFrame(right, text="🖨 Printer Info", padding=12)
        info.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        info.columnconfigure(1, weight=1)

        fields = [
            ("Name",           "_lbl_name"),
            ("Model",          "_lbl_model"),
            ("Purchase Price", "_lbl_price"),
            ("Lifetime",       "_lbl_lifetime"),
            ("Total Printed",  "_lbl_printed"),
            ("Total Time",     "_lbl_time"),
            ("Nozzle Changes", "_lbl_nozzles"),
            ("Active",         "_lbl_active"),
            ("Notes",          "_lbl_notes"),
        ]
        for r, (label, attr) in enumerate(fields):
            ttk.Label(info, text=f"{label}:",
                      style="Section.TLabel").grid(
                row=r, column=0, sticky="w", padx=(0, 12), pady=2)
            lbl = ttk.Label(info, text="—")
            lbl.grid(row=r, column=1, sticky="w", pady=2)
            setattr(self, attr, lbl)

        # Cost cards
        cost_frame = ttk.LabelFrame(right, text="💰 Cost Breakdown", padding=8)
        cost_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        cost_cards = [
            ("Depreciation",   "_cost_depreciation", Colors.DANGER),
            ("Electricity",    "_cost_electricity",  Colors.WARNING),
            ("Nozzle Cost",    "_cost_nozzle",       Colors.INFO),
            ("Total Cost",     "_cost_total",        Colors.PRIMARY),
        ]
        for i, (label, attr, color) in enumerate(cost_cards):
            card = tk.Frame(cost_frame, bg=color, padx=12, pady=8)
            card.grid(row=0, column=i, padx=4, sticky="ew")
            cost_frame.columnconfigure(i, weight=1)
            tk.Label(card, text=label, bg=color, fg="white",
                     font=Fonts.SMALL).pack()
            val = tk.Label(card, text="—", bg=color, fg="white",
                           font=Fonts.BIG_NUMBER)
            val.pack()
            setattr(self, attr, val)

        # Nozzle progress
        nozzle_frame = ttk.LabelFrame(right, text="🔩 Nozzle Wear", padding=8)
        nozzle_frame.grid(row=2, column=0, sticky="ew")
        nozzle_frame.columnconfigure(0, weight=1)

        ttk.Label(nozzle_frame, text="Nozzle Usage:").pack(anchor="w")
        self._nozzle_bar = ttk.Progressbar(nozzle_frame, maximum=100,
                                            mode="determinate")
        self._nozzle_bar.pack(fill=tk.X, pady=4)
        self._nozzle_pct_lbl = ttk.Label(nozzle_frame, text="0% used",
                                          style="Muted.TLabel")
        self._nozzle_pct_lbl.pack(anchor="w")

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _load_printers(self) -> None:
        printers = self._svc.get_all_printers()
        self._tree.delete(*self._tree.get_children())
        for p in printers:
            kg = p.total_printed_grams / 1000
            self._tree.insert("", "end", iid=p.id, values=(
                p.name,
                p.model,
                f"{kg:.2f}",
                "✅" if p.is_active else "❌",
            ))
        self._clear_detail()

    def _clear_detail(self) -> None:
        self._selected_id = None
        for attr in ("_lbl_name", "_lbl_model", "_lbl_price", "_lbl_lifetime",
                     "_lbl_printed", "_lbl_time", "_lbl_nozzles", "_lbl_active",
                     "_lbl_notes"):
            getattr(self, attr).config(text="—")
        for attr in ("_cost_depreciation", "_cost_electricity",
                     "_cost_nozzle", "_cost_total"):
            getattr(self, attr).config(text="—")
        self._nozzle_bar["value"] = 0
        self._nozzle_pct_lbl.config(text="0% used")
        self._btn_edit.config(state="disabled")
        self._btn_nozzle.config(state="disabled")

    def _show_detail(self, printer) -> None:
        self._selected_id = printer.id
        self._lbl_name.config(text=printer.name)
        self._lbl_model.config(text=printer.model)
        self._lbl_price.config(
            text=format_currency(printer.purchase_price))
        self._lbl_lifetime.config(
            text=f"{printer.lifetime_kg:,.0f} kg")
        self._lbl_printed.config(
            text=f"{printer.total_printed_grams:,.1f} g "
                 f"({printer.total_printed_grams/1000:.2f} kg)")
        self._lbl_time.config(
            text=format_time_minutes(printer.total_print_time_minutes))
        self._lbl_nozzles.config(text=str(printer.nozzle_changes))
        self._lbl_active.config(text="Yes" if printer.is_active else "No")
        self._lbl_notes.config(text=printer.notes or "—")

        stats = self._svc.get_printer_stats(printer.id)
        self._cost_depreciation.config(
            text=format_currency(stats.get("total_depreciation", 0)))
        self._cost_electricity.config(
            text=format_currency(stats.get("total_electricity", 0)))
        self._cost_nozzle.config(
            text=format_currency(stats.get("total_nozzle_cost", 0)))
        self._cost_total.config(
            text=format_currency(stats.get("total_cost", 0)))

        pct = min(printer.nozzle_usage_percent, 100)
        self._nozzle_bar["value"] = pct
        self._nozzle_pct_lbl.config(
            text=f"{pct:.1f}% used "
                 f"({printer.current_nozzle_grams:.0f}/"
                 f"{printer.nozzle_lifetime_grams:.0f} g)")

        can_manage = self._user.has_permission(Permission.MANAGE_PRINTERS)
        self._btn_edit.config(state="normal" if can_manage else "disabled")
        self._btn_nozzle.config(state="normal" if can_manage else "disabled")

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _on_select(self, _event=None) -> None:
        sel = self._tree.selection()
        if not sel:
            self._clear_detail()
            return
        printer = self._svc.get_printer(sel[0])
        if printer:
            self._show_detail(printer)

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

    def _add_printer(self) -> None:
        dlg = _PrinterDialog(self, title="Add Printer")
        if dlg.result:
            self._svc.add_printer(**dlg.result)
            self.refresh()
            self._notify()

    def _edit_printer(self) -> None:
        if not self._selected_id:
            return
        printer = self._svc.get_printer(self._selected_id)
        if not printer:
            return
        dlg = _PrinterDialog(self, title="Edit Printer", printer=printer)
        if dlg.result:
            self._svc.update_printer(self._selected_id, **dlg.result)
            self.refresh()
            if self._selected_id in self._tree.get_children():
                self._tree.selection_set(self._selected_id)
            self._on_select()

    def _reset_nozzle(self) -> None:
        if not self._selected_id:
            return
        if not messagebox.askyesno(
            "Reset Nozzle",
            "Record a nozzle change and reset the nozzle counter?",
        ):
            return
        self._svc.reset_nozzle(self._selected_id)
        self.refresh()
        if self._selected_id in self._tree.get_children():
            self._tree.selection_set(self._selected_id)
        self._on_select()


# ---------------------------------------------------------------------------
# Printer dialog
# ---------------------------------------------------------------------------

class _PrinterDialog:
    def __init__(self, parent, title="Printer", printer=None) -> None:
        self.result = None
        self._win = tk.Toplevel(parent)
        self._win.title(title)
        self._win.resizable(False, False)
        self._win.grab_set()
        self._build(printer)
        self._win.wait_window()

    def _build(self, p) -> None:
        f = ttk.Frame(self._win, padding=16)
        f.pack(fill=tk.BOTH, expand=True)
        f.columnconfigure(1, weight=1)
        pad = dict(padx=8, pady=4)

        fields = [
            ("Name *",         "name",            str,   p.name if p else "HIVE"),
            ("Model",          "model",            str,   p.model if p else "Creality Ender-3 Max"),
            ("Purchase Price", "purchase_price",   float, str(p.purchase_price) if p else "25000"),
            ("Lifetime (kg)",  "lifetime_kg",      float, str(p.lifetime_kg) if p else "500"),
            ("Nozzle Cost",    "nozzle_cost",      float, str(p.nozzle_cost) if p else "100"),
            ("Nozzle Life (g)","nozzle_lifetime_grams", float,
             str(p.nozzle_lifetime_grams) if p else "1500"),
            ("Notes",          "notes",            str,   p.notes if p else ""),
        ]
        self._vars: dict = {}
        for r, (label, key, cast, default) in enumerate(fields):
            ttk.Label(f, text=label).grid(row=r, column=0, sticky="w", **pad)
            var = tk.StringVar(value=default)
            ttk.Entry(f, textvariable=var, width=30).grid(
                row=r, column=1, sticky="ew", **pad)
            self._vars[key] = (var, cast)

        # Active checkbox
        self._active_var = tk.BooleanVar(value=p.is_active if p else True)
        ttk.Checkbutton(f, text="Active", variable=self._active_var).grid(
            row=len(fields), column=1, sticky="w", **pad)

        btn_row = ttk.Frame(f)
        btn_row.grid(row=len(fields)+1, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_row, text="💾 Save",
                   command=self._save).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="Cancel",
                   command=self._win.destroy).pack(side=tk.LEFT, padx=4)

    def _save(self) -> None:
        data = {}
        for key, (var, cast) in self._vars.items():
            raw = var.get().strip()
            try:
                data[key] = cast(raw) if raw else (0.0 if cast is float else "")
            except ValueError:
                messagebox.showerror("Invalid",
                                     f"Invalid value for {key}.",
                                     parent=self._win)
                return
        if not data.get("name"):
            messagebox.showwarning("Required", "Name is required.",
                                   parent=self._win)
            return
        data["is_active"] = self._active_var.get()
        self.result = data
        self._win.destroy()