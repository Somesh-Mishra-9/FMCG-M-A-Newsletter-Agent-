"""
NewsAPI source — fetches recent FMCG M&A articles via the NewsAPI /everything endpoint.

Free tier: 100 requests/day, articles up to 30 days old, 24h delay on latest.
"""

import logging
from datetime import datetime, timedelta, timezone

import requests

from config import (
    NEWSAPI_KEY,
    FMCG_ENTITIES,
    DEAL_KEYWORDS,
    FMCG_SECTOR_TERMS,
    INGESTION_LOOKBACK_DAYS,
)

logger = logging.getLogger(__name__)

NEWSAPI_EVERYTHING_URL = "https://newsapi.org/v2/everything"


def _build_query() -> str:
    """
    Build a NewsAPI query string combining FMCG entities/sector terms
    with deal keywords using OR/AND logic.

    Strategy: (entity1 OR entity2 OR ... OR sector1 OR sector2)
              AND (deal_kw1 OR deal_kw2 OR ...)

    NewsAPI query syntax uses AND/OR/NOT and quotes for exact phrases.
    Max query length ~500 chars, so we pick a representative subset.
    """
    # Pick the most common/important entities to stay within query limits
    key_entities = [
        '"Hindustan Unilever"', '"ITC"', '"Nestle India"',
        '"Britannia"', '"Dabur"', '"Marico"', '"Godrej Consumer"',
        '"Tata Consumer"', '"Patanjali"', '"Adani Wilmar"',
        '"Unilever"', '"P&G"', '"PepsiCo"', '"Coca-Cola"',
        '"Mondelez"', '"Reckitt"',
        "FMCG", '"consumer goods"', '"packaged foods"',
    ]
    key_deal_terms = [
        "acquisition", "merger", "stake", "buyout",
        "investment", "funding", "divestment", "IPO",
        '"joint venture"', "deal", "M&A",
    ]

    entity_part = " OR ".join(key_entities)
    deal_part = " OR ".join(key_deal_terms)
    query = f"({entity_part}) AND ({deal_part})"

    # NewsAPI has a practical limit; truncate if needed
    if len(query) > 500:
        logger.warning("NewsAPI query truncated to 500 chars")
        query = query[:500]

    return query


def fetch_newsapi_articles() -> list[dict]:
    """
    Fetch articles from NewsAPI's /everything endpoint.

    Returns a list of raw article dicts as returned by the API.
    Returns an empty list if the API key is missing or the request fails.
    """
    if not NEWSAPI_KEY:
        logger.warning("NEWSAPI_KEY not set — skipping NewsAPI ingestion")
        return []

    from_date = (
        datetime.now(timezone.utc) - timedelta(days=INGESTION_LOOKBACK_DAYS)
    ).strftime("%Y-%m-%d")

    params = {
        "q": _build_query(),
        "from": from_date,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 100,  # max per request on free tier
        "apiKey": NEWSAPI_KEY,
    }

    try:
        logger.info("Fetching articles from NewsAPI...")
        resp = requests.get(NEWSAPI_EVERYTHING_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "ok":
            logger.error("NewsAPI returned status: %s", data.get("status"))
            return []

        articles = data.get("articles", [])
        logger.info("NewsAPI returned %d articles", len(articles))
        return articles

    except requests.RequestException as e:
        logger.error("NewsAPI request failed: %s", e)
        return []
