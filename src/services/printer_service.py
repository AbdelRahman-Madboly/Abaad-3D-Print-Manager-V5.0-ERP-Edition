"""
src/services/printer_service.py
=================================
Printer CRUD + usage tracking for Abaad 3D Print Manager v5.0.
"""

import logging
from typing import Dict, List, Optional

from src.core.config import (
    DEFAULT_PRINTER_LIFETIME_KG,
    DEFAULT_PRINTER_PRICE,
    ELECTRICITY_RATE,
    NOZZLE_COST,
    NOZZLE_LIFETIME_GRAMS,
)
from src.core.models import Printer
from src.utils.helpers import generate_id, now_str

log = logging.getLogger(__name__)


class PrinterService:
    """CRUD and usage-tracking logic for 3D printers.

    Args:
        db: A ``DatabaseManager`` instance.
    """

    def __init__(self, db) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_printer(self, printer_id: str) -> Optional[Printer]:
        rows = self._db.get_all_printers()
        for row in rows:
            if row.get("id") == printer_id:
                return Printer.from_dict(row)
        return None

    def get_all_printers(self) -> List[Printer]:
        return [Printer.from_dict(r) for r in self._db.get_all_printers()]

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_printer(
        self,
        name: str,
        model: str = "Creality Ender-3 Max",
        purchase_price: float = DEFAULT_PRINTER_PRICE,
        lifetime_kg: float = DEFAULT_PRINTER_LIFETIME_KG,
        nozzle_cost: float = NOZZLE_COST,
        nozzle_lifetime_grams: float = NOZZLE_LIFETIME_GRAMS,
        electricity_rate_per_hour: float = ELECTRICITY_RATE,
        notes: str = "",
    ) -> Printer:
        """Create and persist a new printer record.

        Args:
            name:                      Display name (e.g. ``'HIVE 0.1'``).
            model:                     Manufacturer model string.
            purchase_price:            Cost in EGP.
            lifetime_kg:               Expected printable lifetime in kg.
            nozzle_cost:               Replacement nozzle cost in EGP.
            nozzle_lifetime_grams:     Grams per nozzle before replacement.
            electricity_rate_per_hour: EGP per hour of printing.
            notes:                     Free-text notes.

        Returns:
            The newly-created ``Printer``.
        """
        printer = Printer(
            id                        = generate_id(),
            name                      = name.strip(),
            model                     = model.strip(),
            purchase_price            = purchase_price,
            lifetime_kg               = lifetime_kg,
            nozzle_cost               = nozzle_cost,
            nozzle_lifetime_grams     = nozzle_lifetime_grams,
            electricity_rate_per_hour = electricity_rate_per_hour,
            is_active                 = True,
            notes                     = notes,
            created_date              = now_str(),
        )
        self._db.save_printer(printer.to_dict())
        log.info("Added printer '%s'  id=%s", printer.name, printer.id)
        return printer

    def update_printer(self, printer_id: str, **kwargs) -> bool:
        """Update one or more fields on a printer record.

        Args:
            printer_id: Target printer ID.
            **kwargs:   Field names and new values.

        Returns:
            ``True`` on success, ``False`` if not found.
        """
        printer = self.get_printer(printer_id)
        if not printer:
            log.warning("update_printer: %s not found", printer_id)
            return False
        for key, value in kwargs.items():
            if hasattr(printer, key):
                setattr(printer, key, value)
        return self._db.save_printer(printer.to_dict())

    # ------------------------------------------------------------------
    # Usage tracking
    # ------------------------------------------------------------------

    def record_print_job(
        self,
        printer_id: str,
        grams: float,
        minutes: int,
    ) -> bool:
        """Record a completed print job and auto-track nozzle wear.

        Updates ``total_printed_grams``, ``total_print_time_minutes``,
        ``current_nozzle_grams``.  If ``current_nozzle_grams`` exceeds
        ``nozzle_lifetime_grams`` the nozzle counter increments automatically.

        Args:
            printer_id: Target printer ID.
            grams:      Weight printed in grams.
            minutes:    Print duration in minutes.

        Returns:
            ``True`` on success.
        """
        printer = self.get_printer(printer_id)
        if not printer:
            log.warning("record_print_job: printer %s not found", printer_id)
            return False
        printer.add_print(grams, minutes)
        log.debug(
            "Recorded %.1fg / %dm on printer %s  (nozzle %.0f%%)",
            grams, minutes, printer.name, printer.nozzle_usage_percent,
        )
        return self._db.save_printer(printer.to_dict())

    def reset_nozzle(self, printer_id: str) -> bool:
        """Record a manual nozzle change and reset the usage counter.

        Args:
            printer_id: Target printer ID.

        Returns:
            ``True`` on success.
        """
        printer = self.get_printer(printer_id)
        if not printer:
            return False
        printer.nozzle_changes      += 1
        printer.current_nozzle_grams = 0.0
        log.info(
            "Nozzle reset on printer %s  (total changes: %d)",
            printer.name, printer.nozzle_changes,
        )
        return self._db.save_printer(printer.to_dict())

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_printer_stats(self, printer_id: str) -> Optional[Dict]:
        """Return a comprehensive stats dict for one printer.

        Args:
            printer_id: Target printer ID.

        Returns:
            Dict with cost breakdowns and usage percentages,
            or ``None`` if printer not found.
        """
        printer = self.get_printer(printer_id)
        if not printer:
            return None

        lifetime_grams   = printer.lifetime_kg * 1000
        lifetime_used_pct = (
            (printer.total_printed_grams / lifetime_grams * 100)
            if lifetime_grams > 0 else 0.0
        )

        return {
            "id":                    printer.id,
            "name":                  printer.name,
            "model":                 printer.model,
            # Usage
            "total_printed_grams":   printer.total_printed_grams,
            "total_print_time_min":  printer.total_print_time_minutes,
            "total_print_time_hrs":  round(printer.total_print_time_minutes / 60, 1),
            "lifetime_used_pct":     round(lifetime_used_pct, 1),
            # Nozzle
            "nozzle_changes":        printer.nozzle_changes,
            "current_nozzle_grams":  printer.current_nozzle_grams,
            "nozzle_usage_pct":      round(printer.nozzle_usage_percent, 1),
            # Costs
            "depreciation_per_gram": round(printer.depreciation_per_gram, 4),
            "total_depreciation":    round(printer.total_depreciation, 2),
            "total_electricity_cost": round(printer.total_electricity_cost, 2),
            "total_nozzle_cost":     round(printer.total_nozzle_cost, 2),
            "total_running_cost":    round(
                printer.total_depreciation
                + printer.total_electricity_cost
                + printer.total_nozzle_cost,
                2,
            ),
        }