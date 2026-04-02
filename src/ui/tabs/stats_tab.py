"""
src/ui/tabs/stats_tab.py
========================
Statistics dashboard tab for Abaad 3D Print Manager v5.0.
Admin-only tab.

Displays colored stat cards grouped into:
  Revenue / Costs / Profit / Production / Failures / Expenses / Orders / Customers
"""

import tkinter as tk
from tkinter import ttk

from src.services.finance_service import FinanceService
from src.services.customer_service import CustomerService
from src.services.inventory_service import InventoryService
from src.ui.theme import Colors, Fonts
from src.utils.helpers import format_currency, format_time_minutes
from src.ui.context_menu import bind_treeview_menu



class StatsTab(ttk.Frame):
    """Statistics dashboard.

    Args:
        parent:            ttk.Notebook parent.
        finance_service:   FinanceService instance.
        customer_service:  CustomerService instance.
        inventory_service: InventoryService instance.
        user:              Currently logged-in User object.
    """

    def __init__(self, parent, finance_service: FinanceService,
                 customer_service: CustomerService,
                 inventory_service: InventoryService,
                 user, on_status_change=None) -> None:
        super().__init__(parent, padding=10)
        self._fin  = finance_service
        self._cust = customer_service
        self._inv  = inventory_service
        self._user = user
        self._cards: dict = {}

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._load_stats()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)

        # Header row
        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(header, text="📊 Statistics Dashboard",
                  style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Button(header, text="🔄 Refresh",
                   command=self.refresh).pack(side=tk.RIGHT)

        # Scrollable canvas
        canvas = tk.Canvas(self, bg=Colors.BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.grid(row=1, column=0, sticky="nsew")
        vsb.grid(row=1, column=1, sticky="ns")
        self.rowconfigure(1, weight=1)

        self._inner = ttk.Frame(canvas)
        self._inner.columnconfigure(0, weight=1)
        canvas_window = canvas.create_window((0, 0), window=self._inner,
                                              anchor="nw")

        def _on_frame_config(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        self._inner.bind("<Configure>", _on_frame_config)

        def _on_canvas_config(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", _on_canvas_config)

        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        # Build sections
        self._build_section("💰 Revenue",   "revenue",    Colors.SUCCESS,
            ["Total Revenue", "Shipping Collected", "Payment Fees", "Rounding Loss"])
        self._build_section("📉 Costs",     "costs",      Colors.DANGER,
            ["Material Cost", "Electricity", "Depreciation",
             "Nozzle Cost", "Failures Cost", "Total Expenses"])
        self._build_section("📈 Profit",    "profit",     Colors.PRIMARY,
            ["Gross Profit", "Net Profit", "Profit Margin %", "Avg Order Value"])
        self._build_section("🏭 Production","production", Colors.INFO,
            ["Total Weight (g)", "Total Print Time", "Active Spools", "Available Filament"])
        self._build_section("❌ Failures",  "failures",   Colors.WARNING,
            ["Failure Count", "Filament Wasted", "Time Wasted", "Failure Cost"])
        self._build_section("🧾 Orders",    "orders",     Colors.PURPLE,
            ["Total Orders", "Delivered", "R&D Orders", "Cancelled"])
        self._build_section("👤 Customers", "customers",  Colors.CYAN,
            ["Total Customers", "Avg Spent / Customer"])

    def _build_section(self, title: str, key: str, color: str,
                       labels: list) -> None:
        row_count = len(self._inner.grid_slaves()) // 1
        section = ttk.LabelFrame(self._inner, text=title, padding=10)
        section.grid(row=row_count, column=0, sticky="ew",
                     pady=(0, 10), padx=2)

        cards_frame = ttk.Frame(section)
        cards_frame.pack(fill=tk.X)
        per_row = 4
        for i, label in enumerate(labels):
            r, c = divmod(i, per_row)
            card = tk.Frame(cards_frame, bg=color, padx=14, pady=10)
            card.grid(row=r, column=c, padx=4, pady=4, sticky="ew")
            cards_frame.columnconfigure(c, weight=1)
            tk.Label(card, text=label, bg=color, fg="white",
                     font=Fonts.SMALL).pack()
            val_lbl = tk.Label(card, text="—", bg=color, fg="white",
                               font=Fonts.BIG_NUMBER)
            val_lbl.pack()
            card_key = f"{key}_{label.lower().replace(' ', '_').replace('%','pct').replace('(','').replace(')','').replace('/','_')}"
            self._cards[card_key] = val_lbl

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _load_stats(self) -> None:
        stats  = self._fin.get_full_statistics()
        inv    = self._inv.get_inventory_summary()
        f_stat = self._fin.get_failure_stats()
        e_stat = self._fin.get_expense_stats()
        o_stat = self._fin.get_order_stats()
        c_count = len(self._cust.get_all_customers())
        c_spent = stats.get("total_revenue", 0)

        def _set(key: str, value) -> None:
            lbl = self._cards.get(key)
            if lbl:
                lbl.config(text=str(value))

        # Revenue
        _set("revenue_total_revenue",     format_currency(stats.get("total_revenue", 0)))
        _set("revenue_shipping_collected",format_currency(stats.get("total_shipping", 0)))
        _set("revenue_payment_fees",      format_currency(stats.get("total_fees", 0)))
        _set("revenue_rounding_loss",     format_currency(stats.get("total_rounding", 0)))

        # Costs
        _set("costs_material_cost",   format_currency(stats.get("total_material", 0)))
        _set("costs_electricity",     format_currency(stats.get("total_electricity", 0)))
        _set("costs_depreciation",    format_currency(stats.get("total_depreciation", 0)))
        _set("costs_nozzle_cost",     format_currency(stats.get("total_nozzle", 0)))
        _set("costs_failures_cost",   format_currency(f_stat.get("total_cost", 0)))
        _set("costs_total_expenses",  format_currency(e_stat.get("total_expenses", 0)))

        # Profit
        gross = stats.get("gross_profit", 0)
        net   = gross - f_stat.get("total_cost", 0) - e_stat.get("total_expenses", 0)
        rev   = stats.get("total_revenue", 0)
        margin = (net / rev * 100) if rev else 0
        orders = o_stat.get("delivered", 0) or 1
        avg_val = rev / orders

        _set("profit_gross_profit",  format_currency(gross))
        _set("profit_net_profit",    format_currency(net))
        _set("profit_profit_margin_pct", f"{margin:.1f}%")
        _set("profit_avg_order_value",   format_currency(avg_val))

        # Production
        _set("production_total_weight_g",
             f"{stats.get('total_weight', 0):,.0f} g")
        _set("production_total_print_time",
             format_time_minutes(int(stats.get("total_print_time", 0))))
        _set("production_active_spools", str(inv.get("active_spools", 0)))
        _set("production_available_filament",
             f"{inv.get('available_weight_g', 0):,.0f} g")

        # Failures
        _set("failures_failure_count",   str(f_stat.get("total_failures", 0)))
        _set("failures_filament_wasted",
             f"{f_stat.get('total_filament_wasted', 0):.1f} g")
        _set("failures_time_wasted",
             format_time_minutes(int(f_stat.get("total_time_wasted", 0))))
        _set("failures_failure_cost",
             format_currency(f_stat.get("total_cost", 0)))

        # Orders
        _set("orders_total_orders",    str(o_stat.get("total", 0)))
        _set("orders_delivered",       str(o_stat.get("delivered", 0)))
        _set("orders_r&d_orders",      str(o_stat.get("rd", 0)))
        _set("orders_cancelled",       str(o_stat.get("cancelled", 0)))

        # Customers
        _set("customers_total_customers", str(c_count))
        avg_c = (c_spent / c_count) if c_count else 0
        _set("customers_avg_spent___customer", format_currency(avg_c))