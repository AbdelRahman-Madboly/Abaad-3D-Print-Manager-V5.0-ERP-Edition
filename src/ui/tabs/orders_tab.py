"""
src/ui/tabs/orders_tab.py
==========================
Orders management tab for Abaad 3D Print Manager v5.0.

Class OrdersTab(ttk.Frame)
  - Left panel  : searchable / filterable order list
  - Right panel : order detail + items + payment form
  - All business logic delegated to OrderService
  - All styling from theme.Colors / theme.Fonts
"""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from src.core.config import ORDER_STATUSES, PAYMENT_METHODS
from src.core.models import Order, PrintItem
from src.services.order_service import OrderService
from src.ui.theme import Colors, Fonts
from src.utils.helpers import format_currency, safe_float, safe_int
from src.ui.context_menu import bind_treeview_menu



class OrdersTab(ttk.Frame):
    """Orders management tab.

    Args:
        parent:        The ttk.Notebook that owns this tab.
        order_service: An ``OrderService`` instance.
        user:          The currently logged-in user object.
        on_status_change: Optional callback called after any save/delete
                          so the status bar can refresh.
    """

    def __init__(
        self,
        parent,
        order_service: OrderService,
        user,
        on_status_change=None,
    ) -> None:
        super().__init__(parent, padding=10)
        self._svc   = order_service
        self._user  = user
        self._notify = on_status_change or (lambda: None)

        self._current_order: Optional[Order] = None
        self._all_orders: list[Order] = []

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload the order list from the database."""
        self._all_orders = self._svc.get_all_orders()
        self._populate_list(self._all_orders)

    def new_order(self) -> None:
        """Clear the form to start a fresh order."""
        self._current_order = None
        self._clear_form()
        self.cust_name.focus_set()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # ── Left panel ─────────────────────────────────────────────────
        left = ttk.Frame(self)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))

        # Header row
        hdr = ttk.Frame(left)
        hdr.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(hdr, text="📦 Orders", style="Title.TLabel").pack(side=tk.LEFT)
        tk.Button(
            hdr, text="➕ New Order", font=Fonts.BUTTON_BOLD,
            bg=Colors.SUCCESS, fg="white", relief=tk.FLAT,
            padx=12, pady=4, cursor="hand2",
            command=self.new_order,
        ).pack(side=tk.RIGHT)

        # Search + filter row
        sf = ttk.Frame(left)
        sf.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(sf, text="🔍").pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter())
        ttk.Entry(sf, textvariable=self._search_var, width=22,
                  font=Fonts.DEFAULT).pack(side=tk.LEFT, padx=4)

        ttk.Label(sf, text="Status:").pack(side=tk.LEFT, padx=(10, 4))
        self._status_var = tk.StringVar(value="All")
        cb = ttk.Combobox(
            sf, textvariable=self._status_var,
            values=["All"] + ORDER_STATUSES,
            state="readonly", width=13,
        )
        cb.pack(side=tk.LEFT)
        cb.bind("<<ComboboxSelected>>", lambda _: self._filter())

        # Order list treeview
        lf = ttk.Frame(left)
        lf.pack(fill=tk.BOTH, expand=True)

        cols = ("Order#", "Customer", "Items", "Total", "Status", "Date", "R&D")
        self._tree = ttk.Treeview(lf, columns=cols, show="headings", height=22)
        widths = (60, 140, 45, 80, 95, 90, 40)
        for col, w in zip(cols, widths):
            self._tree.heading(col, text=col)
            anchor = tk.W if col == "Customer" else tk.CENTER
            self._tree.column(col, width=w, anchor=anchor)

        vsb = ttk.Scrollbar(lf, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        bind_treeview_menu(self._tree, actions=[
            ("✏️ Edit",            self._edit_current),
            ("📋 Change Status",   self._change_status),
            None,
            ("📄 Generate Quote",    self._gen_quote),
            ("🧾 Generate Receipt",  self._gen_receipt),
            None,
            ("🗑 Delete",           self._delete_order),
        ])

        # ── Right panel ────────────────────────────────────────────────
        right = ttk.Frame(self)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Order title label
        self._title_lbl = ttk.Label(right, text="📝 New Order", style="Title.TLabel")
        self._title_lbl.pack(anchor=tk.W, pady=(0, 6))

        # Customer section
        cust_frm = ttk.LabelFrame(right, text="Customer", padding=8)
        cust_frm.pack(fill=tk.X, pady=4)

        r1 = ttk.Frame(cust_frm)
        r1.pack(fill=tk.X)
        ttk.Label(r1, text="Name:").pack(side=tk.LEFT)
        self.cust_name = ttk.Entry(r1, width=20, font=Fonts.DEFAULT)
        self.cust_name.pack(side=tk.LEFT, padx=4)
        ttk.Label(r1, text="Phone:").pack(side=tk.LEFT, padx=(8, 0))
        self.cust_phone = ttk.Entry(r1, width=14, font=Fonts.DEFAULT)
        self.cust_phone.pack(side=tk.LEFT, padx=4)
        ttk.Button(r1, text="🔍", width=3,
                   command=self._find_customer).pack(side=tk.LEFT, padx=2)

        r2 = ttk.Frame(cust_frm)
        r2.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(r2, text="Status:").pack(side=tk.LEFT)
        self._status_entry = ttk.Combobox(
            r2, values=ORDER_STATUSES, state="readonly", width=13)
        self._status_entry.set("Draft")
        self._status_entry.pack(side=tk.LEFT, padx=4)
        self._rd_var = tk.BooleanVar()
        ttk.Checkbutton(
            r2, text="🔬 R&D Project", variable=self._rd_var,
            command=self._recalc,
        ).pack(side=tk.LEFT, padx=12)

        # Items section
        items_frm = ttk.LabelFrame(right, text="Print Items", padding=6)
        items_frm.pack(fill=tk.BOTH, expand=True, pady=4)

        itb = ttk.Frame(items_frm)
        itb.pack(fill=tk.X, pady=(0, 4))
        for lbl, cmd in [
            ("+ Add",      self._add_item),
            ("Edit",       self._edit_item),
            ("Remove",     self._remove_item),
            ("Set Weight", self._set_weight),
        ]:
            ttk.Button(itb, text=lbl, command=cmd).pack(side=tk.LEFT, padx=2)

        icols = ("Name", "Color", "Weight", "Time", "Settings", "Qty", "Rate", "Total")
        self._items_tree = ttk.Treeview(
            items_frm, columns=icols, show="headings", height=7)
        for col, w in zip(icols, (100, 60, 55, 50, 90, 35, 42, 65)):
            self._items_tree.heading(col, text=col)
            self._items_tree.column(col, width=w, anchor=tk.CENTER)
        self._items_tree.pack(fill=tk.BOTH, expand=True)

        # Payment & Totals section
        pay_frm = ttk.LabelFrame(right, text="Payment & Totals", padding=8)
        pay_frm.pack(fill=tk.X, pady=4)

        # Row: Base / Actual / Rate-disc
        pr1 = ttk.Frame(pay_frm)
        pr1.pack(fill=tk.X)
        ttk.Label(pr1, text="Base:").pack(side=tk.LEFT)
        self._base_lbl = ttk.Label(pr1, text="0.00", font=Fonts.DEFAULT)
        self._base_lbl.pack(side=tk.LEFT, padx=4)
        ttk.Label(pr1, text="Actual:").pack(side=tk.LEFT, padx=(10, 0))
        self._actual_lbl = ttk.Label(
            pr1, text="0.00", font=Fonts.BUTTON_BOLD,
            foreground=Colors.PRIMARY)
        self._actual_lbl.pack(side=tk.LEFT, padx=4)
        ttk.Label(pr1, text="Disc:").pack(side=tk.LEFT, padx=(10, 0))
        self._rdisc_lbl = ttk.Label(
            pr1, text="0%", foreground=Colors.SUCCESS)
        self._rdisc_lbl.pack(side=tk.LEFT, padx=4)

        # Row: Order discount + tolerance
        pr2 = ttk.Frame(pay_frm)
        pr2.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(pr2, text="Order disc %:").pack(side=tk.LEFT)
        self._odisc_var = tk.StringVar(value="0")
        odisc_e = ttk.Entry(pr2, textvariable=self._odisc_var, width=5)
        odisc_e.pack(side=tk.LEFT, padx=4)
        odisc_e.bind("<KeyRelease>", lambda _: self._recalc())
        self._odisc_amt_lbl = ttk.Label(
            pr2, text="(-0.00)", foreground=Colors.SUCCESS)
        self._odisc_amt_lbl.pack(side=tk.LEFT, padx=4)
        self._tol_lbl = ttk.Label(pr2, text="", foreground=Colors.SUCCESS)
        self._tol_lbl.pack(side=tk.LEFT, padx=8)

        # Row: Payment method + fee + shipping
        pr3 = ttk.Frame(pay_frm)
        pr3.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(pr3, text="Payment:").pack(side=tk.LEFT)
        self._pay_var = tk.StringVar(value="Cash")
        pm_cb = ttk.Combobox(
            pr3, textvariable=self._pay_var,
            values=PAYMENT_METHODS, state="readonly", width=13)
        pm_cb.pack(side=tk.LEFT, padx=4)
        pm_cb.bind("<<ComboboxSelected>>", lambda _: self._recalc())
        ttk.Label(pr3, text="Fee:").pack(side=tk.LEFT, padx=(6, 0))
        self._fee_lbl = ttk.Label(pr3, text="0.00")
        self._fee_lbl.pack(side=tk.LEFT, padx=4)
        ttk.Label(pr3, text="Ship:").pack(side=tk.LEFT, padx=(6, 0))
        self._ship_var = tk.StringVar(value="0")
        ship_e = ttk.Entry(pr3, textvariable=self._ship_var, width=7)
        ship_e.pack(side=tk.LEFT, padx=4)
        ship_e.bind("<KeyRelease>", lambda _: self._recalc())

        # Row: Amount received + rounding loss
        pr4 = ttk.Frame(pay_frm)
        pr4.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(pr4, text="Received:").pack(side=tk.LEFT)
        self._recv_var = tk.StringVar(value="0")
        recv_e = ttk.Entry(pr4, textvariable=self._recv_var, width=9)
        recv_e.pack(side=tk.LEFT, padx=4)
        recv_e.bind("<KeyRelease>", lambda _: self._recalc())
        self._round_lbl = ttk.Label(
            pr4, text="Rounding: 0.00", foreground=Colors.WARNING)
        self._round_lbl.pack(side=tk.LEFT, padx=8)

        # Row: TOTAL + Profit
        pr5 = ttk.Frame(pay_frm)
        pr5.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(pr5, text="TOTAL:", font=Fonts.HEADER).pack(side=tk.LEFT)
        self._total_lbl = ttk.Label(
            pr5, text="0.00 EGP", font=Fonts.BIG_NUMBER,
            foreground=Colors.PRIMARY)
        self._total_lbl.pack(side=tk.LEFT, padx=8)
        ttk.Label(pr5, text="Profit:").pack(side=tk.LEFT, padx=(12, 0))
        self._profit_lbl = ttk.Label(
            pr5, text="0.00", foreground=Colors.SUCCESS)
        self._profit_lbl.pack(side=tk.LEFT, padx=4)
        self._rd_cost_lbl = ttk.Label(
            pr5, text="", foreground=Colors.PURPLE)
        self._rd_cost_lbl.pack(side=tk.LEFT, padx=8)

        # Action buttons
        acts = ttk.Frame(right)
        acts.pack(fill=tk.X, pady=8)

        tk.Button(
            acts, text="💾 Save Order", font=Fonts.BUTTON_BOLD,
            bg=Colors.PRIMARY, fg="white", relief=tk.FLAT,
            padx=14, pady=5, cursor="hand2",
            command=self._save_order,
        ).pack(side=tk.LEFT, padx=(0, 8))

        for lbl, color, cmd in [
            ("📄 Quote",   Colors.INFO,           self._gen_quote),
            ("🧾 Receipt", Colors.INFO,            self._gen_receipt),
            ("📋 Text",    Colors.TEXT_SECONDARY,  self._gen_text),
        ]:
            tk.Button(
                acts, text=lbl, font=Fonts.SMALL,
                bg=color, fg="white", relief=tk.FLAT,
                padx=8, pady=4, cursor="hand2", command=cmd,
            ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            acts, text="✨ New", font=Fonts.SMALL,
            bg=Colors.SUCCESS, fg="white", relief=tk.FLAT,
            padx=8, pady=4, cursor="hand2",
            command=self.new_order,
        ).pack(side=tk.RIGHT, padx=2)

        # Only admins / permitted users see Delete
        if self._can_delete():
            tk.Button(
                acts, text="🗑️ Delete", font=Fonts.SMALL,
                bg=Colors.DANGER, fg="white", relief=tk.FLAT,
                padx=8, pady=4, cursor="hand2",
                command=self._delete_order,
            ).pack(side=tk.RIGHT, padx=2)

        # Notes
        nf = ttk.LabelFrame(right, text="📝 Notes", padding=4)
        nf.pack(fill=tk.X, pady=(4, 0))
        self._notes = tk.Text(
            nf, height=2, font=Fonts.DEFAULT,
            relief=tk.FLAT, bg=Colors.CARD)
        self._notes.pack(fill=tk.X)

    # ------------------------------------------------------------------
    # List helpers
    # ------------------------------------------------------------------

    def _populate_list(self, orders: list[Order]) -> None:
        self._tree.delete(*self._tree.get_children())
        status_colors = {
            "Draft":       "",
            "Quote":       "#eff6ff",
            "Confirmed":   "#ecfdf5",
            "In Progress": "#fef9c3",
            "Ready":       "#d1fae5",
            "Delivered":   "#f0fdf4",
            "Cancelled":   "#f1f5f9",
        }
        for o in orders:
            item_count = self._svc.get_order(o.id).item_count if False else "—"
            # Fast path: use stored total_weight approximation
            values = (
                f"#{o.order_number}",
                o.customer_name,
                "—",                      # items loaded on-demand
                f"{o.total:.2f}",
                o.status,
                o.created_date[:10],
                "✓" if o.is_rd_project else "",
            )
            tag = o.status.replace(" ", "_")
            self._tree.insert("", tk.END, iid=o.id, values=values, tags=(tag,))
            bg = status_colors.get(o.status, "")
            if bg:
                self._tree.tag_configure(tag, background=bg)

    def _filter(self) -> None:
        q      = self._search_var.get().strip()
        status = self._status_var.get()
        filtered = self._svc.search_orders(q, status)
        self._populate_list(filtered)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _on_select(self, _event) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        order_id = sel[0]
        order = self._svc.get_order(order_id)
        if order:
            self._current_order = order
            self._load_form(order)

    def _edit_current(self) -> None:
        """Load the selected order into the form for editing (context-menu action)."""
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select an order first.", parent=self)
            return
        order = self._svc.get_order(sel[0])
        if order:
            self._current_order = order
            self._load_form(order)

    def _change_status(self) -> None:
        """Prompt to change the status of the selected order."""
        if not self._current_order:
            messagebox.showinfo("Info", "Select an order first.", parent=self)
            return
        dlg = tk.Toplevel(self)
        dlg.title("Change Status")
        dlg.resizable(False, False)
        dlg.grab_set()
        ttk.Label(dlg, text=f"Order #{self._current_order.order_number}",
                  font=Fonts.BUTTON_BOLD).pack(padx=20, pady=(14, 4))
        ttk.Label(dlg, text="New status:").pack()
        var = tk.StringVar(value=self._current_order.status)
        cb = ttk.Combobox(dlg, textvariable=var,
                          values=ORDER_STATUSES, state="readonly", width=16)
        cb.pack(padx=20, pady=6)

        def _apply():
            new_status = var.get()
            if new_status == self._current_order.status:
                dlg.destroy()
                return
            ok = self._svc.update_status(self._current_order.id, new_status)
            if ok:
                self._current_order.status = new_status
                self.refresh()
                self._notify()
            dlg.destroy()

        bf = ttk.Frame(dlg)
        bf.pack(pady=(0, 12))
        ttk.Button(bf, text="Apply", command=_apply).pack(side=tk.LEFT, padx=6)
        ttk.Button(bf, text="Cancel", command=dlg.destroy).pack(side=tk.LEFT, padx=6)

    # ------------------------------------------------------------------
    # Form load / clear
    # ------------------------------------------------------------------

    def _load_form(self, order: Order) -> None:
        self._title_lbl.config(
            text=f"📦 Order #{order.order_number} — {order.customer_name}")

        self.cust_name.delete(0, tk.END)
        self.cust_name.insert(0, order.customer_name)
        self.cust_phone.delete(0, tk.END)
        self.cust_phone.insert(0, order.customer_phone)

        self._status_entry.set(order.status)
        self._rd_var.set(order.is_rd_project)

        self._odisc_var.set(str(order.order_discount_percent))
        self._pay_var.set(order.payment_method)
        self._ship_var.set(str(order.shipping_cost))
        self._recv_var.set(str(order.amount_received))

        self._notes.delete("1.0", tk.END)
        self._notes.insert("1.0", order.notes)

        self._populate_items(order.items)
        self._update_totals_display(order)

    def _clear_form(self) -> None:
        self._title_lbl.config(text="📝 New Order")
        for w in (self.cust_name, self.cust_phone):
            w.delete(0, tk.END)
        self._status_entry.set("Draft")
        self._rd_var.set(False)
        self._odisc_var.set("0")
        self._pay_var.set("Cash")
        self._ship_var.set("0")
        self._recv_var.set("0")
        self._notes.delete("1.0", tk.END)
        self._items_tree.delete(*self._items_tree.get_children())
        for lbl in (self._base_lbl, self._actual_lbl, self._fee_lbl,
                    self._profit_lbl):
            lbl.config(text="0.00")
        self._total_lbl.config(text="0.00 EGP")
        self._rdisc_lbl.config(text="0%")
        self._odisc_amt_lbl.config(text="(-0.00)")
        self._tol_lbl.config(text="")
        self._round_lbl.config(text="Rounding: 0.00")
        self._rd_cost_lbl.config(text="")

    def _populate_items(self, items: list[PrintItem]) -> None:
        self._items_tree.delete(*self._items_tree.get_children())
        for item in items:
            w = item.weight
            settings_str = (
                f"{item.settings.nozzle_size}mm / {item.settings.layer_height}mm"
            )
            values = (
                item.name,
                item.color,
                f"{w:.1f}g",
                f"{item.time_minutes}m",
                settings_str,
                item.quantity,
                f"{item.rate_per_gram:.1f}",
                f"{item.print_cost:.2f}",
            )
            self._items_tree.insert("", tk.END, iid=item.id, values=values)

    def _update_totals_display(self, order: Order) -> None:
        self._base_lbl.config(text=f"{order.subtotal:.2f}")
        self._actual_lbl.config(text=f"{order.actual_total:.2f}")
        self._rdisc_lbl.config(
            text=f"{order.discount_percent:.1f}%",
            foreground=Colors.SUCCESS if order.discount_percent > 0 else Colors.TEXT,
        )
        self._odisc_amt_lbl.config(
            text=f"(-{order.order_discount_amount:.2f})")
        if order.tolerance_discount_total > 0:
            self._tol_lbl.config(
                text=f"Tol: -{order.tolerance_discount_total:.2f}")
        else:
            self._tol_lbl.config(text="")
        self._fee_lbl.config(text=f"{order.payment_fee:.2f}")
        self._round_lbl.config(
            text=f"Rounding: {order.rounding_loss:.2f}",
            foreground=Colors.WARNING if order.rounding_loss > 0 else Colors.TEXT_SECONDARY,
        )
        self._total_lbl.config(text=f"{order.total:.2f} EGP")
        self._profit_lbl.config(
            text=f"{order.profit:.2f}",
            foreground=Colors.SUCCESS if order.profit >= 0 else Colors.DANGER,
        )
        if order.is_rd_project:
            self._rd_cost_lbl.config(
                text=f"R&D cost: {order.rd_cost:.2f}")
        else:
            self._rd_cost_lbl.config(text="")

    # ------------------------------------------------------------------
    # Live recalc (called when user edits fields)
    # ------------------------------------------------------------------

    def _recalc(self) -> None:
        """Push form values onto current order and recalculate."""
        if self._current_order is None:
            return
        o = self._current_order
        o.order_discount_percent = safe_float(self._odisc_var.get())
        o.payment_method         = self._pay_var.get()
        o.shipping_cost          = safe_float(self._ship_var.get())
        o.amount_received        = safe_float(self._recv_var.get())
        o.is_rd_project          = self._rd_var.get()
        self._svc.calculate_totals(o)
        self._update_totals_display(o)

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

    def _save_order(self) -> None:
        name  = self.cust_name.get().strip()
        phone = self.cust_phone.get().strip()
        if not name:
            messagebox.showwarning("Validation", "Customer name is required.", parent=self)
            return

        if self._current_order is None:
            order = self._svc.create_order(name, phone)
            self._current_order = order
        else:
            order = self._current_order
            order.customer_name  = name
            order.customer_phone = phone

        order.status                 = self._status_entry.get()
        order.is_rd_project          = self._rd_var.get()
        order.order_discount_percent = safe_float(self._odisc_var.get())
        order.payment_method         = self._pay_var.get()
        order.shipping_cost          = safe_float(self._ship_var.get())
        order.amount_received        = safe_float(self._recv_var.get())
        order.notes                  = self._notes.get("1.0", tk.END).strip()

        if self._svc.save_order(order):
            self.refresh()
            self._load_form(order)
            self._notify()
            messagebox.showinfo(
                "Saved",
                f"Order #{order.order_number} saved.",
                parent=self,
            )
        else:
            messagebox.showerror("Error", "Could not save order.", parent=self)

    def _delete_order(self) -> None:
        if not self._current_order:
            return
        o = self._current_order
        if not messagebox.askyesno(
            "Delete Order",
            f"Move Order #{o.order_number} to trash?",
            parent=self,
        ):
            return
        if self._svc.delete_order(o.id):
            self._current_order = None
            self._clear_form()
            self.refresh()
            self._notify()

    # ------------------------------------------------------------------
    # Item actions
    # ------------------------------------------------------------------

    def _add_item(self) -> None:
        if self._current_order is None:
            messagebox.showinfo("Info", "Save the order first.", parent=self)
            return
        _ItemDialog(self, self._current_order, item=None,
                    on_save=self._on_item_saved)

    def _edit_item(self) -> None:
        if not self._current_order:
            return
        sel = self._items_tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select an item first.", parent=self)
            return
        item_id = sel[0]
        item = self._current_order.get_item(item_id)
        if item:
            _ItemDialog(self, self._current_order, item=item,
                        on_save=self._on_item_saved)

    def _remove_item(self) -> None:
        if not self._current_order:
            return
        sel = self._items_tree.selection()
        if not sel:
            return
        item_id = sel[0]
        if messagebox.askyesno("Remove", "Remove this item?", parent=self):
            self._svc.remove_item(self._current_order, item_id)
            self._populate_items(self._current_order.items)
            self._update_totals_display(self._current_order)

    def _set_weight(self) -> None:
        """Set actual weight on the selected item."""
        if not self._current_order:
            return
        sel = self._items_tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select an item first.", parent=self)
            return
        item_id = sel[0]
        item = self._current_order.get_item(item_id)
        if not item:
            return
        _WeightDialog(self, item, on_save=lambda w: self._on_weight_set(item, w))

    def _on_weight_set(self, item: PrintItem, weight: float) -> None:
        item.actual_weight_grams = weight
        self._svc.calculate_totals(self._current_order)
        self._populate_items(self._current_order.items)
        self._update_totals_display(self._current_order)

    def _on_item_saved(self, item_data: dict) -> None:
        """Called by _ItemDialog when user clicks Save."""
        order = self._current_order
        if item_data.get("id") and order.get_item(item_data["id"]):
            self._svc.update_item(order, item_data["id"], item_data)
        else:
            self._svc.add_item(order, item_data)
        self._populate_items(order.items)
        self._update_totals_display(order)

    # ------------------------------------------------------------------
    # Customer lookup
    # ------------------------------------------------------------------

    def _find_customer(self) -> None:
        phone = self.cust_phone.get().strip()
        name  = self.cust_name.get().strip()
        if not phone and not name:
            return
        # Delegate to order service's db — just do a simple search here
        rows = self._svc._db.search_customers(phone or name)
        if rows:
            c = rows[0]
            self.cust_name.delete(0, tk.END)
            self.cust_name.insert(0, c.get("name", ""))
            self.cust_phone.delete(0, tk.END)
            self.cust_phone.insert(0, c.get("phone", ""))
            if self._current_order:
                self._current_order.customer_id    = c.get("id", "")
                self._current_order.customer_name  = c.get("name", "")
                self._current_order.customer_phone = c.get("phone", "")

    # ------------------------------------------------------------------
    # PDF / text generation (stubs — wired to PdfService in Phase 4)
    # ------------------------------------------------------------------

    def _gen_quote(self) -> None:
        if not self._current_order:
            messagebox.showinfo("Info", "Select an order first.", parent=self)
            return
        messagebox.showinfo(
            "Quote PDF",
            f"Quote PDF for Order #{self._current_order.order_number} — "
            "PDF service will be wired in Phase 4.",
            parent=self,
        )

    def _gen_receipt(self) -> None:
        if not self._current_order:
            messagebox.showinfo("Info", "Select an order first.", parent=self)
            return
        messagebox.showinfo(
            "Receipt PDF",
            f"Receipt PDF for Order #{self._current_order.order_number} — "
            "PDF service will be wired in Phase 4.",
            parent=self,
        )

    def _gen_text(self) -> None:
        if not self._current_order:
            return
        o = self._current_order
        lines = [
            f"Order #{o.order_number}  —  {o.customer_name}",
            f"Date: {o.created_date[:10]}",
            "-" * 40,
        ]
        for item in o.items:
            lines.append(
                f"  {item.name}  {item.weight:.1f}g × {item.quantity} "
                f"@ {item.rate_per_gram:.1f} EGP/g = {item.print_cost:.2f} EGP"
            )
        lines += [
            "-" * 40,
            f"Total: {o.total:.2f} EGP",
            f"Payment: {o.payment_method}",
        ]
        _TextDialog(self, "\n".join(lines))

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------

    def _can_delete(self) -> bool:
        try:
            from src.auth.permissions import Permission
            return self._user.has_permission(Permission.DELETE_ORDER)
        except Exception:
            return getattr(self._user, "role", "") == "Admin"


# ======================================================================
# Inline dialogs  (lightweight — full dialogs go in src/ui/dialogs/)
# ======================================================================

class _ItemDialog(tk.Toplevel):
    """Add / edit a print item inline."""

    def __init__(self, parent, order: Order,
                 item: Optional[PrintItem], on_save) -> None:
        super().__init__(parent)
        self.title("Print Item" if item is None else "Edit Item")
        self.resizable(False, False)
        self.grab_set()
        self._order   = order
        self._item    = item
        self._on_save = on_save
        self._build(item)
        self._centre()

    def _build(self, item: Optional[PrintItem]) -> None:
        pad = {"padx": 6, "pady": 3}
        form = ttk.Frame(self, padding=12)
        form.pack()

        fields = [
            ("Name",        "name",             item.name              if item else ""),
            ("Color",       "color",             item.color             if item else "Black"),
            ("Est. Weight", "est_weight",        str(item.estimated_weight_grams) if item else "0"),
            ("Est. Time",   "est_time",          str(item.estimated_time_minutes) if item else "0"),
            ("Quantity",    "qty",               str(item.quantity)     if item else "1"),
            ("Rate (EGP/g)","rate",              str(item.rate_per_gram)if item else "4.0"),
            ("Filament",    "filament_type",     item.filament_type     if item else "PLA+"),
            ("Nozzle mm",   "nozzle",            str(item.settings.nozzle_size) if item else "0.4"),
            ("Layer mm",    "layer",             str(item.settings.layer_height)if item else "0.2"),
            ("Infill %",    "infill",            str(item.settings.infill_density)if item else "20"),
            ("Support",     "support",           item.settings.support_type if item else "None"),
            ("Notes",       "notes",             item.notes             if item else ""),
        ]

        self._vars: dict[str, tk.StringVar] = {}
        for row_i, (label, key, default) in enumerate(fields):
            ttk.Label(form, text=label + ":").grid(
                row=row_i, column=0, sticky=tk.W, **pad)
            var = tk.StringVar(value=str(default))
            self._vars[key] = var
            ttk.Entry(form, textvariable=var, width=22).grid(
                row=row_i, column=1, sticky=tk.EW, **pad)

        btn_f = ttk.Frame(form)
        btn_f.grid(row=len(fields), column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_f, text="Save", command=self._save).pack(
            side=tk.LEFT, padx=4)
        ttk.Button(btn_f, text="Cancel", command=self.destroy).pack(
            side=tk.LEFT, padx=4)

    def _save(self) -> None:
        v = self._vars
        data = {
            "id":                     self._item.id if self._item else None,
            "name":                   v["name"].get().strip(),
            "color":                  v["color"].get().strip(),
            "estimated_weight_grams": safe_float(v["est_weight"].get()),
            "estimated_time_minutes": safe_int(v["est_time"].get()),
            "quantity":               safe_int(v["qty"].get(), 1),
            "rate_per_gram":          safe_float(v["rate"].get(), 4.0),
            "filament_type":          v["filament_type"].get().strip(),
            "nozzle_size":            safe_float(v["nozzle"].get(), 0.4),
            "layer_height":           safe_float(v["layer"].get(), 0.2),
            "infill_density":         safe_int(v["infill"].get(), 20),
            "support_type":           v["support"].get().strip(),
            "notes":                  v["notes"].get().strip(),
        }
        self._on_save(data)
        self.destroy()

    def _centre(self) -> None:
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = self.master.winfo_rootx() + (self.master.winfo_width()  - w) // 2
        y = self.master.winfo_rooty() + (self.master.winfo_height() - h) // 2
        self.geometry(f"+{x}+{y}")


class _WeightDialog(tk.Toplevel):
    """Quick dialog to set actual weight on a printed item."""

    def __init__(self, parent, item: PrintItem, on_save) -> None:
        super().__init__(parent)
        self.title("Set Actual Weight")
        self.resizable(False, False)
        self.grab_set()
        self._on_save = on_save

        frm = ttk.Frame(self, padding=16)
        frm.pack()
        ttk.Label(frm, text=f"Item: {item.name}", font=Fonts.BUTTON_BOLD).pack()
        ttk.Label(frm, text=f"Est. weight: {item.estimated_weight_grams:.1f} g",
                  foreground=Colors.TEXT_SECONDARY).pack(pady=(4, 8))
        ttk.Label(frm, text="Actual weight (g):").pack()
        self._var = tk.StringVar(
            value=str(item.actual_weight_grams or item.estimated_weight_grams))
        ttk.Entry(frm, textvariable=self._var, width=10,
                  font=Fonts.DEFAULT).pack(pady=4)

        bf = ttk.Frame(frm)
        bf.pack(pady=(8, 0))
        ttk.Button(bf, text="Set", command=self._save).pack(side=tk.LEFT, padx=4)
        ttk.Button(bf, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=4)

    def _save(self) -> None:
        self._on_save(safe_float(self._var.get()))
        self.destroy()


class _TextDialog(tk.Toplevel):
    """Display a copyable text receipt."""

    def __init__(self, parent, text: str) -> None:
        super().__init__(parent)
        self.title("Text Receipt")
        self.grab_set()
        txt = tk.Text(self, width=50, height=20, font=Fonts.MONO, padx=8, pady=8)
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert("1.0", text)
        txt.config(state=tk.DISABLED)
        ttk.Button(self, text="Close", command=self.destroy).pack(pady=6)