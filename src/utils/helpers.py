"""
src/utils/helpers.py
====================
Shared utility functions for Abaad 3D Print Manager v5.0.

Consolidates duplicated helpers from v4:
  - generate_id()          was in models.py  (uuid4[:8])
                           and  auth.py       (secrets.token_hex(4))  ← standardised here
  - now_str()              was in models.py AND auth.py
  - format_time()          was in models.py
  - calculate_payment_fee() was in models.py

No external dependencies — stdlib only.
"""

import uuid
from datetime import datetime
from typing import Optional

from src.core.config import PAYMENT_FEES


# ---------------------------------------------------------------------------
# ID & Timestamp
# ---------------------------------------------------------------------------

def generate_id() -> str:
    """Return an 8-character unique identifier.

    Standardised on uuid4[:8] (was token_hex(4) in auth.py,
    uuid4[:8] in models.py — now one implementation everywhere).

    Returns:
        8-character hex string, e.g. ``'3f7a1c2b'``.
    """
    return str(uuid.uuid4())[:8]


def now_str() -> str:
    """Return the current local datetime as an ISO-like string.

    Returns:
        Formatted string, e.g. ``'2025-06-01 14:30:00'``.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_str() -> str:
    """Return today's date as a string.

    Returns:
        Formatted string, e.g. ``'2025-06-01'``.
    """
    return datetime.now().strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Time Formatting
# ---------------------------------------------------------------------------

def format_time(minutes: int) -> str:
    """Convert a duration in minutes to a human-readable string.

    Examples::

        format_time(0)    → '0m'
        format_time(90)   → '1h 30m'
        format_time(1500) → '1d 1h 0m'

    Args:
        minutes: Total duration in minutes (negative treated as 0).

    Returns:
        Human-readable string such as ``'2d 5h 30m'``.
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
    if mins or not parts:          # always show minutes if nothing else
        parts.append(f"{mins}m")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Currency / Financial
# ---------------------------------------------------------------------------

def calculate_payment_fee(amount: float, method: str) -> float:
    """Calculate the payment-method transaction fee.

    Uses the ``PAYMENT_FEES`` table from ``config.py`` so rates,
    minimums, and maximums are maintained in a single place.

    Fee rules:
        * Cash        → 0 %
        * VodaCash    → 0.5 %, min 1.00 EGP,  max 15.00 EGP
        * InstaPay    → 0.1 %, min 0.50 EGP,  max 20.00 EGP

    Args:
        amount: The order total (must be > 0 to generate a fee).
        method: Payment method string — ``'Cash'``, ``'Vodafone Cash'``,
                or ``'InstaPay'``.

    Returns:
        Fee in EGP, rounded to 2 decimal places.
        Returns ``0.0`` for unknown methods or non-positive amounts.
    """
    if amount <= 0:
        return 0.0

    params = PAYMENT_FEES.get(method)
    if params is None or params["rate"] == 0:
        return 0.0

    fee = amount * params["rate"]
    fee = max(params["min"], min(params["max"], fee))
    return round(fee, 2)


def format_currency(amount: float, symbol: str = "EGP") -> str:
    """Format a float as a currency string.

    Args:
        amount: Monetary value.
        symbol: Currency symbol (default ``'EGP'``).

    Returns:
        Formatted string, e.g. ``'1,250.50 EGP'``.
    """
    return f"{amount:,.2f} {symbol}"


def round_to_half(value: float) -> float:
    """Round a value to the nearest 0.5.

    Used for pricing display (e.g. 12.3 → 12.5, 12.7 → 13.0).

    Args:
        value: Input float.

    Returns:
        Value rounded to nearest 0.5.
    """
    return round(value * 2) / 2


# ---------------------------------------------------------------------------
# Weight / Grams
# ---------------------------------------------------------------------------

def filament_length_to_grams(
    length_meters: float,
    diameter_mm: float = 1.75,
    density_g_cm3: float = 1.24,
) -> float:
    """Convert filament length (meters) to weight (grams).

    Formula: mass = volume × density
             volume = π × (d/2)² × length

    Args:
        length_meters:  Filament length in metres.
        diameter_mm:    Filament diameter in mm (default 1.75 mm PLA).
        density_g_cm3:  Material density in g/cm³ (default 1.24 for PLA).

    Returns:
        Weight in grams, rounded to 2 decimal places.
    """
    import math
    radius_cm = (diameter_mm / 2) / 10          # mm → cm
    length_cm = length_meters * 100              # m  → cm
    volume_cm3 = math.pi * radius_cm ** 2 * length_cm
    return round(volume_cm3 * density_g_cm3, 2)


# ---------------------------------------------------------------------------
# String Helpers
# ---------------------------------------------------------------------------

def truncate(text: str, max_len: int = 40, suffix: str = "…") -> str:
    """Truncate a string to *max_len* characters, appending *suffix*.

    Args:
        text:    Input string.
        max_len: Maximum length before truncation (default 40).
        suffix:  Characters appended when truncated (default ``'…'``).

    Returns:
        Original string if short enough, otherwise truncated version.
    """
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def safe_float(value: object, default: float = 0.0) -> float:
    """Convert *value* to float, returning *default* on failure.

    Args:
        value:   Any value to convert.
        default: Fallback if conversion fails (default ``0.0``).

    Returns:
        Float value.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: object, default: int = 0) -> int:
    """Convert *value* to int, returning *default* on failure.

    Args:
        value:   Any value to convert.
        default: Fallback if conversion fails (default ``0``).

    Returns:
        Integer value.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default