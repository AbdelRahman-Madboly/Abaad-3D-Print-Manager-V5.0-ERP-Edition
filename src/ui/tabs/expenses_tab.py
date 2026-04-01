"""
src/ui/tabs/expenses_tab.py
===========================
Expenses tracking tab for Abaad 3D Print Manager v5.0.

Features:
- Expenses list: Date, Category, Name, Amount, Qty, Total, Supplier, Recurring
- Add / Edit / Delete expense (proper edit — not delete-and-re-add)
- Monthly and category totals
- Summary bar
"""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from src.auth.permissions import Permission
from src.core.config import EXPENSE_CATEGORIES
from src.services.finance_service import FinanceService
from src.ui.theme import Colors, Fonts
from src.utils.helpers import format_currency, safe_float


_CATEGORY_ICONS = {
    "Bills":         "💡",
    "Engineer":      "👷",
    "Tools":         "🔧",
    "Consumables":   "📦",
    "Maintenance":   "🛠",
    "Filament":      "🧵",
    "Packaging":     "📫",
    "Shipping":      "🚚",
    "Software":      "💻",
    "Other":         "📋",
}


class ExpensesTab(ttk.Frame):
    """Expenses tracking tab.

    Args:
        parent:          ttk.Notebook parent.
        finance_service: FinanceService instance.
        user:            Currently logged-in User object.
    """

    def __init__(self, parent, finance_service: FinanceService, user,
                 on_status_change=None) -> None:
        super().__init__(parent, padding=10)
        self._fin    = finance_service
        self._user   = user
        self._notify = on_status_change or (lambda: None)
        self._selected_id: Optional[str] = None

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._load_expenses()
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

        ttk.Button(tb, text="➕ Add Expense",
                   command=self._add_expense,
                   state="normal" if can_manage else "disabled").pack(
            side=tk.LEFT, padx=2)
        self._btn_edit = ttk.Button(tb, text="✏️ Edit",
                                    command=self._edit_expense,
                                    state="disabled")
        self._btn_edit.pack(side=tk.LEFT, padx=2)
        self._btn_del = ttk.Button(tb, text="🗑 Delete",
                                   command=self._delete_expense,
                                   state="disabled")
        self._btn_del.pack(side=tk.LEFT, padx=2)

        ttk.Separator(tb, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8)

        # Category filter
        ttk.Label(tb, text="Category:").pack(side=tk.LEFT)
        self._cat_filter = tk.StringVar(value="All")
        ttk.Combobox(tb, textvariable=self._cat_filter,
                     values=["All"] + EXPENSE_CATEGORIES, width=14,
                     state="readonly").pack(side=tk.LEFT, padx=4)

        # Month filter
        ttk.Label(tb, text="Month:").pack(side=tk.LEFT)
        self._month_filter = tk.StringVar(value="All")
        self._month_cb = ttk.Combobox(tb, textvariable=self._month_filter,
                                       width=12, state="readonly")
        self._month_cb.pack(side=tk.LEFT, padx=4)

        ttk.Button(tb, text="🔍 Filter",
                   command=self.refresh).pack(side=tk.LEFT, padx=2)
        ttk.Button(tb, text="🔄 Reset",
                   command=self._reset_filter).pack(side=tk.LEFT, padx=2)

    def _build_list(self) -> None:
        lf = ttk.Frame(self)
        lf.grid(row=1, column=0, sticky="nsew")
        lf.rowconfigure(0, weight=1)
        lf.columnconfigure(0, weight=1)

        cols = ("date", "category", "name", "amount", "qty", "total",
                "supplier", "recurring", "notes")
        self._tree = ttk.Treeview(lf, columns=cols, show="headings",
                                  selectmode="browse")
        headers = [
            ("date",      "Date",       90),
            ("category",  "Category",  110),
            ("name",      "Name",      130),
            ("amount",    "Amount",     80),
            ("qty",       "Qty",        40),
            ("total",     "Total",      80),
            ("supplier",  "Supplier",   90),
            ("recurring", "Recurring",  70),
            ("notes",     "Notes",     130),
        ]
        for col, text, width in headers:
            self._tree.heading(col, text=text,
                               command=lambda c=col: self._sort(c))
            anchor = "e" if col in ("amount", "qty", "total") else "w"
            self._tree.column(col, width=width, anchor=anchor)

        vsb = ttk.Scrollbar(lf, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)

    def _build_summary(self) -> None:
        sf = ttk.LabelFrame(self, text="📊 Expense Summary", padding=8)
        sf.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        cards = [
            ("Total Expenses",   "_sum_total",   Colors.DANGER),
            ("This Month",       "_sum_month",   Colors.WARNING),
            ("Recurring / Month","_sum_recurring",Colors.INFO),
            ("# Transactions",   "_sum_count",   Colors.PRIMARY),
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

    def _load_expenses(self) -> None:
        cat   = self._cat_filter.get()
        month = self._month_filter.get()
        expenses = self._fin.get_all_expenses(
            category_filter=None if cat == "All" else cat,
            month_filter=None if month == "All" else month,
        )
        self._tree.delete(*self._tree.get_children())
        for ex in expenses:
            icon = _CATEGORY_ICONS.get(ex.category, "📋")
            self._tree.insert("", "end", iid=ex.id, values=(
                ex.date[:10] if ex.date else "—",
                f"{icon} {ex.category}",
                ex.name,
                format_currency(ex.amount),
                ex.quantity,
                format_currency(ex.total),
                ex.supplier or "—",
                "✅" if ex.is_recurring else "—",
                ex.notes or "—",
            ))

        # Populate month filter from data
        months = sorted(set(
            ex.date[:7] for ex in self._fin.get_all_expenses()
            if ex.date and len(ex.date) >= 7
        ), reverse=True)
        self._month_cb["values"] = ["All"] + months

        self._selected_id = None
        self._btn_edit.config(state="disabled")
        self._btn_del.config(state="disabled")

    def _update_summary(self) -> None:
        stats = self._fin.get_expense_stats()
        self._sum_total.config(
            text=format_currency(stats.get("total", 0)))
        self._sum_month.config(
            text=format_currency(stats.get("this_month", 0)))
        self._sum_recurring.config(
            text=format_currency(stats.get("monthly_recurring", 0)))
        self._sum_count.config(text=str(stats.get("count", 0)))

    def _sort(self, col: str) -> None:
        items = [(self._tree.set(iid, col), iid)
                 for iid in self._tree.get_children()]
        try:
            items.sort(key=lambda t: float(
                t[0].replace("EGP", "").replace(",", "").strip()))
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
            self._btn_del.config(state="disabled")
            return
        self._selected_id = sel[0]
        can = self._user.has_permission(Permission.VIEW_FINANCIAL)
        self._btn_edit.config(state="normal" if can else "disabled")
        self._btn_del.config(state="normal" if can else "disabled")

    def _reset_filter(self) -> None:
        self._cat_filter.set("All")
        self._month_filter.set("All")
        self.refresh()

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

    def _add_expense(self) -> None:
        dlg = _ExpenseDialog(self, title="Add Expense")
        if dlg.result:
            self._fin.add_expense(**dlg.result)
            self.refresh()
            self._notify()

    def _edit_expense(self) -> None:
        if not self._selected_id:
            return
        expense = next(
            (e for e in self._fin.get_all_expenses() if e.id == self._selected_id),
            None,
        )
        if not expense:
            return
        dlg = _ExpenseDialog(self, title="Edit Expense", expense=expense)
        if dlg.result:
            self._fin.update_expense(self._selected_id, **dlg.result)
            self.refresh()
            self._notify()

    def _delete_expense(self) -> None:
        if not self._selected_id:
            return
        if not messagebox.askyesno("Confirm Delete",
                                   "Delete this expense record?"):
            return
        ok = self._fin.delete_expense(self._selected_id)
        if ok:
            self.refresh()
        else:
            messagebox.showerror("Error", "Could not delete expense.")


# ---------------------------------------------------------------------------
# Expense dialog
# ---------------------------------------------------------------------------

class _ExpenseDialog:
    def __init__(self, parent, title="Expense", expense=None) -> None:
        self.result = None
        self._win = tk.Toplevel(parent)
        self._win.title(title)
        self._win.resizable(False, False)
        self._win.grab_set()
        self._build(expense)
        self._win.wait_window()

    def _build(self, ex) -> None:
        f = ttk.Frame(self._win, padding=16)
        f.pack(fill=tk.BOTH, expand=True)
        f.columnconfigure(1, weight=1)
        pad = dict(padx=8, pady=4)

        # Category
        ttk.Label(f, text="Category *").grid(row=0, column=0, sticky="w", **pad)
        self._cat_var = tk.StringVar(value=ex.category if ex else EXPENSE_CATEGORIES[0])
        ttk.Combobox(f, textvariable=self._cat_var,
                     values=EXPENSE_CATEGORIES, state="readonly",
                     width=22).grid(row=0, column=1, sticky="ew", **pad)

        # Name
        ttk.Label(f, text="Name *").grid(row=1, column=0, sticky="w", **pad)
        self._name_var = tk.StringVar(value=ex.name if ex else "")
        ttk.Entry(f, textvariable=self._name_var, width=28).grid(
            row=1, column=1, sticky="ew", **pad)

        # Amount
        ttk.Label(f, text="Amount (EGP) *").grid(
            row=2, column=0, sticky="w", **pad)
        self._amount_var = tk.StringVar(
            value=str(ex.amount) if ex else "")
        self._amount_var.trace_add("write", self._recalc)
        ttk.Entry(f, textvariable=self._amount_var).grid(
            row=2, column=1, sticky="ew", **pad)

        # Quantity
        ttk.Label(f, text="Quantity").grid(row=3, column=0, sticky="w", **pad)
        self._qty_var = tk.StringVar(
            value=str(ex.quantity) if ex else "1")
        self._qty_var.trace_add("write", self._recalc)
        ttk.Entry(f, textvariable=self._qty_var, width=8).grid(
            row=3, column=1, sticky="w", **pad)

        # Total (auto)
        ttk.Label(f, text="Total").grid(row=4, column=0, sticky="w", **pad)
        self._total_lbl = ttk.Label(f, text="0.00 EGP",
                                     style="Section.TLabel")
        self._total_lbl.grid(row=4, column=1, sticky="w", **pad)

        # Supplier
        ttk.Label(f, text="Supplier").grid(row=5, column=0, sticky="w", **pad)
        self._supplier_var = tk.StringVar(value=ex.supplier if ex else "")
        ttk.Entry(f, textvariable=self._supplier_var).grid(
            row=5, column=1, sticky="ew", **pad)

        # Recurring
        self._recurring_var = tk.BooleanVar(
            value=ex.is_recurring if ex else False)
        self._recurring_var.trace_add("write", self._toggle_period)
        ttk.Checkbutton(f, text="Recurring expense",
                        variable=self._recurring_var).grid(
            row=6, column=0, columnspan=2, sticky="w", **pad)

        ttk.Label(f, text="Period").grid(row=7, column=0, sticky="w", **pad)
        self._period_var = tk.StringVar(
            value=ex.recurring_period if ex else "monthly")
        self._period_cb = ttk.Combobox(f, textvariable=self._period_var,
                                        values=["monthly", "yearly"],
                                        state="readonly", width=12)
        self._period_cb.grid(row=7, column=1, sticky="w", **pad)

        # Notes
        ttk.Label(f, text="Notes").grid(row=8, column=0, sticky="w", **pad)
        self._notes_var = tk.StringVar(value=ex.notes if ex else "")
        ttk.Entry(f, textvariable=self._notes_var, width=28).grid(
            row=8, column=1, sticky="ew", **pad)

        # Date
        from datetime import date as _date
        ttk.Label(f, text="Date").grid(row=9, column=0, sticky="w", **pad)
        self._date_var = tk.StringVar(
            value=(ex.date[:10] if ex else _date.today().isoformat()))
        ttk.Entry(f, textvariable=self._date_var, width=14).grid(
            row=9, column=1, sticky="w", **pad)
        ttk.Label(f, text="YYYY-MM-DD",
                  style="Muted.TLabel").grid(row=9, column=1, sticky="e", **pad)

        btn_row = ttk.Frame(f)
        btn_row.grid(row=10, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_row, text="💾 Save",
                   command=self._save).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="Cancel",
                   command=self._win.destroy).pack(side=tk.LEFT, padx=4)

        self._toggle_period()
        self._recalc()

    def _recalc(self, *_) -> None:
        amount = safe_float(self._amount_var.get())
        qty    = max(1, int(safe_float(self._qty_var.get()) or 1))
        total  = amount * qty
        self._total_lbl.config(text=format_currency(total))

    def _toggle_period(self, *_) -> None:
        state = "readonly" if self._recurring_var.get() else "disabled"
        self._period_cb.config(state=state)

    def _save(self) -> None:
        name   = self._name_var.get().strip()
        amount = safe_float(self._amount_var.get())
        if not name:
            messagebox.showwarning("Required", "Name is required.",
                                   parent=self._win)
            return
        if amount <= 0:
            messagebox.showwarning("Required", "Amount must be > 0.",
                                   parent=self._win)
            return
        qty = max(1, int(safe_float(self._qty_var.get()) or 1))
        self.result = {
            "category":        self._cat_var.get(),
            "name":            name,
            "amount":          amount,
            "quantity":        qty,
            "total":           amount * qty,
            "supplier":        self._supplier_var.get().strip(),
            "is_recurring":    self._recurring_var.get(),
            "recurring_period":self._period_var.get(),
            "notes":           self._notes_var.get().strip(),
            "date":            self._date_var.get().strip(),
        }
        self._win.destroy()