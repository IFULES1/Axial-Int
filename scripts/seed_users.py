"""Seed N professional-email test accounts via the auth service.

Usage: python scripts/seed_users.py --count 10 [--domain axialtest.com]

Requires Supabase to be configured (.env). Prints created credentials so you
can log in immediately. Intended for local/dev only.
"""
from __future__ import annotations

import argparse
import secrets
import sys

from app.db import SessionLocal
from app.errors import AppError
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import register


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed test accounts")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--domain", default="axialtest.com",
                        help="Professional domain (must not be freemail)")
    args = parser.parse_args()

    created = 0
    with SessionLocal() as db:
        for i in range(1, args.count + 1):
            email = f"founder{i}@{args.domain}"
            password = f"Axial-{secrets.token_urlsafe(9)}"
            try:
                register(RegisterRequest(email=email, password=password,
                                         full_name=f"Test Founder {i}"), db)
                print(f"OK  {email}  {password}")
                created += 1
            except AppError as e:
                print(f"SKIP {email}: {e.message}", file=sys.stderr)

    print(f"\n{created}/{args.count} comptes créés.")
    return 0 if created else 1


if __name__ == "__main__":
    raise SystemExit(main())
