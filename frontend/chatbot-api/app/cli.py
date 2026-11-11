import argparse
from getpass import getpass

from app.core.config import Settings
from app.db.factory import create_database
from app.repositories.users import UserRepository
from app.schemas.api import Membership, UserCreate
from app.services.audit import record


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap local chatbot accounts; password entered interactively."
    )
    parser.add_argument("command", choices=["create-user", "cleanup"])
    parser.add_argument("--username")
    parser.add_argument(
        "--department",
        action="append",
        choices=["dbcl", "qtts", "pdt", "pns", "hc", "ctsv", "khcn"],
        default=[],
    )
    parser.add_argument(
        "--role", choices=["member", "department_admin"], default="member"
    )
    parser.add_argument("--system-admin", action="store_true")
    args = parser.parse_args()
    db = create_database(Settings())
    db.initialize()
    if args.command == "cleanup":
        import time

        db.cleanup(time.time())
        print("Expired sessions and rate-limit windows removed.")
        db.close()
        return
    if not args.username:
        parser.error("--username is required")
    password = getpass("Password (12+ characters): ")
    if password != getpass("Confirm password: "):
        parser.error("Passwords do not match")
    body = UserCreate(
        username=args.username,
        password=password,
        memberships=[Membership(department=d, role=args.role) for d in args.department],
    )
    uid = UserRepository(db).create(
        body.username,
        body.password.get_secret_value(),
        body.memberships,
        args.system_admin,
    )
    record(db, "cli_create_user", target_id=uid)
    print(f"Created user {uid}")
    db.close()


if __name__ == "__main__":
    main()
