"""
src/ui/widgets.py
=================
Reusable custom Tkinter widgets for Abaad ERP v5.0.

Widgets:
  SearchEntry       — Entry with placeholder text, clears on focus
  StatCard          — Colored card: label + big number + optional subtitle
  ScrollableFrame   — Frame with vertical auto-scrollbar
  ScrollableTreeview— Treeview pre-fitted with a scrollbar
  FormRow           — Label + Entry pair with optional validation mark
  ActionButton      — Flat colored button with hover effect
  StatusBadge       — Small colored tag label
  ConfirmDialog     — Modal yes/no dialog with custom icon
  TooltipMixin      — Add .add_tooltip(widget, text) to any class
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable

from src.ui.theme import Colors, Fonts


# ---------------------------------------------------------------------------
# SearchEntry
# ---------------------------------------------------------------------------

class SearchEntry(ttk.Entry):
    """Entry with grey placeholder text that disappears on focus.

    Args:
        parent:      Parent widget.
        placeholder: Text shown when the entry is empty.
        **kwargs:    Passed to ttk.Entry.

    Attributes:
        var: The underlying StringVar — trace this for live filtering.
    """

    def __init__(self, parent, placeholder: str = "Search…", **kwargs) -> None:
        self.var = tk.StringVar()
        super().__init__(parent, textvariable=self.var, **kwargs)
        self._placeholder = placeholder
        self._showing_placeholder = False
        self._show_placeholder()
        self.bind("<FocusIn>",  self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)

    def _show_placeholder(self) -> None:
        if not self.var.get():
            self.var.set(self._placeholder)
            self.configure(foreground=Colors.TEXT_LIGHT)
            self._showing_placeholder = True

    def _on_focus_in(self, _event=None) -> None:
        if self._showing_placeholder:
            self.var.set("")
            self.configure(foreground=Colors.TEXT)
            self._showing_placeholder = False

    def _on_focus_out(self, _event=None) -> None:
        if not self.var.get():
            self._show_placeholder()

    def get_value(self) -> str:
        """Return the actual value (empty string when placeholder is shown)."""
        return "" if self._showing_placeholder else self.var.get()

    def clear(self) -> None:
        """Clear value and restore placeholder."""
        self.var.set("")
        self._show_placeholder()


# ---------------------------------------------------------------------------
# StatCard
# ---------------------------------------------------------------------------

class StatCard(tk.Frame):
    """Colored card showing a label, a big number, and an optional subtitle.

    Args:
        parent:    Parent widget.
        label:     Short description text (top of card).
        value:     Main value displayed in large font.
        subtitle:  Optional smaller text below the value.
        color:     Background color (hex string).
        width:     Minimum card width in pixels.
        **kwargs:  Passed to tk.Frame.

    Example::

        card = StatCard(frame, "Total Orders", "142", color=Colors.PRIMARY)
        card.set_value("143")
    """

    def __init__(self, parent, label: str, value: str = "—",
                 subtitle: str = "", color: str = Colors.PRIMARY,
                 width: int = 120, **kwargs) -> None:
        super().__init__(parent, bg=color, padx=14, pady=10,
                         width=width, **kwargs)
        self._color = color

        self._lbl_label = tk.Label(self, text=label, bg=color, fg="white",
                                    font=Fonts.SMALL)
        self._lbl_label.pack()

        self._lbl_value = tk.Label(self, text=value, bg=color, fg="white",
                                    font=Fonts.BIG_NUMBER)
        self._lbl_value.pack()

        if subtitle:
            self._lbl_sub = tk.Label(self, text=subtitle, bg=color,
                                      fg="white", font=Fonts.TINY)
            self._lbl_sub.pack()
        else:
            self._lbl_sub = None

    def set_value(self, value: str) -> None:
        """Update the main value label."""
        self._lbl_value.config(text=value)

    def set_subtitle(self, text: str) -> None:
        """Update or create the subtitle label."""
        if self._lbl_sub:
            self._lbl_sub.config(text=text)
        else:
            self._lbl_sub = tk.Label(self, text=text, bg=self._color,
                                      fg="white", font=Fonts.TINY)
            self._lbl_sub.pack()


# ---------------------------------------------------------------------------
# ScrollableFrame
# ---------------------------------------------------------------------------

class ScrollableFrame(ttk.Frame):
    """A ttk.Frame with a vertical scrollbar.

    Access the inner container via ``.inner``.

    Usage::

        sf = ScrollableFrame(parent)
        sf.pack(fill=tk.BOTH, expand=True)
        ttk.Label(sf.inner, text="Hello").pack()
    """

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        canvas = tk.Canvas(self, bg=Colors.BG, highlightthickness=0)
        vsb    = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self.inner = ttk.Frame(canvas)
        self.inner.columnconfigure(0, weight=1)
        win_id = canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))


# ---------------------------------------------------------------------------
# ScrollableTreeview
# ---------------------------------------------------------------------------

class ScrollableTreeview(ttk.Frame):
    """Treeview with a pre-attached vertical scrollbar.

    The ``tree`` attribute gives direct access to the underlying Treeview.

    Args:
        parent:  Parent widget.
        columns: Column id tuple passed to Treeview.
        **kwargs: Passed to Treeview (e.g. ``show``, ``height``).

    Example::

        stv = ScrollableTreeview(frame, columns=("name", "phone"))
        stv.pack(fill=tk.BOTH, expand=True)
        stv.tree.insert("", "end", values=("Alice", "01234"))
    """

    def __init__(self, parent, columns: tuple, **kwargs) -> None:
        super().__init__(parent)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(self, columns=columns, **kwargs)
        vsb = ttk.Scrollbar(self, orient="vertical",
                             command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

    # Delegate common Treeview methods for convenience
    def insert(self, *args, **kwargs):
        return self.tree.insert(*args, **kwargs)

    def delete(self, *args):
        return self.tree.delete(*args)

    def get_children(self):
        return self.tree.get_children()

    def selection(self):
        return self.tree.selection()


# ---------------------------------------------------------------------------
# FormRow
# ---------------------------------------------------------------------------

class FormRow(ttk.Frame):
    """A label + entry pair for building forms.

    Args:
        parent:       Parent widget.
        label:        Label text (shown to the left).
        var:          StringVar to attach to the entry (created if None).
        required:     If True, appends a red * to the label.
        label_width:  Fixed width for the label column.
        entry_width:  Width of the entry widget.
        widget:       Optional: pass a pre-built widget to use instead of Entry.
        **kwargs:     Passed to ttk.Frame.

    Attributes:
        var:    The StringVar.
        entry:  The Entry (or custom widget) instance.
    """

    def __init__(self, parent, label: str, var: Optional[tk.StringVar] = None,
                 required: bool = False, label_width: int = 14,
                 entry_width: int = 28, widget=None, **kwargs) -> None:
        super().__init__(parent, **kwargs)

        self.var = var or tk.StringVar()

        lbl_text = f"{label} *" if required else label
        ttk.Label(self, text=lbl_text, width=label_width,
                  anchor="w").pack(side=tk.LEFT, padx=(0, 8))

        if widget is not None:
            self.entry = widget
        else:
            self.entry = ttk.Entry(self, textvariable=self.var,
                                   width=entry_width)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, value: str) -> None:
        self.var.set(value)

    def focus(self) -> None:
        self.entry.focus_set()


# ---------------------------------------------------------------------------
# ActionButton
# ---------------------------------------------------------------------------

class ActionButton(tk.Button):
    """Flat colored button with mouse-over highlight.

    Args:
        parent:    Parent widget.
        text:      Button label.
        color:     Normal background color.
        hover_color: Background color on hover (auto-darkened if not given).
        command:   Click callback.
        **kwargs:  Passed to tk.Button.
    """

    def __init__(self, parent, text: str, color: str = Colors.PRIMARY,
                 hover_color: Optional[str] = None,
                 command: Optional[Callable] = None, **kwargs) -> None:
        self._color       = color
        self._hover_color = hover_color or Colors.PRIMARY_DARK

        super().__init__(
            parent, text=text, bg=color, fg="white",
            font=Fonts.BUTTON_BOLD, relief=tk.FLAT, cursor="hand2",
            padx=12, pady=5, command=command, activebackground=self._hover_color,
            activeforeground="white", **kwargs,
        )
        self.bind("<Enter>", lambda _: self.config(bg=self._hover_color))
        self.bind("<Leave>", lambda _: self.config(bg=self._color))

    def set_state(self, enabled: bool) -> None:
        self.config(state="normal" if enabled else "disabled")


# ---------------------------------------------------------------------------
# StatusBadge
# ---------------------------------------------------------------------------

class StatusBadge(tk.Label):
    """Small pill-shaped colored label — useful for role / status indicators.

    Args:
        parent: Parent widget.
        text:   Badge text.
        color:  Background color.
        **kwargs: Passed to tk.Label.
    """

    def __init__(self, parent, text: str, color: str = Colors.PRIMARY,
                 **kwargs) -> None:
        super().__init__(
            parent, text=text, bg=color, fg="white",
            font=Fonts.TINY, padx=8, pady=2, **kwargs,
        )


# ---------------------------------------------------------------------------
# ConfirmDialog
# ---------------------------------------------------------------------------

class ConfirmDialog:
    """Modal yes/no confirmation dialog.

    Args:
        parent:  Parent widget (dialog centres over it).
        title:   Dialog window title.
        message: Body text.
        icon:    Emoji or text prefix shown before the message.
        yes_text / no_text: Button labels.

    Attributes:
        confirmed: ``True`` if the user clicked Yes.

    Usage::

        dlg = ConfirmDialog(root, "Delete Order",
                            "This cannot be undone.", icon="🗑")
        if dlg.confirmed:
            ...
    """

    def __init__(self, parent, title: str = "Confirm",
                 message: str = "Are you sure?",
                 icon: str = "❓",
                 yes_text: str = "Yes",
                 no_text: str = "Cancel") -> None:
        self.confirmed = False

        win = tk.Toplevel(parent)
        win.title(title)
        win.resizable(False, False)
        win.grab_set()

        # Content
        body = ttk.Frame(win, padding=20)
        body.pack(fill=tk.BOTH, expand=True)

        tk.Label(body, text=icon, font=("Segoe UI", 24),
                 bg=Colors.BG).pack()
        ttk.Label(body, text=title,
                  style="Header.TLabel").pack(pady=(4, 0))
        ttk.Label(body, text=message, style="Subtitle.TLabel",
                  wraplength=320, justify="center").pack(pady=(8, 16))

        btn_row = ttk.Frame(body)
        btn_row.pack()
        ActionButton(btn_row, text=yes_text, color=Colors.DANGER,
                     command=lambda: self._confirm(win)).pack(
            side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text=no_text,
                   command=win.destroy).pack(side=tk.LEFT, padx=6)

        # Centre over parent
        win.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width()  // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = win.winfo_width(), win.winfo_height()
        win.geometry(f"+{px - w//2}+{py - h//2}")

        win.wait_window()

    def _confirm(self, win) -> None:
        self.confirmed = True
        win.destroy()


# ---------------------------------------------------------------------------
# TooltipMixin
# ---------------------------------------------------------------------------

class TooltipMixin:
    """Mixin that adds tooltip support to any tkinter widget host class.

    Usage (in a Frame subclass)::

        class MyTab(ttk.Frame, TooltipMixin):
            def _build(self):
                btn = ttk.Button(self, text="Delete")
                self.add_tooltip(btn, "Permanently delete this record")
    """

    def add_tooltip(self, widget: tk.Widget, text: str) -> None:
        """Attach a hover tooltip to *widget*."""
        tip_win: list = [None]   # mutable container for the Toplevel ref

        def _show(_event=None):
            if tip_win[0]:
                return
            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + widget.winfo_height() + 4
            tw = tk.Toplevel(widget)
            tw.wm_overrideredirect(True)
            tw.geometry(f"+{x}+{y}")
            tk.Label(tw, text=text, bg="#fffbcc", fg=Colors.TEXT,
                     font=Fonts.SMALL, padx=6, pady=3,
                     relief="solid", borderwidth=1).pack()
            tip_win[0] = tw

        def _hide(_event=None):
            if tip_win[0]:
                tip_win[0].destroy()
                tip_win[0] = None

        widget.bind("<Enter>", _show)
        widget.bind("<Leave>", _hide)