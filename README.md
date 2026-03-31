# Abaad 3D Print Manager — v5.0 ERP Edition

> **Full-featured desktop ERP for a 3D printing service business.**
> Built with Python + Tkinter + SQLite. Runs on Windows (primary), macOS, and Linux.
> Currency: EGP (Egyptian Pound). Business location: Ismailia, Egypt.

---

## Features

**Order Management**
- Full order lifecycle: Draft → Quote → Confirmed → In Progress → Ready → Delivered
- Per-item pricing with weight-based calculation (EGP per gram)
- Tolerance discount system (1–5g overweight → automatic 1g discount per unit)
- R&D mode: orders priced at cost only (material + electricity + depreciation), zero profit
- Order discount (%) on top of item-level discounts
- Payment methods: Cash, Vodafone Cash (0.5% fee), InstaPay (0.1% fee)
- Shipping cost, amount received, rounding loss tracking
- Quote and Receipt PDF generation
- Text receipt for WhatsApp copy-paste

**Filament Inventory**
- Standard spools (1 kg / 840 EGP) and Remaining spools (custom weight, 0 cost)
- Pending reservation system: reserve → commit → release
- available weight = current − pending (prevents double-booking)
- Spool lifecycle: active → low (< 20g) → trash → archived history
- Per-gram cost tracking for accurate profit calculation

**Customer Management**
- Phone-first deduplication via `find_or_create()`
- Per-customer discount percentage
- Order history and lifetime spend tracking

**Printer Tracking**
- Depreciation per gram (purchase price ÷ lifetime kg)
- Nozzle wear tracking with auto-increment at 1,500g threshold
- Electricity cost per job (0.31 EGP/hr)
- Full cost report: depreciation + electricity + nozzle replacement

**Finance**
- Expense categories: Bills, Engineer, Tools, Consumables, Maintenance, Filament, Packaging, Shipping, Software, Other
- Print failure log with cost calculation and filament deduction
- Statistics dashboard: revenue, costs, gross profit, net profit, profit margin
- Monthly breakdown for analytics charts

**Users & Permissions**
- Two roles: Admin (all permissions) and User (create/view/edit orders, manage customers, view inventory)
- Admin-only: delete orders, manage settings, view statistics, export data, system backup

**Cura Integration**
- Parse `.gcode` files directly — no Tesseract required
- Extracts: print time, filament weight (or calculates from length), layer height
- Optional OCR from clipboard screenshots (requires Tesseract + Pillow)

**PDF Generation** *(Phase 4)*
- Quote PDF with company header, logo, items table, validity period, deposit amount
- Receipt PDF with payment method and change
- Full invoice with itemized table

---

## Quick Start — Windows

```bat
git clone https://github.com/yourname/Abaad-3D-Print-Manager-V5.0-ERP-Edition
cd Abaad-3D-Print-Manager-V5.0-ERP-Edition
SETUP.bat
Launch_App.bat
```

`SETUP.bat` will:
1. Check Python 3.10+ is installed
2. Create a virtual environment (`venv/`)
3. Install all dependencies from `requirements.txt`
4. Create the data directory

## Quick Start — macOS / Linux

```bash
git clone https://github.com/yourname/Abaad-3D-Print-Manager-V5.0-ERP-Edition
cd Abaad-3D-Print-Manager-V5.0-ERP-Edition
chmod +x setup.sh && ./setup.sh
./launch.sh
```

---

## Manual Installation

**Requirements:** Python 3.10 or later

```bash
# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

**requirements.txt:**
```
reportlab==4.1.0
Pillow==10.4.0
pytesseract==0.3.13
matplotlib==3.9.0
```

> **Note:** `pytesseract` and `matplotlib` are optional. The app runs without them — OCR and analytics charts are simply disabled.

---

## Optional: Tesseract OCR

OCR lets you import print parameters by taking a screenshot of Cura instead of the `.gcode` file.

> **Recommended:** Use the `.gcode` file import instead — it is more accurate and needs no extra software.

**Windows:**
1. Download the Tesseract installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
2. Install to `C:\Program Files\Tesseract-OCR\`
3. Add that folder to your PATH environment variable

**macOS:**
```bash
brew install tesseract
```

**Ubuntu / Debian:**
```bash
sudo apt install tesseract-ocr
```

---

## Migrating from v4

If you have an existing v4 JSON database (`data/abaad_v4.db.json` and `data/users.json`):

```bash
python scripts/migrate_v4_to_v5.py
```

The script will:
- Read all data from the v4 JSON files
- Create the v5 SQLite database at `data/abaad_v5.db`
- Migrate all tables: customers, orders, print items, spools, printers, failures, expenses, history, colors, settings, users
- Print a validation table comparing source and destination counts
- Exit with code 2 if any counts do not match

To re-run and overwrite existing records:
```bash
python scripts/migrate_v4_to_v5.py --force
```

---

## How to Use

### Creating an Order

1. Open the **Orders** tab
2. Click **New** or press `Ctrl+N`
3. Enter customer name and phone — existing customers are found automatically
4. Set status to **Quote** or **Confirmed**
5. Click **Add Item** to add each printed part:
   - Enter item name, estimated weight (g), print time (min)
   - Select colour and spool
   - Adjust quantity and rate if needed
   - Click **Import from Cura** to fill from a `.gcode` file
6. Set payment method and shipping cost
7. Enter amount received to calculate change
8. Click **Save** — order number is assigned automatically
9. Click **Quote PDF** or **Receipt PDF** to generate documents

### Managing Filament

1. Open the **Filament** tab
2. Click **Add New Spool**:
   - **Standard**: 1 kg, 840 EGP — cost_per_gram = 0.84
   - **Remaining**: enter current weight, cost = 0 (already paid)
3. When a spool drops below 20g, a **Move to Trash** button appears
4. Trashed spools move to the history log with used/wasted weight recorded
5. Pending weight is reserved automatically when orders are confirmed — committed when printing starts

### Importing from Cura (G-code)

1. Slice your model in Cura and save the `.gcode` file
2. In the **Add Item** dialog, click **Import from Cura**
3. Browse to the `.gcode` file
4. Print time and filament weight are extracted automatically
5. Review and adjust before saving

### Logging a Print Failure

1. Open the **Failures** tab
2. Click **Log Failure**
3. Select source (customer order, R&D, personal/test)
4. Enter filament wasted and print time lost
5. Costs are calculated automatically
6. Check **Deduct from spool** to update inventory

---

## User Roles

| Permission | Admin | User |
|------------|-------|------|
| Create / edit orders | ✅ | ✅ |
| Delete orders | ✅ | ❌ |
| Update order status | ✅ | ✅ |
| View customers | ✅ | ✅ |
| Manage customers | ✅ | ❌ |
| View inventory | ✅ | ✅ |
| Manage inventory | ✅ | ❌ |
| Generate quote / receipt | ✅ | ✅ |
| View statistics | ✅ | ❌ |
| View financial data | ✅ | ❌ |
| Manage settings | ✅ | ❌ |
| Manage users | ✅ | ❌ |
| Export data | ✅ | ❌ |
| System backup | ✅ | ❌ |

---

## Configuration

### Company Settings

Open **Settings** tab → **Company Information**:
- Company Name, Phone, Address
- These appear on all generated PDFs

### Pricing Defaults

Open **Settings** tab → **Pricing Defaults**:
- Default rate per gram (default: 4.00 EGP/g)
- Spool price (default: 840.00 EGP)

These can be overridden per order item.

### Business Constants (code-level)

Defined in `src/core/config.py`:

```python
DEFAULT_RATE_PER_GRAM    = 4.0      # EGP — selling price per gram
DEFAULT_COST_PER_GRAM    = 0.84     # EGP — material cost per gram
SPOOL_PRICE_FIXED        = 840.0    # EGP — 1 kg eSUN PLA+ spool
ELECTRICITY_RATE         = 0.31     # EGP per hour
DEFAULT_PRINTER_PRICE    = 25000.0  # EGP — Creality Ender-3 Max
DEFAULT_PRINTER_LIFETIME_KG = 500   # kg before retirement
NOZZLE_COST              = 100.0    # EGP per nozzle
NOZZLE_LIFETIME_GRAMS    = 1500.0   # grams per nozzle
TRASH_THRESHOLD_GRAMS    = 20       # g below which "Move to Trash" appears
TOLERANCE_THRESHOLD_GRAMS = 5      # max overweight that earns discount
```

---

## Pricing Calculation

For each order item:

```
item_total = weight × qty × rate_per_gram − tolerance_discount
```

**Tolerance discount:** If actual weight is 1–5g MORE than estimated:
```
discount = 1g × rate × qty
```

**Order totals:**
```
subtotal        = Σ items at base rate (4.0 EGP/g)
actual_total    = Σ items at their rate (may be discounted)
rate_discount   = subtotal − actual_total
order_discount  = actual_total × order_discount_pct / 100
after_discount  = actual_total − order_discount
payment_fee     = calculate_payment_fee(after_discount, method)
final_total     = after_discount + shipping + payment_fee
```

**R&D mode:**
```
final_total = material_cost + electricity_cost + depreciation_cost
```

**Profit:**
```
profit = after_discount − material_cost − electricity_cost − depreciation_cost
```

**Payment fees:**
| Method | Rate | Min | Max |
|--------|------|-----|-----|
| Cash | 0% | — | — |
| Vodafone Cash | 0.5% | 1.00 EGP | 15.00 EGP |
| InstaPay | 0.1% | 0.50 EGP | 20.00 EGP |

---

## Data Storage

| Item | Location |
|------|----------|
| SQLite database | `data/abaad_v5.db` |
| Automatic backups | `data/backups/` |
| Generated PDFs | `exports/` |
| v4 JSON source | `data/abaad_v4.db.json` |
| App logo | `assets/Abaad.png` |
| App icon | `assets/Print3D_Manager.ico` |

### Backup

**From the app:** Settings tab → Data Management → **Backup Database**

**Manual:**
```bash
python -c "from src.core.database import DatabaseManager; DatabaseManager().backup_database()"
```

Backups are timestamped copies of the `.db` file placed in `data/backups/`.

### Export to CSV

Settings tab → Data Management → **Export to CSV**

Exports all tables as individual `.csv` files into the `exports/` folder.

---

## Project Structure

```
Abaad-3D-Print-Manager-V5.0-ERP-Edition/
├── assets/
│   ├── Abaad.png
│   └── Print3D_Manager.ico
├── data/
│   ├── abaad_v5.db              SQLite database (WAL mode)
│   ├── abaad_v4.db.json         v4 source (for migration)
│   └── backups/
├── exports/                     Generated PDFs and CSVs
├── scripts/
│   ├── install.py
│   └── migrate_v4_to_v5.py
├── src/
│   ├── auth/
│   │   ├── auth_manager.py      AuthManager, User, get_auth_manager()
│   │   └── permissions.py       Permission enum, ROLE_PERMISSIONS
│   ├── core/
│   │   ├── config.py            All constants, paths, company info
│   │   ├── database.py          SQLite manager (WAL, FK, transactions)
│   │   └── models.py            Dataclass models with to_dict/from_dict
│   ├── services/
│   │   ├── order_service.py     Order CRUD + full pricing chain
│   │   ├── inventory_service.py Filament spool + pending system
│   │   ├── customer_service.py  Customer CRUD + find_or_create
│   │   ├── printer_service.py   Printer tracking + nozzle wear
│   │   ├── finance_service.py   Expenses, failures, statistics
│   │   ├── pdf_service.py       ReportLab quote/receipt/invoice
│   │   └── cura_service.py      G-code parsing + optional OCR
│   ├── ui/
│   │   ├── app.py               Main window (< 200 lines)
│   │   ├── theme.py             Colors, Fonts, setup_styles()
│   │   ├── widgets.py           Reusable widgets
│   │   ├── dialogs/
│   │   │   ├── login_dialog.py
│   │   │   ├── item_dialog.py
│   │   │   ├── spool_dialog.py
│   │   │   ├── expense_dialog.py
│   │   │   ├── customer_dialog.py
│   │   │   └── failure_dialog.py
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
│       ├── helpers.py           generate_id, format_time, payment fee calc, etc.
│       └── migration.py
├── tests/
├── main.py                      Entry point (< 50 lines)
├── requirements.txt
├── SETUP.bat
├── setup.sh
├── Launch_App.bat
└── launch.sh
```

### Architecture

```
UI Tabs  →  Services  →  DatabaseManager  →  SQLite
              ↑
           Models (dataclasses)
              ↑
           Config (constants)  ←  Helpers (utilities)
```

**Rules:**
- UI code **never** does business logic — tabs call services, services call database
- Services contain **all** business rules
- Database returns plain dicts — services convert to model objects
- Config is the single source of truth for every constant and path

---

## Troubleshooting

**App won't start — "No module named 'src'"**
Make sure you run from the project root:
```bash
cd C:\Dan_WS\Abaad-3D-Print-Manager-V5.0-ERP-Edition
python main.py
```

**"database is locked" error**
Another process has the database open. Close any SQLite browser tools and restart the app. The database runs in WAL mode, which allows concurrent reads, but only one writer at a time.

**Migration: count mismatch**
Run with `--force` to overwrite partially-migrated records:
```bash
python scripts/migrate_v4_to_v5.py --force
```

**Cura import shows 0g weight**
The `.gcode` file may not contain a `;WEIGHT:` line. The service will calculate weight from filament length instead. If the result looks wrong, check that the material is PLA (density 1.24 g/cm³) and diameter is 1.75mm — other materials may need a manual override.

**OCR not working**
Confirm Tesseract is installed and on PATH:
```bash
tesseract --version
```
If the command is not found, re-install Tesseract and add its folder to the PATH environment variable. Use the `.gcode` file import as a more reliable alternative.

**PDF not opening after generation**
The PDF is saved to the `exports/` folder. The app attempts to open it with the system default viewer (`os.startfile` on Windows, `open` on macOS, `xdg-open` on Linux). If that fails, open the file manually from the `exports/` folder.

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Follow the architecture rules in `CLAUDE_PROJECT_INSTRUCTIONS.md`
4. Run the test suite: `pytest tests/`
5. Submit a pull request

**Code style:**
- Type hints on all function signatures
- Docstrings on all public methods
- f-strings for string formatting
- `pathlib.Path` for all file paths
- Catch specific exceptions, not bare `except:`

---

## Contact

**Abaad 3D Printing Services**
Ismailia, Egypt
Phone: 01070750477
Social: @abaad3d

---

## License

Private — internal business software. Not for redistribution.
