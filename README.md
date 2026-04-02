# Abaad 3D Print Manager — v5.0 ERP Edition

> Full-featured desktop ERP for a 3D printing service business.  
> Built with **Python + Tkinter + SQLite**. Runs on Windows, macOS, and Linux.  
> Currency: **EGP (Egyptian Pound)**. Business location: Ismailia, Egypt.

---

## What This System Does

Abaad ERP replaces spreadsheets and manual tracking for a 3D printing shop.
It manages the complete business workflow in one app:

- Take a customer order → track it through printing → deliver and record payment
- Manage filament spools and know exactly how much material is available
- Track print failures and their cost to the business
- Record business expenses and see true profit after all costs
- Generate professional PDF quotes and receipts

---

## Features at a Glance

### Orders
- Full order lifecycle: **Draft → Quote → Confirmed → In Progress → Ready → Delivered**
- Per-item pricing based on weight (EGP per gram), with quantity and rate override
- Tolerance discount: if actual weight is 1–5g heavier than estimated, one gram is discounted per unit automatically
- R&D mode: prices at cost only (material + electricity + depreciation), zero profit margin
- Order-level percentage discount on top of item discounts
- Payment methods: **Cash**, **Vodafone Cash** (0.5% fee), **InstaPay** (0.1% fee)
- Tracks shipping cost, amount received, and rounding loss
- Generate **Quote PDF** and **Receipt PDF** with one click
- **Text receipt** formatted for WhatsApp copy-paste

### Filament Inventory
- Two spool types: **Standard** (1 kg / 840 EGP) and **Remaining** (custom weight, zero cost — already paid for)
- **Pending reservation system**: reserve filament when order is confirmed, commit when printing starts, release if cancelled — prevents double-booking
- Available weight = current weight − pending weight at all times
- Spool lifecycle: active → low (below 20g) → trash → archived history
- Per-gram cost tracking for accurate profit calculation

### Customer Management
- Phone-number deduplication: entering an existing phone finds the customer automatically
- Per-customer discount percentage (applied to all their orders)
- Order history and lifetime spend visible per customer

### Printer Tracking
- Depreciation calculated per gram printed (purchase price ÷ lifetime kg)
- Nozzle wear tracking: auto-increments nozzle count after every 1,500g printed
- Electricity cost per job (0.31 EGP/hr by default)
- Full cost breakdown: depreciation + electricity + nozzle replacement per printer

### Finance
- **Expense log**: categorised business expenses (Bills, Engineer, Tools, Consumables, Maintenance, Filament, Packaging, Shipping, Software, Other)
- **Print failure log**: records failed prints with cost calculation and optional filament deduction from spool
- **Statistics dashboard**: revenue, all cost types, gross profit, net profit, profit margin
- **Analytics tab**: monthly revenue vs cost chart, failure trend, expense breakdown

### Users and Permissions
- Two roles: **Admin** (all permissions) and **User** (create/view/edit orders, manage customers, view inventory)
- Admin-only: delete orders, manage settings, view financial statistics, export data, system backup

### Cura Integration
- Import print time and filament weight directly from a `.gcode` file — no extra software needed
- Optional OCR: take a screenshot of Cura's preview and import parameters from the image (requires Tesseract + Pillow)

### PDF Generation
- Quote PDF with company header, logo, items table, validity period, and deposit amount
- Receipt PDF with payment method and change calculation
- Full invoice with itemised table

---

## Installation

### Requirements
- **Python 3.10 or later** (3.11 or 3.12 recommended)
- Windows (primary), macOS, or Linux

### Windows — Quick Install

```bat
git clone https://github.com/yourname/Abaad-3D-Print-Manager-V5.0-ERP-Edition
cd Abaad-3D-Print-Manager-V5.0-ERP-Edition
SETUP.bat
```

`SETUP.bat` will check Python, create a virtual environment, and install all dependencies automatically.

### macOS / Linux — Quick Install

```bash
git clone https://github.com/yourname/Abaad-3D-Print-Manager-V5.0-ERP-Edition
cd Abaad-3D-Print-Manager-V5.0-ERP-Edition
chmod +x setup.sh && ./setup.sh
```

### Manual Installation (any OS)

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate it
#    Windows:
venv\Scripts\activate
#    macOS / Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

**Current dependencies (`requirements.txt`):**
```
reportlab==4.4.1      # Required — PDF generation
Pillow==11.2.1        # Optional — Cura OCR screenshots
pytesseract==0.3.13   # Optional — Cura OCR screenshots
matplotlib==3.10.3    # Optional — Analytics tab charts
```

The app starts and runs fully without the optional packages.
OCR and chart features are silently disabled if the packages are missing.

---

## Running the App

### Windows
```bat
Launch_App.bat
```
Or manually:
```bat
venv\Scripts\activate
python main.py
```

### macOS / Linux
```bash
./launch.sh
```
Or manually:
```bash
source venv/bin/activate
python main.py
```

**Important:** Always run from the project root directory, not from inside `src/`.

---

## First-Time Setup

1. Launch the app. The login dialog appears.
2. Log in with the default Admin account (see `data/users.json` for credentials, or check `SETUP.bat` output).
3. Open the **Settings** tab and fill in your company name, phone, and address — these appear on all generated PDFs.
4. Add your filament spools in the **Filament** tab.
5. Add your printers in the **Printers** tab.
6. You are ready to take orders.

---

## How to Use

### Creating an Order

1. Open the **Orders** tab
2. Click **New** or press `Ctrl+N`
3. Enter the customer's name and phone number. If the customer already exists, their record is loaded automatically.
4. Set the order status (**Quote** for estimates, **Confirmed** for accepted orders)
5. Click **Add Item** for each part to be printed:
   - Enter item name, estimated weight in grams, estimated print time in minutes
   - Select filament colour and spool
   - Adjust quantity and rate per gram if needed
   - Click **Import from Cura** to fill weight and time automatically from a `.gcode` file
6. Set the payment method and enter any shipping cost
7. Enter the amount received — change is calculated automatically
8. Click **Save** — an order number is assigned automatically
9. Click **Quote PDF** or **Receipt PDF** to generate and open the document

### Changing an Order's Status

Select the order in the list, then click **Change Status** and pick the new status.
Status options: Draft → Quote → Confirmed → In Progress → Ready → Delivered (or Cancelled).

When an order moves to **In Progress**, filament reservations are committed to the spools automatically.
When an order is **Cancelled**, reserved filament is released back.

### Managing Filament Spools

1. Open the **Filament** tab
2. Click **Add New Spool**
   - Choose **Standard** for a fresh 1 kg spool (840 EGP, cost 0.84 EGP/g)
   - Choose **Remaining** for a partial spool you already own (enter current weight; cost is zero)
3. Select the filament colour
4. When a spool's available weight drops below 20g, a **Move to Trash** button appears — click it to retire the spool and move it to history

### Logging a Print Failure

1. Open the **Failures** tab
2. Click **Log Failure**
3. Select the failure reason and source
4. Enter how many grams were wasted and how many minutes of print time were lost
5. Costs are calculated automatically
6. Optionally tick **Deduct from spool** and select the spool to update inventory
7. Click **Save**

### Recording an Expense

1. Open the **Expenses** tab
2. Click **Add Expense**
3. Select a category, enter the name, amount, and quantity
4. Click **Save**

### Viewing Statistics

Open the **Statistics** tab (Admin only) to see:
- Total revenue, all cost types, gross and net profit
- Filament usage and active spool count
- Failure counts and total failure cost
- Order counts by status

Open the **Analytics** tab for monthly charts.

### Generating PDFs

From the Orders tab with an order selected:
- **Quote PDF** — professional estimate with items, totals, and validity note
- **Receipt PDF** — payment confirmation with change amount
- **Text Receipt** — plain text for WhatsApp, copied to clipboard

PDFs are saved to the `exports/` folder and opened automatically.

### Importing from Cura (G-code)

1. Slice your model in Cura and save the `.gcode` file anywhere on your computer
2. In the **Add Item** dialog, click **Import from Cura**
3. Browse to the `.gcode` file
4. Print time and filament weight are extracted automatically
5. Review the values and adjust if needed, then click **Save**

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New order (switches to Orders tab) |
| `Ctrl+S` | Save current form |
| `Ctrl+F` | Focus search box on current tab |
| `F5` | Refresh all tabs |
| `Escape` | Clear selection on current tab |

---

## User Roles

| Permission | Admin | User |
|------------|:-----:|:----:|
| Create / edit orders | ✅ | ✅ |
| Delete orders | ✅ | ❌ |
| Update order status | ✅ | ✅ |
| View customers | ✅ | ✅ |
| Manage customers | ✅ | ❌ |
| View filament inventory | ✅ | ✅ |
| Manage filament | ✅ | ❌ |
| View printers | ✅ | ✅ |
| Manage printers | ✅ | ❌ |
| Log print failures | ✅ | ❌ |
| Record expenses | ✅ | ❌ |
| Generate quote / receipt | ✅ | ✅ |
| View statistics | ✅ | ❌ |
| View financial data | ✅ | ❌ |
| Manage settings | ✅ | ❌ |
| Manage users | ✅ | ❌ |
| Export data | ✅ | ❌ |
| System backup | ✅ | ❌ |

---

## Configuration

### Company Information
Open **Settings** → **Company Information** to set:
- Company name, phone number, address
- These appear on all generated PDFs

### Pricing Defaults
Open **Settings** → **Pricing Defaults** to change:
- Default rate per gram (default: 4.00 EGP/g)
- Spool price (default: 840.00 EGP)

These are the starting values; each order item can override them.

### Business Constants (code-level)
Defined in `src/core/config.py`:

```python
DEFAULT_RATE_PER_GRAM       = 4.0      # EGP — selling price per gram
DEFAULT_COST_PER_GRAM       = 0.84     # EGP — material cost per gram
SPOOL_PRICE_FIXED           = 840.0    # EGP — 1 kg eSUN PLA+ spool
ELECTRICITY_RATE            = 0.31     # EGP per hour
DEFAULT_PRINTER_PRICE       = 25000.0  # EGP — Creality Ender-3 Max
DEFAULT_PRINTER_LIFETIME_KG = 500      # kg before retirement
NOZZLE_COST                 = 100.0    # EGP per nozzle
NOZZLE_LIFETIME_GRAMS       = 1500.0   # g printed per nozzle
TRASH_THRESHOLD_GRAMS       = 20       # g below which spool goes to trash
TOLERANCE_THRESHOLD_GRAMS   = 5        # max overweight that earns discount
```

---

## Pricing Formulas

**Per item:**
```
item_total = actual_weight × quantity × rate_per_gram − tolerance_discount
```

**Tolerance discount** (if actual weight is 1–5g over estimated):
```
tolerance_discount = 1 g × rate_per_gram × quantity
```

**Order totals:**
```
subtotal        = Σ items at base rate (4.00 EGP/g)
actual_total    = Σ items at their individual rates
order_discount  = actual_total × order_discount_pct / 100
after_discount  = actual_total − order_discount
payment_fee     = calculated by payment method (see table below)
final_total     = after_discount + shipping + payment_fee
```

**R&D orders (cost-only):**
```
final_total = material_cost + electricity_cost + depreciation_cost
```

**Profit per order:**
```
profit = after_discount − material_cost − electricity_cost − depreciation_cost
```

**Payment fees:**

| Method | Rate | Minimum | Maximum |
|--------|------|---------|---------|
| Cash | 0% | — | — |
| Vodafone Cash | 0.5% | 1.00 EGP | 15.00 EGP |
| InstaPay | 0.1% | 0.50 EGP | 20.00 EGP |

---

## Data Storage

| Item | Location |
|------|----------|
| Main database | `data/abaad_v5.db` (SQLite, WAL mode) |
| Automatic backups | `data/backups/` |
| Generated PDFs and CSV exports | `exports/` |
| v4 JSON source (for migration) | `data/abaad_v4.db.json` |
| App logo | `assets/Abaad.png` |
| App icon | `assets/Print3D_Manager.ico` |

### Backup

From the app: **Settings** tab → **Data Management** → **Backup Database**

Manual:
```bash
python -c "from src.core.database import get_database; get_database().backup_database()"
```

Backups are timestamped copies of the `.db` file.

### Export to CSV

**Settings** tab → **Data Management** → **Export to CSV**

Exports every table as a separate `.csv` file into the `exports/` folder.

---

## Migrating from v4

If you have an existing v4 JSON database:

```bash
python scripts/migrate_v4_to_v5.py
```

The script reads all v4 data and creates the v5 SQLite database at `data/abaad_v5.db`.
It prints a validation table comparing record counts. If any counts do not match, it exits with code 2.

To overwrite an existing v5 database:
```bash
python scripts/migrate_v4_to_v5.py --force
```

---

## Optional: Tesseract OCR (for Cura screenshot import)

> **Recommended:** Use `.gcode` file import instead — more accurate, needs no extra software.

If you want to import Cura parameters from a screenshot:

**Windows:**
1. Download Tesseract from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
2. Install to `C:\Program Files\Tesseract-OCR\`
3. Add that folder to the Windows PATH environment variable

**macOS:**
```bash
brew install tesseract
```

**Ubuntu / Debian:**
```bash
sudo apt install tesseract-ocr
```

Verify installation:
```bash
tesseract --version
```

---

## Troubleshooting

**App won't start — "No module named 'src'"**  
Run from the project root, not from inside a subfolder:
```bash
cd C:\Dan_WS\Abaad-3D-Print-Manager-V5.0-ERP-Edition
python main.py
```

**"database is locked" error**  
Another process has the `.db` file open. Close any SQLite browser tools (e.g. DB Browser for SQLite) and restart the app.

**Migration: count mismatch**  
```bash
python scripts/migrate_v4_to_v5.py --force
```

**Cura import shows 0g weight**  
The `.gcode` file may not contain a `;WEIGHT:` comment. The service will calculate weight from filament length instead. If the result looks wrong, confirm your material is PLA (density 1.24 g/cm³, diameter 1.75mm) in Cura.

**OCR not working**  
Confirm Tesseract is installed and on PATH: `tesseract --version`. If the command is not found, re-install and add it to PATH. Use `.gcode` import as the reliable alternative.

**PDF not opening after generation**  
The PDF is saved in the `exports/` folder. The app tries to open it with the system default PDF viewer. If that fails, open the file manually from the `exports/` folder.

**Statistics tab shows zeros**  
See `BUG_REPORT_AND_FIX_PLAN.md` — there are known dict key mismatches between the finance service and the stats tab that need to be patched.

---

## Project Structure

```
Abaad-3D-Print-Manager-V5.0-ERP-Edition/
├── assets/
│   ├── Abaad.png                  App logo (appears on PDFs)
│   └── Print3D_Manager.ico        Window icon
├── data/
│   ├── abaad_v5.db                SQLite database (WAL mode)
│   ├── abaad_v4.db.json           v4 source file (migration only)
│   └── backups/                   Timestamped backup copies
├── exports/                       Generated PDFs and CSV exports
├── scripts/
│   ├── install.py
│   └── migrate_v4_to_v5.py        v4 JSON → v5 SQLite migration
├── src/
│   ├── auth/
│   │   ├── auth_manager.py        AuthManager, User, get_auth_manager()
│   │   └── permissions.py         Permission enum, ROLE_PERMISSIONS dict
│   ├── core/
│   │   ├── config.py              All constants, paths, company defaults
│   │   ├── database.py            SQLite manager (WAL, FK, transactions)
│   │   └── models.py              Dataclass models with to_dict/from_dict
│   ├── services/
│   │   ├── order_service.py       Order CRUD and full pricing chain
│   │   ├── inventory_service.py   Filament spool management and pending system
│   │   ├── customer_service.py    Customer CRUD and find_or_create
│   │   ├── printer_service.py     Printer tracking and nozzle wear
│   │   ├── finance_service.py     Expenses, failures, and statistics
│   │   ├── pdf_service.py         ReportLab quote/receipt/invoice generation
│   │   └── cura_service.py        G-code parsing and optional OCR
│   ├── ui/
│   │   ├── app.py                 Main window, assembles all tabs
│   │   ├── theme.py               Colors, Fonts, setup_styles()
│   │   ├── widgets.py             Reusable UI widgets
│   │   ├── context_menu.py        Right-click menu helper
│   │   ├── dialogs/
│   │   │   ├── login_dialog.py
│   │   │   └── item_dialog.py
│   │   └── tabs/
│   │       ├── orders_tab.py
│   │       ├── customers_tab.py
│   │       ├── filament_tab.py
│   │       ├── printers_tab.py
│   │       ├── failures_tab.py
│   │       ├── expenses_tab.py
│   │       ├── stats_tab.py
│   │       ├── analytics_tab.py
│   │       └── settings_tab.py
│   └── utils/
│       └── helpers.py             generate_id, format_currency, format_time, etc.
├── tests/
│   ├── test_database.py
│   ├── test_inventory_service.py
│   ├── test_migration.py
│   ├── test_models.py
│   └── test_order_service.py
├── main.py                        Entry point (< 80 lines)
├── requirements.txt
├── BUG_REPORT_AND_FIX_PLAN.md    Known bugs and how to fix them
├── SETUP.bat                      Windows one-click install
├── setup.sh                       macOS/Linux one-click install
├── Launch_App.bat                 Windows launcher
└── launch.sh                      macOS/Linux launcher
```

### Architecture

```
UI Tabs  →  Services  →  DatabaseManager  →  SQLite
              ↑
           Models (dataclasses)
              ↑
           Config (constants)  ←  Helpers (utilities)
```

**Rules (do not break these):**
- UI tabs **never** contain business logic — they call services only
- Services contain **all** business rules
- The database layer returns plain Python dicts — services convert them to model objects
- `config.py` is the single source of truth for every constant and every path

---

## Contact

**Abaad 3D Printing Services**  
Ismailia, Egypt  
Phone: 01070750477  
Social: @abaad3d

---

## License

Private — internal business software. Not for redistribution.
