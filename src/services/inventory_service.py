"""
src/services/inventory_service.py
===================================
All filament spool business logic for Abaad 3D Print Manager v5.0.

Pending system rules:
  - reserve_filament   → pending_weight ↑   (order saved/confirmed)
  - release_filament   → pending_weight ↓   (order cancelled/edited)
  - commit_filament    → current_weight ↓, pending_weight ↓  (order in-progress/ready)
  - available_weight   = current_weight - pending_weight

Spool lifecycle:
  active  →  low (< TRASH_THRESHOLD_GRAMS)  →  trash  →  archived (FilamentHistory)
"""

import logging
from typing import Dict, List, Optional

from src.core.config import (
    DEFAULT_COST_PER_GRAM,
    SPOOL_PRICE_FIXED,
    TRASH_THRESHOLD_GRAMS,
)
from src.core.models import FilamentHistory, FilamentSpool
from src.utils.helpers import generate_id, now_str

log = logging.getLogger(__name__)


class InventoryService:
    """CRUD + pending-reservation logic for filament spools.

    Args:
        db: A ``DatabaseManager`` instance (from ``src.core.database``).
    """

    def __init__(self, db) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_spool(self, spool_id: str) -> Optional[FilamentSpool]:
        """Load a single spool by ID.

        Returns:
            ``FilamentSpool`` or ``None`` if not found.
        """
        row = self._db.get_spool(spool_id)
        return FilamentSpool.from_dict(row) if row else None

    def get_all_spools(self) -> List[FilamentSpool]:
        """Return all spools (active, low, trash, archived)."""
        return [FilamentSpool.from_dict(r) for r in self._db.get_all_spools()]

    def get_active_spools(self) -> List[FilamentSpool]:
        """Return spools that are usable (not trashed, weight > 0)."""
        return [FilamentSpool.from_dict(r) for r in self._db.get_active_spools()]

    def get_spools_by_color(self, color: str) -> List[FilamentSpool]:
        """Return active spools for a colour, sorted by available weight descending.

        Args:
            color: Colour name string (e.g. ``'Black'``).

        Returns:
            Sorted list of matching ``FilamentSpool`` objects.
        """
        rows = self._db.get_spools_by_color(color)
        return [FilamentSpool.from_dict(r) for r in rows]

    def get_low_spools(self) -> List[FilamentSpool]:
        """Return active spools below the trash threshold (< 20 g by default).

        Returns:
            List of spools that should show a "Move to Trash" button.
        """
        return [s for s in self.get_active_spools() if s.should_show_trash_button]

    def get_colors(self) -> List[str]:
        """Return the list of defined filament colours."""
        return self._db.get_colors()

    def add_color(self, color_name: str) -> bool:
        """Add a new colour to the colours table.

        Args:
            color_name: The colour label to add.

        Returns:
            ``True`` if added, ``False`` if already exists or empty.
        """
        return self._db.add_color(color_name)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_spool(
        self,
        color: str,
        filament_type: str = "PLA+",
        brand: str = "eSUN",
        name: str = "",
        category: str = "standard",
        initial_weight_grams: float = 1000.0,
        purchase_price_egp: float = SPOOL_PRICE_FIXED,
        notes: str = "",
    ) -> FilamentSpool:
        """Create and persist a new filament spool.

        For ``'standard'`` spools the purchase price defaults to 840 EGP.
        For ``'remaining'`` spools the price should be passed as 0 (already paid).

        Args:
            color:                Colour label (must exist in colours table).
            filament_type:        Material type (default ``'PLA+'``).
            brand:                Manufacturer (default ``'eSUN'``).
            name:                 Optional custom name; auto-generated if empty.
            category:             ``'standard'`` or ``'remaining'``.
            initial_weight_grams: Starting weight in grams (default 1000).
            purchase_price_egp:   Cost paid in EGP.
            notes:                Optional notes.

        Returns:
            The newly-created ``FilamentSpool``.
        """
        spool = FilamentSpool(
            id                   = generate_id(),
            name                 = name.strip(),
            filament_type        = filament_type,
            brand                = brand,
            color                = color,
            category             = category,
            status               = "active",
            initial_weight_grams = initial_weight_grams,
            current_weight_grams = initial_weight_grams,
            pending_weight_grams = 0.0,
            purchase_price_egp   = purchase_price_egp,
            purchase_date        = now_str(),
            is_active            = True,
            notes                = notes,
        )
        self._db.save_spool(spool.to_dict())
        log.info("Added spool %s  %s %s  %.0fg", spool.id, brand, color, initial_weight_grams)
        return spool

    def update_spool(self, spool_id: str, **kwargs) -> bool:
        """Update one or more fields on an existing spool.

        Args:
            spool_id: Target spool ID.
            **kwargs: Field names and new values.

        Returns:
            ``True`` on success, ``False`` if spool not found.
        """
        spool = self.get_spool(spool_id)
        if not spool:
            log.warning("update_spool: spool %s not found", spool_id)
            return False
        for key, value in kwargs.items():
            if hasattr(spool, key):
                setattr(spool, key, value)
        return self._db.save_spool(spool.to_dict())

    def delete_spool(self, spool_id: str) -> bool:
        """Permanently delete a spool record (use sparingly — prefer trash).

        Args:
            spool_id: Target spool ID.

        Returns:
            ``True`` on success.
        """
        # Use raw DB delete — no model needed
        try:
            with self._db._transaction() as conn:
                conn.execute(
                    "DELETE FROM filament_spools WHERE id=?", (spool_id,)
                )
            return True
        except Exception as e:
            log.error("delete_spool failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Pending system
    # ------------------------------------------------------------------

    def reserve_filament(self, spool_id: str, grams: float) -> bool:
        """Mark filament as pending (reserved by an order).

        Does NOT deduct from current_weight yet.  Call when an order
        item is assigned to a spool.

        Args:
            spool_id: Target spool ID.
            grams:    Amount to reserve.

        Returns:
            ``True`` if reservation succeeded (sufficient available weight).
        """
        spool = self.get_spool(spool_id)
        if not spool:
            log.warning("reserve_filament: spool %s not found", spool_id)
            return False
        if not spool.reserve_filament(grams):
            log.warning(
                "reserve_filament: insufficient weight on %s (need %.1fg, available %.1fg)",
                spool_id, grams, spool.available_weight_grams,
            )
            return False
        return self._db.save_spool(spool.to_dict())

    def release_filament(self, spool_id: str, grams: float) -> bool:
        """Release a pending reservation (order cancelled or item removed).

        Args:
            spool_id: Target spool ID.
            grams:    Amount to release from pending.

        Returns:
            ``True`` on success.
        """
        spool = self.get_spool(spool_id)
        if not spool:
            return False
        spool.release_pending(grams)
        return self._db.save_spool(spool.to_dict())

    def commit_filament(self, spool_id: str, grams: float) -> bool:
        """Permanently deduct filament (order moved to In Progress / Ready).

        Reduces current_weight and clears the matching pending amount.
        Automatically sets status to ``'low'`` if below threshold.

        Args:
            spool_id: Target spool ID.
            grams:    Amount to commit.

        Returns:
            ``True`` on success, ``False`` if insufficient weight.
        """
        spool = self.get_spool(spool_id)
        if not spool:
            log.warning("commit_filament: spool %s not found", spool_id)
            return False
        if not spool.commit_filament(grams):
            log.warning(
                "commit_filament: insufficient weight on %s (need %.1fg, current %.1fg)",
                spool_id, grams, spool.current_weight_grams,
            )
            return False
        return self._db.save_spool(spool.to_dict())

    def use_filament_direct(self, spool_id: str, grams: float) -> bool:
        """Directly deduct filament without going through the pending system.

        Use for manual adjustments from the filament tab.

        Args:
            spool_id: Target spool ID.
            grams:    Amount to deduct.

        Returns:
            ``True`` on success.
        """
        return self.commit_filament(spool_id, grams)

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def move_to_trash(self, spool_id: str, reason: str = "trash") -> bool:
        """Archive a spool and create a ``FilamentHistory`` record.

        The spool's status is set to ``'trash'`` and ``is_active`` to ``False``.
        A history entry records how much was used vs wasted.

        Args:
            spool_id: Target spool ID.
            reason:   Reason label stored in history (e.g. ``'finished'``,
                      ``'trash'``, ``'defective'``).

        Returns:
            ``True`` on success.
        """
        spool = self.get_spool(spool_id)
        if not spool:
            log.warning("move_to_trash: spool %s not found", spool_id)
            return False

        # Create history record before mutating the spool
        history = FilamentHistory(
            id               = generate_id(),
            spool_id         = spool.id,
            spool_name       = spool.display_name,
            color            = spool.color,
            initial_weight   = spool.initial_weight_grams,
            used_weight      = spool.used_weight_grams,
            remaining_weight = spool.current_weight_grams,
            waste_weight     = spool.current_weight_grams,   # leftover = waste
            archived_date    = now_str(),
            reason           = reason,
        )
        self._db.save_history(history.to_dict())

        # Mutate spool
        spool.move_to_trash()
        self._db.save_spool(spool.to_dict())

        log.info(
            "Spool %s moved to trash  (used %.1fg, wasted %.1fg)",
            spool_id, history.used_weight, history.waste_weight,
        )
        return True

    def restore_from_trash(self, spool_id: str) -> bool:
        """Restore a trashed spool to active status.

        Args:
            spool_id: Target spool ID.

        Returns:
            ``True`` on success.
        """
        spool = self.get_spool(spool_id)
        if not spool:
            return False
        spool.status       = "active"
        spool.is_active    = True
        spool.archived_date = ""
        return self._db.save_spool(spool.to_dict())

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_inventory_summary(self) -> Dict:
        """Aggregate inventory statistics for the stats dashboard.

        Returns:
            Dict with total_spools, active_spools, total_weight_g,
            pending_weight_g, available_weight_g, and total_value_egp.
        """
        all_spools    = self.get_all_spools()
        active_spools = [s for s in all_spools if s.is_active and s.status != "trash"]

        total_weight    = sum(s.current_weight_grams for s in active_spools)
        pending_weight  = sum(s.pending_weight_grams for s in active_spools)
        available_weight = sum(s.available_weight_grams for s in active_spools)

        # Value = remaining weight × cost_per_gram (0 for "remaining" category)
        total_value = sum(
            s.current_weight_grams * s.cost_per_gram
            for s in active_spools
        )

        return {
            "total_spools":      len(all_spools),
            "active_spools":     len(active_spools),
            "low_spools":        len([s for s in active_spools if s.should_show_trash_button]),
            "trashed_spools":    len([s for s in all_spools if s.status == "trash"]),
            "total_weight_g":    round(total_weight, 1),
            "pending_weight_g":  round(pending_weight, 1),
            "available_weight_g": round(available_weight, 1),
            "total_value_egp":   round(total_value, 2),
        }

    def get_spool_cost_report(self) -> List[Dict]:
        """Return per-spool cost analysis rows for reporting.

        Returns:
            List of dicts with spool metadata and cost breakdown.
        """
        report = []
        for spool in self.get_all_spools():
            used    = spool.used_weight_grams
            cost    = used * spool.cost_per_gram
            report.append({
                "id":            spool.id,
                "display_name":  spool.display_name,
                "color":         spool.color,
                "category":      spool.category,
                "status":        spool.status,
                "initial_g":     spool.initial_weight_grams,
                "current_g":     spool.current_weight_grams,
                "used_g":        round(used, 1),
                "pending_g":     spool.pending_weight_grams,
                "available_g":   round(spool.available_weight_grams, 1),
                "remaining_pct": round(spool.remaining_percent, 1),
                "cost_per_gram": spool.cost_per_gram,
                "cost_used_egp": round(cost, 2),
                "purchase_price": spool.purchase_price_egp,
            })
        return sorted(report, key=lambda r: r["color"])

    def get_filament_history(self) -> List[FilamentHistory]:
        """Return all archived spool history records, newest first.

        Returns:
            List of ``FilamentHistory`` objects.
        """
        rows = self._db.get_all_history()
        history = [FilamentHistory.from_dict(r) for r in rows]
        return sorted(history, key=lambda h: h.archived_date, reverse=True)

    def get_total_waste_grams(self) -> float:
        """Return total filament wasted across all trashed spools.

        Returns:
            Total waste in grams.
        """
        history = self.get_filament_history()
        return sum(h.waste_weight for h in history)