"""
GDELT Doc 2.0 API source — fetches FMCG M&A articles from GDELT's free API.

GDELT indexes news globally in near real-time. No API key required.
We filter by economic themes (mergers/acquisitions) and FMCG keywords.
"""

import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


def fetch_gdelt_articles() -> list[dict]:
    """
    Query GDELT Doc 2.0 API for FMCG-related M&A articles.

    Returns a list of raw article dicts from GDELT's JSON response.
    Each dict typically has: url, title, seendate, domain, language, sourcecountry.
    """
    # GDELT query: combine FMCG terms with deal/M&A terms
    query_terms = (
        '(FMCG OR "consumer goods" OR "packaged foods" OR "consumer products") '
        '(acquisition OR merger OR "stake sale" OR investment OR buyout OR deal)'
    )

    params = {
        "query": query_terms,
        "mode": "ArtList",
        "maxrecords": 100,
        "format": "json",
        "timespan": "30d",
        "sort": "DateDesc",
    }

    try:
        logger.info("Fetching articles from GDELT Doc API...")
        resp = requests.get(GDELT_DOC_API, params=params, timeout=30)
        resp.raise_for_status()

        data = resp.json()
        articles = data.get("articles", [])
        logger.info("GDELT returned %d articles", len(articles))
        return articles

    except requests.RequestException as e:
        logger.error("GDELT request failed: %s", e)
        return []
    except ValueError as e:
        # GDELT sometimes returns non-JSON for empty results
        logger.warning("GDELT returned non-JSON response: %s", e)
        return []
