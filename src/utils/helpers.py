"""
src/utils/helpers.py  — v5.0  (drop-in replacement)
====================================================
All utility functions in one place.

Added in v5:
  format_time_minutes()  — alias for format_time() used by new tabs
  safe_float / safe_int  — already existed
  filament_length_to_grams — already existed
"""

import math
import uuid
from datetime import datetime
from typing import Optional

from src.core.config import PAYMENT_FEES


# ---------------------------------------------------------------------------
# ID & Timestamp
# ---------------------------------------------------------------------------

def generate_id() -> str:
    """Return an 8-character unique identifier."""
    return str(uuid.uuid4())[:8]


def now_str() -> str:
    """Current datetime as ``'YYYY-MM-DD HH:MM:SS'``."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str() -> str:
    """Today's date as ``'YYYY-MM-DD'``."""
    return datetime.now().strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Time Formatting
# ---------------------------------------------------------------------------

def format_time(minutes: int) -> str:
    """Convert minutes to a human-readable string.

    Examples::

        format_time(90)   → '1h 30m'
        format_time(1500) → '1d 1h 0m'
    """
    if minutes <= 0:
        return "0m"
    days      = minutes // (24 * 60)
    remaining = minutes  % (24 * 60)
    hours     = remaining // 60
    mins      = remaining  % 60
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins or not parts:
        parts.append(f"{mins}m")
    return " ".join(parts)


# Alias used by the new v5 tabs
format_time_minutes = format_time


# ---------------------------------------------------------------------------
# Currency / Financial
# ---------------------------------------------------------------------------

def calculate_payment_fee(amount: float, method: str) -> float:
    """Calculate payment-method transaction fee in EGP."""
    if amount <= 0:
        return 0.0
    params = PAYMENT_FEES.get(method)
    if params is None or params["rate"] == 0:
        return 0.0
    fee = amount * params["rate"]
    fee = max(params["min"], min(params["max"], fee))
    return round(fee, 2)


def format_currency(amount: float, symbol: str = "EGP") -> str:
    """Format a float as a currency string, e.g. ``'1,250.50 EGP'``."""
    return f"{amount:,.2f} {symbol}"


def round_to_half(value: float) -> float:
    """Round *value* to the nearest 0.5."""
    return round(value * 2) / 2


# ---------------------------------------------------------------------------
# Weight / Grams
# ---------------------------------------------------------------------------

def filament_length_to_grams(
    length_meters: float,
    diameter_mm: float = 1.75,
    density_g_cm3: float = 1.24,
) -> float:
    """Convert filament length (m) to weight (g) for 1.75 mm PLA."""
    radius_cm = (diameter_mm / 2) / 10
    length_cm = length_meters * 100
    volume_cm3 = math.pi * radius_cm ** 2 * length_cm
    return round(volume_cm3 * density_g_cm3, 2)


# ---------------------------------------------------------------------------
# String Helpers
# ---------------------------------------------------------------------------

def truncate(text: str, max_len: int = 40, suffix: str = "…") -> str:
    """Truncate *text* to *max_len* characters."""
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def safe_float(value: object, default: float = 0.0) -> float:
    """Convert *value* to float, returning *default* on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: object, default: int = 0) -> int:
    """Convert *value* to int, returning *default* on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default