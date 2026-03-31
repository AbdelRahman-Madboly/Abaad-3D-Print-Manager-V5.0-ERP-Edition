"""
src/ui/tabs/analytics_tab.py
============================
Visual analytics tab for Abaad 3D Print Manager v5.0.
Admin-only tab. Requires matplotlib.

Charts:
  1. Monthly Revenue bar chart
  2. Order Status pie chart
  3. Profit over time line chart
  4. Expenses by Category pie chart
  5. Filament Usage by Color bar chart
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from src.services.finance_service import FinanceService
from src.ui.theme import Colors, Fonts

# Matplotlib is optional — graceful degradation
try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


_CHART_COLORS = [
    "#1e3a8a", "#3b82f6", "#10b981", "#f59e0b",
    "#ef4444", "#7c3aed", "#06b6d4", "#f97316",
    "#ec4899", "#84cc16",
]


class AnalyticsTab(ttk.Frame):
    """Visual analytics tab.

    Args:
        parent:          ttk.Notebook parent.
        finance_service: FinanceService instance.
        user:            Currently logged-in User object.
    """

    def __init__(self, parent, finance_service: FinanceService,
                 user, on_status_change=None) -> None:
        super().__init__(parent, padding=10)
        self._fin  = finance_service
        self._user = user

        if not MATPLOTLIB_AVAILABLE:
            self._build_unavailable()
        else:
            self._build_ui()
            self.refresh()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        if MATPLOTLIB_AVAILABLE:
            self._draw_charts()

    # ------------------------------------------------------------------
    # Fallback when matplotlib is missing
    # ------------------------------------------------------------------

    def _build_unavailable(self) -> None:
        ttk.Label(self, text="📈 Analytics",
                  style="Title.TLabel").pack(pady=20)
        ttk.Label(
            self,
            text="matplotlib is not installed.\n\n"
                 "Install it to enable charts:\n"
                 "    pip install matplotlib",
            style="Subtitle.TLabel",
            justify="center",
        ).pack(pady=10)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        # Toolbar
        tb = ttk.Frame(self)
        tb.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(tb, text="📈 Analytics",
                  style="Header.TLabel").pack(side=tk.LEFT)

        ttk.Label(tb, text="Period:").pack(side=tk.LEFT, padx=(20, 4))
        self._period_var = tk.StringVar(value="last_90")
        periods = [
            ("Last 30 days", "last_30"),
            ("Last 90 days", "last_90"),
            ("This year",    "this_year"),
            ("All time",     "all"),
        ]
        for label, val in periods:
            ttk.Radiobutton(tb, text=label, variable=self._period_var,
                            value=val, command=self.refresh).pack(
                side=tk.LEFT, padx=4)

        ttk.Button(tb, text="🔄 Refresh",
                   command=self.refresh).pack(side=tk.RIGHT)

        # Charts notebook
        self._nb = ttk.Notebook(self)
        self._nb.grid(row=1, column=0, sticky="nsew")

        self._chart_frames: dict = {}
        chart_tabs = [
            ("revenue",  "💰 Monthly Revenue"),
            ("status",   "📦 Order Status"),
            ("profit",   "📈 Profit Trend"),
            ("expenses", "🧾 Expenses"),
            ("filament", "🧵 Filament"),
        ]
        for key, label in chart_tabs:
            frame = ttk.Frame(self._nb)
            self._nb.add(frame, text=label)
            self._chart_frames[key] = frame

    # ------------------------------------------------------------------
    # Chart rendering
    # ------------------------------------------------------------------

    def _get_date_range(self) -> tuple[str, str]:
        """Return (start_date, end_date) based on the selected period."""
        period = self._period_var.get()
        now = datetime.now()
        if period == "last_30":
            start = now - timedelta(days=30)
        elif period == "last_90":
            start = now - timedelta(days=90)
        elif period == "this_year":
            start = datetime(now.year, 1, 1)
        else:
            start = datetime(2020, 1, 1)
        return start.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")

    def _clear_frame(self, key: str) -> None:
        for w in self._chart_frames[key].winfo_children():
            w.destroy()

    def _draw_charts(self) -> None:
        start, end = self._get_date_range()
        self._draw_revenue_chart(start, end)
        self._draw_status_pie(start, end)
        self._draw_profit_trend(start, end)
        self._draw_expenses_pie(start, end)
        self._draw_filament_chart(start, end)

    def _embed_figure(self, fig: "Figure", key: str) -> None:
        self._clear_frame(key)
        canvas = FigureCanvasTkAgg(fig, master=self._chart_frames[key])
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # -- Revenue bar chart --

    def _draw_revenue_chart(self, start: str, end: str) -> None:
        monthly = self._fin.get_monthly_revenue(start, end)
        fig = Figure(figsize=(10, 4), dpi=95, facecolor=Colors.BG)
        ax  = fig.add_subplot(111, facecolor=Colors.BG)

        months  = [m["month"] for m in monthly]
        revenue = [m["revenue"] for m in monthly]
        costs   = [m["costs"]   for m in monthly]
        profit  = [m["profit"]  for m in monthly]

        x = range(len(months))
        width = 0.25
        ax.bar([i - width for i in x], revenue, width, label="Revenue",
               color=Colors.SUCCESS, alpha=0.85)
        ax.bar(list(x), costs, width, label="Costs",
               color=Colors.DANGER, alpha=0.85)
        ax.bar([i + width for i in x], profit, width, label="Profit",
               color=Colors.PRIMARY, alpha=0.85)

        ax.set_title("Monthly Revenue vs Costs vs Profit",
                     color=Colors.TEXT, fontsize=12)
        ax.set_xticks(list(x))
        ax.set_xticklabels(months, rotation=45, ha="right",
                            color=Colors.TEXT_SECONDARY, fontsize=8)
        ax.legend(facecolor=Colors.CARD, labelcolor=Colors.TEXT)
        ax.tick_params(colors=Colors.TEXT_SECONDARY)
        for spine in ax.spines.values():
            spine.set_edgecolor(Colors.BORDER)
        fig.tight_layout()
        self._embed_figure(fig, "revenue")

    # -- Order status pie --

    def _draw_status_pie(self, start: str, end: str) -> None:
        data = self._fin.get_order_status_breakdown(start, end)
        fig  = Figure(figsize=(6, 4), dpi=95, facecolor=Colors.BG)
        ax   = fig.add_subplot(111, facecolor=Colors.BG)

        if not data:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    transform=ax.transAxes, color=Colors.TEXT_SECONDARY)
        else:
            labels = [d["status"] for d in data]
            sizes  = [d["count"]  for d in data]
            ax.pie(sizes, labels=labels, autopct="%1.0f%%",
                   colors=_CHART_COLORS[:len(labels)],
                   textprops={"color": Colors.TEXT})
        ax.set_title("Order Status Breakdown", color=Colors.TEXT, fontsize=12)
        fig.tight_layout()
        self._embed_figure(fig, "status")

    # -- Profit trend line --

    def _draw_profit_trend(self, start: str, end: str) -> None:
        monthly = self._fin.get_monthly_revenue(start, end)
        fig = Figure(figsize=(10, 4), dpi=95, facecolor=Colors.BG)
        ax  = fig.add_subplot(111, facecolor=Colors.BG)

        months = [m["month"]  for m in monthly]
        profit = [m["profit"] for m in monthly]

        ax.plot(months, profit, marker="o", color=Colors.PRIMARY,
                linewidth=2, markersize=5)
        ax.fill_between(months, profit, alpha=0.15, color=Colors.PRIMARY)
        ax.axhline(0, color=Colors.DANGER, linewidth=0.8, linestyle="--")
        ax.set_title("Profit Trend", color=Colors.TEXT, fontsize=12)
        ax.set_xticks(range(len(months)))
        ax.set_xticklabels(months, rotation=45, ha="right",
                            color=Colors.TEXT_SECONDARY, fontsize=8)
        ax.tick_params(colors=Colors.TEXT_SECONDARY)
        for spine in ax.spines.values():
            spine.set_edgecolor(Colors.BORDER)
        fig.tight_layout()
        self._embed_figure(fig, "profit")

    # -- Expenses pie --

    def _draw_expenses_pie(self, start: str, end: str) -> None:
        data = self._fin.get_expenses_by_category(start, end)
        fig  = Figure(figsize=(6, 4), dpi=95, facecolor=Colors.BG)
        ax   = fig.add_subplot(111, facecolor=Colors.BG)

        if not data:
            ax.text(0.5, 0.5, "No expenses", ha="center", va="center",
                    transform=ax.transAxes, color=Colors.TEXT_SECONDARY)
        else:
            labels = [d["category"] for d in data]
            sizes  = [d["total"]    for d in data]
            ax.pie(sizes, labels=labels, autopct="%1.0f%%",
                   colors=_CHART_COLORS[:len(labels)],
                   textprops={"color": Colors.TEXT})
        ax.set_title("Expenses by Category", color=Colors.TEXT, fontsize=12)
        fig.tight_layout()
        self._embed_figure(fig, "expenses")

    # -- Filament bar --

    def _draw_filament_chart(self, start: str, end: str) -> None:
        data = self._fin.get_filament_usage_by_color(start, end)
        fig  = Figure(figsize=(10, 4), dpi=95, facecolor=Colors.BG)
        ax   = fig.add_subplot(111, facecolor=Colors.BG)

        colors_list = [d["color"] for d in data]
        grams       = [d["grams"] for d in data]

        ax.barh(colors_list, grams, color=_CHART_COLORS[:len(colors_list)],
                alpha=0.85)
        ax.set_title("Filament Usage by Color (g)", color=Colors.TEXT,
                     fontsize=12)
        ax.tick_params(colors=Colors.TEXT_SECONDARY)
        for spine in ax.spines.values():
            spine.set_edgecolor(Colors.BORDER)
        fig.tight_layout()
        self._embed_figure(fig, "filament")