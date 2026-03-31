"""
src/ui/dialogs/item_dialog.py
=============================
Add / Edit print item dialog for Abaad ERP v5.0.

Features:
- All item fields: name, weight, time, color, spool, qty, rate, notes
- Print settings: nozzle, layer height, infill, support type, scale
- Live cost preview as user types
- Import from Cura (.gcode file) or clipboard OCR
- Tolerance discount indicator
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from src.core.config import (
    DEFAULT_RATE_PER_GRAM, DEFAULT_COST_PER_GRAM,
    DEFAULT_NOZZLE, DEFAULT_LAYER_HEIGHT,
    SUPPORT_TYPES, ELECTRICITY_RATE,
    TOLERANCE_THRESHOLD_GRAMS,
)
from src.ui.theme import Colors, Fonts
from src.utils.helpers import format_currency, safe_float, safe_int


class ItemDialog:
    """Add or Edit a print item.

    Args:
        parent:    Parent widget.
        colors:    List of available color strings.
        spools:    List of FilamentSpool objects.
        item:      Existing PrintItem to edit (None for new).
        title:     Dialog window title.

    Attributes:
        result: Dict of item fields, or None if cancelled.
    """

    def __init__(self, parent, colors: list, spools: list,
                 item=None, title: str = "Print Item") -> None:
        self.result = None
        self._colors = colors
        self._spools = spools
        self._item   = item
        self._spool_map: dict = {}

        self._win = tk.Toplevel(parent)
        self._win.title(title)
        self._win.resizable(True, False)
        self._win.grab_set()
        self._build()
        self._centre(parent)
        if item:
            self._populate(item)
        self._recalc()
        self._win.wait_window()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        outer = ttk.Frame(self._win, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=1)

        # ── Left column: core fields ──────────────────────────────────
        left = ttk.LabelFrame(outer, text="Item Details", padding=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.columnconfigure(1, weight=1)

        pad = dict(padx=6, pady=3)

        # Name
        ttk.Label(left, text="Name *").grid(row=0, column=0, sticky="w", **pad)
        self._name_var = tk.StringVar()
        ttk.Entry(left, textvariable=self._name_var, width=24).grid(
            row=0, column=1, sticky="ew", **pad)

        # Color
        ttk.Label(left, text="Color").grid(row=1, column=0, sticky="w", **pad)
        self._color_var = tk.StringVar()
        self._color_var.trace_add("write", self._update_spools)
        ttk.Combobox(left, textvariable=self._color_var,
                     values=self._colors, width=18).grid(
            row=1, column=1, sticky="ew", **pad)

        # Spool
        ttk.Label(left, text="Spool").grid(row=2, column=0, sticky="w", **pad)
        self._spool_var = tk.StringVar()
        self._spool_cb = ttk.Combobox(left, textvariable=self._spool_var,
                                       state="readonly", width=22)
        self._spool_cb.grid(row=2, column=1, sticky="ew", **pad)

        # Weight estimated
        ttk.Label(left, text="Est. Weight (g) *").grid(
            row=3, column=0, sticky="w", **pad)
        self._weight_var = tk.StringVar(value="0")
        self._weight_var.trace_add("write", self._recalc)
        ttk.Entry(left, textvariable=self._weight_var, width=10).grid(
            row=3, column=1, sticky="w", **pad)

        # Actual weight
        ttk.Label(left, text="Actual Weight (g)").grid(
            row=4, column=0, sticky="w", **pad)
        self._actual_var = tk.StringVar(value="0")
        self._actual_var.trace_add("write", self._recalc)
        ttk.Entry(left, textvariable=self._actual_var, width=10).grid(
            row=4, column=1, sticky="w", **pad)

        # Print time
        ttk.Label(left, text="Print Time (min) *").grid(
            row=5, column=0, sticky="w", **pad)
        self._time_var = tk.StringVar(value="0")
        self._time_var.trace_add("write", self._recalc)
        ttk.Entry(left, textvariable=self._time_var, width=10).grid(
            row=5, column=1, sticky="w", **pad)

        # Quantity
        ttk.Label(left, text="Quantity").grid(
            row=6, column=0, sticky="w", **pad)
        self._qty_var = tk.StringVar(value="1")
        self._qty_var.trace_add("write", self._recalc)
        ttk.Spinbox(left, textvariable=self._qty_var,
                    from_=1, to=999, width=6).grid(
            row=6, column=1, sticky="w", **pad)

        # Rate per gram
        ttk.Label(left, text="Rate (EGP/g)").grid(
            row=7, column=0, sticky="w", **pad)
        self._rate_var = tk.StringVar(value=str(DEFAULT_RATE_PER_GRAM))
        self._rate_var.trace_add("write", self._recalc)
        ttk.Entry(left, textvariable=self._rate_var, width=8).grid(
            row=7, column=1, sticky="w", **pad)

        # Notes
        ttk.Label(left, text="Notes").grid(
            row=8, column=0, sticky="w", **pad)
        self._notes_var = tk.StringVar()
        ttk.Entry(left, textvariable=self._notes_var, width=24).grid(
            row=8, column=1, sticky="ew", **pad)

        # ── Right column: print settings ─────────────────────────────
        right = ttk.LabelFrame(outer, text="Print Settings", padding=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right.columnconfigure(1, weight=1)

        # Nozzle
        ttk.Label(right, text="Nozzle (mm)").grid(
            row=0, column=0, sticky="w", **pad)
        self._nozzle_var = tk.StringVar(value=str(DEFAULT_NOZZLE))
        ttk.Combobox(right, textvariable=self._nozzle_var,
                     values=["0.2", "0.4", "0.6", "0.8"],
                     width=8).grid(row=0, column=1, sticky="w", **pad)

        # Layer height
        ttk.Label(right, text="Layer Height (mm)").grid(
            row=1, column=0, sticky="w", **pad)
        self._layer_var = tk.StringVar(value=str(DEFAULT_LAYER_HEIGHT))
        ttk.Combobox(right, textvariable=self._layer_var,
                     values=["0.1", "0.15", "0.2", "0.25", "0.3"],
                     width=8).grid(row=1, column=1, sticky="w", **pad)

        # Infill
        ttk.Label(right, text="Infill %").grid(
            row=2, column=0, sticky="w", **pad)
        self._infill_var = tk.StringVar(value="20")
        ttk.Combobox(right, textvariable=self._infill_var,
                     values=["10", "15", "20", "25", "30",
                              "40", "50", "75", "100"],
                     width=8).grid(row=2, column=1, sticky="w", **pad)

        # Support
        ttk.Label(right, text="Support").grid(
            row=3, column=0, sticky="w", **pad)
        self._support_var = tk.StringVar(value="None")
        ttk.Combobox(right, textvariable=self._support_var,
                     values=SUPPORT_TYPES, state="readonly",
                     width=10).grid(row=3, column=1, sticky="w", **pad)

        # Scale
        ttk.Label(right, text="Scale %").grid(
            row=4, column=0, sticky="w", **pad)
        self._scale_var = tk.StringVar(value="100")
        ttk.Entry(right, textvariable=self._scale_var, width=8).grid(
            row=4, column=1, sticky="w", **pad)

        # Cura import
        ttk.Separator(right, orient="horizontal").grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Label(right, text="Import from Cura:",
                  style="Section.TLabel").grid(
            row=6, column=0, columnspan=2, sticky="w", **pad)

        btn_row = ttk.Frame(right)
        btn_row.grid(row=7, column=0, columnspan=2, sticky="w", **pad)
        ttk.Button(btn_row, text="📂 .gcode File",
                   command=self._import_gcode).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="📋 Clipboard OCR",
                   command=self._import_ocr).pack(side=tk.LEFT, padx=2)

        self._cura_status = ttk.Label(right, text="",
                                       style="Muted.TLabel", wraplength=200)
        self._cura_status.grid(row=8, column=0, columnspan=2,
                                sticky="w", **pad)

        # ── Cost preview (full width) ─────────────────────────────────
        cost_frame = ttk.LabelFrame(outer, text="💰 Cost Preview", padding=10)
        cost_frame.grid(row=1, column=0, columnspan=2,
                        sticky="ew", pady=(10, 0))
        cost_frame.columnconfigure((0, 1, 2, 3, 4), weight=1)

        self._cost_labels: dict = {}
        cost_items = [
            ("Weight Used",   "weight"),
            ("Material Cost", "material"),
            ("Electricity",   "electricity"),
            ("Tolerance Disc","tolerance"),
            ("Item Total",    "total"),
        ]
        for i, (label, key) in enumerate(cost_items):
            tk.Frame(cost_frame).grid(row=0, column=i)
            ttk.Label(cost_frame, text=label,
                      style="Muted.TLabel").grid(row=0, column=i, padx=8)
            val = ttk.Label(cost_frame, text="—",
                            style="Section.TLabel")
            val.grid(row=1, column=i, padx=8, pady=4)
            self._cost_labels[key] = val

        # ── Buttons ───────────────────────────────────────────────────
        btn_frame = ttk.Frame(outer)
        btn_frame.grid(row=2, column=0, columnspan=2,
                       sticky="e", pady=(12, 0))
        ttk.Button(btn_frame, text="💾 Save Item",
                   command=self._save).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Cancel",
                   command=self._win.destroy).pack(side=tk.LEFT, padx=4)

        self._update_spools()

    # ------------------------------------------------------------------
    # Spool management
    # ------------------------------------------------------------------

    def _update_spools(self, *_) -> None:
        color = self._color_var.get()
        filtered = [s for s in self._spools
                    if not color or s.color == color]
        labels = [
            f"{s.color} — {s.available_weight:.0f}g avail (id:{s.id[:6]})"
            for s in filtered
        ]
        self._spool_map = {lbl: s.id for lbl, s in zip(labels, filtered)}
        self._spool_cb["values"] = labels
        if labels:
            self._spool_cb.current(0)

    # ------------------------------------------------------------------
    # Cost preview
    # ------------------------------------------------------------------

    def _recalc(self, *_) -> None:
        weight   = safe_float(self._weight_var.get())
        actual   = safe_float(self._actual_var.get()) or weight
        minutes  = safe_float(self._time_var.get())
        qty      = max(1, safe_int(self._qty_var.get(), 1))
        rate     = safe_float(self._rate_var.get(), DEFAULT_RATE_PER_GRAM)

        # Tolerance discount
        diff = actual - weight
        tol_disc = 0.0
        if 0 < diff <= TOLERANCE_THRESHOLD_GRAMS:
            tol_disc = rate * qty        # 1g × rate × qty

        used      = weight * qty
        material  = used * DEFAULT_COST_PER_GRAM
        elec      = (minutes / 60) * ELECTRICITY_RATE * qty
        item_total = weight * qty * rate - tol_disc

        self._cost_labels["weight"].config(text=f"{used:.1f} g")
        self._cost_labels["material"].config(
            text=format_currency(material))
        self._cost_labels["electricity"].config(
            text=format_currency(elec))
        tol_text = (f"-{format_currency(tol_disc)}" if tol_disc
                    else "—")
        tol_color = Colors.SUCCESS if tol_disc else Colors.TEXT
        self._cost_labels["tolerance"].config(
            text=tol_text, foreground=tol_color)
        self._cost_labels["total"].config(
            text=format_currency(item_total))

    # ------------------------------------------------------------------
    # Cura import
    # ------------------------------------------------------------------

    def _import_gcode(self) -> None:
        path = filedialog.askopenfilename(
            title="Select .gcode file",
            filetypes=[("G-code files", "*.gcode *.gco *.g"),
                       ("All files", "*.*")],
        )
        if not path:
            return
        try:
            from src.services.cura_service import CuraService
            result = CuraService.parse_gcode(path)
            if result:
                self._apply_cura_result(result)
                self._cura_status.config(
                    text=f"✅ Imported: {result.get('weight_grams', 0):.1f}g, "
                         f"{result.get('time_minutes', 0):.0f} min",
                    foreground=Colors.SUCCESS)
            else:
                self._cura_status.config(
                    text="⚠ Could not parse file.",
                    foreground=Colors.WARNING)
        except Exception as exc:
            self._cura_status.config(
                text=f"❌ Error: {exc}",
                foreground=Colors.DANGER)

    def _import_ocr(self) -> None:
        try:
            from src.services.cura_service import CuraService
            result = CuraService.extract_from_clipboard()
            if result:
                self._apply_cura_result(result)
                self._cura_status.config(
                    text="✅ OCR import successful.",
                    foreground=Colors.SUCCESS)
            else:
                self._cura_status.config(
                    text="⚠ No data found in clipboard.",
                    foreground=Colors.WARNING)
        except Exception as exc:
            self._cura_status.config(
                text=f"❌ {exc}",
                foreground=Colors.DANGER)

    def _apply_cura_result(self, result: dict) -> None:
        if "weight_grams" in result:
            self._weight_var.set(f"{result['weight_grams']:.1f}")
        if "time_minutes" in result:
            self._time_var.set(f"{result['time_minutes']:.0f}")
        if "layer_height" in result:
            self._layer_var.set(str(result["layer_height"]))

    # ------------------------------------------------------------------
    # Populate for edit
    # ------------------------------------------------------------------

    def _populate(self, item) -> None:
        self._name_var.set(item.name or "")
        self._color_var.set(item.color or "")
        self._weight_var.set(str(item.weight_grams or 0))
        self._actual_var.set(str(item.actual_weight or item.weight_grams or 0))
        self._time_var.set(str(item.print_time_minutes or 0))
        self._qty_var.set(str(item.quantity or 1))
        self._rate_var.set(str(item.rate_per_gram or DEFAULT_RATE_PER_GRAM))
        self._notes_var.set(item.notes or "")
        self._nozzle_var.set(str(item.nozzle_size or DEFAULT_NOZZLE))
        self._layer_var.set(str(item.layer_height or DEFAULT_LAYER_HEIGHT))
        self._infill_var.set(str(item.infill_percent or 20))
        self._support_var.set(item.support_type or "None")
        self._scale_var.set(str(item.scale_percent or 100))

        # Select spool in combobox
        if item.spool_id:
            for lbl, sid in self._spool_map.items():
                if sid == item.spool_id:
                    self._spool_var.set(lbl)
                    break

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self) -> None:
        name = self._name_var.get().strip()
        if not name:
            messagebox.showwarning("Required", "Item name is required.",
                                   parent=self._win)
            return

        weight = safe_float(self._weight_var.get())
        if weight <= 0:
            messagebox.showwarning("Required",
                                   "Estimated weight must be > 0.",
                                   parent=self._win)
            return

        spool_lbl = self._spool_var.get()
        spool_id  = self._spool_map.get(spool_lbl)

        self.result = {
            "name":              name,
            "color":             self._color_var.get().strip(),
            "spool_id":          spool_id,
            "weight_grams":      weight,
            "actual_weight":     safe_float(self._actual_var.get()) or weight,
            "print_time_minutes":safe_int(self._time_var.get()),
            "quantity":          max(1, safe_int(self._qty_var.get(), 1)),
            "rate_per_gram":     safe_float(self._rate_var.get(),
                                            DEFAULT_RATE_PER_GRAM),
            "notes":             self._notes_var.get().strip(),
            "nozzle_size":       safe_float(self._nozzle_var.get(),
                                            DEFAULT_NOZZLE),
            "layer_height":      safe_float(self._layer_var.get(),
                                            DEFAULT_LAYER_HEIGHT),
            "infill_percent":    safe_int(self._infill_var.get(), 20),
            "support_type":      self._support_var.get(),
            "scale_percent":     safe_float(self._scale_var.get(), 100),
        }
        self._win.destroy()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _centre(self, parent) -> None:
        self._win.update_idletasks()
        w = self._win.winfo_width()
        h = self._win.winfo_height()
        px = parent.winfo_rootx() + parent.winfo_width()  // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        self._win.geometry(f"+{px - w//2}+{py - h//2}")