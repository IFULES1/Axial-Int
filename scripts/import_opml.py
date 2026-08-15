"""Import an Inoreader/OPML feed export into `rss_feeds` for a user.

OPML folders map to veille categories (see FOLDER_CAT); feeds outside a folder use
a per-title map or fall back to 'general'. With --replace, the user's existing feeds
are cleared first so the DB mirrors the export.

    doppler run -- .venv/bin/python scripts/import_opml.py \
        --email founder2@axialtest.com --opml "path/to/export.opml" --replace
"""
from __future__ import annotations

import argparse
import uuid
import xml.etree.ElementTree as ET
from collections import Counter

from sqlalchemy import delete, select, text

from app.db import SessionLocal
from app.modules.watches.models import RssFeed

# OPML folder title (lowercased) → veille category.
FOLDER_CAT = {
    "aides publiques": "financement",
    "produit & tech": "produit",
    "réglementaire": "reglementaire",
    "reglementaire": "reglementaire",
    "vc's watch": "vc",
    "axial watches": "marche",
    "concurrents": "concurrence",
    "concurrence": "concurrence",
}
# Feeds sitting at the OPML root (no folder) → category by title.
TITLE_CAT = {
    "product hunt — the best new products, every day": "produit",
    "bloomberg technology": "tech",
    "reuters": "general",
}


def _cat(folder: str | None, title: str | None) -> str:
    if folder:
        return FOLDER_CAT.get(folder.strip().lower(), "general")
    return TITLE_CAT.get((title or "").strip().lower(), "general")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--opml", required=True)
    ap.add_argument("--replace", action="store_true", help="clear existing feeds first")
    args = ap.parse_args()

    body = ET.parse(args.opml).find("body")
    feeds: list[tuple[str, str | None, str]] = []
    for outline in body.findall("outline"):
        if outline.get("xmlUrl"):  # feed at root
            feeds.append((outline.get("xmlUrl"), outline.get("title"), _cat(None, outline.get("title"))))
        else:                       # folder → its child feeds
            folder = outline.get("title")
            for child in outline.findall("outline"):
                if child.get("xmlUrl"):
                    feeds.append((child.get("xmlUrl"), child.get("title"), _cat(folder, child.get("title"))))

    with SessionLocal() as db:
        uid = db.execute(text("select id from dev_users where email=:e"), {"e": args.email}).scalar()
        if not uid:
            print(f"⚠️  utilisateur introuvable : {args.email}")
            return 1
        if args.replace:
            db.execute(delete(RssFeed).where(RssFeed.user_id == uid))
            db.commit()
        existing = {f.url for f in db.scalars(select(RssFeed).where(RssFeed.user_id == uid))}
        added, cats = 0, Counter()
        for url, title, cat in feeds:
            if url in existing:
                continue
            db.add(RssFeed(id=uuid.uuid4(), user_id=uid, url=url, category=cat,
                           title=((title or "")[:300] or None)))
            existing.add(url)
            added += 1
            cats[cat] += 1
        db.commit()
        print(f"✅ {added} flux importés pour {args.email}")
        for c, n in sorted(cats.items()):
            print(f"   {c:14} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
