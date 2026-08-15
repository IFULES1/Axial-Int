"""Seed RSS feeds in bulk from a CSV into the `rss_feeds` table for a given user.

CSV columns: url,category[,title]  (header required). Category must be one the
skills consume (concurrence|startup|financement|vc|reglementaire|juridique|
produit|tech|marche|general). Idempotent-ish: skips a url already present for the user.

    doppler run -- .venv/bin/python scripts/seed_rss_feeds.py \
        --email founder2@axialtest.com --csv data/rss_feeds.csv
"""
from __future__ import annotations

import argparse
import csv
import uuid

from sqlalchemy import select, text

from app.db import SessionLocal
from app.modules.watches.models import RssFeed

VALID = {"concurrence", "startup", "financement", "vc", "reglementaire",
         "juridique", "produit", "tech", "marche", "general"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True, help="owner account email")
    ap.add_argument("--csv", default="data/rss_feeds.csv")
    args = ap.parse_args()

    with SessionLocal() as db:
        uid = db.execute(text("select id from dev_users where email=:e"),
                         {"e": args.email}).scalar()
        if not uid:
            print(f"⚠️  utilisateur introuvable : {args.email}")
            return 1
        existing = {
            f.url for f in db.scalars(select(RssFeed).where(RssFeed.user_id == uid))
        }
        added, skipped = 0, 0
        with open(args.csv, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                url = (row.get("url") or "").strip()
                if not url or url in existing:
                    skipped += 1
                    continue
                category = (row.get("category") or "general").strip()
                if category not in VALID:
                    print(f"  ⚠️  catégorie inconnue '{category}' pour {url} → 'general'")
                    category = "general"
                db.add(RssFeed(id=uuid.uuid4(), user_id=uid, url=url, category=category,
                               title=(row.get("title") or "").strip() or None))
                existing.add(url)
                added += 1
        db.commit()
        print(f"✅ {added} flux ajoutés, {skipped} ignorés (déjà présents/vides) pour {args.email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
