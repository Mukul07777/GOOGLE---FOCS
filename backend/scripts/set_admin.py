"""Choose the admin panel's ID and password.

    python scripts/set_admin.py              asks for both, saves them to backend/.env
    python scripts/set_admin.py --print-hash prints a hash to paste into a hosting dashboard instead

Only a bcrypt hash of the password is stored. Setting a new password signs every open admin session out.
"""
import getpass
import os
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.security import hash_password  # noqa: E402

ENV = BACKEND / ".env"
DEFAULT_ID = "admin@focs"
MIN_LENGTH = 10


def ask_password(admin_id: str) -> str:
    while True:
        pw = getpass.getpass(f"  New admin password (at least {MIN_LENGTH} characters, typing is hidden): ")
        if len(pw) < MIN_LENGTH:
            print(f"  Too short: use at least {MIN_LENGTH} characters.\n")
        elif pw.strip().lower() == admin_id.lower():
            print("  The password can't be the same as the ID.\n")
        elif getpass.getpass("  Type it again: ") != pw:
            print("  The two didn't match. Try again.\n")
        else:
            return pw


def save(values: dict[str, str]) -> None:
    text = ENV.read_text(encoding="utf-8").replace("\x00", "") if ENV.exists() else ""
    lines = text.splitlines()
    for key, value in values.items():
        line = f"{key}={value}"
        for i, existing in enumerate(lines):
            if re.match(rf"\s*{key}\s*=", existing):
                lines[i] = line
                break
        else:
            lines.append(line)
    tmp = ENV.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, ENV)  # never leaves a half-written .env behind


def main() -> None:
    print("\n  Focs admin panel sign-in\n")
    admin_id = input(f"  Admin ID [{DEFAULT_ID}]: ").strip() or DEFAULT_ID
    hashed = hash_password(ask_password(admin_id))
    if "--print-hash" in sys.argv:
        print(f"\n  Set these on your host:\n    ADMIN_USERNAME={admin_id}\n    ADMIN_PASSWORD_HASH={hashed}\n")
        return
    # single quotes: the hash is full of "$", which must never be read as a variable
    save({"ADMIN_USERNAME": admin_id, "ADMIN_PASSWORD_HASH": f"'{hashed}'"})
    print(f"\n  Saved. Restart Focs, then open /admin and sign in as {admin_id}.\n")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n  Cancelled, nothing changed.")
