"""
src/core/_model_aliases.py
==========================
Adds missing property aliases to existing model dataclasses so that
the v5 UI code (tabs, pdf_service) works without modifying the models.

Called by src/services/_compat.apply_all_patches().

Aliases added to Order:
  .final_total     → .total
  .rate_discount   → .discount_amount

Aliases added to PrintItem:
  .weight_grams    → .estimated_weight_grams
  .actual_weight   → .actual_weight_grams
  .print_time_minutes → .estimated_time_minutes

These are read-only properties — setting them still uses the original name.
"""


def apply_model_aliases() -> None:
    _patch_order()
    _patch_print_item()


def _patch_order():
    from src.core.models import Order

    if hasattr(Order, "final_total"):
        return  # already patched

    Order.final_total   = property(lambda self: self.total)
    Order.rate_discount = property(lambda self: self.discount_amount)


def _patch_print_item():
    from src.core.models import PrintItem

    if hasattr(PrintItem, "weight_grams"):
        return

    PrintItem.weight_grams       = property(
        lambda self: self.estimated_weight_grams)
    PrintItem.actual_weight      = property(
        lambda self: self.actual_weight_grams)
    PrintItem.print_time_minutes = property(
        lambda self: self.estimated_time_minutes)
    PrintItem.nozzle_size        = property(
        lambda self: getattr(self.settings, "nozzle_size",
                             getattr(self.settings, "nozzle", 0.4))
                     if self.settings else 0.4)
    PrintItem.layer_height       = property(
        lambda self: getattr(self.settings, "layer_height", 0.2)
                     if self.settings else 0.2)
    PrintItem.infill_percent     = property(
        lambda self: getattr(self.settings, "infill_percent", 20)
                     if self.settings else 20)
    PrintItem.support_type       = property(
        lambda self: getattr(self.settings, "support_type", "None")
                     if self.settings else "None")
    PrintItem.scale_percent      = property(
        lambda self: getattr(self.settings, "scale", 100)
                     if self.settings else 100)