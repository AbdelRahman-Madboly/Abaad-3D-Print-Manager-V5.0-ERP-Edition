"""
src/auth/permissions.py
=======================
Role-Based Access Control definitions for Abaad ERP v5.0.

Kept as a standalone file so auth_manager.py and UI code can both
import permissions without circular imports.
"""

from enum import Enum
from typing import Dict, List


class UserRole(str, Enum):
    ADMIN = "Admin"
    USER  = "User"


class Permission(str, Enum):
    # Orders
    CREATE_ORDER  = "create_order"
    VIEW_ORDER    = "view_order"
    EDIT_ORDER    = "edit_order"
    DELETE_ORDER  = "delete_order"
    UPDATE_STATUS = "update_status"

    # Customers
    VIEW_CUSTOMERS   = "view_customers"
    MANAGE_CUSTOMERS = "manage_customers"

    # Inventory
    VIEW_INVENTORY   = "view_inventory"
    MANAGE_INVENTORY = "manage_inventory"

    # Printers
    VIEW_PRINTERS   = "view_printers"
    MANAGE_PRINTERS = "manage_printers"

    # Finance
    VIEW_STATISTICS = "view_statistics"
    VIEW_FINANCIAL  = "view_financial"
    EXPORT_DATA     = "export_data"

    # Admin
    MANAGE_USERS    = "manage_users"
    MANAGE_SETTINGS = "manage_settings"
    SYSTEM_BACKUP   = "system_backup"

    # PDFs
    GENERATE_QUOTE   = "generate_quote"
    GENERATE_RECEIPT = "generate_receipt"


ROLE_PERMISSIONS: Dict[UserRole, List[Permission]] = {
    UserRole.ADMIN: list(Permission),   # all permissions
    UserRole.USER: [
        Permission.CREATE_ORDER,
        Permission.VIEW_ORDER,
        Permission.EDIT_ORDER,
        Permission.UPDATE_STATUS,
        Permission.VIEW_CUSTOMERS,
        Permission.VIEW_INVENTORY,
        Permission.VIEW_PRINTERS,
        Permission.GENERATE_QUOTE,
        Permission.GENERATE_RECEIPT,
    ],
}