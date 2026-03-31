# Abaad v5.0 — Refactoring Progress Tracker

> **How to use:** Work through tasks in order. For each task, copy the prompt into a Claude Sonnet chat (with the Project Instructions loaded). Check off completed tasks. Paste relevant current code when prompted.

---

## STATUS DASHBOARD

| Phase | Tasks | Done | Status |
|-------|-------|------|--------|
| 1. Foundation | 8 | 6 | 🟡 In Progress |
| 2. Split main.py | 12 | 1 | 🟡 In Progress |
| 3. Service Layer | 5 | 5 | ✅ Complete |
| 4. Features | 3 | 0 | ⬜ Not Started |
| 5. Installation | 5 | 0 | ⬜ Not Started |
| 6. Testing | 5 | 0 | ⬜ Not Started |
| **TOTAL** | **38** | **12** | **32%** |

---

## FILES CONFIRMED ON DISK ✅

| File | Path | Status |
|------|------|--------|
| config.py | `src/core/config.py` | ✅ Done |
| theme.py | `src/ui/theme.py` | ✅ Done |
| helpers.py | `src/utils/helpers.py` | ✅ Done |
| database.py | `src/core/database.py` | ✅ Done |
| migrate_v4_to_v5.py | `scripts/migrate_v4_to_v5.py` | ✅ Done + Verified |
| models.py | `src/core/models.py` | ✅ Done |
| order_service.py | `src/services/order_service.py` | ✅ Done |
| inventory_service.py | `src/services/inventory_service.py` | ✅ Done |
| customer_service.py | `src/services/customer_service.py` | ✅ Done |
| printer_service.py | `src/services/printer_service.py` | ✅ Done |
| finance_service.py | `src/services/finance_service.py` | ✅ Done |
| orders_tab.py | `src/ui/tabs/orders_tab.py` | ✅ Done |

---

## PHASE 1: FOUNDATION

### ✅ Task 1.1 — `src/core/config.py`
All constants, paths, company info, `PAYMENT_FEES` dict, `DEFAULT_COLORS`, `DEFAULT_SETTINGS`, enum string lists, `ensure_directories()`. No external deps.

---

### ✅ Task 1.2 — `src/ui/theme.py`
Full `Colors` + `Fonts` classes, `setup_styles(root)`. Extras: `TCheckbutton`, `TRadiobutton`, `TSpinbox`, `TScrollbar`, `TSeparator`, `TProgressbar`, `Card.TFrame`, `Card.TLabel`, `StatusBar.TLabel`. PRIMARY unified to `#1e3a8a`.

**To delete after cutover:**
- `Colors` class in `login.py` (lines 15–68)
- Duplicate `Colors` class in `admin_panel.py`
- `App._setup_styles()` in `main.py` (lines 106–143)

---

### ✅ Task 1.3 — `src/utils/helpers.py`
`generate_id()`, `now_str()`, `today_str()`, `format_time()`, `calculate_payment_fee()`, `format_currency()`, `round_to_half()`, `filament_length_to_grams()`, `truncate()`, `safe_float()`, `safe_int()`.

**To delete after cutover:**
- `generate_id()`, `now_str()`, `format_time()`, `calculate_payment_fee()` from `models.py` (v4 lines 96–135)
- `generate_id()`, `now_str()` from `auth.py` (v4 lines 75–82)

---

### ✅ Task 1.4 — `src/core/database.py`
WAL + FK mode, `@contextmanager _transaction()`, full CRUD for all tables, `save_user/get_user/get_all_users/delete_user`, `export_to_csv`, `backup_database()`, `_seed_defaults()` (idempotent `INSERT OR IGNORE`).

**To delete after cutover:** `src/database.py` (v4, 766 lines)

---

### ✅ Task 1.5 — `scripts/migrate_v4_to_v5.py`
Migrates all tables including nested `print_items`, handles `deleted_orders` → `is_deleted=1`, `--force` flag, validation table.

**Verified live run — all counts match:**
```
customers 6/6 ✓ | orders 10/10 ✓ | filament_spools 4/4 ✓
printers 1/1 ✓  | print_failures 3/3 ✓ | expenses 6/6 ✓
users 2/2 ✓     | items: 58 migrated
```

---

### ✅ Task 1.6 — `src/core/models.py`
All constants removed → import from `config.py`. All enums removed → string lists in `config.py`. Utility functions → import from `helpers.py`. All dataclasses kept with `to_dict()` / `from_dict()`. `PrintItem` flattened (no nested settings dict). `Order.calculate_totals()` business logic removed → lives in `order_service.py`. `PrintItem.calculate_tolerance_discount()` kept. `FilamentSpool` reserve/release/commit methods kept. `Statistics` dataclass kept.

---

### ⬜ Task 1.7 — Refactor `src/auth/auth_manager.py`

**What:** Split auth into two files, import helpers from new locations.

**Prompt:**
```
Refactor the auth module into two files:

1. src/auth/permissions.py — Contains:
   - UserRole enum (or string constants matching USER_ROLES in config.py)
   - Permission enum with values: CREATE_ORDER, EDIT_ORDER, DELETE_ORDER,
     VIEW_ORDERS, VIEW_CUSTOMERS, MANAGE_CUSTOMERS, VIEW_INVENTORY,
     MANAGE_INVENTORY, VIEW_PRINTERS, MANAGE_PRINTERS, VIEW_STATS,
     VIEW_FINANCIAL, MANAGE_SETTINGS, MANAGE_USERS, EXPORT_DATA,
     SYSTEM_BACKUP, GENERATE_QUOTE, GENERATE_RECEIPT, UPDATE_STATUS
   - ROLE_PERMISSIONS: dict mapping "Admin" and "User" to sets of Permissions

2. src/auth/auth_manager.py — Contains:
   - User dataclass (with password hashing using hashlib + secrets)
   - AuthManager class (singleton, manages users via the SQLite DB)
   - get_auth_manager() function
   - require_admin and require_login decorators

Changes from current auth.py:
- Import generate_id and now_str from src.utils.helpers (NOT defined here)
- Import DB_PATH from src.core.config
- Store users in SQLite via DatabaseManager (not users.json)
- Remove the duplicate generate_id() and now_str() functions

Admin permissions: ALL
User permissions: CREATE_ORDER, EDIT_ORDER, VIEW_ORDERS, UPDATE_STATUS,
  VIEW_CUSTOMERS, VIEW_INVENTORY, VIEW_PRINTERS, GENERATE_QUOTE, GENERATE_RECEIPT

Here is the current auth.py:
[Paste auth.py]
```

---

### ⬜ Task 1.8 — Create `__init__.py` files

**What:** Set up proper Python package structure with clean imports.

**Prompt:**
```
Create the __init__.py files for the new package structure.

Dependency direction (no circular imports):
  config ← models ← database ← services ← ui

Files to create:

1. src/__init__.py — empty

2. src/core/__init__.py
   from src.core.database import DatabaseManager, get_database
   from src.core import config
   from src.core.models import (
       PrintSettings, Printer, FilamentSpool, PrintItem,
       Customer, Order, FilamentHistory, PrintFailure, Expense, Statistics
   )

3. src/services/__init__.py
   from src.services.order_service import OrderService
   from src.services.inventory_service import InventoryService
   from src.services.customer_service import CustomerService
   from src.services.printer_service import PrinterService
   from src.services.finance_service import FinanceService

4. src/auth/__init__.py
   from src.auth.auth_manager import AuthManager, get_auth_manager
   from src.auth.permissions import Permission, ROLE_PERMISSIONS

5. src/ui/__init__.py
   from src.ui.theme import Colors, Fonts, setup_styles

6. src/ui/tabs/__init__.py — empty

7. src/ui/dialogs/__init__.py — empty

8. src/utils/__init__.py
   from src.utils.helpers import (
       generate_id, now_str, today_str, format_time,
       calculate_payment_fee, format_currency, safe_float, safe_int
   )
```

---

## PHASE 2: SPLIT MAIN.PY

### ✅ Task 2.1 — `src/ui/tabs/orders_tab.py`
Full `OrdersTab(ttk.Frame)`, left/right panel, status-coloured Treeview rows, live search + status filter, full order form with R&D toggle, items treeview, payment/totals with live recalc, three inline dialogs (`_ItemDialog`, `_WeightDialog`, `_TextDialog`), PDF stubs, permission-gated Delete button.

**To delete after cutover:** `_build_orders_tab` and all order-related methods from `main.py`.

---

### ⬜ Task 2.2 — `src/ui/tabs/customers_tab.py`

**Prompt:**
```
Create src/ui/tabs/customers_tab.py — Customer management tab.

Class CustomersTab(ttk.Frame):
    __init__(self, parent, db, auth, user)

Layout:
- Left panel: Customer Treeview with search bar
  - Columns: Name, Phone, Orders, Total Spent, Discount %
  - Search filters by name or phone (live, on keypress)

- Right panel: Customer detail / edit form
  - Fields: Name*, Phone, Email, Address, Notes (Text widget), Discount %
  - Stats row: Total Orders | Total Spent | Avg Order Value
  - Order history mini-Treeview: Order#, Date, Status, Total
  - Buttons: Save, Delete (admin-only), Clear

Public method: refresh() — reloads customer list from DB.

Use CustomerService for all data operations.
Use Colors and Fonts from src.ui.theme.
```

---

### ⬜ Task 2.3 — `src/ui/tabs/filament_tab.py`

**Prompt:**
```
Create src/ui/tabs/filament_tab.py — Filament inventory management.

Class FilamentTab(ttk.Frame):
    __init__(self, parent, db, auth, user)

Layout:
- Top: Active spools Treeview
  - Columns: Name, Color, Brand, Type, Initial(g), Current(g), Pending(g), Available(g), Status
  - Row colors: green if available > 200g, yellow if 20-200g, red if < 20g

- Bottom-left: Spool detail / add form
  - Fields: Name, Brand (default eSUN), Type (default PLA+), Color (dropdown)
  - Category radio: Standard (840 EGP / 1000g) | Remaining (custom weight, 0 cost)
  - Initial Weight, Purchase Price
  - Notes

- Bottom-right: Action buttons
  - Add New Spool
  - Save Changes
  - Use Filament (dialog: enter grams to deduct)
  - Move to Trash (only enabled if available < 20g)
  - View History (shows FilamentHistory in a Toplevel)
  - Manage Colors (add/view colors list)

Pending system note:
  - available = current - pending
  - Display all three: current, pending, available

Use InventoryService for all operations.
```

---

### ⬜ Task 2.4 — `src/ui/tabs/printers_tab.py`

**Prompt:**
```
Create src/ui/tabs/printers_tab.py — Printer management.

Class PrintersTab(ttk.Frame):
    __init__(self, parent, db, auth, user)

Layout:
- Left: Printer list Treeview
  - Columns: Name, Model, Total Printed (kg), Print Hours, Nozzle %, Active

- Right: Printer detail form
  - Fields: Name, Model, Purchase Price (EGP), Lifetime (kg)
  - Nozzle section: Cost per nozzle, Lifetime (g), Current usage (g, read-only)
  - Electricity Rate (EGP/hr)
  - Active checkbox
  - Stats section (read-only): Total Depreciation, Total Electricity, Total Nozzle Cost, Total Running Cost

- Buttons: Add New, Save, Reset Nozzle (records manual nozzle change), Deactivate

Use PrinterService for all operations.
Admin-only for add/edit/delete. All users can view.
```

---

### ⬜ Task 2.5 — `src/ui/tabs/failures_tab.py`

**Prompt:**
```
Create src/ui/tabs/failures_tab.py — Print failure tracking.

Class FailuresTab(ttk.Frame):
    __init__(self, parent, db, auth, user)

Layout:
- Top: Failures Treeview
  - Columns: Date, Source, Item, Reason, Filament (g), Time (min), Total Loss (EGP), Resolved
  - Resolved rows shown in green, unresolved in red

- Bottom: Summary stats bar
  - Total failures | Total cost | Total filament wasted | Unresolved count

- Buttons: Log Failure (opens dialog), Mark Resolved, Delete (admin-only), Refresh

Log Failure Dialog (Toplevel):
  - Source dropdown: Customer Order, R&D Project, Personal/Test, Other
  - If Customer Order: Order # field (optional link)
  - Item name, Reason dropdown, Description (Text)
  - Filament wasted (g), Time wasted (min), Color
  - Spool dropdown (active spools), Printer dropdown
  - Auto-calculated: Filament Cost + Electricity Cost = Total Loss (shown live)
  - Deduct from spool checkbox (default ON)

Use FinanceService for all operations.
```

---

### ⬜ Task 2.6 — `src/ui/tabs/expenses_tab.py`

**Prompt:**
```
Create src/ui/tabs/expenses_tab.py — Business expenses tracking.

Class ExpensesTab(ttk.Frame):
    __init__(self, parent, db, auth, user)

Layout:
- Left: Expenses Treeview
  - Columns: Date, Category, Name, Amount, Qty, Total, Supplier, Recurring
  - Group/color by category

- Right: Expense detail / add form
  - Category dropdown: Bills, Engineer, Tools, Consumables, Maintenance,
    Filament, Packaging, Shipping, Software, Other
  - Fields: Name*, Amount*, Quantity (default 1), Supplier, Description
  - Recurring checkbox + Period dropdown (Monthly / Yearly)
  - Auto-calc: Total = Amount × Quantity (shown live)
  - Date (defaults to today)

- Buttons: Save (add or update), Delete, Clear/New

- Bottom summary: Total Expenses | Breakdown by top 3 categories

IMPORTANT: Editing must work (not "delete and re-add"). Use FinanceService.update_expense().
```

---

### ⬜ Task 2.7 — `src/ui/tabs/stats_tab.py`

**Prompt:**
```
Create src/ui/tabs/stats_tab.py — Statistics dashboard.

Class StatsTab(ttk.Frame):
    __init__(self, parent, db, auth, user)

Admin-only tab. Show a Refresh button at top.

Display stat cards in a grid. Each card: colored header label + big number + unit/subtitle.

Sections:
1. Revenue — Total Revenue | Total Shipping | Payment Fees | Rounding Loss
2. Costs   — Material Cost | Electricity | Depreciation | Nozzle Cost
3. Profit  — Gross Profit | Net Profit | Profit Margin %
4. Production — Total Weight Printed | Total Print Time | Active Spools | Filament Remaining
5. Failures — Count | Total Cost | Filament Wasted (g) | Time Wasted
6. Expenses — Total | (top 3 categories)
7. Orders  — Total | Delivered | R&D | Cancelled
8. Customers — Total count

Use FinanceService.get_full_statistics() to populate.
Use Colors.SUCCESS for revenue cards, Colors.DANGER for cost cards, Colors.PRIMARY for production.
```

---

### ⬜ Task 2.8 — `src/ui/tabs/analytics_tab.py`

**Prompt:**
```
Create src/ui/tabs/analytics_tab.py — Visual analytics with matplotlib.

Class AnalyticsTab(ttk.Frame):
    __init__(self, parent, db, auth, user)

Only initializes if matplotlib is importable — show a "matplotlib not installed" message otherwise.

Date range filter at top: Last 30 Days | Last 90 Days | This Year | All Time

Charts (embed using FigureCanvasTkAgg, 2×2 grid):
1. Monthly Revenue — bar chart (revenue vs cost bars per month)
2. Order Status — pie chart
3. Profit Over Time — line chart (monthly net profit)
4. Expenses by Category — pie chart

Refresh button to redraw all charts.

Use FinanceService.get_monthly_breakdown() for time-series data.
Use Colors.PRIMARY, Colors.SUCCESS, Colors.DANGER for chart colors.
Admin-only tab.
```

---

### ⬜ Task 2.9 — `src/ui/tabs/settings_tab.py`

**Prompt:**
```
Create src/ui/tabs/settings_tab.py — Application settings.

Class SettingsTab(ttk.Frame):
    __init__(self, parent, db, auth, user)

Admin-only tab. Sections using LabelFrames:

1. Company Information
   - Company Name, Phone, Address (saves to settings table in DB)

2. Pricing Defaults
   - Default rate per gram (EGP), Spool price (EGP)

3. Quote / Invoice
   - Deposit %, Quote validity days

4. Data Management
   - Backup Database button → calls db.backup_database(), shows path
   - Export to CSV button → calls db.export_to_csv(), shows folder
   - Import from v4 JSON button → runs migration script

5. About
   - App version (from config.APP_VERSION)
   - Database stats: order count, customer count, spool count, DB file size

Save All Settings button at bottom.
Load settings from db.get_all_settings() on init.
```

---

### ⬜ Task 2.10 — `src/ui/app.py` + new `main.py`

**Prompt:**
```
Create two files:

1. src/ui/app.py — Main application window (< 200 lines)

class App:
    __init__(self, root: tk.Tk, user: User, db: DatabaseManager)

    - Configure window: title from config.APP_TITLE, icon from config.ICON_PATH
    - Call setup_styles(root) from theme
    - Header bar (dark): logo (Abaad.png), app title, user name + role badge, Logout button
    - Create ttk.Notebook
    - Add tabs based on user role:
        All users: Orders, Customers, Filament, Printers, Failures, Expenses
        Admin only: Stats, Analytics, Settings
    - Status bar (dark): "Orders: N | Spools: N | Revenue: X EGP | v5.0 | HH:MM"
    - _update_status_bar(): refresh every 60 seconds
    - _logout(): destroy window cleanly

2. main.py — Entry point (< 50 lines)

    from src.core.config import ensure_directories, DB_PATH
    from src.core.database import DatabaseManager
    from src.ui.dialogs.login_dialog import LoginDialog
    from src.ui.app import App

    def main():
        ensure_directories()
        root = tk.Tk()
        root.withdraw()
        db = DatabaseManager()
        login = LoginDialog(root, db)
        root.wait_window(login.dialog)
        if login.result:
            root.deiconify()
            App(root, login.result, db)
            root.mainloop()

    if __name__ == "__main__":
        main()
```

---

### ⬜ Task 2.11 — `src/ui/widgets.py`

**Prompt:**
```
Create src/ui/widgets.py — Reusable custom Tkinter widgets.

1. class SearchEntry(ttk.Entry)
   - Placeholder text ("Search...") shown in TEXT_MUTED color
   - Clears placeholder on focus, restores on blur if empty
   - .get_value() returns "" if placeholder is active

2. class StatCard(ttk.Frame)
   - __init__(self, parent, label, value, unit="", color=Colors.PRIMARY)
   - Shows: colored header strip | big number | unit label
   - .update(value) to refresh displayed number

3. class ScrollableTreeview(ttk.Frame)
   - Wraps Treeview + vertical Scrollbar in one widget
   - .tree property exposes the inner Treeview

4. class ConfirmDialog
   - __init__(self, parent, title, message)
   - Modal Toplevel with Yes / No buttons
   - .result: True if Yes, False if No/closed

5. class ActionButton(tk.Button)
   - Consistent styling using Colors and Fonts
   - .set_state("normal" | "disabled") helper

Use Colors and Fonts from src.ui.theme.
```

---

### ⬜ Task 2.12 — Extract dialogs to `src/ui/dialogs/`

**Prompt:**
```
Extract all popup dialogs from main.py into separate files.

Each dialog is a class with:
  - __init__(self, parent, ...) — creates modal Toplevel
  - .result — set to data dict on Save, None on Cancel
  - _center() — centers on screen
  - _on_save() / _on_cancel()

Files to create:

1. src/ui/dialogs/login_dialog.py
   - class LoginDialog — username + password form
   - Shows user list for quick-select OR manual entry
   - .result = User object or None

2. src/ui/dialogs/item_dialog.py
   - class ItemDialog — add/edit a PrintItem
   - Fields: Name, Estimated Weight (g), Print Time (min), Color (dropdown),
     Spool (dropdown filtered by color), Quantity, Rate (EGP/g), Notes
   - Print settings section: Nozzle, Layer Height, Infill %, Support Type, Scale
   - Cura import button: opens file picker for .gcode OR paste from clipboard
   - Live cost display: weight × qty × rate = X EGP
   - .result = PrintItem or None

3. src/ui/dialogs/spool_dialog.py
   - class SpoolDialog — add/edit a FilamentSpool
   - .result = dict of spool fields or None

4. src/ui/dialogs/expense_dialog.py
   - class ExpenseDialog — add/edit an Expense
   - .result = dict of expense fields or None

5. src/ui/dialogs/customer_dialog.py
   - class CustomerDialog — quick-add customer
   - Fields: Name, Phone only (minimal for speed)
   - .result = Customer or None

6. src/ui/dialogs/failure_dialog.py
   - class FailureDialog — log a print failure
   - All fields from Task 2.5 Log Failure section
   - .result = dict of failure fields or None
```

---

## PHASE 3: SERVICE LAYER ✅ COMPLETE

### ✅ Task 3.1 — `src/services/order_service.py`
Full pricing chain (11 steps), `get_order()` injects items, `calculate_totals()` authoritative in service, `_persist_order()` saves header + items atomically, `get_price_breakdown()`, `get_order_summary()`.

### ✅ Task 3.2 — `src/services/inventory_service.py`
Full pending system (reserve → commit / release), `move_to_trash()` creates `FilamentHistory` atomically, `get_inventory_summary()`, `get_spool_cost_report()`, `get_total_waste_grams()`.

### ✅ Task 3.3 — `src/services/customer_service.py`
`find_or_create()` (phone-first lookup), `update_customer_stats()` recalculates from live order data.

### ✅ Task 3.4 — `src/services/printer_service.py`
`record_print_job()` auto-increments nozzle changes at threshold, `reset_nozzle()`, `get_printer_stats()` full cost breakdown.

### ✅ Task 3.5 — `src/services/finance_service.py`
Expenses CRUD + `get_expense_stats()`, `log_failure()` auto-calculates + deducts filament, `resolve_failure()`, `get_full_statistics()` → `Statistics` dataclass, `get_monthly_breakdown(n)`, `get_profit_report(start, end)`. Bug #1 fixed: expense editing works.

---

## PHASE 4: FEATURE IMPROVEMENTS

### ⬜ Task 4.1 — `src/services/cura_service.py`

**Prompt:**
```
Create src/services/cura_service.py.

class CuraService:

    # PRIMARY — works without any extra libraries
    def parse_gcode_file(self, file_path: str) -> Optional[dict]:
        """Parse a Cura-generated .gcode file.
        Reads Cura header comments:
          ;TIME:14400          → time_seconds → time_minutes
          ;Filament used: 12.345m → filament_length_m
          ;WEIGHT:123          → weight_grams (if present)
          ;Layer height: 0.2   → layer_height
          ;Generated with Cura_SteamEngine X.X → cura_version
        If weight not in file, convert from length:
          weight = filament_length_to_grams(length_m) from helpers.py
        Returns: {time_minutes, weight_grams, filament_length_m, layer_height, cura_version}
        """

    def parse_gcode_text(self, text: str) -> Optional[dict]:
        """Same parsing but from a string (pasted content)."""

    # OPTIONAL — requires Pillow + pytesseract
    def extract_from_clipboard(self) -> Optional[dict]:
        """Screenshot OCR — only works if Tesseract installed."""

    def extract_from_image_file(self, path: str) -> Optional[dict]:
        """Image file OCR — only works if Tesseract installed."""

    def is_ocr_available(self) -> bool:
        """Return True if Pillow and pytesseract are importable."""
```

---

### ⬜ Task 4.2 — `src/services/pdf_service.py`

**Prompt:**
```
Create src/services/pdf_service.py — PDF generation with ReportLab.

class PdfService:
    __init__(self, db)

Methods:
1. generate_quote(order: Order) -> str
   - Professional quote PDF with company header, logo (Abaad.png), order items table,
     totals breakdown, validity period, deposit amount
   - Save to exports/Quote_ORDER#_DATE.pdf
   - Return the file path

2. generate_receipt(order: Order) -> str
   - Receipt PDF: order summary, items, payment method, amount paid, change
   - Save to exports/Receipt_ORDER#_DATE.pdf
   - Return the file path

3. generate_invoice(order: Order) -> str
   - Full invoice: company info, customer info, itemized table, tax if any
   - Save to exports/Invoice_ORDER#_DATE.pdf

Company header data from config.COMPANY dict.
Logo from config.LOGO_PATH (skip gracefully if file not found).
Use ReportLab's SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer.
All currency formatted with format_currency() from helpers.
```

---

### ⬜ Task 4.3 — UI Polish

**Prompt:**
```
Add UX improvements across all tabs:

1. Keyboard shortcuts (bind in App):
   - Ctrl+N: New order (switch to Orders tab + call new_order())
   - Ctrl+S: Save current form
   - Ctrl+F: Focus search bar of active tab
   - F5: Refresh active tab
   - Escape: Clear selection

2. Better validation in forms:
   - Highlight invalid fields with DANGER border color
   - Show validation error label under field (not messagebox)
   - Prevent save if required fields empty

3. Double-click to edit in all Treeviews

4. Right-click context menus:
   - Orders Treeview: Edit | Change Status | Generate Quote PDF | Generate Receipt PDF | Delete
   - Spools Treeview: Edit | Use Filament | Move to Trash
   - Customers Treeview: Edit | View Orders | Delete

5. Status bar "Saved ✓" feedback (show for 2 seconds after each save)
```

---

## PHASE 5: INSTALLATION & DISTRIBUTION

### ⬜ Task 5.1 — `scripts/install.py`
Cross-platform installer: checks Python version, creates venv, installs requirements, creates launch scripts.

### ⬜ Task 5.2 — `SETUP.bat` + `setup.sh`
Windows and macOS/Linux setup scripts.

### ⬜ Task 5.3 — `requirements.txt`
```
reportlab==4.1.0
Pillow==10.4.0
pytesseract==0.3.13
matplotlib==3.9.0
```

### ⬜ Task 5.4 — `README.md`
*(Generated separately — see project README)*

### ⬜ Task 5.5 — `pyproject.toml`
Standard Python project config with project metadata and optional dependencies.

---

## PHASE 6: TESTING

### ⬜ Task 6.1 — `tests/test_models.py`
All `to_dict()` / `from_dict()` roundtrips for every model.

### ⬜ Task 6.2 — `tests/test_order_service.py`
Pricing calculation: tolerance discount, R&D mode, payment fees, rate discount, order discount.

### ⬜ Task 6.3 — `tests/test_inventory_service.py`
Reserve → commit → release cycle, trash lifecycle, available weight calculation.

### ⬜ Task 6.4 — `tests/test_database.py`
CRUD for all tables, WAL mode, FK cascade, backup, export CSV.

### ⬜ Task 6.5 — `tests/test_migration.py`
Full v4 JSON → v5 SQLite round-trip, count validation.

---

## NOTES & DECISIONS LOG

| Date | Decision | Reason |
|------|----------|--------|
| | Keep Tkinter (not CustomTkinter) | Minimal dependencies, familiar to team |
| | SQLite over TinyDB | Real SQL, built-in, transactions, WAL |
| | Keep dataclasses (not SQLAlchemy) | Simpler, less overhead for desktop app |
| | Service layer pattern | Clean separation, testable without UI |
| | G-code parsing as primary Cura input | Works without Tesseract dependency |
| | Enums removed from models → string lists in config | DB string compatibility |
| | PrintItem flattened (no nested settings dict) | Matches SQLite schema directly |
| | calculate_totals() authoritative in service | Service owns business logic |
| | Users stored in SQLite (not users.json) | Single source of truth, transactions |
| | PRIMARY = #1e3a8a (not #2563eb) | Was inconsistent between files — unified |

---

## BUGS FIXED

| # | Description | File (v4) | Status |
|---|-------------|-----------|--------|
| 1 | Expense edit said "Delete and re-add" | main.py:2607 | ✅ Fixed in Task 3.5 |
| 2 | Colors class duplicated | login.py, admin_panel.py | ✅ Fixed in Task 1.2 |
| 3 | generate_id() duplicated with different impl | models.py, auth.py | ✅ Fixed in Task 1.3 |
| 4 | No validation before JSON save | database.py | ✅ Fixed in Task 1.4 |
| 5 | No cascade delete | database.py | ✅ Fixed with FK in SQLite |
| 6 | PRIMARY color inconsistent | login.py, admin_panel.py | ✅ Fixed in Task 1.2 |

---

## ⚡ NEXT UP

**Task 1.7** — `src/auth/auth_manager.py` split ← paste your current `auth.py` to start

Then in order:
1. **1.8** — `__init__.py` files
2. **2.2 → 2.6** — customers, filament, printers, failures, expenses tabs
3. **2.7 → 2.9** — stats, analytics, settings tabs
4. **2.10** — `app.py` + `main.py`
5. **2.11** — `widgets.py`
6. **2.12** — all dialogs
7. **4.1** — `cura_service.py`
8. **4.2** — `pdf_service.py`
9. **4.3** — UI polish
10. **5.x → 6.x** — install scripts + tests
