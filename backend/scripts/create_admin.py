"""Create (or reset) an admin-panel account from the command line.

Usage (from backend/):
    python -m scripts.create_admin --email ops@example.edu --name "Ops Lead" [--role super_admin]

The password is read from the ADMIN_PASSWORD environment variable or prompted for (never passed as an
argument, so it does not end up in shell history). Use this to bootstrap the first Super Admin.
"""
import argparse
import getpass
import os
import sys

from sqlalchemy import func, select

from app.core.admin_permissions import SUPER_ADMIN_ROLE, SYSTEM_ROLES
from app.core.admin_security import revoke_sessions, sync_system_roles, utcnow
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.entities import AdminRole, AdminUser
from app.schemas.admin import AdminCreateIn


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", default=SUPER_ADMIN_ROLE, choices=sorted(SYSTEM_ROLES))
    parser.add_argument("--reset", action="store_true", help="Reset the password (and role) of an existing admin")
    args = parser.parse_args()

    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password (min 12 chars, letters + digits): ")
    with SessionLocal() as db:
        sync_system_roles(db)
        role = db.scalar(select(AdminRole).where(AdminRole.key == args.role))
        # Reuse the API's validation rules (email format, password strength).
        data = AdminCreateIn(email=args.email, full_name=args.name, password=password, role_id=role.id)
        existing = db.scalar(select(AdminUser).where(func.lower(AdminUser.email) == data.email.lower()))
        if existing and not args.reset:
            print(f"Admin {data.email} already exists (use --reset to change its password).", file=sys.stderr)
            return 1
        if existing:
            existing.password_hash = hash_password(data.password)
            existing.role_id = role.id
            existing.full_name = data.full_name
            existing.is_active = True
            existing.failed_login_count = 0
            existing.locked_until = None
            existing.password_changed_at = utcnow()
            revoke_sessions(db, existing.id)
            action = "Reset"
        else:
            db.add(AdminUser(email=data.email.lower(), full_name=data.full_name, password_hash=hash_password(data.password),
                             role_id=role.id, password_changed_at=utcnow()))
            action = "Created"
        db.commit()
        print(f"{action} admin {data.email} with role {role.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
