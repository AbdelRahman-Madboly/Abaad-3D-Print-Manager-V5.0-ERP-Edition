"""
src/ui/context_menu.py
======================
TreeviewContextMenu — a reusable right-click menu for Treeview widgets.
Task 4.3: UI Polish — right-click context menus and double-click to edit.

Usage in any tab:
    from src.ui.context_menu import bind_treeview_menu

    bind_treeview_menu(self._tree, actions=[
        ("✏️ Edit",    self._edit_order),
        ("🗑 Delete",  self._delete_order),
        None,                              # separator
        ("📄 Quote PDF",  self._gen_quote),
        ("🧾 Receipt PDF", self._gen_receipt),
    ])

    # Also binds double-click to the first non-separator action automatically.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable, List, Tuple, Union


# Action = (label, callback) or None for a separator
Action = Optional[Tuple[str, Callable]]


def bind_treeview_menu(
    tree: ttk.Treeview,
    actions: List[Action],
    needs_selection: bool = True,
) -> None:
    """Attach a right-click context menu and double-click handler to *tree*.

    Args:
        tree:             The Treeview to augment.
        actions:          List of (label, callback) tuples, or None for separators.
        needs_selection:  If True, menu entries are disabled when nothing is selected.
    """
    menu = tk.Menu(tree, tearoff=False)

    for action in actions:
        if action is None:
            menu.add_separator()
        else:
            label, cmd = action
            menu.add_command(label=label, command=cmd)

    def _show_menu(event):
        # Select the row under cursor first
        row = tree.identify_row(event.y)
        if row:
            tree.selection_set(row)

        if needs_selection and not tree.selection():
            return

        # Enable / disable entries based on selection
        state = "normal" if tree.selection() else "disabled"
        for i in range(menu.index("end") + 1):
            try:
                if menu.type(i) != "separator":
                    menu.entryconfig(i, state=state)
            except tk.TclError:
                pass

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    tree.bind("<Button-3>", _show_menu)           # Windows / Linux right-click
    tree.bind("<Button-2>", _show_menu)           # macOS right-click (two-finger)

    # Double-click calls the first non-separator action
    first_action = next((a for a in actions if a is not None), None)
    if first_action:
        _, first_cmd = first_action
        tree.bind("<Double-1>", lambda _e: first_cmd())