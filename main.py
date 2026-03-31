"""
main.py
=======
Entry point for Abaad 3D Print Manager v5.0.
Keep this file under 60 lines — no business logic here.

Boot sequence
-------------
1.  Bootstrap runtime directories
2.  Apply API compatibility patches   ← must happen before any import of services
3.  Open v4 JSON database (singleton)
4.  Initialise auth manager
5.  Login loop:
      show LoginDialog → on success build services and open App
      on window close / logout → loop back to login
      on dialog cancel → exit
"""

import logging
import tkinter as tk

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("abaad")


def main() -> None:
    # 1. Directories
    from src.core.config import ensure_directories
    ensure_directories()

    # 2. Patches — MUST come before service imports
    from src.services._compat import apply_all_patches
    apply_all_patches()

    # 3. Database (v4 JSON, singleton)
    from src.core.database import DatabaseManager
    db = DatabaseManager()

    # 4. Auth
    from src.auth.auth_manager import get_auth_manager
    auth = get_auth_manager()
    auth._load_from_json_fallback()   # load from data/users.json if present
    auth._ensure_default_admin()

    # 5. Login loop
    while True:
        root = tk.Tk()
        root.withdraw()

        from src.ui.dialogs.login_dialog import LoginDialog
        user = LoginDialog(root).result

        if user is None:
            root.destroy()
            break                    # cancelled → exit

        services = {
            "order":     _svc("order_service",    "OrderService",     db),
            "customer":  _svc("customer_service", "CustomerService",  db),
            "inventory": _svc("inventory_service","InventoryService", db),
            "printer":   _svc("printer_service",  "PrinterService",   db),
            "finance":   _svc("finance_service",  "FinanceService",   db),
        }

        root.deiconify()
        from src.ui.app import App
        App(root, user, db, services)
        root.mainloop()
        # after mainloop returns (logout or close), loop back to login


def _svc(module: str, cls: str, db):
    import importlib
    mod = importlib.import_module(f"src.services.{module}")
    return getattr(mod, cls)(db)


if __name__ == "__main__":
    main()