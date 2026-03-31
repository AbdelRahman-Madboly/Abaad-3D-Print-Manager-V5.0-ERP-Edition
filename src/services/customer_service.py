"""
src/services/customer_service.py
==================================
Customer CRUD + stats for Abaad 3D Print Manager v5.0.
"""

import logging
from typing import List, Optional

from src.core.models import Customer, Order
from src.utils.helpers import generate_id, now_str

log = logging.getLogger(__name__)


class CustomerService:
    """CRUD and lookup logic for customers.

    Args:
        db: A ``DatabaseManager`` instance.
    """

    def __init__(self, db) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_customer(self, customer_id: str) -> Optional[Customer]:
        row = self._db.get_customer(customer_id)
        return Customer.from_dict(row) if row else None

    def get_all_customers(self) -> List[Customer]:
        return [Customer.from_dict(r) for r in self._db.get_all_customers()]

    def search(self, query: str) -> List[Customer]:
        """Case-insensitive search on name and phone.

        Args:
            query: Search string.

        Returns:
            Matching customers, sorted by name.
        """
        rows = self._db.search_customers(query)
        return sorted([Customer.from_dict(r) for r in rows], key=lambda c: c.name)

    # ------------------------------------------------------------------
    # Create / update / delete
    # ------------------------------------------------------------------

    def create_customer(
        self,
        name: str,
        phone: str = "",
        email: str = "",
        address: str = "",
        notes: str = "",
        discount_percent: float = 0.0,
    ) -> Customer:
        """Create and persist a new customer.

        Args:
            name:             Display name (required).
            phone:            Phone number.
            email:            Email address.
            address:          Physical address.
            notes:            Free-text notes.
            discount_percent: Default order discount for this customer.

        Returns:
            The newly-created ``Customer``.
        """
        customer = Customer(
            id               = generate_id(),
            name             = name.strip(),
            phone            = phone.strip(),
            email            = email.strip(),
            address          = address.strip(),
            notes            = notes,
            discount_percent = discount_percent,
            created_date     = now_str(),
            updated_date     = now_str(),
        )
        self._db.save_customer(customer.to_dict())
        log.info("Created customer %s  id=%s", customer.name, customer.id)
        return customer

    def update_customer(self, customer_id: str, **kwargs) -> bool:
        """Update one or more fields on a customer record.

        Args:
            customer_id: Target customer ID.
            **kwargs:    Field names and new values.

        Returns:
            ``True`` on success, ``False`` if not found.
        """
        customer = self.get_customer(customer_id)
        if not customer:
            log.warning("update_customer: %s not found", customer_id)
            return False
        for key, value in kwargs.items():
            if hasattr(customer, key):
                setattr(customer, key, value)
        customer.updated_date = now_str()
        return self._db.save_customer(customer.to_dict())

    def delete_customer(self, customer_id: str) -> bool:
        """Permanently delete a customer.

        Note: existing orders keep ``customer_name`` as a string snapshot
        so order history is preserved.

        Args:
            customer_id: Target customer ID.

        Returns:
            ``True`` on success.
        """
        return self._db.delete_customer(customer_id)

    # ------------------------------------------------------------------
    # Smart lookup
    # ------------------------------------------------------------------

    def find_or_create(self, name: str, phone: str = "") -> Customer:
        """Return an existing customer matching phone or name, or create one.

        Search priority:
          1. Exact phone match (if phone provided)
          2. Case-insensitive name match
          3. Create new record

        Args:
            name:  Customer display name.
            phone: Phone number (used as primary key for lookup).

        Returns:
            Existing or newly-created ``Customer``.
        """
        name  = name.strip()
        phone = phone.strip()

        # 1. Phone match
        if phone:
            for row in self._db.get_all_customers():
                if row.get("phone") == phone:
                    return Customer.from_dict(row)

        # 2. Name match (case-insensitive)
        if name:
            name_lower = name.lower()
            for row in self._db.get_all_customers():
                if row.get("name", "").lower() == name_lower:
                    return Customer.from_dict(row)

        # 3. Create
        return self.create_customer(name, phone)

    # ------------------------------------------------------------------
    # Customer orders
    # ------------------------------------------------------------------

    def get_customer_orders(self, customer_id: str) -> List[Order]:
        """Return all non-deleted orders for a customer, newest first.

        Items are NOT pre-loaded (use OrderService.get_order for full detail).

        Args:
            customer_id: Target customer ID.

        Returns:
            List of ``Order`` objects ordered by created_date descending.
        """
        rows = self._db.get_all_orders(include_deleted=False)
        orders = []
        for row in rows:
            if row.get("customer_id") == customer_id:
                orders.append(Order.from_dict(row))
        return sorted(orders, key=lambda o: o.created_date, reverse=True)

    # ------------------------------------------------------------------
    # Stats sync
    # ------------------------------------------------------------------

    def update_customer_stats(self, customer_id: str) -> None:
        """Recalculate and persist total_orders and total_spent from live data.

        Call after any order status change that affects revenue
        (e.g. Delivered, Cancelled).

        Args:
            customer_id: Target customer ID.
        """
        customer = self.get_customer(customer_id)
        if not customer:
            return

        orders = self.get_customer_orders(customer_id)
        customer.total_orders = len(orders)
        customer.total_spent  = sum(
            o.total for o in orders
            if o.status not in ("Cancelled", "Draft")
        )
        customer.updated_date = now_str()
        self._db.save_customer(customer.to_dict())
        log.debug(
            "Stats updated for %s: %d orders, %.2f EGP",
            customer.name, customer.total_orders, customer.total_spent,
        )