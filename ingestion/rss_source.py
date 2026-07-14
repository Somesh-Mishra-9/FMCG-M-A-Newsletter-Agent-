"""
RSS feed source — fetches FMCG-related articles from curated business RSS feeds.

Client-side keyword filtering applied since RSS feeds don't support query params.
"""

import logging
from datetime import datetime, timezone

import feedparser
from dateutil import parser as dateutil_parser

from config import (
    RSS_FEEDS,
    FMCG_ENTITIES,
    DEAL_KEYWORDS,
    FMCG_SECTOR_TERMS,
)

logger = logging.getLogger(__name__)


def _matches_keywords(text: str) -> bool:
    """
    Check if text contains at least one FMCG entity/sector term
    AND at least one deal keyword. Case-insensitive.
    """
    text_lower = text.lower()

    has_fmcg = any(
        entity.lower() in text_lower
        for entity in FMCG_ENTITIES + FMCG_SECTOR_TERMS
    )
    has_deal = any(kw.lower() in text_lower for kw in DEAL_KEYWORDS)

    return has_fmcg and has_deal


def _parse_date(entry) -> str:
    """
    Extract and normalize the publication date from a feed entry.
    Falls back to current UTC time if parsing fails.
    """
    date_str = entry.get("published") or entry.get("updated", "")
    if date_str:
        try:
            dt = dateutil_parser.parse(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except (ValueError, TypeError):
            pass

    return datetime.now(timezone.utc).isoformat()


def fetch_rss_articles() -> list[dict]:
    """
    Fetch and filter articles from configured RSS feeds.

    Returns a list of dicts with keys: title, link, published, summary, source_name.
    Only entries matching FMCG + deal keywords in title/summary are returned.
    """
    all_articles = []

    for feed_config in RSS_FEEDS:
        feed_name = feed_config["name"]
        feed_url = feed_config["url"]

        try:
            logger.info("Parsing RSS feed: %s", feed_name)
            feed = feedparser.parse(feed_url)

            if feed.bozo and not feed.entries:
                logger.warning("Feed %s returned no entries (bozo=%s)", feed_name, feed.bozo)
                continue

            matched = 0
            for entry in feed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                combined_text = f"{title} {summary}"

                if _matches_keywords(combined_text):
                    article = {
                        "title": title,
                        "link": entry.get("link", ""),
                        "published": _parse_date(entry),
                        "summary": summary,
                        "source_name": feed_name,
                    }
                    all_articles.append(article)
                    matched += 1

            logger.info("Feed %s: %d entries, %d matched keywords", feed_name, len(feed.entries), matched)

        except Exception as e:
            logger.error("Failed to parse feed %s: %s", feed_name, e)
            continue

    logger.info("RSS total: %d matched articles from %d feeds", len(all_articles), len(RSS_FEEDS))
    return all_articles
