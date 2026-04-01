"""
src/auth/auth_manager.py
========================
Authentication and session management for Abaad ERP v5.0.

Bug B fix: _load_from_db() now calls self._db.get_all_users()
           instead of the non-existent self._db.execute_query()

Bug C fix: _save_user_to_db() now calls self._db.save_user(dict)
           delete_user() now calls self._db.delete_user(id)
           instead of the non-existent self._db.execute_update()
"""

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List

from src.auth.permissions import Permission, UserRole, ROLE_PERMISSIONS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_id() -> str:
    return secrets.token_hex(4)


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return digest, salt


def _verify_password(plain: str, stored_hash: str, salt: str) -> bool:
    computed, _ = _hash_password(plain, salt)
    return secrets.compare_digest(computed, stored_hash)


# ---------------------------------------------------------------------------
# User dataclass
# ---------------------------------------------------------------------------

@dataclass
class User:
    """Represents an authenticated application user."""

    id:            str  = field(default_factory=_generate_id)
    username:      str  = ""
    password_hash: str  = ""
    password_salt: str  = ""
    role:          str  = UserRole.USER.value
    display_name:  str  = ""
    email:         str  = ""
    is_active:     bool = True
    created_date:  str  = field(default_factory=_now_str)
    last_login:    str  = ""
    login_count:   int  = 0
    notes:         str  = ""

    @property
    def permissions(self) -> List[Permission]:
        try:
            role_enum = UserRole(self.role)
        except ValueError:
            role_enum = UserRole.USER
        return ROLE_PERMISSIONS.get(role_enum, [])

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions

    def can_access_tab(self, tab_name: str) -> bool:
        tab_map: Dict[str, Permission] = {
            "orders":    Permission.VIEW_ORDER,
            "customers": Permission.VIEW_CUSTOMERS,
            "filament":  Permission.VIEW_INVENTORY,
            "printers":  Permission.VIEW_PRINTERS,
            "failures":  Permission.VIEW_FINANCIAL,
            "expenses":  Permission.VIEW_FINANCIAL,
            "stats":     Permission.VIEW_STATISTICS,
            "analytics": Permission.VIEW_STATISTICS,
            "settings":  Permission.MANAGE_SETTINGS,
            "admin":     Permission.MANAGE_USERS,
        }
        required = tab_map.get(tab_name.lower())
        if required is None:
            return True
        return self.has_permission(required)

    def set_password(self, plain: str) -> None:
        self.password_hash, self.password_salt = _hash_password(plain)

    def check_password(self, plain: str) -> bool:
        return _verify_password(plain, self.password_hash, self.password_salt)

    def record_login(self) -> None:
        self.last_login = _now_str()
        self.login_count += 1

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "username":      self.username,
            "password_hash": self.password_hash,
            "password_salt": self.password_salt,
            "role":          self.role,
            "display_name":  self.display_name,
            "email":         self.email,
            "is_active":     int(self.is_active),
            "created_date":  self.created_date,
            "last_login":    self.last_login,
            "login_count":   self.login_count,
            "notes":         self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        u = cls()
        u.id            = data.get("id", _generate_id())
        u.username      = data.get("username", "")
        u.password_hash = data.get("password_hash", "")
        u.password_salt = data.get("password_salt", "")
        u.role          = data.get("role", UserRole.USER.value)
        u.display_name  = data.get("display_name", "")
        u.email         = data.get("email", "")
        u.is_active     = bool(data.get("is_active", True))
        u.created_date  = data.get("created_date", _now_str())
        u.last_login    = data.get("last_login", "")
        u.login_count   = int(data.get("login_count", 0))
        u.notes         = data.get("notes", "")
        return u


# ---------------------------------------------------------------------------
# AuthManager
# ---------------------------------------------------------------------------

class AuthManager:
    """Singleton that manages user accounts and the current login session."""

    _instance: Optional["AuthManager"] = None

    def __new__(cls) -> "AuthManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._ready = False
        return cls._instance

    def __init__(self) -> None:
        if self._ready:
            return
        self._db = None
        self._users: Dict[str, User] = {}
        self._current_user: Optional[User] = None
        self._json_fallback_loaded = False
        self._ready = True

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def initialise(self, db) -> None:
        """Attach the DatabaseManager and load users from the DB.
        Call once from main.py after the database is ready."""
        self._db = db
        self._load_from_db()
        self._ensure_default_admin()

    def _load_from_db(self) -> None:
        """Load all users from the SQLite users table.

        BUG B FIX: calls self._db.get_all_users() (which exists in v5
        DatabaseManager) instead of execute_query() (which does not).
        """
        if self._db is None:
            return
        try:
            rows = self._db.get_all_users()          # ← Bug B fix
            self._users = {r["id"]: User.from_dict(r) for r in rows}
            print(f"✓ Auth: loaded {len(self._users)} users from DB")
        except Exception as exc:
            print(f"✗ Auth: could not load users from DB — {exc}")
            self._load_from_json_fallback()

    def _load_from_json_fallback(self) -> None:
        """Load users from the legacy JSON file (first-run / migration)."""
        import json
        from pathlib import Path
        path = Path("data/users.json")
        if not path.exists() or self._json_fallback_loaded:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            for u_data in data.get("users", []):
                u = User.from_dict(u_data)
                self._users[u.id] = u
            self._json_fallback_loaded = True
            print(f"✓ Auth: loaded {len(self._users)} users from JSON fallback")
        except Exception as exc:
            print(f"✗ Auth: JSON fallback failed — {exc}")

    def _save_user_to_db(self, user: User) -> bool:
        """Upsert a single user record into SQLite.

        BUG C FIX: calls self._db.save_user(dict) (which exists in v5
        DatabaseManager) instead of execute_update() (which does not).
        """
        if self._db is None:
            return False
        try:
            return self._db.save_user(user.to_dict())   # ← Bug C fix
        except Exception as exc:
            print(f"✗ Auth: save user failed — {exc}")
            return False

    def _ensure_default_admin(self) -> None:
        admins = [u for u in self._users.values() if u.role == UserRole.ADMIN.value]
        if admins:
            return
        admin = User(
            id="admin_default",
            username="admin",
            role=UserRole.ADMIN.value,
            display_name="Administrator",
            notes="Default admin — change password!",
        )
        admin.set_password("admin123")
        self._users[admin.id] = admin
        self._save_user_to_db(admin)
        print("✓ Auth: created default admin (username: admin, password: admin123)")

    # ------------------------------------------------------------------
    # Login / logout
    # ------------------------------------------------------------------

    def login(self, username: str, password: str) -> tuple[bool, str, Optional[User]]:
        if not self._users:
            self._load_from_json_fallback()
            self._ensure_default_admin()

        user = next(
            (u for u in self._users.values()
             if u.username.lower() == username.lower()),
            None,
        )
        if user is None:
            return False, "User not found.", None
        if not user.is_active:
            return False, "Account is disabled.", None
        if not user.check_password(password):
            return False, "Incorrect password.", None

        user.record_login()
        self._save_user_to_db(user)
        self._current_user = user
        name = user.display_name or user.username
        return True, f"Welcome, {name}!", user

    def logout(self) -> None:
        self._current_user = None

    # ------------------------------------------------------------------
    # Session properties
    # ------------------------------------------------------------------

    @property
    def current_user(self) -> Optional[User]:
        return self._current_user

    @property
    def is_logged_in(self) -> bool:
        return self._current_user is not None

    @property
    def is_admin(self) -> bool:
        return (
            self._current_user is not None
            and self._current_user.role == UserRole.ADMIN.value
        )

    def has_permission(self, permission: Permission) -> bool:
        if self._current_user is None:
            return False
        return self._current_user.has_permission(permission)

    # ------------------------------------------------------------------
    # User management (admin-only)
    # ------------------------------------------------------------------

    def create_user(self, username: str, password: str,
                    role: str = UserRole.USER.value,
                    display_name: str = "", email: str = "",
                    ) -> tuple[bool, str, Optional[User]]:
        if not self.is_admin:
            return False, "Permission denied.", None
        if any(u.username.lower() == username.lower() for u in self._users.values()):
            return False, "Username already exists.", None

        user = User(
            username=username,
            role=role,
            display_name=display_name or username,
            email=email,
        )
        user.set_password(password)
        self._users[user.id] = user
        self._save_user_to_db(user)
        return True, f"User '{username}' created.", user

    def update_user(self, user_id: str, **kwargs) -> tuple[bool, str]:
        if not self.is_admin:
            return False, "Permission denied."
        user = self._users.get(user_id)
        if not user:
            return False, "User not found."
        for key in ("display_name", "email", "role", "is_active", "notes"):
            if key in kwargs:
                setattr(user, key, kwargs[key])
        if kwargs.get("password"):
            user.set_password(kwargs["password"])
        self._save_user_to_db(user)
        return True, "User updated."

    def delete_user(self, user_id: str) -> tuple[bool, str]:
        if not self.is_admin:
            return False, "Permission denied."
        user = self._users.get(user_id)
        if not user:
            return False, "User not found."
        if self._current_user and user_id == self._current_user.id:
            return False, "Cannot delete yourself."
        admins = [u for u in self._users.values() if u.role == UserRole.ADMIN.value]
        if user.role == UserRole.ADMIN.value and len(admins) <= 1:
            return False, "Cannot delete the last admin."

        del self._users[user_id]
        if self._db:
            try:
                self._db.delete_user(user_id)          # ← Bug C fix
            except Exception as exc:
                print(f"✗ Auth: delete user DB error — {exc}")
        return True, "User deleted."

    def get_all_users(self) -> List[User]:
        if not self.is_admin:
            return []
        return list(self._users.values())

    def get_user(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    def change_password(self, old_password: str, new_password: str) -> tuple[bool, str]:
        if not self._current_user:
            return False, "Not logged in."
        if not self._current_user.check_password(old_password):
            return False, "Current password is incorrect."
        self._current_user.set_password(new_password)
        self._save_user_to_db(self._current_user)
        return True, "Password changed."


# ---------------------------------------------------------------------------
# Module-level singleton accessor
# ---------------------------------------------------------------------------

_auth_manager: Optional[AuthManager] = None


def get_auth_manager() -> AuthManager:
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager