"""
src/core/config.py
==================
Single source of truth for all constants, paths, and company info.
Abaad 3D Print Manager — v5.0
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Project Paths
# ---------------------------------------------------------------------------

# Resolves to the folder containing main.py, regardless of cwd
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent

DATA_DIR:    Path = PROJECT_ROOT / "data"
DB_PATH:     Path = DATA_DIR    / "abaad_v5.db"
OLD_JSON_DB: Path = DATA_DIR    / "abaad_v4.db.json"
OLD_USERS_JSON: Path = DATA_DIR / "users.json"

EXPORT_DIR:  Path = PROJECT_ROOT / "exports"
BACKUP_DIR:  Path = DATA_DIR     / "backups"
ASSETS_DIR:  Path = PROJECT_ROOT / "assets"
LOGO_PATH:   Path = ASSETS_DIR   / "Abaad.png"
ICON_PATH:   Path = ASSETS_DIR   / "Print3D_Manager.ico"

# ---------------------------------------------------------------------------
# App Metadata
# ---------------------------------------------------------------------------

APP_NAME:    str = "Abaad ERP"
APP_VERSION: str = "5.0"
APP_TITLE:   str = f"{APP_NAME} v{APP_VERSION}"

# ---------------------------------------------------------------------------
# Company Info
# ---------------------------------------------------------------------------

COMPANY: dict = {
    "name":     "Abaad",
    "subtitle": "3D Printing Services",
    "phone":    "01070750477",
    "address":  "Ismailia, Egypt",
    "tagline":  "Quality 3D Printing Solutions",
    "social":   "@abaad3d",
}

# ---------------------------------------------------------------------------
# Business Constants
# ---------------------------------------------------------------------------

DEFAULT_RATE_PER_GRAM: float  = 4.0      # EGP — selling price per gram
DEFAULT_COST_PER_GRAM: float  = 0.84     # EGP — material cost (840 EGP / 1000 g)
SPOOL_PRICE_FIXED:     float  = 840.0    # EGP — cost of one 1 kg eSUN PLA+ spool

DEFAULT_NOZZLE:        float  = 0.4      # mm
DEFAULT_LAYER_HEIGHT:  float  = 0.2      # mm

TRASH_THRESHOLD_GRAMS:     int   = 20    # Below this → suggest "Move to Trash"
TOLERANCE_THRESHOLD_GRAMS: int   = 5     # Max extra grams that qualify for discount

ELECTRICITY_RATE:          float = 0.31  # EGP per hour of printing

DEFAULT_PRINTER_PRICE:        float = 25_000.0   # EGP — Creality Ender-3 Max
DEFAULT_PRINTER_LIFETIME_KG:  int   = 500        # Expected lifetime in kg

NOZZLE_COST:           float = 100.0   # EGP per nozzle
NOZZLE_LIFETIME_GRAMS: float = 1_500.0 # Grams per nozzle before replacement

# ---------------------------------------------------------------------------
# Payment Fees
# ---------------------------------------------------------------------------

PAYMENT_FEES: dict = {
    "Cash":          {"rate": 0.000, "min": 0.00, "max": 0.00},
    "Vodafone Cash": {"rate": 0.005, "min": 1.00, "max": 15.00},
    "InstaPay":      {"rate": 0.001, "min": 0.50, "max": 20.00},
}

# ---------------------------------------------------------------------------
# Default Seed Data
# ---------------------------------------------------------------------------

DEFAULT_COLORS: list[str] = [
    "Black", "Light Blue", "Silver", "White", "Red", "Beige", "Purple",
]

DEFAULT_SETTINGS: dict = {
    "company_name":       COMPANY["name"],
    "company_phone":      COMPANY["phone"],
    "company_address":    COMPANY["address"],
    "default_rate_per_gram": str(DEFAULT_RATE_PER_GRAM),
    "next_order_number":  "1",
    "deposit_percent":    "50",
    "quote_validity_days": "7",
}

# ---------------------------------------------------------------------------
# Enums (string values — must stay compatible with DB and JSON)
# ---------------------------------------------------------------------------

ORDER_STATUSES: list[str] = [
    "Draft", "Quote", "Confirmed", "In Progress",
    "Ready", "Delivered", "Cancelled",
]

PAYMENT_METHODS: list[str] = ["Cash", "Vodafone Cash", "InstaPay"]

SUPPORT_TYPES: list[str] = ["None", "Normal", "Tree"]

SPOOL_CATEGORIES: list[str] = ["standard", "remaining"]
SPOOL_STATUSES:   list[str] = ["active", "low", "trash", "archived"]

FAILURE_REASONS: list[str] = [
    "Nozzle Clog", "Bed Adhesion", "Layer Shift", "Filament Tangle",
    "Power Outage", "Stringing/Blobs", "Warping", "Under Extrusion",
    "Over Extrusion", "Broken Part", "Wrong Settings", "Filament Ran Out",
    "Machine Error", "Other",
]

EXPENSE_CATEGORIES: list[str] = [
    "Bills", "Engineer", "Tools", "Consumables", "Maintenance",
    "Filament", "Packaging", "Shipping", "Software", "Other",
]

FAILURE_SOURCES: list[str] = [
    "Customer Order", "R&D Project", "Personal/Test", "Other",
]

USER_ROLES: list[str] = ["Admin", "User"]

# ---------------------------------------------------------------------------
# Directory Bootstrap
# ---------------------------------------------------------------------------

def ensure_directories() -> None:
    """Create all runtime directories if they do not exist.

    Call once at application startup before any file I/O.
    """
    for directory in (DATA_DIR, EXPORT_DIR, BACKUP_DIR):
        directory.mkdir(parents=True, exist_ok=True)