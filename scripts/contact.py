#!/usr/bin/env python3
"""Consigner ou lire les contacts manuels avec les utilisateurs.

    python scripts/contact.py --lister
    python scripts/contact.py --lister --email christian@eqonx.com
    python scripts/contact.py --ajouter --email x@y.fr --canal whatsapp \
        --resume "..." --le 2026-08-27 --suite "..." --relance 2026-09-05
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.modules.emailing.contacts import CANAUX, ContactManuel, consigner  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ajouter", action="store_true")
    ap.add_argument("--lister", action="store_true")
    ap.add_argument("--email")
    ap.add_argument("--canal", choices=CANAUX, default="whatsapp")
    ap.add_argument("--sens", choices=("sortant", "entrant"), default="sortant")
    ap.add_argument("--resume")
    ap.add_argument("--suite", help="ce qui a été promis ou reste à faire")
    ap.add_argument("--le", help="date de l'échange (AAAA-MM-JJ), défaut aujourd'hui")
    ap.add_argument("--relance", help="date de relance prévue (AAAA-MM-JJ)")
    ap.add_argument("--auteur", default="Miradie")
    args = ap.parse_args()

    with SessionLocal() as db:
        if args.ajouter:
            if not (args.email and args.resume):
                ap.error("--email et --resume sont requis")
            quand = (dt.datetime.fromisoformat(args.le).replace(tzinfo=dt.timezone.utc)
                     if args.le else dt.datetime.now(dt.timezone.utc))
            c = consigner(db, email=args.email, canal=args.canal, sens=args.sens,
                          resume=args.resume, survenu_le=quand,
                          suite_prevue=args.suite,
                          relance_le=dt.date.fromisoformat(args.relance) if args.relance else None,
                          auteur=args.auteur)
            print(f"consigné : {c.email} · {c.canal} · {str(c.survenu_le)[:10]}")
            return

        stmt = select(ContactManuel).order_by(ContactManuel.survenu_le.desc())
        if args.email:
            stmt = stmt.where(ContactManuel.email == args.email.lower().strip())
        lignes = list(db.scalars(stmt))
        if not lignes:
            print("aucun contact consigné.")
            return
        print(f"{len(lignes)} contact(s)\n")
        for c in lignes:
            print(f"  {str(c.survenu_le)[:10]}  {c.email:38} {c.canal:9} {c.sens}")
            print(f"     {c.resume}")
            if c.suite_prevue:
                print(f"     → suite : {c.suite_prevue}")
            if c.relance_le:
                reste = (c.relance_le - dt.date.today()).days
                etat = "en retard" if reste < 0 else f"dans {reste} j"
                print(f"     → relance prévue le {c.relance_le} ({etat})")
            print()


if __name__ == "__main__":
    main()
