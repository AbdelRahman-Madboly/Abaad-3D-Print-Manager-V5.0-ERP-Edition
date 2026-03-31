"""
src/ui/tabs/customers_tab.py
============================
Customer management tab for Abaad 3D Print Manager v5.0.

Features:
- Searchable customer list (name / phone)
- Customer detail panel: info, order history, lifetime spend
- Add / Edit / Delete customer (permission-gated)
- Quick find-or-create used by OrdersTab via the service
"""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from src.auth.permissions import Permission
from src.services.customer_service import CustomerService
from src.ui.theme import Colors, Fonts
from src.utils.helpers import format_currency


class CustomersTab(ttk.Frame):
    """Customer management tab.

    Args:
        parent:           ttk.Notebook parent.
        customer_service: CustomerService instance.
        user:             Currently logged-in User object.
        on_status_change: Optional callback after data mutation.
    """

    def __init__(self, parent, customer_service: CustomerService, user,
                 on_status_change=None) -> None:
        super().__init__(parent, padding=10)
        self._svc    = customer_service
        self._user   = user
        self._notify = on_status_change or (lambda: None)
        self._selected_id: Optional[str] = None

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload list from service."""
        self._populate_list(self._svc.get_all_customers())

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_left()
        self._build_right()

    def _build_left(self) -> None:
        left = ttk.Frame(self, width=300)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_propagate(False)

        # Search bar
        search_frame = ttk.Frame(left)
        search_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(search_frame, text="🔍").pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search)
        ttk.Entry(search_frame, textvariable=self._search_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        # Treeview
        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("name", "phone", "orders", "spent")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  selectmode="browse")
        self._tree.heading("name",   text="Name")
        self._tree.heading("phone",  text="Phone")
        self._tree.heading("orders", text="Orders")
        self._tree.heading("spent",  text="Spent")
        self._tree.column("name",   width=110)
        self._tree.column("phone",  width=90)
        self._tree.column("orders", width=50, anchor="center")
        self._tree.column("spent",  width=70, anchor="e")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                             command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>", lambda _: self._edit_customer())

        # Buttons
        btn_frame = ttk.Frame(left)
        btn_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(btn_frame, text="➕ Add",    command=self._add_customer).pack(
            side=tk.LEFT, padx=2)
        self._btn_edit = ttk.Button(btn_frame, text="✏️ Edit",
                                    command=self._edit_customer, state="disabled")
        self._btn_edit.pack(side=tk.LEFT, padx=2)
        self._btn_del = ttk.Button(btn_frame, text="🗑️ Delete",
                                   command=self._delete_customer, state="disabled")
        self._btn_del.pack(side=tk.LEFT, padx=2)

        # Count label
        self._count_lbl = ttk.Label(left, text="0 customers",
                                    style="Muted.TLabel")
        self._count_lbl.pack(pady=(4, 0))

    def _build_right(self) -> None:
        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        # Detail card
        detail = ttk.LabelFrame(right, text="👤 Customer Details", padding=12)
        detail.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        detail.columnconfigure(1, weight=1)

        fields = [
            ("Name",     "_lbl_name"),
            ("Phone",    "_lbl_phone"),
            ("Email",    "_lbl_email"),
            ("Address",  "_lbl_address"),
            ("Discount", "_lbl_discount"),
            ("Notes",    "_lbl_notes"),
        ]
        for r, (label, attr) in enumerate(fields):
            ttk.Label(detail, text=f"{label}:",
                      style="Section.TLabel").grid(
                row=r, column=0, sticky="w", padx=(0, 12), pady=2)
            lbl = ttk.Label(detail, text="—")
            lbl.grid(row=r, column=1, sticky="w", pady=2)
            setattr(self, attr, lbl)

        # Stats row
        stats_row = ttk.Frame(detail)
        stats_row.grid(row=len(fields), column=0, columnspan=2,
                       sticky="ew", pady=(10, 0))
        for i, (title, attr) in enumerate([
            ("Total Orders", "_stat_orders"),
            ("Total Spent",  "_stat_spent"),
            ("Joined",       "_stat_joined"),
        ]):
            card = tk.Frame(stats_row, bg=Colors.PRIMARY, padx=14, pady=8)
            card.grid(row=0, column=i, padx=4, sticky="ew")
            stats_row.columnconfigure(i, weight=1)
            tk.Label(card, text=title, bg=Colors.PRIMARY, fg="white",
                     font=Fonts.SMALL).pack()
            val_lbl = tk.Label(card, text="—", bg=Colors.PRIMARY, fg="white",
                               font=Fonts.BIG_NUMBER)
            val_lbl.pack()
            setattr(self, attr, val_lbl)

        # Order history
        hist_frame = ttk.LabelFrame(right, text="📋 Order History", padding=8)
        hist_frame.grid(row=1, column=0, sticky="nsew")
        hist_frame.rowconfigure(0, weight=1)
        hist_frame.columnconfigure(0, weight=1)

        h_cols = ("order_no", "date", "status", "total")
        self._hist_tree = ttk.Treeview(hist_frame, columns=h_cols,
                                       show="headings", height=8)
        self._hist_tree.heading("order_no", text="#")
        self._hist_tree.heading("date",     text="Date")
        self._hist_tree.heading("status",   text="Status")
        self._hist_tree.heading("total",    text="Total")
        self._hist_tree.column("order_no", width=60,  anchor="center")
        self._hist_tree.column("date",     width=100)
        self._hist_tree.column("status",   width=100)
        self._hist_tree.column("total",    width=90,  anchor="e")

        h_vsb = ttk.Scrollbar(hist_frame, orient="vertical",
                               command=self._hist_tree.yview)
        self._hist_tree.configure(yscrollcommand=h_vsb.set)
        self._hist_tree.grid(row=0, column=0, sticky="nsew")
        h_vsb.grid(row=0, column=1, sticky="ns")

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _populate_list(self, customers: list) -> None:
        self._tree.delete(*self._tree.get_children())
        for c in customers:
            self._tree.insert("", "end", iid=c.id, values=(
                c.name,
                c.phone or "—",
                c.total_orders,
                format_currency(c.total_spent),
            ))
        self._count_lbl.config(text=f"{len(customers)} customer(s)")
        self._clear_detail()

    def _clear_detail(self) -> None:
        self._selected_id = None
        for attr in ("_lbl_name", "_lbl_phone", "_lbl_email", "_lbl_address",
                     "_lbl_discount", "_lbl_notes"):
            getattr(self, attr).config(text="—")
        for attr in ("_stat_orders", "_stat_spent", "_stat_joined"):
            getattr(self, attr).config(text="—")
        self._hist_tree.delete(*self._hist_tree.get_children())
        self._btn_edit.config(state="disabled")
        self._btn_del.config(state="disabled")

    def _show_detail(self, customer) -> None:
        self._selected_id = customer.id
        self._lbl_name.config(text=customer.name or "—")
        self._lbl_phone.config(text=customer.phone or "—")
        self._lbl_email.config(text=customer.email or "—")
        self._lbl_address.config(text=customer.address or "—")
        disc = f"{customer.discount_percent:.1f}%" if customer.discount_percent else "—"
        self._lbl_discount.config(text=disc)
        self._lbl_notes.config(text=customer.notes or "—")

        self._stat_orders.config(text=str(customer.total_orders))
        self._stat_spent.config(text=format_currency(customer.total_spent))
        joined = customer.created_date[:10] if customer.created_date else "—"
        self._stat_joined.config(text=joined)

        # Order history
        self._hist_tree.delete(*self._hist_tree.get_children())
        orders = self._svc.get_customer_orders(customer.id)
        for o in orders:
            self._hist_tree.insert("", "end", values=(
                o.order_number or o.id[:6],
                o.created_date[:10] if o.created_date else "—",
                o.status,
                format_currency(o.final_total),
            ))

        can_manage = self._user.has_permission(Permission.MANAGE_CUSTOMERS)
        self._btn_edit.config(state="normal" if can_manage else "disabled")
        self._btn_del.config(state="normal" if can_manage else "disabled")

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _on_search(self, *_) -> None:
        query = self._search_var.get().strip()
        results = self._svc.search(query) if query else self._svc.get_all_customers()
        self._populate_list(results)

    def _on_select(self, _event=None) -> None:
        sel = self._tree.selection()
        if not sel:
            self._clear_detail()
            return
        customer = self._svc.get_customer(sel[0])
        if customer:
            self._show_detail(customer)

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

    def _add_customer(self) -> None:
        if not self._user.has_permission(Permission.MANAGE_CUSTOMERS):
            messagebox.showwarning("Permission Denied",
                                   "You don't have permission to add customers.")
            return
        dlg = _CustomerDialog(self, title="Add Customer")
        if dlg.result:
            self._svc.create_customer(**dlg.result)
            self.refresh()
            self._notify()

    def _edit_customer(self) -> None:
        if not self._selected_id:
            return
        customer = self._svc.get_customer(self._selected_id)
        if not customer:
            return
        dlg = _CustomerDialog(self, title="Edit Customer", customer=customer)
        if dlg.result:
            self._svc.update_customer(self._selected_id, **dlg.result)
            self.refresh()
            # Re-select
            if self._selected_id in self._tree.get_children():
                self._tree.selection_set(self._selected_id)
            self._on_select()

    def _delete_customer(self) -> None:
        if not self._selected_id:
            return
        customer = self._svc.get_customer(self._selected_id)
        if not customer:
            return
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete customer '{customer.name}'?\n\n"
            "This cannot be undone. Orders linked to this customer will remain.",
        ):
            return
        ok, msg = self._svc.delete_customer(self._selected_id)
        if ok:
            self.refresh()
            self._notify()
        else:
            messagebox.showerror("Delete Failed", msg)


# ---------------------------------------------------------------------------
# Inline Add/Edit dialog
# ---------------------------------------------------------------------------

class _CustomerDialog:
    """Simple modal dialog for adding or editing a customer."""

    def __init__(self, parent, title: str = "Customer", customer=None) -> None:
        self.result = None
        self._win = tk.Toplevel(parent)
        self._win.title(title)
        self._win.resizable(False, False)
        self._win.grab_set()

        self._customer = customer
        self._build(customer)
        parent.winfo_toplevel().update_idletasks()
        x = parent.winfo_rootx() + 80
        y = parent.winfo_rooty() + 60
        self._win.geometry(f"+{x}+{y}")
        self._win.wait_window()

    def _build(self, customer) -> None:
        pad = dict(padx=10, pady=4)
        frame = ttk.Frame(self._win, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)

        fields = [
            ("Name *",    "name",             str),
            ("Phone",     "phone",            str),
            ("Email",     "email",            str),
            ("Address",   "address",          str),
            ("Discount%", "discount_percent", float),
            ("Notes",     "notes",            str),
        ]
        self._vars: dict = {}
        for r, (label, key, _) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=r, column=0, sticky="w", **pad)
            var = tk.StringVar(value=str(getattr(customer, key, ""))
                               if customer else "")
            ttk.Entry(frame, textvariable=var, width=32).grid(
                row=r, column=1, sticky="ew", **pad)
            self._vars[key] = (var, _)

        # Buttons
        btn_row = ttk.Frame(frame)
        btn_row.grid(row=len(fields), column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_row, text="💾 Save",
                   command=self._save).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="Cancel",
                   command=self._win.destroy).pack(side=tk.LEFT, padx=4)

    def _save(self) -> None:
        data = {}
        for key, (var, cast) in self._vars.items():
            raw = var.get().strip()
            if raw:
                try:
                    data[key] = cast(raw)
                except ValueError:
                    data[key] = raw
            else:
                data[key] = "" if cast is str else 0.0

        if not data.get("name"):
            messagebox.showwarning("Required", "Customer name is required.",
                                   parent=self._win)
            return
        self.result = data
        self._win.destroy()