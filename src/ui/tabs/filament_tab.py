"""
src/ui/tabs/filament_tab.py
===========================
Filament inventory management tab for Abaad 3D Print Manager v5.0.

Features:
- Spool list with color, brand, weight, pending, available
- "Move to Trash" button for low spools (< 20 g)
- Add Standard spool / Add Remaining spool
- Color palette management
- Inventory summary bar
"""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Optional

from src.auth.permissions import Permission
from src.core.config import TRASH_THRESHOLD_GRAMS
from src.services.inventory_service import InventoryService
from src.ui.theme import Colors, Fonts
from src.utils.helpers import format_currency
from src.ui.context_menu import bind_treeview_menu



class FilamentTab(ttk.Frame):
    """Filament inventory management tab.

    Args:
        parent:            ttk.Notebook parent.
        inventory_service: InventoryService instance.
        user:              Currently logged-in User object.
        on_status_change:  Optional callback after data mutation.
    """

    def __init__(self, parent, inventory_service: InventoryService, user,
                 on_status_change=None) -> None:
        super().__init__(parent, padding=10)
        self._svc    = inventory_service
        self._user   = user
        self._notify = on_status_change or (lambda: None)
        self._selected_id: Optional[str] = None

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._load_spools()
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

        can_manage = self._user.has_permission(Permission.MANAGE_INVENTORY)

        ttk.Button(tb, text="➕ Standard Spool",
                   command=self._add_standard,
                   state="normal" if can_manage else "disabled").pack(
            side=tk.LEFT, padx=2)
        ttk.Button(tb, text="➕ Remaining Spool",
                   command=self._add_remaining,
                   state="normal" if can_manage else "disabled").pack(
            side=tk.LEFT, padx=2)
        ttk.Button(tb, text="🎨 Manage Colors",
                   command=self._manage_colors,
                   state="normal" if can_manage else "disabled").pack(
            side=tk.LEFT, padx=2)

        ttk.Separator(tb, orient="vertical").pack(side=tk.LEFT, fill=tk.Y,
                                                   padx=8)
        # Filter
        ttk.Label(tb, text="Show:").pack(side=tk.LEFT)
        self._filter_var = tk.StringVar(value="active")
        for label, val in [("Active", "active"), ("Low", "low"),
                            ("Trash", "trash"), ("All", "all")]:
            ttk.Radiobutton(tb, text=label, variable=self._filter_var,
                            value=val, command=self.refresh).pack(
                side=tk.LEFT, padx=4)

        ttk.Button(tb, text="🔄 Refresh",
                   command=self.refresh).pack(side=tk.RIGHT, padx=2)

        self._btn_trash = ttk.Button(tb, text="🗑 Move to Trash",
                                     command=self._move_to_trash,
                                     state="disabled")
        self._btn_trash.pack(side=tk.RIGHT, padx=2)

        self._btn_edit = ttk.Button(tb, text="✏️ Edit",
                                    command=self._edit_spool,
                                    state="disabled")
        self._btn_edit.pack(side=tk.RIGHT, padx=2)

    def _build_list(self) -> None:
        list_frame = ttk.Frame(self)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        cols = ("color", "brand", "type", "category", "current", "pending",
                "available", "cost_g", "status")
        self._tree = ttk.Treeview(list_frame, columns=cols, show="headings",
                                  selectmode="browse")

        headers = [
            ("color",     "Color",         120),
            ("brand",     "Brand",         80),
            ("type",      "Type",          60),
            ("category",  "Category",      80),
            ("current",   "Current (g)",   80),
            ("pending",   "Pending (g)",   80),
            ("available", "Available (g)", 90),
            ("cost_g",    "Cost/g",        70),
            ("status",    "Status",        70),
        ]
        for col, text, width in headers:
            self._tree.heading(col, text=text,
                               command=lambda c=col: self._sort(c))
            anchor = "e" if col in ("current", "pending", "available",
                                    "cost_g") else "w"
            self._tree.column(col, width=width, anchor=anchor)

        vsb = ttk.Scrollbar(list_frame, orient="vertical",
                             command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        bind_treeview_menu(self._tree, actions=[
            ("✏️ Edit",          self._edit_spool),
            ("🗑 Move to Trash",  self._move_to_trash),
        ])
        self._tree.tag_configure("low",   background="#fff3cd")
        self._tree.tag_configure("trash", background="#f8d7da")
        self._tree.tag_configure("std",   background=Colors.CARD)

    def _build_summary(self) -> None:
        summary = ttk.LabelFrame(self, text="📊 Inventory Summary", padding=8)
        summary.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        cards = [
            ("Active Spools",  "_sum_active",    Colors.SUCCESS),
            ("Total Remaining","_sum_remaining",  Colors.PRIMARY),
            ("Total Pending",  "_sum_pending",    Colors.WARNING),
            ("Total Available","_sum_available",  Colors.INFO),
            ("Inventory Value","_sum_value",      Colors.PURPLE),
        ]
        for i, (label, attr, color) in enumerate(cards):
            card = tk.Frame(summary, bg=color, padx=12, pady=6)
            card.grid(row=0, column=i, padx=4, sticky="ew")
            summary.columnconfigure(i, weight=1)
            tk.Label(card, text=label, bg=color, fg="white",
                     font=Fonts.SMALL).pack()
            val = tk.Label(card, text="—", bg=color, fg="white",
                           font=Fonts.BIG_NUMBER)
            val.pack()
            setattr(self, attr, val)

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _load_spools(self) -> None:
        filt = self._filter_var.get()
        all_spools = self._svc.get_all_spools()
        if filt == "active":
            spools = [s for s in all_spools if s.is_active and s.status not in ("trash", "archived")]
        elif filt == "low":
            spools = [s for s in all_spools if s.status == "low"]
        elif filt == "trash":
            spools = [s for s in all_spools if s.status == "trash"]
        else:
            spools = all_spools
        self._tree.delete(*self._tree.get_children())
        for s in spools:
            tag = "low" if s.status == "low" else "trash" if s.status == "trash" else "std"
            self._tree.insert("", "end", iid=s.id, values=(
                s.color,
                s.brand or "—",
                s.filament_type or "PLA+",
                s.category.capitalize(),
                f"{s.current_weight_grams:.1f}",
                f"{s.pending_weight_grams:.1f}",
                f"{s.available_weight_grams:.1f}",
                f"{s.cost_per_gram:.2f}",
                s.status.capitalize(),
            ), tags=(tag,))
        self._selected_id = None
        self._btn_edit.config(state="disabled")
        self._btn_trash.config(state="disabled")

    def _update_summary(self) -> None:
        info = self._svc.get_inventory_summary()
        self._sum_active.config(text=str(info.get("active_spools", 0)))
        self._sum_remaining.config(
            text=f"{info.get('total_weight_g', 0):.0f} g")
        self._sum_pending.config(
            text=f"{info.get('pending_weight_g', 0):.0f} g")
        self._sum_available.config(
            text=f"{info.get('available_weight_g', 0):.0f} g")
        self._sum_value.config(
            text=format_currency(info.get("total_value_egp", 0)))

    def _sort(self, col: str) -> None:
        """Toggle sort on a column."""
        items = [(self._tree.set(iid, col), iid)
                 for iid in self._tree.get_children()]
        try:
            items.sort(key=lambda t: float(t[0]))
        except ValueError:
            items.sort(key=lambda t: t[0].lower())
        for idx, (_, iid) in enumerate(items):
            self._tree.move(iid, "", idx)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _on_select(self, _event=None) -> None:
        sel = self._tree.selection()
        if not sel:
            self._selected_id = None
            self._btn_edit.config(state="disabled")
            self._btn_trash.config(state="disabled")
            return
        self._selected_id = sel[0]
        can_manage = self._user.has_permission(Permission.MANAGE_INVENTORY)
        self._btn_edit.config(state="normal" if can_manage else "disabled")

        spool = self._svc.get_spool(self._selected_id)
        show_trash = (can_manage and spool and
                      spool.current_weight_grams <= TRASH_THRESHOLD_GRAMS and
                      spool.status not in ("trash", "archived"))
        self._btn_trash.config(state="normal" if show_trash else "disabled")

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

    def _add_standard(self) -> None:
        dlg = _SpoolDialog(self, title="Add Standard Spool", category="standard",
                           colors=self._svc.get_colors())
        if dlg.result:
            self._svc.add_spool(**dlg.result)
            self.refresh()
            self._notify()

    def _add_remaining(self) -> None:
        dlg = _SpoolDialog(self, title="Add Remaining Spool", category="remaining",
                           colors=self._svc.get_colors())
        if dlg.result:
            self._svc.add_spool(**dlg.result)
            self.refresh()
            self._notify()

    def _edit_spool(self) -> None:
        if not self._selected_id:
            return
        spool = self._svc.get_spool(self._selected_id)
        if not spool:
            return
        dlg = _SpoolDialog(self, title="Edit Spool", spool=spool,
                           category=spool.category,
                           colors=self._svc.get_colors())
        if dlg.result:
            self._svc.update_spool(self._selected_id, **dlg.result)
            self.refresh()
            self._notify()

    def _move_to_trash(self) -> None:
        if not self._selected_id:
            return
        spool = self._svc.get_spool(self._selected_id)
        if not spool:
            return
        if not messagebox.askyesno(
            "Move to Trash",
            f"Move '{spool.color}' spool ({spool.current_weight_grams:.1f}g remaining) to trash?\n"
            "This will archive it and record the wasted weight.",
        ):
            return
        ok = self._svc.move_to_trash(self._selected_id)
        if ok:
            self.refresh()
            self._notify()
        else:
            messagebox.showerror("Error", "Could not move spool to trash.")

    def _manage_colors(self) -> None:
        dlg = _ColorsDialog(self, service=self._svc)
        dlg.run()
        self.refresh()


# ---------------------------------------------------------------------------
# Spool dialog
# ---------------------------------------------------------------------------

class _SpoolDialog:
    def __init__(self, parent, title="Spool", category="standard",
                 spool=None, colors: list = None) -> None:
        self.result = None
        self._win = tk.Toplevel(parent)
        self._win.title(title)
        self._win.resizable(False, False)
        self._win.grab_set()
        self._category = category
        self._spool = spool
        self._colors = colors or []
        self._build()
        self._win.wait_window()

    def _build(self) -> None:
        f = ttk.Frame(self._win, padding=16)
        f.pack(fill=tk.BOTH, expand=True)
        f.columnconfigure(1, weight=1)
        pad = dict(padx=8, pady=4)

        s = self._spool

        # Color
        ttk.Label(f, text="Color *").grid(row=0, column=0, sticky="w", **pad)
        self._color_var = tk.StringVar(value=s.color if s else "")
        color_cb = ttk.Combobox(f, textvariable=self._color_var,
                                values=self._colors, width=22)
        color_cb.grid(row=0, column=1, sticky="ew", **pad)

        # Brand
        ttk.Label(f, text="Brand").grid(row=1, column=0, sticky="w", **pad)
        self._brand_var = tk.StringVar(value=s.brand if s else "eSUN")
        ttk.Entry(f, textvariable=self._brand_var).grid(
            row=1, column=1, sticky="ew", **pad)

        # Type
        ttk.Label(f, text="Type").grid(row=2, column=0, sticky="w", **pad)
        self._type_var = tk.StringVar(
            value=s.filament_type if s else "PLA+")
        ttk.Combobox(f, textvariable=self._type_var,
                     values=["PLA", "PLA+", "PETG", "ABS", "TPU", "ASA",
                             "Resin", "Other"]).grid(
            row=2, column=1, sticky="ew", **pad)

        # Weight (only editable for remaining or new standard)
        ttk.Label(f, text="Weight (g) *").grid(row=3, column=0, sticky="w", **pad)
        default_w = "1000" if self._category == "standard" else (
            str(s.current_weight_grams) if s else "")
        self._weight_var = tk.StringVar(value=default_w)
        state = "disabled" if (self._category == "standard" and not s) else "normal"
        ttk.Entry(f, textvariable=self._weight_var,
                  state=state).grid(row=3, column=1, sticky="ew", **pad)

        # Price (standard only)
        ttk.Label(f, text="Price (EGP)").grid(row=4, column=0, sticky="w", **pad)
        default_p = "840" if self._category == "standard" else "0"
        self._price_var = tk.StringVar(
            value=str(s.purchase_price_egp) if s else default_p)
        price_state = "disabled" if self._category == "remaining" else "normal"
        ttk.Entry(f, textvariable=self._price_var,
                  state=price_state).grid(row=4, column=1, sticky="ew", **pad)

        # Notes
        ttk.Label(f, text="Notes").grid(row=5, column=0, sticky="w", **pad)
        self._notes_var = tk.StringVar(value=s.notes if s else "")
        ttk.Entry(f, textvariable=self._notes_var).grid(
            row=5, column=1, sticky="ew", **pad)

        # Category info
        info = ("Standard spool: 1 kg, cost per gram = price ÷ 1000"
                if self._category == "standard"
                else "Remaining spool: cost per gram = 0 (already paid)")
        ttk.Label(f, text=info, style="Muted.TLabel").grid(
            row=6, column=0, columnspan=2, sticky="w", **pad)

        btn_row = ttk.Frame(f)
        btn_row.grid(row=7, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_row, text="💾 Save",
                   command=self._save).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="Cancel",
                   command=self._win.destroy).pack(side=tk.LEFT, padx=4)

    def _save(self) -> None:
        color = self._color_var.get().strip()
        if not color:
            messagebox.showwarning("Required", "Color is required.",
                                   parent=self._win)
            return
        try:
            weight = float(self._weight_var.get() or 1000)
            price  = float(self._price_var.get() or 0)
        except ValueError:
            messagebox.showerror("Invalid", "Weight and price must be numbers.",
                                 parent=self._win)
            return

        self.result = {
            "color":                color,
            "brand":                self._brand_var.get().strip(),
            "filament_type":        self._type_var.get().strip(),
            "category":             self._category,
            "initial_weight_grams": weight,
            "purchase_price_egp":   price,
            "notes":                self._notes_var.get().strip(),
        }
        self._win.destroy()


# ---------------------------------------------------------------------------
# Color management dialog
# ---------------------------------------------------------------------------

class _ColorsDialog:
    def __init__(self, parent, service: InventoryService) -> None:
        self._svc = service
        self._win = tk.Toplevel(parent)
        self._win.title("Manage Colors")
        self._win.resizable(False, False)
        self._win.grab_set()
        self._build()

    def run(self) -> None:
        self._win.wait_window()

    def _build(self) -> None:
        f = ttk.Frame(self._win, padding=12)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text="Colors", style="Header.TLabel").pack(pady=(0, 6))

        self._listbox = tk.Listbox(f, height=10, width=24)
        self._listbox.pack(fill=tk.BOTH, expand=True)
        self._reload()

        entry_row = ttk.Frame(f)
        entry_row.pack(fill=tk.X, pady=6)
        self._new_color = tk.StringVar()
        ttk.Entry(entry_row, textvariable=self._new_color).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(entry_row, text="Add",
                   command=self._add_color).pack(side=tk.LEFT, padx=4)

        ttk.Button(f, text="Close",
                   command=self._win.destroy).pack()

    def _reload(self) -> None:
        self._listbox.delete(0, tk.END)
        for c in self._svc.get_colors():
            self._listbox.insert(tk.END, c)

    def _add_color(self) -> None:
        color = self._new_color.get().strip()
        if not color:
            return
        self._svc.add_color(color)
        self._new_color.set("")
        self._reload()