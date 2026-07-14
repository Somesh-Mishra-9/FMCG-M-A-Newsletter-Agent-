"""
Source credibility scoring — static domain whitelist approach.

Assigns each article a credibility tier (1-3) based on the publishing domain.
Tier 1 = major financial/business press, Tier 2 = reputable industry sources,
Tier 3 = unknown or niche sources.

This is a practical v1 approach — a production system would use dynamic
reputation scoring based on historical accuracy, but the static whitelist
is transparent and defensible for a demo.
"""

import logging

from config import SOURCE_CREDIBILITY, CREDIBILITY_SCORES, DEFAULT_CREDIBILITY_TIER

logger = logging.getLogger(__name__)


def score_credibility(articles: list[dict]) -> list[dict]:
    """
    Assign credibility_tier and credibility_score to every article.

    Applied to ALL articles regardless of pipeline_status, so the full
    decision trail is visible in the raw data export.
    """
    tier_counts = {1: 0, 2: 0, 3: 0}

    for article in articles:
        domain = article.get("source_domain", "").lower()

        # Check exact domain match first
        tier = SOURCE_CREDIBILITY.get(domain, None)

        # Try parent domain if subdomain doesn't match
        if tier is None and "." in domain:
            parts = domain.split(".")
            if len(parts) > 2:
                parent = ".".join(parts[-2:])
                tier = SOURCE_CREDIBILITY.get(parent, None)

        if tier is None:
            tier = DEFAULT_CREDIBILITY_TIER

        article["credibility_tier"] = tier
        article["credibility_score"] = CREDIBILITY_SCORES[tier]
        tier_counts[tier] += 1

    logger.info(
        "Credibility scoring: Tier 1=%d, Tier 2=%d, Tier 3=%d",
        tier_counts[1], tier_counts[2], tier_counts[3],
    )
    return articles
