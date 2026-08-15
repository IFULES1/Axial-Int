"""RSS/Atom fetching for veille agents.

Given a set of feeds, pull recent entries, keep only those newer than the last
run and not already seen, and normalise them to a small dict the analysis layer
can merge with web-search results. Fail-soft: a broken feed is logged and skipped
so one bad URL never sinks a run.
"""
from __future__ import annotations

import calendar
import datetime as dt
import logging

logger = logging.getLogger("axial.watches.rss")

MAX_PER_FEED = 25
MAX_TOTAL = 60


def _entry_dt(entry) -> dt.datetime | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not parsed:
        return None
    try:
        # feedparser dates are UTC struct_time → timegm (NOT mktime, which is local).
        return dt.datetime.fromtimestamp(calendar.timegm(parsed), tz=dt.timezone.utc)
    except Exception:
        return None


def fetch_new_articles(feeds: list, *, since: dt.datetime | None,
                       seen_urls: set[str] | None = None) -> list[dict]:
    """Fetch entries from `feeds` (objects with .url/.title), keep the fresh ones.

    Freshness = published after `since` (when the feed dates its entries) AND URL
    not in `seen_urls`. Returns normalised article dicts, newest first.
    """
    import feedparser

    seen = seen_urls or set()
    out: list[dict] = []
    for feed in feeds:
        try:
            parsed = feedparser.parse(feed.url)
        except Exception as e:  # noqa: BLE001 — one bad feed must not sink the run
            logger.warning("RSS feed failed (%s): %s", getattr(feed, "url", "?"), e)
            continue
        source_title = feed.title or (getattr(parsed.feed, "title", "") or feed.url)
        for entry in parsed.entries[:MAX_PER_FEED]:
            url = getattr(entry, "link", "") or ""
            if not url or url in seen:
                continue
            published = _entry_dt(entry)
            # If the entry is dated and older than the cutoff, skip it. Undated
            # entries are kept (better a rare dup than missing a real signal).
            if since and published and published <= since:
                continue
            seen.add(url)
            out.append({
                "title": (getattr(entry, "title", "") or "").strip(),
                "url": url,
                "summary": (getattr(entry, "summary", "") or "")[:600],
                "published": published.isoformat() if published else None,
                "source": source_title,
                "provider": "rss",
            })
    out.sort(key=lambda a: a.get("published") or "", reverse=True)
    return out[:MAX_TOTAL]
