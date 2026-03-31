"""
src/core/models.py
==================
Dataclass models for Abaad 3D Print Manager v5.0.

Changes from v4 (src/models.py):
  - All constants removed  → live in src/core/config.py
  - All enums removed      → string lists live in src/core/config.py
  - generate_id / now_str  → imported from src/utils/helpers.py
  - PrintItem.to_dict()    → flattens settings sub-dict into top-level keys
                             (matches the SQLite print_items schema)
  - PrintItem.from_dict()  → reads flat keys; still accepts old nested
                             'settings' sub-dict for migration compatibility
  - Order.to_dict()        → no 'items' key (items stored in separate table)
  - Order.from_dict()      → accepts optional 'items' list for in-memory use
  - Statistics dataclass   → kept for FinanceService.get_full_statistics()
"""

from dataclasses import dataclass, field
from typing import List, Optional

from src.core.config import (
    DEFAULT_COST_PER_GRAM,
    DEFAULT_LAYER_HEIGHT,
    DEFAULT_NOZZLE,
    DEFAULT_RATE_PER_GRAM,
    ELECTRICITY_RATE,
    SPOOL_PRICE_FIXED,
    TOLERANCE_THRESHOLD_GRAMS,
    TRASH_THRESHOLD_GRAMS,
)
from src.utils.helpers import calculate_payment_fee, generate_id, now_str


# ---------------------------------------------------------------------------
# PrintSettings  (value object — no separate table, flattened into print_items)
# ---------------------------------------------------------------------------

@dataclass
class PrintSettings:
    """Slicer settings attached to a print item."""

    nozzle_size:     float = DEFAULT_NOZZLE
    layer_height:    float = DEFAULT_LAYER_HEIGHT
    infill_density:  int   = 20
    support_type:    str   = "None"
    scale_ratio:     float = 1.0

    def to_dict(self) -> dict:
        return {
            "nozzle_size":    self.nozzle_size,
            "layer_height":   self.layer_height,
            "infill_density": self.infill_density,
            "support_type":   self.support_type,
            "scale_ratio":    self.scale_ratio,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PrintSettings":
        return cls(
            nozzle_size    = float(data.get("nozzle_size",    DEFAULT_NOZZLE)),
            layer_height   = float(data.get("layer_height",   DEFAULT_LAYER_HEIGHT)),
            infill_density = int(  data.get("infill_density", 20)),
            support_type   =       data.get("support_type",   "None"),
            scale_ratio    = float(data.get("scale_ratio",    1.0)),
        )

    def __str__(self) -> str:
        parts = [f"{self.nozzle_size}mm nozzle", f"{self.layer_height}mm layers"]
        if self.support_type != "None":
            parts.append(self.support_type)
        return " / ".join(parts)


# ---------------------------------------------------------------------------
# PrintItem
# ---------------------------------------------------------------------------

@dataclass
class PrintItem:
    """A single print job within an order."""

    id:                         str   = field(default_factory=generate_id)
    name:                       str   = ""
    estimated_weight_grams:     float = 0.0
    actual_weight_grams:        float = 0.0
    estimated_time_minutes:     int   = 0
    actual_time_minutes:        int   = 0
    filament_type:              str   = "PLA+"
    color:                      str   = "Black"
    spool_id:                   str   = ""
    settings:                   PrintSettings = field(default_factory=PrintSettings)
    quantity:                   int   = 1
    rate_per_gram:              float = DEFAULT_RATE_PER_GRAM
    notes:                      str   = ""
    is_printed:                 bool  = False
    filament_pending:           bool  = False
    filament_deducted:          bool  = False
    printer_id:                 str   = ""
    tolerance_discount_applied: bool  = False
    tolerance_discount_amount:  float = 0.0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def weight(self) -> float:
        """Effective weight: actual if available, else estimated."""
        return self.actual_weight_grams if self.actual_weight_grams > 0 else self.estimated_weight_grams

    @property
    def time_minutes(self) -> int:
        """Effective print time: actual if available, else estimated."""
        return self.actual_time_minutes if self.actual_time_minutes > 0 else self.estimated_time_minutes

    @property
    def total_weight(self) -> float:
        return self.weight * self.quantity

    @property
    def print_cost(self) -> float:
        """Revenue contribution: weight × qty × rate − tolerance discount."""
        return self.weight * self.quantity * self.rate_per_gram - self.tolerance_discount_amount

    @property
    def discount_from_base(self) -> float:
        """Percentage discount vs the base rate (4.0 EGP/g)."""
        if self.rate_per_gram >= DEFAULT_RATE_PER_GRAM:
            return 0.0
        return ((DEFAULT_RATE_PER_GRAM - self.rate_per_gram) / DEFAULT_RATE_PER_GRAM) * 100

    @property
    def weight_difference(self) -> float:
        """Actual minus estimated weight (positive = heavier than expected)."""
        if self.actual_weight_grams <= 0:
            return 0.0
        return self.actual_weight_grams - self.estimated_weight_grams

    # ------------------------------------------------------------------
    # Business logic
    # ------------------------------------------------------------------

    def calculate_tolerance_discount(self) -> float:
        """Apply tolerance discount when actual weight is 1–5 g over estimate.

        Discount = 1 g × rate_per_gram × quantity.
        Sets tolerance_discount_applied and tolerance_discount_amount in-place.

        Returns:
            The total discount amount applied (0 if not applicable).
        """
        diff = self.weight_difference
        if 1 <= diff <= TOLERANCE_THRESHOLD_GRAMS:
            self.tolerance_discount_amount  = self.rate_per_gram * self.quantity
            self.tolerance_discount_applied = True
            return self.tolerance_discount_amount
        self.tolerance_discount_amount  = 0.0
        self.tolerance_discount_applied = False
        return 0.0

    # ------------------------------------------------------------------
    # Serialisation  (flat — matches SQLite print_items schema)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a flat dict compatible with the print_items SQLite table.

        Settings sub-dict fields are promoted to top-level keys.
        No 'settings' nested key is emitted.
        """
        return {
            "id":                         self.id,
            "name":                       self.name,
            "estimated_weight_grams":     self.estimated_weight_grams,
            "actual_weight_grams":        self.actual_weight_grams,
            "estimated_time_minutes":     self.estimated_time_minutes,
            "actual_time_minutes":        self.actual_time_minutes,
            "filament_type":              self.filament_type,
            "color":                      self.color,
            "spool_id":                   self.spool_id,
            # Flattened PrintSettings
            "nozzle_size":                self.settings.nozzle_size,
            "layer_height":               self.settings.layer_height,
            "infill_density":             self.settings.infill_density,
            "support_type":               self.settings.support_type,
            "scale_ratio":                self.settings.scale_ratio,
            # Item-level fields
            "quantity":                   self.quantity,
            "rate_per_gram":              self.rate_per_gram,
            "notes":                      self.notes,
            "is_printed":                 self.is_printed,
            "filament_pending":           self.filament_pending,
            "filament_deducted":          self.filament_deducted,
            "printer_id":                 self.printer_id,
            "tolerance_discount_applied": self.tolerance_discount_applied,
            "tolerance_discount_amount":  self.tolerance_discount_amount,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PrintItem":
        """Build a PrintItem from a flat dict (SQLite row) or v4 nested dict.

        Accepts both:
          - Flat keys (``nozzle_size``, ``layer_height``, …)  ← v5 SQLite
          - Nested ``settings`` sub-dict                       ← v4 JSON
        """
        item = cls()
        item.id                         = data.get("id", generate_id())
        item.name                       = data.get("name", "")
        item.estimated_weight_grams     = float(data.get("estimated_weight_grams", 0))
        item.actual_weight_grams        = float(data.get("actual_weight_grams", 0))
        item.estimated_time_minutes     = int(  data.get("estimated_time_minutes", 0))
        item.actual_time_minutes        = int(  data.get("actual_time_minutes", 0))
        item.filament_type              =       data.get("filament_type", "PLA+")
        item.color                      =       data.get("color", "Black")
        item.spool_id                   =       data.get("spool_id", "")
        item.quantity                   = int(  data.get("quantity", 1))
        item.rate_per_gram              = float(data.get("rate_per_gram", DEFAULT_RATE_PER_GRAM))
        item.notes                      =       data.get("notes", "")
        item.is_printed                 = bool( data.get("is_printed", False))
        item.filament_pending           = bool( data.get("filament_pending", False))
        item.filament_deducted          = bool( data.get("filament_deducted", False))
        item.printer_id                 =       data.get("printer_id", "")
        item.tolerance_discount_applied = bool( data.get("tolerance_discount_applied", False))
        item.tolerance_discount_amount  = float(data.get("tolerance_discount_amount", 0.0))

        # Settings: prefer flat keys; fall back to nested 'settings' sub-dict
        nested = data.get("settings", {})
        item.settings = PrintSettings(
            nozzle_size    = float(data.get("nozzle_size",    nested.get("nozzle_size",    DEFAULT_NOZZLE))),
            layer_height   = float(data.get("layer_height",   nested.get("layer_height",   DEFAULT_LAYER_HEIGHT))),
            infill_density = int(  data.get("infill_density", nested.get("infill_density", 20))),
            support_type   =       data.get("support_type",   nested.get("support_type",   "None")),
            scale_ratio    = float(data.get("scale_ratio",    nested.get("scale_ratio",    1.0))),
        )
        return item


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

@dataclass
class Customer:
    """Customer record."""

    id:               str   = field(default_factory=generate_id)
    name:             str   = ""
    phone:            str   = ""
    email:            str   = ""
    address:          str   = ""
    notes:            str   = ""
    discount_percent: float = 0.0
    total_orders:     int   = 0
    total_spent:      float = 0.0
    created_date:     str   = field(default_factory=now_str)
    updated_date:     str   = field(default_factory=now_str)

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "name":             self.name,
            "phone":            self.phone,
            "email":            self.email,
            "address":          self.address,
            "notes":            self.notes,
            "discount_percent": self.discount_percent,
            "total_orders":     self.total_orders,
            "total_spent":      self.total_spent,
            "created_date":     self.created_date,
            "updated_date":     self.updated_date,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Customer":
        c = cls()
        c.id               =       data.get("id", generate_id())
        c.name             =       data.get("name", "")
        c.phone            =       data.get("phone", "")
        c.email            =       data.get("email", "")
        c.address          =       data.get("address", "")
        c.notes            =       data.get("notes", "")
        c.discount_percent = float(data.get("discount_percent", 0.0))
        c.total_orders     = int(  data.get("total_orders", 0))
        c.total_spent      = float(data.get("total_spent", 0.0))
        c.created_date     =       data.get("created_date", now_str())
        c.updated_date     =       data.get("updated_date", now_str())
        return c


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------

@dataclass
class Order:
    """Customer order with full pricing, R&D mode and quote/deposit tracking."""

    id:                       str   = field(default_factory=generate_id)
    order_number:             int   = 0
    customer_id:              str   = ""
    customer_name:            str   = ""
    customer_phone:           str   = ""
    status:                   str   = "Draft"
    items:                    List[PrintItem] = field(default_factory=list)
    is_rd_project:            bool  = False

    # Pricing
    subtotal:                 float = 0.0   # Items at base rate (4 EGP/g)
    actual_total:             float = 0.0   # Items at actual rates
    discount_percent:         float = 0.0   # Auto-calculated rate discount %
    discount_amount:          float = 0.0
    order_discount_percent:   float = 0.0   # Manual order-level discount
    order_discount_amount:    float = 0.0
    tolerance_discount_total: float = 0.0
    shipping_cost:            float = 0.0
    total:                    float = 0.0
    amount_received:          float = 0.0
    rounding_loss:            float = 0.0
    payment_method:           str   = "Cash"
    payment_fee:              float = 0.0

    # Costs (internal)
    material_cost:            float = 0.0
    electricity_cost:         float = 0.0
    depreciation_cost:        float = 0.0
    profit:                   float = 0.0

    # Dates
    created_date:             str   = field(default_factory=now_str)
    updated_date:             str   = field(default_factory=now_str)
    confirmed_date:           str   = ""
    delivered_date:           str   = ""
    deleted_date:             str   = ""

    notes:                    str   = ""
    is_deleted:               bool  = False

    # Quote / deposit
    quote_sent:               bool  = False
    quote_sent_date:          str   = ""
    deposit_amount:           float = 0.0
    deposit_received:         bool  = False

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def item_count(self) -> int:
        return sum(i.quantity for i in self.items)

    @property
    def total_weight(self) -> float:
        return sum(i.total_weight for i in self.items)

    @property
    def total_time(self) -> int:
        return sum(i.time_minutes * i.quantity for i in self.items)

    @property
    def rd_cost(self) -> float:
        """R&D total = material + electricity + depreciation (zero profit)."""
        return self.material_cost + self.electricity_cost + self.depreciation_cost

    @property
    def is_confirmed(self) -> bool:
        return self.status in ("Confirmed", "In Progress", "Ready", "Delivered")

    # ------------------------------------------------------------------
    # Business logic
    # ------------------------------------------------------------------

    def add_item(self, item: PrintItem) -> None:
        """Append an item and recalculate totals."""
        self.items.append(item)
        self.calculate_totals()

    def remove_item(self, item_id: str) -> None:
        """Remove an item by id and recalculate totals."""
        self.items = [i for i in self.items if i.id != item_id]
        self.calculate_totals()

    def get_item(self, item_id: str) -> Optional[PrintItem]:
        for i in self.items:
            if i.id == item_id:
                return i
        return None

    def calculate_totals(self) -> None:
        """Recalculate all pricing fields from current items.

        Implements the full pricing chain from the spec:
        1. Per-item tolerance discounts
        2. Subtotal at base rate
        3. Actual total at item rates
        4. Rate discount (auto)
        5. Order discount (manual)
        6. R&D override
        7. Payment fee
        8. Final total
        9. Profit
        """
        # 1. Tolerance discounts
        self.tolerance_discount_total = 0.0
        for item in self.items:
            if item.actual_weight_grams > 0:
                item.calculate_tolerance_discount()
            self.tolerance_discount_total += item.tolerance_discount_amount

        # 2. Subtotal at base rate
        self.subtotal = sum(
            item.weight * item.quantity * DEFAULT_RATE_PER_GRAM
            for item in self.items
        )

        # 3. Actual total at item rates (includes tolerance discounts)
        self.actual_total = sum(item.print_cost for item in self.items)

        # 4. Rate discount (auto-calculated)
        if self.subtotal > 0:
            self.discount_amount  = self.subtotal - self.actual_total
            self.discount_percent = (self.discount_amount / self.subtotal) * 100
        else:
            self.discount_amount  = 0.0
            self.discount_percent = 0.0

        # 5. Manual order discount
        after_rate_discount = self.actual_total
        if self.order_discount_percent > 0:
            self.order_discount_amount = after_rate_discount * (self.order_discount_percent / 100)
        else:
            self.order_discount_amount = 0.0

        final_subtotal = after_rate_discount - self.order_discount_amount

        # Cost tracking
        self.material_cost    = self.total_weight * DEFAULT_COST_PER_GRAM
        self.electricity_cost = (self.total_time / 60) * ELECTRICITY_RATE
        self.depreciation_cost = self.total_weight * (25_000.0 / 500_000.0)  # 25k EGP / 500 kg

        # 6. R&D override: total = costs, zero profit
        if self.is_rd_project:
            final_subtotal             = self.rd_cost
            self.order_discount_percent = 0.0
            self.order_discount_amount  = 0.0

        # 7. Payment fee
        subtotal_with_shipping = final_subtotal + self.shipping_cost
        self.payment_fee = calculate_payment_fee(subtotal_with_shipping, self.payment_method)

        # 8. Final total
        self.total = final_subtotal + self.shipping_cost + self.payment_fee

        # Rounding loss (if customer underpays by rounding)
        if self.amount_received > 0:
            diff = self.total - self.amount_received
            self.rounding_loss = max(0.0, diff)

        # 9. Profit
        total_costs = self.material_cost + self.electricity_cost + self.depreciation_cost
        self.profit = 0.0 if self.is_rd_project else final_subtotal - total_costs

        self.updated_date = now_str()

    # ------------------------------------------------------------------
    # Serialisation  (no 'items' key — items live in a separate table)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a flat dict for the SQLite orders table.

        The ``items`` list is intentionally excluded — items are persisted
        separately via ``db.save_items()``.
        """
        return {
            "id":                       self.id,
            "order_number":             self.order_number,
            "customer_id":              self.customer_id,
            "customer_name":            self.customer_name,
            "customer_phone":           self.customer_phone,
            "status":                   self.status,
            "is_rd_project":            self.is_rd_project,
            "subtotal":                 self.subtotal,
            "actual_total":             self.actual_total,
            "discount_percent":         self.discount_percent,
            "discount_amount":          self.discount_amount,
            "order_discount_percent":   self.order_discount_percent,
            "order_discount_amount":    self.order_discount_amount,
            "tolerance_discount_total": self.tolerance_discount_total,
            "shipping_cost":            self.shipping_cost,
            "total":                    self.total,
            "amount_received":          self.amount_received,
            "rounding_loss":            self.rounding_loss,
            "payment_method":           self.payment_method,
            "payment_fee":              self.payment_fee,
            "material_cost":            self.material_cost,
            "electricity_cost":         self.electricity_cost,
            "depreciation_cost":        self.depreciation_cost,
            "profit":                   self.profit,
            "notes":                    self.notes,
            "is_deleted":               self.is_deleted,
            "quote_sent":               self.quote_sent,
            "quote_sent_date":          self.quote_sent_date,
            "deposit_amount":           self.deposit_amount,
            "deposit_received":         self.deposit_received,
            "created_date":             self.created_date,
            "updated_date":             self.updated_date,
            "confirmed_date":           self.confirmed_date,
            "delivered_date":           self.delivered_date,
            "deleted_date":             self.deleted_date,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Order":
        """Build an Order from a SQLite row dict.

        Accepts an optional ``items`` key (list of item dicts) for
        in-memory assembly — the service layer injects items after loading.
        """
        o = cls()
        o.id                       =       data.get("id", generate_id())
        o.order_number             = int(  data.get("order_number", 0))
        o.customer_id              =       data.get("customer_id", "")
        o.customer_name            =       data.get("customer_name", "")
        o.customer_phone           =       data.get("customer_phone", "")
        o.status                   =       data.get("status", "Draft")
        o.is_rd_project            = bool( data.get("is_rd_project", False))
        o.subtotal                 = float(data.get("subtotal", 0))
        o.actual_total             = float(data.get("actual_total", 0))
        o.discount_percent         = float(data.get("discount_percent", 0))
        o.discount_amount          = float(data.get("discount_amount", 0))
        o.order_discount_percent   = float(data.get("order_discount_percent", 0))
        o.order_discount_amount    = float(data.get("order_discount_amount", 0))
        o.tolerance_discount_total = float(data.get("tolerance_discount_total", 0))
        o.shipping_cost            = float(data.get("shipping_cost", 0))
        o.total                    = float(data.get("total", 0))
        o.amount_received          = float(data.get("amount_received", 0))
        o.rounding_loss            = float(data.get("rounding_loss", 0))
        o.payment_method           =       data.get("payment_method", "Cash")
        o.payment_fee              = float(data.get("payment_fee", 0))
        o.material_cost            = float(data.get("material_cost", 0))
        o.electricity_cost         = float(data.get("electricity_cost", 0))
        o.depreciation_cost        = float(data.get("depreciation_cost", 0))
        o.profit                   = float(data.get("profit", 0))
        o.notes                    =       data.get("notes", "")
        o.is_deleted               = bool( data.get("is_deleted", False))
        o.quote_sent               = bool( data.get("quote_sent", False))
        o.quote_sent_date          =       data.get("quote_sent_date", "")
        o.deposit_amount           = float(data.get("deposit_amount", 0))
        o.deposit_received         = bool( data.get("deposit_received", False))
        o.created_date             =       data.get("created_date", now_str())
        o.updated_date             =       data.get("updated_date", now_str())
        o.confirmed_date           =       data.get("confirmed_date", "")
        o.delivered_date           =       data.get("delivered_date", "")
        o.deleted_date             =       data.get("deleted_date", "")
        # Optional in-memory items list (injected by service layer)
        o.items = [PrintItem.from_dict(i) for i in data.get("items", [])]
        return o


# ---------------------------------------------------------------------------
# FilamentSpool
# ---------------------------------------------------------------------------

@dataclass
class FilamentSpool:
    """Filament spool with pending-reservation system."""

    id:                   str   = field(default_factory=generate_id)
    name:                 str   = ""
    filament_type:        str   = "PLA+"
    brand:                str   = "eSUN"
    color:                str   = "Black"
    category:             str   = "standard"   # "standard" | "remaining"
    status:               str   = "active"     # "active" | "low" | "trash" | "archived"
    initial_weight_grams: float = 1000.0
    current_weight_grams: float = 1000.0
    pending_weight_grams: float = 0.0
    purchase_price_egp:   float = SPOOL_PRICE_FIXED
    purchase_date:        str   = field(default_factory=now_str)
    archived_date:        str   = ""
    notes:                str   = ""
    is_active:            bool  = True

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def available_weight_grams(self) -> float:
        """Current weight minus any pending reservations."""
        return self.current_weight_grams - self.pending_weight_grams

    @property
    def used_weight_grams(self) -> float:
        return self.initial_weight_grams - self.current_weight_grams

    @property
    def remaining_percent(self) -> float:
        if self.initial_weight_grams <= 0:
            return 0.0
        return (self.current_weight_grams / self.initial_weight_grams) * 100

    @property
    def cost_per_gram(self) -> float:
        """0 for 'remaining' spools (already paid); fixed rate for 'standard'."""
        if self.category == "remaining":
            return 0.0
        if self.initial_weight_grams <= 0:
            return DEFAULT_COST_PER_GRAM
        return SPOOL_PRICE_FIXED / self.initial_weight_grams

    @property
    def display_name(self) -> str:
        return self.name if self.name else f"{self.brand} {self.filament_type} {self.color}"

    @property
    def should_show_trash_button(self) -> bool:
        return (
            self.current_weight_grams < TRASH_THRESHOLD_GRAMS
            and self.status != "trash"
        )

    # ------------------------------------------------------------------
    # Business logic  (pending system)
    # ------------------------------------------------------------------

    def reserve_filament(self, grams: float) -> bool:
        """Reserve grams without deducting — returns False if insufficient."""
        if grams <= 0:
            return True
        if grams > self.available_weight_grams:
            return False
        self.pending_weight_grams += grams
        return True

    def release_pending(self, grams: float) -> bool:
        """Release a pending reservation (order cancelled/edited)."""
        if grams <= 0:
            return True
        self.pending_weight_grams = max(0.0, self.pending_weight_grams - grams)
        return True

    def commit_filament(self, grams: float) -> bool:
        """Confirm deduction — reduces current_weight and clears pending."""
        if grams <= 0:
            return True
        if grams > self.current_weight_grams:
            return False
        self.current_weight_grams -= grams
        self.pending_weight_grams  = max(0.0, self.pending_weight_grams - grams)
        # Auto-update status
        if self.current_weight_grams < TRASH_THRESHOLD_GRAMS:
            self.status = "low"
        if self.current_weight_grams < 1:
            self.is_active = False
        return True

    def move_to_trash(self) -> None:
        """Mark spool as trash and deactivate."""
        self.status       = "trash"
        self.is_active    = False
        self.archived_date = now_str()

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id":                   self.id,
            "name":                 self.name or self.display_name,
            "filament_type":        self.filament_type,
            "brand":                self.brand,
            "color":                self.color,
            "category":             self.category,
            "status":               self.status,
            "initial_weight_grams": self.initial_weight_grams,
            "current_weight_grams": self.current_weight_grams,
            "pending_weight_grams": self.pending_weight_grams,
            "purchase_price_egp":   self.purchase_price_egp,
            "purchase_date":        self.purchase_date,
            "archived_date":        self.archived_date,
            "notes":                self.notes,
            "is_active":            self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FilamentSpool":
        s = cls()
        s.id                   =       data.get("id", generate_id())
        s.name                 =       data.get("name", "")
        s.filament_type        =       data.get("filament_type", "PLA+")
        s.brand                =       data.get("brand", "eSUN")
        s.color                =       data.get("color", "Black")
        s.category             =       data.get("category", "standard")
        s.status               =       data.get("status", "active")
        s.initial_weight_grams = float(data.get("initial_weight_grams", 1000.0))
        s.current_weight_grams = float(data.get("current_weight_grams", 1000.0))
        s.pending_weight_grams = float(data.get("pending_weight_grams", 0.0))
        s.purchase_price_egp   = float(data.get("purchase_price_egp", SPOOL_PRICE_FIXED))
        s.purchase_date        =       data.get("purchase_date", now_str())
        s.archived_date        =       data.get("archived_date", "")
        s.notes                =       data.get("notes", "")
        s.is_active            = bool( data.get("is_active", True))
        return s


# ---------------------------------------------------------------------------
# Printer
# ---------------------------------------------------------------------------

@dataclass
class Printer:
    """3D printer with usage and depreciation tracking."""

    id:                        str   = field(default_factory=generate_id)
    name:                      str   = "HIVE 0.1"
    model:                     str   = "Creality Ender-3 Max"
    purchase_price:            float = 25_000.0
    lifetime_kg:               float = 500.0
    total_printed_grams:       float = 0.0
    total_print_time_minutes:  int   = 0
    nozzle_changes:            int   = 0
    nozzle_cost:               float = 100.0
    nozzle_lifetime_grams:     float = 1_500.0
    current_nozzle_grams:      float = 0.0
    electricity_rate_per_hour: float = ELECTRICITY_RATE
    is_active:                 bool  = True
    notes:                     str   = ""
    created_date:              str   = field(default_factory=now_str)

    @property
    def depreciation_per_gram(self) -> float:
        return self.purchase_price / (self.lifetime_kg * 1000)

    @property
    def total_depreciation(self) -> float:
        return self.total_printed_grams * self.depreciation_per_gram

    @property
    def total_electricity_cost(self) -> float:
        return (self.total_print_time_minutes / 60) * self.electricity_rate_per_hour

    @property
    def total_nozzle_cost(self) -> float:
        return self.nozzle_changes * self.nozzle_cost

    @property
    def nozzle_usage_percent(self) -> float:
        if self.nozzle_lifetime_grams <= 0:
            return 0.0
        return (self.current_nozzle_grams / self.nozzle_lifetime_grams) * 100

    def add_print(self, grams: float, minutes: int) -> None:
        """Record a completed print job and auto-track nozzle changes."""
        self.total_printed_grams      += grams
        self.total_print_time_minutes += minutes
        self.current_nozzle_grams     += grams
        if self.current_nozzle_grams >= self.nozzle_lifetime_grams:
            self.nozzle_changes       += 1
            self.current_nozzle_grams -= self.nozzle_lifetime_grams

    def to_dict(self) -> dict:
        return {
            "id":                        self.id,
            "name":                      self.name,
            "model":                     self.model,
            "purchase_price":            self.purchase_price,
            "lifetime_kg":               self.lifetime_kg,
            "total_printed_grams":       self.total_printed_grams,
            "total_print_time_minutes":  self.total_print_time_minutes,
            "nozzle_changes":            self.nozzle_changes,
            "nozzle_cost":               self.nozzle_cost,
            "nozzle_lifetime_grams":     self.nozzle_lifetime_grams,
            "current_nozzle_grams":      self.current_nozzle_grams,
            "electricity_rate_per_hour": self.electricity_rate_per_hour,
            "is_active":                 self.is_active,
            "notes":                     self.notes,
            "created_date":              self.created_date,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Printer":
        p = cls()
        p.id                        =       data.get("id", generate_id())
        p.name                      =       data.get("name", "HIVE 0.1")
        p.model                     =       data.get("model", "Creality Ender-3 Max")
        p.purchase_price            = float(data.get("purchase_price", 25_000.0))
        p.lifetime_kg               = float(data.get("lifetime_kg", 500.0))
        p.total_printed_grams       = float(data.get("total_printed_grams", 0.0))
        p.total_print_time_minutes  = int(  data.get("total_print_time_minutes", 0))
        p.nozzle_changes            = int(  data.get("nozzle_changes", 0))
        p.nozzle_cost               = float(data.get("nozzle_cost", 100.0))
        p.nozzle_lifetime_grams     = float(data.get("nozzle_lifetime_grams", 1_500.0))
        p.current_nozzle_grams      = float(data.get("current_nozzle_grams", 0.0))
        p.electricity_rate_per_hour = float(data.get("electricity_rate_per_hour", ELECTRICITY_RATE))
        p.is_active                 = bool( data.get("is_active", True))
        p.notes                     =       data.get("notes", "")
        p.created_date              =       data.get("created_date", now_str())
        return p


# ---------------------------------------------------------------------------
# FilamentHistory
# ---------------------------------------------------------------------------

@dataclass
class FilamentHistory:
    """Archive record created when a spool is trashed or archived."""

    id:               str   = field(default_factory=generate_id)
    spool_id:         str   = ""
    spool_name:       str   = ""
    color:            str   = ""
    initial_weight:   float = 0.0
    used_weight:      float = 0.0
    remaining_weight: float = 0.0
    waste_weight:     float = 0.0
    archived_date:    str   = field(default_factory=now_str)
    reason:           str   = ""

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "spool_id":         self.spool_id,
            "spool_name":       self.spool_name,
            "color":            self.color,
            "initial_weight":   self.initial_weight,
            "used_weight":      self.used_weight,
            "remaining_weight": self.remaining_weight,
            "waste_weight":     self.waste_weight,
            "archived_date":    self.archived_date,
            "reason":           self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FilamentHistory":
        h = cls()
        h.id               =       data.get("id", generate_id())
        h.spool_id         =       data.get("spool_id", "")
        h.spool_name       =       data.get("spool_name", "")
        h.color            =       data.get("color", "")
        h.initial_weight   = float(data.get("initial_weight", 0.0))
        h.used_weight      = float(data.get("used_weight", 0.0))
        h.remaining_weight = float(data.get("remaining_weight", 0.0))
        h.waste_weight     = float(data.get("waste_weight", 0.0))
        h.archived_date    =       data.get("archived_date", now_str())
        h.reason           =       data.get("reason", "")
        return h


# ---------------------------------------------------------------------------
# PrintFailure
# ---------------------------------------------------------------------------

@dataclass
class PrintFailure:
    """A failed print job with associated costs."""

    id:                    str   = field(default_factory=generate_id)
    date:                  str   = field(default_factory=now_str)
    source:                str   = "Other"
    order_id:              str   = ""
    order_number:          int   = 0
    customer_name:         str   = ""
    item_name:             str   = ""
    reason:                str   = "Other"
    description:           str   = ""
    filament_wasted_grams: float = 0.0
    time_wasted_minutes:   int   = 0
    spool_id:              str   = ""
    color:                 str   = ""
    filament_cost:         float = 0.0
    electricity_cost:      float = 0.0
    total_loss:            float = 0.0
    printer_id:            str   = ""
    printer_name:          str   = ""
    resolved:              bool  = False
    resolution_notes:      str   = ""

    def calculate_costs(
        self,
        cost_per_gram: float = DEFAULT_COST_PER_GRAM,
        electricity_rate: float = ELECTRICITY_RATE,
    ) -> None:
        """Compute filament and electricity costs from wasted material/time."""
        self.filament_cost    = self.filament_wasted_grams * cost_per_gram
        self.electricity_cost = (self.time_wasted_minutes / 60) * electricity_rate
        self.total_loss       = self.filament_cost + self.electricity_cost

    def to_dict(self) -> dict:
        return {
            "id":                    self.id,
            "date":                  self.date,
            "source":                self.source,
            "order_id":              self.order_id,
            "order_number":          self.order_number,
            "customer_name":         self.customer_name,
            "item_name":             self.item_name,
            "reason":                self.reason,
            "description":           self.description,
            "filament_wasted_grams": self.filament_wasted_grams,
            "time_wasted_minutes":   self.time_wasted_minutes,
            "spool_id":              self.spool_id,
            "color":                 self.color,
            "filament_cost":         self.filament_cost,
            "electricity_cost":      self.electricity_cost,
            "total_loss":            self.total_loss,
            "printer_id":            self.printer_id,
            "printer_name":          self.printer_name,
            "resolved":              self.resolved,
            "resolution_notes":      self.resolution_notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PrintFailure":
        f = cls()
        f.id                    =       data.get("id", generate_id())
        f.date                  =       data.get("date", now_str())
        f.source                =       data.get("source", "Other")
        f.order_id              =       data.get("order_id", "")
        f.order_number          = int(  data.get("order_number", 0))
        f.customer_name         =       data.get("customer_name", "")
        f.item_name             =       data.get("item_name", "")
        f.reason                =       data.get("reason", "Other")
        f.description           =       data.get("description", "")
        f.filament_wasted_grams = float(data.get("filament_wasted_grams", 0.0))
        f.time_wasted_minutes   = int(  data.get("time_wasted_minutes", 0))
        f.spool_id              =       data.get("spool_id", "")
        f.color                 =       data.get("color", "")
        f.filament_cost         = float(data.get("filament_cost", 0.0))
        f.electricity_cost      = float(data.get("electricity_cost", 0.0))
        f.total_loss            = float(data.get("total_loss", 0.0))
        f.printer_id            =       data.get("printer_id", "")
        f.printer_name          =       data.get("printer_name", "")
        f.resolved              = bool( data.get("resolved", False))
        f.resolution_notes      =       data.get("resolution_notes", "")
        return f


# ---------------------------------------------------------------------------
# Expense
# ---------------------------------------------------------------------------

@dataclass
class Expense:
    """A business expense entry."""

    id:               str   = field(default_factory=generate_id)
    date:             str   = field(default_factory=now_str)
    category:         str   = "Other"
    name:             str   = ""
    description:      str   = ""
    amount:           float = 0.0
    quantity:         int   = 1
    total_cost:       float = 0.0
    supplier:         str   = ""
    receipt_number:   str   = ""
    is_recurring:     bool  = False
    recurring_period: str   = ""

    def calculate_total(self) -> None:
        """Set total_cost = amount × quantity."""
        self.total_cost = self.amount * self.quantity

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "date":             self.date,
            "category":         self.category,
            "name":             self.name,
            "description":      self.description,
            "amount":           self.amount,
            "quantity":         self.quantity,
            "total_cost":       self.total_cost,
            "supplier":         self.supplier,
            "receipt_number":   self.receipt_number,
            "is_recurring":     self.is_recurring,
            "recurring_period": self.recurring_period,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Expense":
        e = cls()
        e.id               =       data.get("id", generate_id())
        e.date             =       data.get("date", now_str())
        e.category         =       data.get("category", "Other")
        e.name             =       data.get("name", "")
        e.description      =       data.get("description", "")
        e.amount           = float(data.get("amount", 0.0))
        e.quantity         = int(  data.get("quantity", 1))
        e.total_cost       = float(data.get("total_cost", 0.0))
        e.supplier         =       data.get("supplier", "")
        e.receipt_number   =       data.get("receipt_number", "")
        e.is_recurring     = bool( data.get("is_recurring", False))
        e.recurring_period =       data.get("recurring_period", "")
        return e


# ---------------------------------------------------------------------------
# Statistics  (aggregate — built by FinanceService, not stored in DB)
# ---------------------------------------------------------------------------

@dataclass
class Statistics:
    """Aggregated business statistics computed by FinanceService."""

    # Orders
    total_orders:     int   = 0
    completed_orders: int   = 0
    rd_orders:        int   = 0

    # Revenue
    total_revenue:       float = 0.0
    total_shipping:      float = 0.0
    total_payment_fees:  float = 0.0
    total_rounding_loss: float = 0.0

    # Production costs
    total_material_cost:     float = 0.0
    total_electricity_cost:  float = 0.0
    total_depreciation_cost: float = 0.0
    total_nozzle_cost:       float = 0.0

    # Failures
    total_failures:          int   = 0
    total_failure_cost:      float = 0.0
    failure_filament_wasted: float = 0.0
    failure_time_wasted:     int   = 0

    # Expenses
    total_expenses:         float = 0.0
    expenses_tools:         float = 0.0
    expenses_consumables:   float = 0.0
    expenses_maintenance:   float = 0.0
    expenses_other:         float = 0.0

    # Profit
    gross_profit: float = 0.0
    total_profit: float = 0.0

    # Production
    total_weight_printed:  float = 0.0
    total_time_printed:    int   = 0
    total_filament_used:   float = 0.0
    total_filament_waste:  float = 0.0
    total_tolerance_discounts: float = 0.0

    # Inventory
    active_spools:     int   = 0
    remaining_filament: float = 0.0
    pending_filament:  float = 0.0

    # Counts
    total_customers: int = 0
    total_printers:  int = 0

    @property
    def profit_margin(self) -> float:
        if self.total_revenue <= 0:
            return 0.0
        return (self.total_profit / self.total_revenue) * 100

    @property
    def gross_margin(self) -> float:
        if self.total_revenue <= 0:
            return 0.0
        return (self.gross_profit / self.total_revenue) * 100

    @property
    def total_production_costs(self) -> float:
        return (
            self.total_material_cost
            + self.total_electricity_cost
            + self.total_depreciation_cost
            + self.total_nozzle_cost
        )

    @property
    def total_costs(self) -> float:
        return self.total_production_costs + self.total_failure_cost + self.total_expenses