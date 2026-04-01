# Abaad v5.0 — Refactoring Progress Tracker

> **How to use:** Work top-to-bottom. Fix bugs first (app won't start without them).
> Each task has a ready-to-paste prompt for a new Claude chat.

---

## STATUS DASHBOARD

| Phase | Tasks | Done | Status |
|-------|-------|------|--------|
| 1. Foundation | 8 | 8 | ✅ Complete |
| 2. Split main.py | 12 | 12 | ✅ Complete |
| 3. Service Layer | 5 | 5 | ✅ Complete |
| 4. Features | 3 | 2 | 🟡 In Progress |
| 5. Installation | 5 | 0 | ⬜ Not Started |
| 6. Testing | 5 | 0 | ⬜ Not Started |
| **TOTAL** | **38** | **27** | **71%** |

---

## ⚡ IMMEDIATE ACTION REQUIRED — Fix these before anything else

The app will not start until bugs A–D are fixed. Apply in order.
All fixes are small edits, not rewrites. See FIX.md for exact code.

| # | Bug | File to edit | Fix type |
|---|-----|-------------|----------|
| A | `_compat.py` patches v4 JSON DB; current DB is v5 SQLite | `src/services/_compat.py` + `main.py` | Delete file + remove 3 lines |
| B | `_load_from_db()` calls `execute_query` (not in DB) | `src/auth/auth_manager.py` | 1-line change |
| C | `_save_user_to_db()` calls `execute_update` (not in DB) | `src/auth/auth_manager.py` | Replace 2 methods |
| D | `stats_tab.py` reads wrong key names from `get_full_statistics()` | `src/services/finance_service.py` | Replace return statement |

After A–D: `python main.py` should open the login dialog with no errors.

---

## 🗂 FILE INVENTORY

### ✅ Files confirmed on disk and correct

| File | Path |
|------|------|
| config.py | `src/core/config.py` |
| theme.py | `src/ui/theme.py` |
| helpers.py | `src/utils/helpers.py` |
| database.py | `src/core/database.py` |
| migrate_v4_to_v5.py | `scripts/migrate_v4_to_v5.py` |
| models.py | `src/core/models.py` |
| _model_aliases.py | `src/core/_model_aliases.py` |
| auth_manager.py | `src/auth/auth_manager.py` — needs Bug B + C fixes |
| permissions.py | `src/auth/permissions.py` |
| order_service.py | `src/services/order_service.py` |
| inventory_service.py | `src/services/inventory_service.py` |
| customer_service.py | `src/services/customer_service.py` |
| printer_service.py | `src/services/printer_service.py` |
| finance_service.py | `src/services/finance_service.py` — needs Bug D fix |
| cura_service.py | `src/services/cura_service.py` |
| orders_tab.py | `src/ui/tabs/orders_tab.py` |
| customers_tab.py | `src/ui/tabs/customers_tab.py` |
| filament_tab.py | `src/ui/tabs/filament_tab.py` |
| printers_tab.py | `src/ui/tabs/printers_tab.py` |
| failures_tab.py | `src/ui/tabs/failures_tab.py` |
| expenses_tab.py | `src/ui/tabs/expenses_tab.py` |
| stats_tab.py | `src/ui/tabs/stats_tab.py` |
| analytics_tab.py | `src/ui/tabs/analytics_tab.py` |
| settings_tab.py | `src/ui/tabs/settings_tab.py` |
| app.py | `src/ui/app.py` |
| login_dialog.py | `src/ui/dialogs/login_dialog.py` |
| item_dialog.py | `src/ui/dialogs/item_dialog.py` |
| widgets.py | `src/ui/widgets.py` |
| main.py | `main.py` — needs Bug A fix |

### ❌ Files to delete

| File | Why |
|------|-----|
| `src/services/_compat.py` | Bug A — patches wrong DB version, causes crash |
| `src/core/_model_aliases.py` | No longer needed — v5 models have correct field names natively |
| Everything in `/files/` folder | Stale duplicates from earlier sessions — entire folder can be deleted |

### ⚠️ Files needing rewrite

| File | Problem | Task |
|------|---------|------|
| `src/services/pdf_service.py` | Contains CuraService code instead of PdfService | Task 4.2 |

### 🆕 Files missing from disk (need to be created)

| File | Used by | Priority | Phase |
|------|---------|----------|-------|
| `src/utils/migration.py` | `settings_tab.py` "Import v4" button | Medium | Now |
| `src/__init__.py` | Python package structure | High | Now |
| `tests/__init__.py` | Test runner | Low | Phase 6 |
| `tests/test_models.py` | CI | Low | Phase 6 |
| `tests/test_order_service.py` | CI | Low | Phase 6 |
| `tests/test_inventory_service.py` | CI | Low | Phase 6 |
| `tests/test_database.py` | CI | Low | Phase 6 |
| `tests/test_migration.py` | CI | Low | Phase 6 |
| `scripts/install.py` | End users | Medium | Phase 5 |
| `SETUP.bat` | End users (Windows) | Medium | Phase 5 |
| `setup.sh` | End users (macOS/Linux) | Medium | Phase 5 |
| `Launch_App.bat` | End users (Windows) | Medium | Phase 5 |
| `launch.sh` | End users (macOS/Linux) | Medium | Phase 5 |
| `requirements.txt` | pip install | High | Phase 5 |
| `README.md` | Everyone | Medium | Phase 5 |
| `pyproject.toml` | Packaging | Low | Phase 5 |

---

## RECOMMENDED NEXT-CHAT ORDER

```
Chat 1 — Bug fixes A+B+C+D       (small edits, app runs after)
Chat 2 — Task 4.2: pdf_service.py (write from scratch)
Chat 3 — Missing: src/utils/migration.py + src/__init__.py
Chat 4 — Task 4.3: UI Polish
Chat 5 — Phase 5: Installation files
Chat 6 — Phase 6: Tests
```

---

## PHASE 1: FOUNDATION ✅ COMPLETE

### ✅ 1.1 `src/core/config.py`
### ✅ 1.2 `src/ui/theme.py`
### ✅ 1.3 `src/utils/helpers.py`
### ✅ 1.4 `src/core/database.py` — v5 SQLite
### ✅ 1.5 `scripts/migrate_v4_to_v5.py`
### ✅ 1.6 `src/core/models.py`
### ✅ 1.7 `src/auth/auth_manager.py` + `permissions.py` — needs Bug B+C fixes
### ✅ 1.8 All `__init__.py` files — `src/__init__.py` still needed

---

## PHASE 2: SPLIT MAIN.PY ✅ COMPLETE

### ✅ 2.1 `src/ui/tabs/orders_tab.py`
### ✅ 2.2 `src/ui/tabs/customers_tab.py`
### ✅ 2.3 `src/ui/tabs/filament_tab.py`
### ✅ 2.4 `src/ui/tabs/printers_tab.py`
### ✅ 2.5 `src/ui/tabs/failures_tab.py`
### ✅ 2.6 `src/ui/tabs/expenses_tab.py`
### ✅ 2.7 `src/ui/tabs/stats_tab.py`
### ✅ 2.8 `src/ui/tabs/analytics_tab.py`
### ✅ 2.9 `src/ui/tabs/settings_tab.py`
### ✅ 2.10 `src/ui/app.py` + `main.py`
### ✅ 2.11 `src/ui/widgets.py`
### ✅ 2.12 `src/ui/dialogs/login_dialog.py` + `item_dialog.py`

---

## PHASE 3: SERVICE LAYER ✅ COMPLETE

### ✅ 3.1 `src/services/order_service.py`
### ✅ 3.2 `src/services/inventory_service.py`
### ✅ 3.3 `src/services/customer_service.py`
### ✅ 3.4 `src/services/printer_service.py`
### ✅ 3.5 `src/services/finance_service.py`

---

## PHASE 4: FEATURE IMPROVEMENTS 🟡 IN PROGRESS

### ✅ 4.1 `src/services/cura_service.py`

### ⬜ 4.2 — Write `src/services/pdf_service.py` from scratch ← NEXT

**Problem:** Current file on disk contains CuraService code, not PdfService.
Must be completely rewritten.

**Paste these files into the next chat:**
- `src/core/config.py`
- `src/core/models.py`
- `src/utils/helpers.py`

**Prompt:**
```
Create src/services/pdf_service.py — PDF generation with ReportLab.

class PdfService:
    def __init__(self, db=None)  # db used to read company settings

Methods:

1. generate_quote(order: Order) -> str
   - A4 PDF: company header + logo (assets/Abaad.png, skip if missing),
     customer section, items table, totals section with deposit amount,
     quote validity date (quote_validity_days from DB settings, default 7)
   - Save to exports/Quote_<order_number>_<YYYYMMDD_HHMMSS>.pdf
   - Return file path string

2. generate_receipt(order: Order) -> str
   - A4 PDF: company header, customer section, items table,
     payment method, amount received, change given
   - Save to exports/Receipt_<order_number>_<YYYYMMDD_HHMMSS>.pdf
   - Return file path string

3. generate_text_receipt(order: Order) -> str
   - Returns plain text string (no file) for WhatsApp copy-paste
   - Format: company name, order number, items list, total, payment info

4. open_file(path: str) -> None
   - Opens the PDF with the system default viewer
   - os.startfile on Windows, subprocess open/xdg-open elsewhere

Rules:
- If reportlab is not installed raise RuntimeError with install instructions
- Company data from src.core.config.COMPANY dict
- Logo from src.core.config.LOGO_PATH (try/except — skip if not found)
- All money formatted with format_currency() from src.utils.helpers
- EXPORT_DIR from src.core.config, create it if missing
- order.items is a list of PrintItem objects
- PrintItem fields: name, color, estimated_weight_grams, quantity,
  rate_per_gram, print_cost, tolerance_discount_applied, tolerance_discount_amount
- Order totals fields: subtotal, actual_total, discount_amount,
  order_discount_percent, order_discount_amount, tolerance_discount_total,
  shipping_cost, payment_method, payment_fee, total, amount_received,
  rounding_loss, is_rd_project, order_number, customer_name, customer_phone,
  created_date, status

Items table columns: #, Description, Color, Qty, Weight(g), Rate/g, Total
Totals section rows (show only non-zero rows):
  Base total (4 EGP/g)
  Rate discount (if > 0)
  Order discount % (if > 0)
  Tolerance discounts (if > 0)
  ─────────────
  Subtotal
  Shipping (if > 0)
  Payment fee (if > 0)
  ═════════════
  TOTAL (bold, large)
  [Quote only] Deposit required (deposit_pct% of total)
  [Quote only] Balance on delivery
  [Receipt only] Amount received
  [Receipt only] Change

Footer: company tagline, phone, address, social handle
        "Generated by Abaad ERP v5.0 — <timestamp>"

Use these exact ReportLab imports (no others needed):
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from reportlab.lib import colors as rl_colors
```

---

### ⬜ 4.3 — UI Polish

**Prompt:**
```
Add these UX improvements across all v5 tabs. Work through each file and add:

1. Keyboard shortcuts (bind on the root window in app.py):
   Ctrl+N → new order (calls orders_tab.new_order())
   Ctrl+S → save current form
   Ctrl+F → focus the search entry on the active tab
   F5     → refresh all tabs
   Escape → clear selection / close dialog

2. Double-click to edit in all Treeviews
   Each tab already has an _edit_* method — bind <Double-1> to call it

3. Right-click context menus on Treeviews:
   Orders: Edit, Change Status, Generate Quote PDF, Generate Receipt PDF, Delete
   Customers: Edit, View Orders, Delete
   Filament: Edit, Move to Trash
   Failures: Delete
   Expenses: Edit, Delete

4. Inline validation:
   Required fields turn border red on failed save attempt
   Error message appears below the field (not a messagebox)
   Clears when user starts typing

5. Status bar "Saved ✓" flash:
   After any successful save, status bar shows "Saved ✓" in green for 2 seconds
   then reverts to normal counts

Paste these files:
  src/ui/app.py
  src/ui/tabs/orders_tab.py
  src/ui/tabs/customers_tab.py
  src/ui/tabs/filament_tab.py
```

---

## PHASE 5: INSTALLATION & DISTRIBUTION ⬜ NOT STARTED

### ⬜ 5.1 — `scripts/install.py`

**Prompt:**
```
Create scripts/install.py — cross-platform installer, stdlib only.

Steps:
1. Check Python >= 3.10; print error and exit if not
2. Create venv/ in project root
3. Install requirements.txt into venv
4. Check if data/abaad_v5.db exists
   If not and data/abaad_v4.db.json exists: run migration automatically
   If neither exists: create empty DB
5. Print success summary with launch instructions

Output style: colored terminal (use ANSI codes, with fallback for Windows cmd)
No third-party dependencies — stdlib only (subprocess, venv, sys, os, pathlib)
```

### ⬜ 5.2 — `SETUP.bat` + `setup.sh` + `Launch_App.bat` + `launch.sh`

**Prompt:**
```
Create 4 shell scripts for the project root:

SETUP.bat (Windows):
  @echo off
  Runs: python scripts/install.py
  If python not found, shows download URL

setup.sh (macOS/Linux):
  #!/bin/bash
  Runs: python3 scripts/install.py
  chmod +x launch.sh after running

Launch_App.bat (Windows):
  @echo off
  Activates venv\Scripts\activate
  Runs: python main.py
  Keeps window open on error

launch.sh (macOS/Linux):
  #!/bin/bash
  Activates source venv/bin/activate
  Runs: python main.py
```

### ⬜ 5.3 — `requirements.txt`

```
reportlab>=4.1.0
Pillow>=10.4.0
pytesseract>=0.3.13
matplotlib>=3.9.0
```

### ⬜ 5.4 — `README.md`

**Prompt:**
```
Write README.md for Abaad 3D Print Manager v5.0.

Sections:
1. Title + one-line description
2. Features list (from README already in repo — update for v5)
3. Quick Start: Windows (SETUP.bat → Launch_App.bat), macOS/Linux (setup.sh → launch.sh)
4. Manual install steps
5. Optional: Tesseract OCR setup (link to UB Mannheim for Windows)
6. Migrating from v4 (python scripts/migrate_v4_to_v5.py)
7. User roles table (Admin vs User permissions)
8. Business rules summary (pricing formula, filament system)
9. Data locations table (DB, exports, backups)
10. Troubleshooting FAQ (5 most common issues)
11. Project structure (abbreviated tree)
12. Contact: Abaad 3D Printing Services, Ismailia, Egypt, 01070750477
```

### ⬜ 5.5 — `pyproject.toml`

```
[build-system] + [project] with name, version, python requires >=3.10,
dependencies list, [project.scripts] entry point for main.py
```

---

## PHASE 6: TESTING ⬜ NOT STARTED

### ⬜ 6.1 — `tests/test_models.py`

**Prompt:**
```
Create tests/test_models.py with pytest.

Test these with to_dict() / from_dict() roundtrips:
  Order, PrintItem, Customer, FilamentSpool, Printer, PrintFailure, Expense

Also test Order.calculate_totals() with these scenarios:
  - Single item, cash payment, no discounts
  - Two items with different rates (rate discount auto-calculated)
  - Item with tolerance discount (actual_weight 3g over estimate)
  - R&D mode order (total = material + electricity + depreciation)
  - VodaCash payment fee (0.5%, min 1, max 15)
  - InstaPay payment fee (0.1%, min 0.50, max 20)
  - Order discount 10% on top of rate discount
```

### ⬜ 6.2 — `tests/test_order_service.py`

**Prompt:**
```
Create tests/test_order_service.py with pytest.

Use an in-memory SQLite DB (DB_PATH = ":memory:").

Test:
  create_order() creates correct order number sequence
  add_item() calculates totals
  update_status() changes status
  delete_order() soft-deletes
  search_orders() returns matching results
  calculate_totals() matches the pricing rules
```

### ⬜ 6.3 — `tests/test_inventory_service.py`

**Prompt:**
```
Create tests/test_inventory_service.py with pytest.

Test:
  add_spool() standard and remaining categories
  reserve_filament() reduces available_weight
  commit_filament() reduces current_weight
  release_filament() restores available_weight
  move_to_trash() creates history record
  get_inventory_summary() totals are correct
```

### ⬜ 6.4 — `tests/test_database.py`

**Prompt:**
```
Create tests/test_database.py with pytest using in-memory SQLite.

Test all CRUD methods: save/get/delete for each table.
Test WAL mode is enabled.
Test foreign key constraints are on.
Test backup_database() creates a file.
Test export_to_csv() creates CSV files.
```

### ⬜ 6.5 — `tests/test_migration.py`

**Prompt:**
```
Create tests/test_migration.py with pytest.

Create a minimal v4 JSON fixture (2 orders, 2 customers, 2 spools, 1 printer).
Run the migration to an in-memory SQLite DB.
Assert all record counts match.
Assert key fields (order_number, customer_name, spool color) are preserved.
```

---

## BUGS LOG

| # | Description | File | Status |
|---|-------------|------|--------|
| 1 | Expense edit said "Delete and re-add" | main.py v4 | ✅ Fixed in 3.5 |
| 2 | Colors class duplicated | login.py, admin_panel.py | ✅ Fixed in 1.2 |
| 3 | generate_id() duplicated with different impl | models.py, auth.py | ✅ Fixed in 1.3 |
| 4 | No validation before JSON save | database.py | ✅ Fixed in 1.4 |
| 5 | No cascade delete | database.py | ✅ Fixed with FK in SQLite |
| 6 | PRIMARY color inconsistent | login.py, admin_panel.py | ✅ Fixed in 1.2 |
| A | `_compat.py` patches v4 DB; current DB is v5 SQLite → crash | `_compat.py` + `main.py` | ❌ Fix: delete file |
| B | `_load_from_db()` calls `execute_query` (not in v5 DB) | `auth_manager.py` | ❌ Fix: 1-line change |
| C | `_save_user_to_db()` calls `execute_update` (not in v5 DB) | `auth_manager.py` | ❌ Fix: replace 2 methods |
| D | `stats_tab` uses wrong dict keys from `get_full_statistics()` | `finance_service.py` | ❌ Fix: change return |
| E | `pdf_service.py` contains CuraService code instead of PdfService | `pdf_service.py` | ❌ Task 4.2: full rewrite |

---

## DECISIONS LOG

| Decision | Reason |
|----------|--------|
| Keep Tkinter | Minimal dependencies, familiar to team |
| SQLite + WAL mode | Real SQL, built-in, concurrent reads |
| Keep dataclasses | Simpler than SQLAlchemy for desktop app |
| Service layer pattern | Clean separation, testable without UI |
| G-code parsing as primary Cura input | Works without Tesseract dependency |
| Enums → string lists in config.py | DB string compatibility, simpler |
| PrintItem flattened (no nested settings dict) | Matches SQLite schema directly |
| Users stored in SQLite (not users.json) | Single source of truth, transactions |
| Delete _compat.py | Written for v4 JSON DB; v5 SQLite has all methods natively |
| PRIMARY = #1e3a8a | Was #2563eb in some files — unified |