"""
src/services/_compat.py
=======================
Compatibility layer between the v5 tab/service API and the v4
JSON DatabaseManager.

Call ``apply_all_patches()`` once in ``main.py`` BEFORE importing any service.

What this fixes
---------------
DatabaseManager (v4 JSON) patches
  • save_spool / save_printer / save_expense / save_failure  — v4 expects
    model objects; v5 services pass dicts.  Patched to accept both.
  • get_all_orders(include_deleted=False)  — v4 doesn't accept kwargs.
  • get_all_failures / get_all_expenses / get_all_spools / get_all_printers
    — v4 returns model objects; v5 services call .from_dict(row).
    Patched to return plain dicts so from_dict() works.
  • execute_query / execute_update  — used by SettingsTab.  Mapped to
    v4 settings dict.
  • get_orders_by_customer — not in v4; added via linear scan.
  • delete_customer — not in v4; added.
  • backup_database / export_to_csv — already exist, just normalise return.
  • get_table_count — not in v4; added.

InventoryService patches
  • get_spools(status_filter)
  • get_inventory_summary()
  • move_to_trash(id) → (bool, str)
  • add_spool(initial_weight=, price=) keyword aliases

FinanceService patches
  • get_expenses(category_filter, month_filter)
  • get_expense(id)
  • add_expense(notes=, total=) keyword aliases
  • update_expense(notes=) keyword alias
  • log_failure(**flat_kwargs)
  • get_failures(reason_filter, source_filter)
  • delete_failure(id) → (bool, str)
  • get_failure_stats() → consistent keys
  • get_expense_stats() → consistent keys
  • get_full_statistics() → flat dict
  • get_order_stats() → flat dict
  • get_monthly_revenue(start, end)
  • get_order_status_breakdown(start, end)
  • get_expenses_by_category(start, end)
  • get_filament_usage_by_color(start, end)

CustomerService patches
  • get_customer_orders(id)
  • delete_customer(id) → (bool, str)

Model property aliases (read-only, non-breaking)
  Order:         final_total, rate_discount
  PrintItem:     weight_grams, actual_weight, print_time_minutes,
                 nozzle_size, layer_height, infill_percent,
                 support_type, scale_percent
  FilamentSpool: current_weight, pending_weight, available_weight,
                 price, cost_per_gram
  PrintFailure:  filament_wasted, print_time_wasted, material_cost,
                 electricity_cost (already exists on model), total_cost
  Expense:       total, notes
  Customer:      (total_orders / total_spent already exist in v4 model)
"""

import logging
from collections import defaultdict, Counter
from datetime import date as _date
from typing import List, Optional

log = logging.getLogger(__name__)

# ============================================================================
# DatabaseManager patches
# ============================================================================

def _patch_database(cls):
    """Patch v4 DatabaseManager to speak the v5 service API."""

    # ------------------------------------------------------------------ #
    #  save_* methods — accept dict OR model object                        #
    # ------------------------------------------------------------------ #

    def save_spool(self, spool_or_dict):
        d = spool_or_dict if isinstance(spool_or_dict, dict) else spool_or_dict.to_dict()
        self.data["spools"][d["id"]] = d
        return self._save()

    def save_printer(self, printer_or_dict):
        d = printer_or_dict if isinstance(printer_or_dict, dict) else printer_or_dict.to_dict()
        self.data["printers"][d["id"]] = d
        return self._save()

    def save_expense(self, expense_or_dict):
        d = expense_or_dict if isinstance(expense_or_dict, dict) else expense_or_dict.to_dict()
        # Recalculate total_cost when saving dict
        if isinstance(expense_or_dict, dict):
            d["total_cost"] = d.get("amount", 0) * d.get("quantity", 1)
        else:
            expense_or_dict.calculate_total()
            d = expense_or_dict.to_dict()
        self.data.setdefault("expenses", {})[d["id"]] = d
        return self._save()

    def save_failure(self, failure_or_dict):
        d = failure_or_dict if isinstance(failure_or_dict, dict) else failure_or_dict.to_dict()
        if not isinstance(failure_or_dict, dict):
            failure_or_dict.calculate_costs()
            d = failure_or_dict.to_dict()
        self.data.setdefault("failures", {})[d["id"]] = d
        return self._save()

    # ------------------------------------------------------------------ #
    #  get_all_* — return plain dicts so services can call .from_dict()   #
    # ------------------------------------------------------------------ #

    def get_all_orders_compat(self, include_deleted: bool = False):
        result = []
        for d in self.data.get("orders", {}).values():
            if not include_deleted and d.get("is_deleted", False):
                continue
            result.append(d)              # return raw dict
        return sorted(result, key=lambda d: d.get("created_date", ""),
                      reverse=True)

    def get_all_spools_compat(self):
        return list(self.data.get("spools", {}).values())

    def get_active_spools_compat(self):
        from src.core.models import SpoolStatus
        return [d for d in self.get_all_spools_compat()
                if d.get("is_active") and
                d.get("current_weight_grams", 0) > 0 and
                d.get("status") != SpoolStatus.TRASH.value]

    def get_spools_by_color_compat(self, color: str):
        return sorted(
            [d for d in self.get_active_spools_compat()
             if d.get("color") == color],
            key=lambda d: d.get("current_weight_grams", 0) - d.get("pending_weight_grams", 0),
            reverse=True,
        )

    def get_all_printers_compat(self):
        return list(self.data.get("printers", {}).values())

    def get_all_failures_compat(self):
        rows = list(self.data.get("failures", {}).values())
        return sorted(rows, key=lambda d: d.get("date", ""), reverse=True)

    def get_all_expenses_compat(self):
        rows = list(self.data.get("expenses", {}).values())
        return sorted(rows, key=lambda d: d.get("date", ""), reverse=True)

    def get_all_customers_compat(self):
        return list(self.data.get("customers", {}).values())

    def get_customer_compat(self, customer_id: str):
        return self.data.get("customers", {}).get(customer_id)

    def search_customers_compat(self, query: str):
        q = query.lower().strip()
        return [
            d for d in self.data.get("customers", {}).values()
            if q in d.get("name", "").lower() or q in d.get("phone", "")
        ]

    def get_order_compat(self, order_id: str):
        return self.data.get("orders", {}).get(order_id)

    def get_spool_compat(self, spool_id: str):
        return self.data.get("spools", {}).get(spool_id)

    def get_orders_by_customer(self, customer_id: str):
        return [d for d in self.data.get("orders", {}).values()
                if d.get("customer_id") == customer_id and
                not d.get("is_deleted", False)]

    def delete_customer(self, customer_id: str) -> bool:
        if customer_id in self.data.get("customers", {}):
            del self.data["customers"][customer_id]
            return self._save()
        return False

    def get_table_count(self, table: str) -> int:
        table_map = {
            "customers":      "customers",
            "orders":         "orders",
            "filament_spools":"spools",
            "printers":       "printers",
            "expenses":       "expenses",
            "print_failures": "failures",
        }
        key = table_map.get(table, table)
        return len(self.data.get(key, {}))

    # ------------------------------------------------------------------ #
    #  execute_query / execute_update — used by SettingsTab               #
    # ------------------------------------------------------------------ #

    def execute_query(self, sql: str, params=None):
        """Minimal SQL emulation for settings reads."""
        sql_upper = sql.strip().upper()
        if "FROM SETTINGS" in sql_upper:
            settings = self.data.get("settings", {})
            # Handle WHERE key IN (?,?,...)
            if params and ("WHERE KEY IN" in sql_upper or
                           "WHERE KEY =" in sql_upper):
                keys = list(params) if not isinstance(params, (list, tuple)) else params
                return [{"key": k, "value": str(settings.get(k, ""))}
                        for k in keys if k in settings]
            # SELECT * or SELECT key, value
            return [{"key": k, "value": str(v)}
                    for k, v in settings.items()]
        # COUNT queries
        if "COUNT(*)" in sql_upper:
            table = None
            for t in ("customers","orders","spools","printers","expenses","failures"):
                if t in sql_upper or t.replace("_","") in sql_upper.replace("_",""):
                    table = t
                    break
            if table:
                return [{"cnt": get_table_count(self, table)}]
        return []

    def execute_update(self, sql: str, params=None):
        """Minimal SQL emulation for settings writes."""
        sql_upper = sql.strip().upper()
        if "INSERT INTO SETTINGS" in sql_upper or "SETTINGS" in sql_upper:
            if isinstance(params, (list, tuple)) and len(params) >= 2:
                key, value = str(params[0]), str(params[1])
                self.data.setdefault("settings", {})[key] = value
                return self._save()
            elif isinstance(params, dict):
                k = params.get("key") or (list(params.values())[0] if params else None)
                v = params.get("value") or (list(params.values())[1] if len(params) > 1 else "")
                if k:
                    self.data.setdefault("settings", {})[str(k)] = str(v)
                    return self._save()
        if "DELETE FROM USERS" in sql_upper:
            if params:
                uid = params[0] if isinstance(params, (list, tuple)) else params
                users_data = self.data.get("users_json", {})  # not in v4 db
        return True

    # ------------------------------------------------------------------ #
    #  backup_database normalisation                                       #
    # ------------------------------------------------------------------ #

    def backup_database_compat(self):
        """Return Path object (tabs use str() on it)."""
        path_str = self._backup_original()
        from pathlib import Path
        return Path(path_str)

    def export_to_csv_compat(self, export_dir: str = "exports"):
        """Return the export directory path."""
        files = self._export_original(export_dir)
        from pathlib import Path
        return Path(export_dir)

    # ------------------------------------------------------------------ #
    #  Apply all patches                                                   #
    # ------------------------------------------------------------------ #

    cls.save_spool              = save_spool
    cls.save_printer            = save_printer
    cls.save_expense            = save_expense
    cls.save_failure            = save_failure

    cls.get_all_orders          = get_all_orders_compat
    cls.get_all_spools          = get_all_spools_compat
    cls.get_active_spools       = get_active_spools_compat
    cls.get_spools_by_color     = get_spools_by_color_compat
    cls.get_all_printers        = get_all_printers_compat
    cls.get_all_failures        = get_all_failures_compat
    cls.get_all_expenses        = get_all_expenses_compat
    cls.get_all_customers       = get_all_customers_compat
    cls.get_customer            = get_customer_compat
    cls.search_customers        = search_customers_compat
    cls.get_order               = get_order_compat
    cls.get_spool               = get_spool_compat
    cls.get_orders_by_customer  = get_orders_by_customer
    cls.delete_customer         = delete_customer
    cls.get_table_count         = get_table_count
    cls.execute_query           = execute_query
    cls.execute_update          = execute_update

    if not hasattr(cls, "_backup_original"):
        cls._backup_original  = cls.backup_database
        cls.backup_database   = backup_database_compat
    if not hasattr(cls, "_export_original"):
        cls._export_original  = cls.export_to_csv
        cls.export_to_csv     = export_to_csv_compat

    return cls


# ============================================================================
# InventoryService patches
# ============================================================================

def _patch_inventory(cls):

    def get_spools(self, status_filter: str = "active") -> list:
        all_rows = self._db.get_all_spools()
        from src.core.models import FilamentSpool
        spools = [FilamentSpool.from_dict(r) for r in all_rows]
        if status_filter == "all":
            return spools
        if status_filter == "active":
            return [s for s in spools if s.is_active and
                    s.status not in ("trash", "archived")]
        if status_filter in ("low", "trash", "archived"):
            return [s for s in spools if s.status == status_filter]
        return spools

    def get_inventory_summary(self) -> dict:
        from src.core.models import FilamentSpool
        spools = [FilamentSpool.from_dict(r)
                  for r in self._db.get_all_spools()]
        active = [s for s in spools if s.is_active and
                  s.status not in ("trash", "archived")]
        return {
            "active_spools":   len(active),
            "total_weight":    sum(s.current_weight_grams for s in active),
            "total_pending":   sum(s.pending_weight_grams for s in active),
            "total_available": sum(
                s.current_weight_grams - s.pending_weight_grams
                for s in active),
            "total_value":     sum(
                s.current_weight_grams *
                (s.purchase_price_egp / s.initial_weight_grams
                 if s.initial_weight_grams > 0 else 0)
                for s in active),
        }

    def move_to_trash(self, spool_id: str) -> tuple:
        try:
            ok = self._db.move_spool_to_trash(spool_id, reason="trash")
            return (True, "Moved to trash.") if ok else (False, "Spool not found.")
        except Exception as exc:
            return False, str(exc)

    def add_spool_compat(self, color: str, category: str = "standard",
                          brand: str = "eSUN", filament_type: str = "PLA+",
                          initial_weight: float = None,
                          initial_weight_grams: float = 1000.0,
                          price: float = None,
                          purchase_price_egp: float = None,
                          notes: str = "", name: str = "", **_kw):
        from src.core.config import SPOOL_PRICE_FIXED
        w = initial_weight if initial_weight is not None else initial_weight_grams
        p = (price if price is not None
             else purchase_price_egp if purchase_price_egp is not None
             else (SPOOL_PRICE_FIXED if category == "standard" else 0.0))
        return self._add_spool_orig(
            color=color, category=category, brand=brand,
            filament_type=filament_type, name=name,
            initial_weight_grams=w, purchase_price_egp=p, notes=notes)

    cls.get_spools            = get_spools
    cls.get_inventory_summary = get_inventory_summary
    cls.move_to_trash         = move_to_trash
    if not hasattr(cls, "_add_spool_orig"):
        cls._add_spool_orig = cls.add_spool
        cls.add_spool       = add_spool_compat
    return cls


# ============================================================================
# FinanceService patches
# ============================================================================

def _patch_finance(cls):

    def get_expenses(self, category_filter=None, month_filter=None) -> list:
        from src.core.models import Expense
        expenses = [Expense.from_dict(r) for r in self._db.get_all_expenses()]
        if category_filter:
            expenses = [e for e in expenses if e.category == category_filter]
        if month_filter:
            expenses = [e for e in expenses
                        if e.date and e.date[:7] == month_filter]
        return expenses

    def get_expense(self, expense_id: str):
        from src.core.models import Expense
        for r in self._db.get_all_expenses():
            if r.get("id") == expense_id:
                return Expense.from_dict(r)
        return None

    def add_expense_compat(self, category: str, name: str, amount: float,
                            quantity: int = 1, supplier: str = "",
                            notes: str = "", description: str = "",
                            is_recurring: bool = False,
                            recurring_period: str = "",
                            total: float = None, date: str = "", **_kw):
        return self._add_expense_orig(
            category=category, name=name, amount=amount,
            quantity=quantity, supplier=supplier,
            description=notes or description,
            is_recurring=is_recurring,
            recurring_period=recurring_period,
            date=date)

    def update_expense_compat(self, expense_id: str, **kwargs):
        if "notes" in kwargs:
            kwargs["description"] = kwargs.pop("notes")
        kwargs.pop("total", None)
        return self._update_expense_orig(expense_id, **kwargs)

    def get_failures(self, reason_filter=None, source_filter=None) -> list:
        from src.core.models import PrintFailure
        failures = [PrintFailure.from_dict(r)
                    for r in self._db.get_all_failures()]
        if reason_filter:
            failures = [f for f in failures if f.reason == reason_filter]
        if source_filter:
            failures = [f for f in failures if f.source == source_filter]
        return failures

    def delete_failure(self, failure_id: str) -> tuple:
        try:
            ok = self._db.delete_failure(failure_id)
            return (True, "Deleted.") if ok else (False, "Not found.")
        except Exception as exc:
            return False, str(exc)

    def get_failure_stats(self) -> dict:
        from src.core.models import PrintFailure
        failures = [PrintFailure.from_dict(r)
                    for r in self._db.get_all_failures()]
        return {
            "count":          len(failures),
            "total_filament": sum(f.filament_wasted_grams for f in failures),
            "total_time":     sum(f.time_wasted_minutes   for f in failures),
            "total_cost":     sum(f.total_loss            for f in failures),
        }

    def get_expense_stats_compat(self) -> dict:
        from src.core.models import Expense
        expenses = [Expense.from_dict(r) for r in self._db.get_all_expenses()]
        this_month = _date.today().strftime("%Y-%m")
        monthly_rec = sum(
            e.total_cost for e in expenses
            if e.is_recurring and e.recurring_period == "monthly")
        return {
            "total":             sum(e.total_cost for e in expenses),
            "count":             len(expenses),
            "this_month":        sum(e.total_cost for e in expenses
                                     if e.date and e.date[:7] == this_month),
            "monthly_recurring": monthly_rec,
        }

    def log_failure_compat(self, reason: str = "", source: str = "",
                            filament_wasted: float = 0,
                            print_time_wasted: int = 0,
                            material_cost: float = 0,
                            electricity_cost: float = 0,
                            total_cost: float = 0,
                            notes: str = "", **_kw):
        return self._log_failure_orig(
            source=source or "Other",
            item_name=notes or reason or "Unknown",
            reason=reason or "Other",
            filament_wasted_grams=filament_wasted,
            time_wasted_minutes=int(print_time_wasted),
            description=notes,
        )

    def get_full_statistics(self) -> dict:
        try:
            stats = self.calculate_statistics()
        except Exception as exc:
            log.error("calculate_statistics failed: %s", exc)
            return {}
        return {
            "total_revenue":      getattr(stats, "total_revenue", 0),
            "total_shipping":     getattr(stats, "total_shipping", 0),
            "total_fees":         getattr(stats, "total_payment_fees", 0),
            "total_rounding":     getattr(stats, "total_rounding_loss", 0),
            "total_material":     getattr(stats, "total_material_cost", 0),
            "total_electricity":  getattr(stats, "total_electricity_cost", 0),
            "total_depreciation": getattr(stats, "total_depreciation_cost", 0),
            "total_nozzle":       getattr(stats, "total_nozzle_cost", 0),
            "gross_profit":       getattr(stats, "gross_profit", 0),
            "total_weight":       getattr(stats, "total_weight_printed", 0),
            "total_print_time":   getattr(stats, "total_time_printed", 0),
        }

    def get_order_stats(self) -> dict:
        from src.core.models import Order
        rows = self._db.get_all_orders(include_deleted=False)
        orders = [Order.from_dict(r) for r in rows]
        return {
            "total":     len(orders),
            "delivered": sum(1 for o in orders if o.status == "Delivered"),
            "rd":        sum(1 for o in orders if o.is_rd_project),
            "cancelled": sum(1 for o in orders if o.status == "Cancelled"),
        }

    def get_monthly_revenue(self, start_date: str, end_date: str) -> list:
        rows = self.get_monthly_breakdown(months=36)
        result = []
        for r in rows:
            if r["month"] < start_date[:7]:
                continue
            if r["month"] > end_date[:7]:
                continue
            costs = (r.get("material_cost", 0) +
                     r.get("electricity_cost", 0) +
                     r.get("depreciation_cost", 0) +
                     r.get("failure_cost", 0) +
                     r.get("expense_cost", 0))
            result.append({
                "month":   r["month"],
                "revenue": round(r.get("revenue", 0), 2),
                "costs":   round(costs, 2),
                "profit":  round(r.get("profit", 0), 2),
            })
        return result

    def get_order_status_breakdown(self, start_date: str, end_date: str) -> list:
        from src.core.models import Order
        rows = self._db.get_all_orders(include_deleted=False)
        orders = [Order.from_dict(r) for r in rows
                  if r.get("created_date", "")[:10] >= start_date[:10]
                  and r.get("created_date", "")[:10] <= end_date[:10]]
        counter = Counter(o.status for o in orders)
        return [{"status": k, "count": v}
                for k, v in sorted(counter.items(), key=lambda x: -x[1])]

    def get_expenses_by_category(self, start_date: str, end_date: str) -> list:
        from src.core.models import Expense
        expenses = [Expense.from_dict(r) for r in self._db.get_all_expenses()]
        totals: dict = defaultdict(float)
        for e in expenses:
            if (e.date and e.date[:10] >= start_date[:10]
                    and e.date[:10] <= end_date[:10]):
                totals[e.category] += e.total_cost
        return [{"category": k, "total": round(v, 2)}
                for k, v in sorted(totals.items(), key=lambda x: -x[1])]

    def get_filament_usage_by_color(self, start_date: str, end_date: str) -> list:
        from src.core.models import Order
        rows = self._db.get_all_orders(include_deleted=False)
        usage: dict = defaultdict(float)
        for r in rows:
            if r.get("status") in ("Cancelled", "Draft"):
                continue
            d = r.get("created_date", "")[:10]
            if d < start_date[:10] or d > end_date[:10]:
                continue
            for item_d in r.get("items", []):
                color = item_d.get("color", "Unknown")
                w = (item_d.get("actual_weight_grams", 0) or
                     item_d.get("estimated_weight_grams", 0))
                q = item_d.get("quantity", 1)
                usage[color] += w * q
        return [{"color": k, "grams": round(v, 1)}
                for k, v in sorted(usage.items(), key=lambda x: -x[1])]

    # Wrap methods that don't exist yet
    if not hasattr(cls, "_add_expense_orig"):
        cls._add_expense_orig      = cls.add_expense
        cls.add_expense            = add_expense_compat
    if not hasattr(cls, "_update_expense_orig"):
        cls._update_expense_orig   = cls.update_expense
        cls.update_expense         = update_expense_compat
    if not hasattr(cls, "_log_failure_orig"):
        cls._log_failure_orig      = cls.log_failure
        cls.log_failure            = log_failure_compat

    cls.get_expenses                = get_expenses
    cls.get_expense                 = get_expense
    cls.get_failures                = get_failures
    cls.delete_failure              = delete_failure
    cls.get_failure_stats           = get_failure_stats
    cls.get_expense_stats           = get_expense_stats_compat
    cls.get_full_statistics         = get_full_statistics
    cls.get_order_stats             = get_order_stats
    cls.get_monthly_revenue         = get_monthly_revenue
    cls.get_order_status_breakdown  = get_order_status_breakdown
    cls.get_expenses_by_category    = get_expenses_by_category
    cls.get_filament_usage_by_color = get_filament_usage_by_color
    return cls


# ============================================================================
# CustomerService patches
# ============================================================================

def _patch_customers(cls):

    def get_customer_orders(self, customer_id: str) -> list:
        from src.core.models import Order
        rows = self._db.get_orders_by_customer(customer_id)
        return [Order.from_dict(r) for r in rows]

    def delete_customer(self, customer_id: str) -> tuple:
        try:
            ok = self._db.delete_customer(customer_id)
            return (True, "Deleted.") if ok else (False, "Not found.")
        except Exception as exc:
            return False, str(exc)

    cls.get_customer_orders = get_customer_orders
    cls.delete_customer     = delete_customer
    return cls


# ============================================================================
# Model property aliases
# ============================================================================

def _patch_models():
    from src.core.models import (Order, PrintItem, FilamentSpool,
                                  PrintFailure, Expense)

    # -- Order --
    if not hasattr(Order, "final_total"):
        Order.final_total   = property(lambda self: self.total)
        Order.rate_discount = property(lambda self: self.discount_amount)

    # -- PrintItem --
    if not hasattr(PrintItem, "weight_grams"):
        PrintItem.weight_grams        = property(
            lambda self: self.estimated_weight_grams)
        PrintItem.actual_weight       = property(
            lambda self: self.actual_weight_grams)
        PrintItem.print_time_minutes  = property(
            lambda self: self.estimated_time_minutes)
        PrintItem.nozzle_size         = property(
            lambda self: getattr(self.settings, "nozzle_size",
                                 getattr(self.settings, "nozzle", 0.4))
                         if self.settings else 0.4)
        PrintItem.layer_height        = property(
            lambda self: getattr(self.settings, "layer_height", 0.2)
                         if self.settings else 0.2)
        PrintItem.infill_percent      = property(
            lambda self: getattr(self.settings, "infill_percent", 20)
                         if self.settings else 20)
        PrintItem.support_type        = property(
            lambda self: getattr(self.settings, "support_type", "None")
                         if self.settings else "None")
        PrintItem.scale_percent       = property(
            lambda self: getattr(self.settings, "scale", 100)
                         if self.settings else 100)

    # -- FilamentSpool --
    if not hasattr(FilamentSpool, "current_weight"):
        FilamentSpool.current_weight   = property(
            lambda self: self.current_weight_grams)
        FilamentSpool.pending_weight   = property(
            lambda self: self.pending_weight_grams)
        FilamentSpool.available_weight = property(
            lambda self: self.current_weight_grams - self.pending_weight_grams)
        FilamentSpool.price            = property(
            lambda self: self.purchase_price_egp)
        FilamentSpool.cost_per_gram    = property(
            lambda self: (self.purchase_price_egp / self.initial_weight_grams
                          if self.initial_weight_grams > 0 else 0.0))

    # -- PrintFailure --
    if not hasattr(PrintFailure, "filament_wasted"):
        PrintFailure.filament_wasted   = property(
            lambda self: self.filament_wasted_grams)
        PrintFailure.print_time_wasted = property(
            lambda self: self.time_wasted_minutes)
        PrintFailure.material_cost     = property(
            lambda self: self.filament_cost)
        # electricity_cost already exists on the model
        PrintFailure.total_cost        = property(
            lambda self: self.total_loss)
        PrintFailure.notes             = property(
            lambda self: self.description)

    # -- Expense --
    if not hasattr(Expense, "total"):
        Expense.total = property(lambda self: self.total_cost)
        Expense.notes = property(lambda self: self.description)


# ============================================================================
# Main entry point
# ============================================================================

def apply_all_patches() -> None:
    """
    Apply every compatibility patch.
    Must be called ONCE in main.py before importing any service class.
    """
    from src.core.database import DatabaseManager
    from src.services.inventory_service import InventoryService
    from src.services.finance_service   import FinanceService
    from src.services.customer_service  import CustomerService

    _patch_database(DatabaseManager)
    _patch_inventory(InventoryService)
    _patch_finance(FinanceService)
    _patch_customers(CustomerService)
    _patch_models()

    log.info("✓ All compatibility patches applied.")