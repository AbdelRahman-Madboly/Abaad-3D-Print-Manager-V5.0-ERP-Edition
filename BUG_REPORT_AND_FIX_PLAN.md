# Abaad ERP v5.0 — Bug Report & Fix Plan

> **Purpose:** This document catalogues every confirmed bug found by static
> code analysis of the project files, explains the root cause of each,
> specifies exactly which files must be changed, and provides the precise
> code fix. Use this document in a fresh chat session: paste the file
> contents that need editing and apply the fixes one by one, in order.

---

## Quick Summary

| # | Severity | Crashes App? | File to Fix | Short Description |
|---|----------|-------------|-------------|-------------------|
| 1 | 🔴 Critical | **YES** | `failures_tab.py` | `get_all_failures()` called with wrong keyword arguments |
| 2 | 🔴 Critical | **YES (on load)** | `failures_tab.py` | Wrong attribute names used on `PrintFailure` model |
| 3 | 🔴 Critical | **YES (on add)** | `failures_tab.py` | `log_failure()` called with wrong keyword arguments |
| 4 | 🔴 Critical | **YES (on add)** | `failures_tab.py` | `get_spools()` method does not exist on `InventoryService` |
| 5 | 🟠 High | **YES (Stats tab)** | `stats_tab.py` | `get_order_stats()` does not exist on `FinanceService` |
| 6 | 🟠 High | Silent wrong data | `stats_tab.py` | Wrong dict keys used from `get_failure_stats()` |
| 7 | 🟠 High | Silent wrong data | `stats_tab.py` | Wrong dict key `"total"` used from `get_expense_stats()` |
| 8 | 🟡 Medium | Silent wrong data | `failures_tab.py` | Wrong dict keys used from `get_failure_stats()` in summary panel |
| 9 | 🟡 Medium | No | `README.md` | Pinned package versions are out of date |

---

## Bug 1 — CRASH ON STARTUP (Root Cause of the Error You Saw)

### Error
```
TypeError: FinanceService.get_all_failures() got an unexpected keyword argument 'reason_filter'
```

### Location
`failures_tab.py` → `_load_failures()` method (line 172)

### Root Cause
The UI calls `get_all_failures()` with two filter arguments that the service
method simply does not accept. The service method has this signature:

```python
# finance_service.py  (actual)
def get_all_failures(self) -> List[PrintFailure]:
    """Return all failure records, newest first."""
    return [PrintFailure.from_dict(r) for r in self._db.get_all_failures()]
```

But the tab calls it like:
```python
# failures_tab.py  (broken call)
failures = self._fin.get_all_failures(
    reason_filter=None if reason == "All" else reason,
    source_filter=None if source == "All" else source,
)
```

### Fix

**Option A — Fix the service** (recommended, keeps filtering server-side):

In `finance_service.py`, change `get_all_failures()` to accept and apply the
filters:

```python
def get_all_failures(
    self,
    reason_filter: Optional[str] = None,
    source_filter: Optional[str] = None,
) -> List[PrintFailure]:
    """Return failure records, newest first.

    Args:
        reason_filter: If given, only return records with this reason.
        source_filter: If given, only return records with this source.
    """
    rows = self._db.get_all_failures()
    failures = [PrintFailure.from_dict(r) for r in rows]
    if reason_filter:
        failures = [f for f in failures if f.reason == reason_filter]
    if source_filter:
        failures = [f for f in failures if f.source == source_filter]
    return failures
```

**Files affected:** `finance_service.py`

---

## Bug 2 — CRASH ON LOAD (Wrong Model Attribute Names)

### Error
```
AttributeError: 'PrintFailure' object has no attribute 'filament_wasted'
AttributeError: 'PrintFailure' object has no attribute 'print_time_wasted'
AttributeError: 'PrintFailure' object has no attribute 'material_cost'
AttributeError: 'PrintFailure' object has no attribute 'total_cost'
AttributeError: 'PrintFailure' object has no attribute 'notes'
```
(These would crash immediately after Bug 1 is fixed, in the same `_load_failures()` call)

### Location
`failures_tab.py` → `_load_failures()` method (lines 178–188)

### Root Cause
The tab uses invented field names that do not exist on the `PrintFailure`
dataclass. Comparing what the tab uses vs what the model actually defines:

| Tab uses (wrong) | Model actually has |
|---|---|
| `fl.filament_wasted` | `fl.filament_wasted_grams` |
| `fl.print_time_wasted` | `fl.time_wasted_minutes` |
| `fl.material_cost` | `fl.filament_cost` |
| `fl.electricity_cost` | ✅ exists |
| `fl.total_cost` | `fl.total_loss` |
| `fl.notes` | `fl.description` |

### Fix

In `failures_tab.py`, replace the broken `_load_failures()` rows block:

```python
# BEFORE (broken)
for fl in failures:
    self._tree.insert("", "end", iid=fl.id, values=(
        fl.date[:10] if fl.date else "—",
        fl.reason,
        fl.source,
        f"{fl.filament_wasted:.1f}",
        format_time_minutes(fl.print_time_wasted),
        format_currency(fl.material_cost),
        format_currency(fl.electricity_cost),
        format_currency(fl.total_cost),
        fl.notes or "—",
    ))
```

```python
# AFTER (fixed)
for fl in failures:
    self._tree.insert("", "end", iid=fl.id, values=(
        fl.date[:10] if fl.date else "—",
        fl.reason,
        fl.source,
        f"{fl.filament_wasted_grams:.1f}",
        format_time_minutes(fl.time_wasted_minutes),
        format_currency(fl.filament_cost),
        format_currency(fl.electricity_cost),
        format_currency(fl.total_loss),
        fl.description or "—",
    ))
```

**Files affected:** `failures_tab.py`

---

## Bug 3 — CRASH ON "LOG FAILURE" (Wrong kwargs to log_failure)

### Error
```
TypeError: FinanceService.log_failure() got an unexpected keyword argument 'filament_wasted'
```
(Triggered when user clicks "Log Failure" and saves the dialog)

### Location
`failures_tab.py` → `_FailureDialog._save()` method (lines 412–422) and
`FailuresTab._add_failure()` (lines 225–238)

### Root Cause
The dialog returns a dict with keys that do not match `log_failure()`'s
parameter names. The service expects:

```python
# finance_service.py log_failure() signature
def log_failure(
    self,
    source: str,
    item_name: str,          # ← required, missing from dialog result
    reason: str,
    filament_wasted_grams: float = 0.0,
    time_wasted_minutes: int = 0,
    ...
    description: str = "",
    ...
)
```

But the dialog sends:
```python
# failures_tab.py dialog result (broken)
{
    "reason":            ...,
    "source":            ...,
    "filament_wasted":   g,         # wrong key
    "print_time_wasted": int(min_), # wrong key
    "material_cost":     mat,       # not a log_failure param
    "electricity_cost":  elec,      # not a log_failure param
    "total_cost":        mat+elec,  # not a log_failure param
    "notes":             ...,       # wrong key (should be description)
    "spool_id":          spool_id,
    "deduct_from_spool": ...,
}
```

Also: the `log_failure()` service already auto-calculates costs internally —
sending pre-computed cost fields causes confusion and they are ignored anyway.

### Fix

In `failures_tab.py`, replace `_FailureDialog._save()` result dict:

```python
# AFTER (fixed)
self.result = {
    "reason":                self._reason_var.get(),
    "source":                self._source_var.get(),
    "item_name":             "",          # dialog has no item name field; pass empty
    "filament_wasted_grams": g,
    "time_wasted_minutes":   int(min_),
    "description":           self._notes_var.get().strip(),
    "spool_id":              spool_id,
    "deduct_from_spool":     self._deduct_var.get(),
}
```

And in `FailuresTab._add_failure()`, also fix the fallback reference after pop:

```python
# AFTER (fixed)
def _add_failure(self) -> None:
    colors = self._inv.get_colors()
    spools = self._inv.get_active_spools()   # fix Bug 4 — see below
    dlg = _FailureDialog(self, colors=colors, spools=spools)
    if dlg.result:
        data = dlg.result.copy()
        spool_id = data.pop("spool_id", None)
        deduct   = data.pop("deduct_from_spool", False)
        self._fin.log_failure(**data)
        if deduct and spool_id:
            grams = data.get("filament_wasted_grams", 0)
            self._inv.commit_filament(spool_id, grams)
        self.refresh()
        self._notify()
```

**Files affected:** `failures_tab.py`

---

## Bug 4 — CRASH ON "LOG FAILURE" OPEN (get_spools method missing)

### Error
```
AttributeError: 'InventoryService' object has no attribute 'get_spools'
```
(Triggered when user opens the "Log Failure" dialog)

### Location
`failures_tab.py` → `_add_failure()` method (line 227)

### Root Cause
The tab calls `self._inv.get_spools(status_filter="active")`, but `InventoryService`
has no method called `get_spools()`. The correct existing methods are:

```python
# inventory_service.py — what actually exists
def get_all_spools(self) -> List[FilamentSpool]: ...
def get_active_spools(self) -> List[FilamentSpool]: ...   # ← use this
```

### Fix

In `failures_tab.py`, change line 227:

```python
# BEFORE (broken)
spools = self._inv.get_spools(status_filter="active")

# AFTER (fixed)
spools = self._inv.get_active_spools()
```

**Files affected:** `failures_tab.py`

---

## Bug 5 — CRASH ON STATS TAB (get_order_stats missing)

### Error
```
AttributeError: 'FinanceService' object has no attribute 'get_order_stats'
```
(Triggered when the Statistics tab loads or refreshes)

### Location
`stats_tab.py` → `_load_stats()` method (line 143)

### Root Cause
`stats_tab.py` calls `self._fin.get_order_stats()`, but that method does not
exist anywhere in `FinanceService`. Order statistics need to be derived from
the orders in the database.

### Fix

**Option A — Add `get_order_stats()` to `FinanceService`** (recommended):

In `finance_service.py`, add this method to the "Full Statistics" section:

```python
def get_order_stats(self) -> dict:
    """Return basic order counts by status.

    Returns:
        Dict with: total, delivered, cancelled, rd (R&D orders).
    """
    from src.core.models import Order
    rows = self._db.get_all_orders(include_deleted=False)
    orders = [Order.from_dict(r) for r in rows]
    return {
        "total":     len(orders),
        "delivered": sum(1 for o in orders if o.status == "Delivered"),
        "cancelled": sum(1 for o in orders if o.status == "Cancelled"),
        "rd":        sum(1 for o in orders if o.is_rd),
    }
```

**Files affected:** `finance_service.py`

---

## Bug 6 — SILENT WRONG DATA on Stats Tab (Wrong failure stats keys)

### Symptom
Failure count, filament wasted, and time wasted all show **0** or **—**
on the Statistics tab even when failures exist.

### Location
`stats_tab.py` → `_load_stats()` method (lines 189–195)

### Root Cause
`stats_tab.py` asks for keys `"count"`, `"total_filament"`, `"total_time"`
but `get_failure_stats()` returns `"total_failures"`, `"total_filament_wasted"`,
`"total_time_wasted"`:

```python
# finance_service.py — what get_failure_stats() actually returns
{
    "total_failures":        len(failures),
    "total_cost":            sum(f.total_loss ...),
    "total_filament_wasted": sum(f.filament_wasted_grams ...),
    "total_time_wasted":     sum(f.time_wasted_minutes ...),
    "unresolved_count":      ...,
    "by_reason":             ...,
}

# stats_tab.py — wrong keys it requests
f_stat.get("count", 0)            # should be "total_failures"
f_stat.get("total_filament", 0)   # should be "total_filament_wasted"
f_stat.get("total_time", 0)       # should be "total_time_wasted"
```

### Fix

In `stats_tab.py`, change lines 189–195:

```python
# BEFORE (broken)
_set("failures_failure_count",   str(f_stat.get("count", 0)))
_set("failures_filament_wasted",
     f"{f_stat.get('total_filament', 0):.1f} g")
_set("failures_time_wasted",
     format_time_minutes(int(f_stat.get("total_time", 0))))
_set("failures_failure_cost",
     format_currency(f_stat.get("total_cost", 0)))
```

```python
# AFTER (fixed)
_set("failures_failure_count",   str(f_stat.get("total_failures", 0)))
_set("failures_filament_wasted",
     f"{f_stat.get('total_filament_wasted', 0):.1f} g")
_set("failures_time_wasted",
     format_time_minutes(int(f_stat.get("total_time_wasted", 0))))
_set("failures_failure_cost",
     format_currency(f_stat.get("total_cost", 0)))
```

**Files affected:** `stats_tab.py`

---

## Bug 7 — SILENT WRONG DATA on Stats Tab (Wrong expense stats key)

### Symptom
Total expenses and net profit show **0** on the Statistics tab even when
expenses exist.

### Location
`stats_tab.py` → `_load_stats()` method (lines 164, 168)

### Root Cause
`stats_tab.py` reads `e_stat.get("total", 0)` but `get_expense_stats()`
returns `"total_expenses"`, not `"total"`:

```python
# finance_service.py — what get_expense_stats() returns
{
    "total_expenses": ...,   # ← correct key
    "expense_count":  ...,
    "by_category":    ...,
    "monthly":        ...,
}

# stats_tab.py — wrong key used
e_stat.get("total", 0)   # ← key does not exist → always 0
```

### Fix

In `stats_tab.py`, replace the two uses of `e_stat.get("total", 0)`:

```python
# BEFORE (broken)
_set("costs_total_expenses",  format_currency(e_stat.get("total", 0)))
net = gross - f_stat.get("total_cost", 0) - e_stat.get("total", 0)
```

```python
# AFTER (fixed)
_set("costs_total_expenses",  format_currency(e_stat.get("total_expenses", 0)))
net = gross - f_stat.get("total_cost", 0) - e_stat.get("total_expenses", 0)
```

**Files affected:** `stats_tab.py`

---

## Bug 8 — SILENT WRONG DATA in Failures Tab Summary Panel

### Symptom
The summary cards at the bottom of the Failures tab ("Total Failures",
"Filament Wasted", "Time Wasted") all show **—** instead of real values.

### Location
`failures_tab.py` → `_update_summary()` method (lines 193–200)

### Root Cause
Same key name mismatch as Bug 6 — `_update_summary()` uses `"count"`,
`"total_filament"`, `"total_time"` but `get_failure_stats()` returns
`"total_failures"`, `"total_filament_wasted"`, `"total_time_wasted"`:

```python
# failures_tab.py — broken
self._sum_count.config(text=str(stats.get("count", 0)))
self._sum_filament.config(text=f"{stats.get('total_filament', 0):.1f} g")
self._sum_time.config(text=format_time_minutes(int(stats.get("total_time", 0))))
self._sum_cost.config(text=format_currency(stats.get("total_cost", 0)))
```

### Fix

In `failures_tab.py`, change `_update_summary()`:

```python
# AFTER (fixed)
def _update_summary(self) -> None:
    stats = self._fin.get_failure_stats()
    self._sum_count.config(text=str(stats.get("total_failures", 0)))
    self._sum_filament.config(
        text=f"{stats.get('total_filament_wasted', 0):.1f} g")
    self._sum_time.config(
        text=format_time_minutes(int(stats.get("total_time_wasted", 0))))
    self._sum_cost.config(
        text=format_currency(stats.get("total_cost", 0)))
```

**Files affected:** `failures_tab.py`

---

## Bug 9 — Package Version Mismatch in README

### Symptom
The `README.md` lists old package versions that do not match `requirements.txt`.

### Detail

| Package | README says | requirements.txt says |
|---------|------------|----------------------|
| reportlab | 4.1.0 | 4.4.1 |
| Pillow | 10.4.0 | 11.2.1 |
| matplotlib | 3.9.0 | 3.10.3 |

### Fix
Update the installation code block in `README.md` to match `requirements.txt`:

```
reportlab==4.4.1
Pillow==11.2.1
pytesseract==0.3.13
matplotlib==3.10.3
```

**Files affected:** `README.md`

---

## Fix Order (Apply in This Sequence)

Apply fixes in this order to unblock the app step by step:

1. **`finance_service.py`** — Fix `get_all_failures()` signature (Bug 1) + add `get_order_stats()` (Bug 5)
2. **`failures_tab.py`** — Fix attribute names in `_load_failures()` (Bug 2) + fix `_add_failure()` call (Bug 3 & 4) + fix `_update_summary()` keys (Bug 8)
3. **`stats_tab.py`** — Fix failure stats keys (Bug 6) + fix expense stats key (Bug 7)
4. **`README.md`** — Update version numbers (Bug 9)

---

## Architecture Reference (for future debugging)

Use this table every time something looks broken. If a tab is showing zeros
or crashing, check the **key names** returned by the service against what
the tab is reading.

### `get_failure_stats()` → returns these keys
```
"total_failures"        int
"total_cost"            float
"total_filament_wasted" float
"total_time_wasted"     int
"unresolved_count"      int
"by_reason"             dict[str, int]
```

### `get_expense_stats()` → returns these keys
```
"total_expenses"   float
"expense_count"    int
"by_category"      dict[str, float]
"monthly"          dict[str, float]
```

### `get_full_statistics()` → returns these keys
```
"total_revenue"      "total_shipping"   "total_fees"
"total_rounding"     "total_material"   "total_electricity"
"total_depreciation" "total_nozzle"     "gross_profit"
"total_weight"       "total_print_time"
```

### `get_inventory_summary()` → returns these keys
```
"total_spools"       "active_spools"
"pending_weight_g"   "available_weight_g"
"total_value_egp"
```

### `PrintFailure` model fields (use these, not invented names)
```python
id, date, source, order_id, order_number, customer_name,
item_name, reason, description,           # ← NOT "notes"
filament_wasted_grams,                    # ← NOT "filament_wasted"
time_wasted_minutes,                      # ← NOT "print_time_wasted"
spool_id, color,
filament_cost,                            # ← NOT "material_cost"
electricity_cost, total_loss,             # ← NOT "total_cost"
printer_id, printer_name, resolved, resolution_notes
```

### `log_failure()` accepted parameters
```python
source, item_name, reason,
filament_wasted_grams, time_wasted_minutes,
spool_id, color, printer_id, printer_name,
order_id, order_number, customer_name,
description, date
```
**Do NOT pass:** `filament_wasted`, `print_time_wasted`, `material_cost`,
`total_cost`, `notes` — none of these are valid parameter names.

---

## How to Avoid These Bugs in the Future

1. **Always verify attribute names against `models.py`** before accessing them
   in UI code. The dataclass is the single source of truth.

2. **Always verify method signatures in service files** before calling them
   from tab files. Check parameter names and types exactly.

3. **Always verify dict keys returned by service methods** before reading
   them in UI code. Print the dict or read the docstring carefully.

4. **Name keys consistently.** A pattern like `"total_filament"` in the UI
   but `"total_filament_wasted"` in the service is the root cause of most
   silent failures. Consider using TypedDict or dataclasses for return values.

5. **Run the app after each individual file change** to isolate new errors
   quickly instead of applying all fixes at once.

6. **Use the test suite.** Run `pytest tests/` after every fix. Add a test
   for every bug found so it cannot regress.
