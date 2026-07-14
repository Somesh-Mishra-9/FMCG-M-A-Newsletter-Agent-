"""
De-duplication module — three-layer dedup pipeline.

Layer 1: Exact URL match (same canonical URL → same article)
Layer 2: Fuzzy title matching via rapidfuzz (catches syndicated articles with minor edits)
Layer 3: Semantic similarity via sentence-transformers (catches paraphrased coverage)

Within each duplicate cluster, we keep the article from the highest-credibility source.
"""

import logging
from datetime import datetime, timezone

from dateutil import parser as dateutil_parser
from rapidfuzz import fuzz

from config import (
    FUZZY_DEDUP_THRESHOLD,
    SEMANTIC_DEDUP_THRESHOLD,
    DEDUP_TIME_WINDOW_HOURS,
    SOURCE_CREDIBILITY,
    DEFAULT_CREDIBILITY_TIER,
)

logger = logging.getLogger(__name__)


def _parse_dt(iso_str: str) -> datetime:
    """Parse an ISO date string into a timezone-aware datetime."""
    try:
        dt = dateutil_parser.parse(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def _within_time_window(art_a: dict, art_b: dict, hours: int) -> bool:
    """Check if two articles were published within `hours` of each other."""
    dt_a = _parse_dt(art_a.get("published_at", ""))
    dt_b = _parse_dt(art_b.get("published_at", ""))
    delta = abs((dt_a - dt_b).total_seconds())
    return delta <= hours * 3600


def _get_credibility_tier(article: dict) -> int:
    """Get the credibility tier for an article's source domain."""
    domain = article.get("source_domain", "")
    return SOURCE_CREDIBILITY.get(domain, DEFAULT_CREDIBILITY_TIER)


def dedup_exact(articles: list[dict]) -> list[dict]:
    """
    Layer 1: Remove articles with duplicate IDs (same canonical URL).

    Returns deduplicated list. Duplicate articles are marked with
    pipeline_status='duplicate'.
    """
    seen_ids = {}
    result = []

    for article in articles:
        article_id = article["id"]
        if article_id in seen_ids:
            article["pipeline_status"] = "duplicate"
            article["duplicate_of"] = seen_ids[article_id]
            result.append(article)
            logger.debug("Exact duplicate: %s", article.get("title", "")[:60])
        else:
            seen_ids[article_id] = article_id
            result.append(article)

    kept = sum(1 for a in result if a.get("pipeline_status") != "duplicate")
    dupes = len(result) - kept
    logger.info("Exact dedup: %d total → %d kept, %d duplicates", len(articles), kept, dupes)
    return result


def dedup_fuzzy(articles: list[dict]) -> list[dict]:
    """
    Layer 2: Fuzzy title matching within a time window.

    Uses rapidfuzz token_sort_ratio to catch syndicated articles
    with minor title differences (e.g. added source attribution).
    """
    # Separate already-marked duplicates from candidates
    candidates = [a for a in articles if a.get("pipeline_status") != "duplicate"]
    already_dupes = [a for a in articles if a.get("pipeline_status") == "duplicate"]

    # Track which candidate indices have been marked as duplicates
    is_dup = [False] * len(candidates)
    dup_of = [None] * len(candidates)

    for i in range(len(candidates)):
        if is_dup[i]:
            continue
        for j in range(i + 1, len(candidates)):
            if is_dup[j]:
                continue

            # Only compare within the time window
            if not _within_time_window(
                candidates[i], candidates[j], DEDUP_TIME_WINDOW_HOURS
            ):
                continue

            title_i = candidates[i].get("title", "")
            title_j = candidates[j].get("title", "")

            score = fuzz.token_sort_ratio(title_i, title_j)
            if score >= FUZZY_DEDUP_THRESHOLD:
                # Keep the one with better credibility
                tier_i = _get_credibility_tier(candidates[i])
                tier_j = _get_credibility_tier(candidates[j])

                if tier_i <= tier_j:
                    # Keep i, mark j as duplicate
                    is_dup[j] = True
                    dup_of[j] = candidates[i]["id"]
                else:
                    # Keep j, mark i as duplicate
                    is_dup[i] = True
                    dup_of[i] = candidates[j]["id"]
                    break  # i is now a dup, no need to compare further

    result = list(already_dupes)
    fuzzy_dupes = 0
    for idx, article in enumerate(candidates):
        if is_dup[idx]:
            article["pipeline_status"] = "duplicate"
            article["duplicate_of"] = dup_of[idx]
            fuzzy_dupes += 1
        result.append(article)

    logger.info("Fuzzy dedup: found %d additional duplicates", fuzzy_dupes)
    return result


def dedup_semantic(articles: list[dict]) -> list[dict]:
    """
    Layer 3: Semantic similarity using sentence-transformers embeddings.

    Catches paraphrased or rephrased coverage of the same deal.
    Only runs on articles not already marked as duplicates.
    """
    candidates = [a for a in articles if a.get("pipeline_status") != "duplicate"]
    already_dupes = [a for a in articles if a.get("pipeline_status") == "duplicate"]

    if len(candidates) <= 1:
        return articles

    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        from config import EMBEDDING_MODEL

        logger.info("Loading embedding model for semantic dedup...")
        model = SentenceTransformer(EMBEDDING_MODEL)

        # Build text for embedding: title + first ~200 chars of raw_text
        texts = []
        for art in candidates:
            title = art.get("title", "")
            snippet = art.get("raw_text", "")[:200]
            texts.append(f"{title}. {snippet}")

        embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)

        # Pairwise cosine similarity (since embeddings are normalized, dot product = cosine)
        is_dup = [False] * len(candidates)
        dup_of = [None] * len(candidates)
        semantic_dupes = 0

        for i in range(len(candidates)):
            if is_dup[i]:
                continue
            for j in range(i + 1, len(candidates)):
                if is_dup[j]:
                    continue

                if not _within_time_window(
                    candidates[i], candidates[j], DEDUP_TIME_WINDOW_HOURS
                ):
                    continue

                similarity = float(np.dot(embeddings[i], embeddings[j]))
                if similarity >= SEMANTIC_DEDUP_THRESHOLD:
                    tier_i = _get_credibility_tier(candidates[i])
                    tier_j = _get_credibility_tier(candidates[j])

                    if tier_i <= tier_j:
                        is_dup[j] = True
                        dup_of[j] = candidates[i]["id"]
                    else:
                        is_dup[i] = True
                        dup_of[i] = candidates[j]["id"]
                        break
                    semantic_dupes += 1

        result = list(already_dupes)
        for idx, article in enumerate(candidates):
            if is_dup[idx]:
                article["pipeline_status"] = "duplicate"
                article["duplicate_of"] = dup_of[idx]
            result.append(article)

        logger.info("Semantic dedup: found %d additional duplicates", semantic_dupes)
        return result

    except ImportError:
        logger.warning("sentence-transformers not available, skipping semantic dedup")
        return articles
    except Exception as e:
        logger.error("Semantic dedup failed: %s", e)
        return articles


def run_dedup(articles: list[dict]) -> list[dict]:
    """
    Run the full three-layer dedup pipeline.

    Returns all articles with pipeline_status and duplicate_of fields set.
    """
    logger.info("Starting dedup pipeline with %d articles", len(articles))

    # Layer 1: Exact URL dedup
    articles = dedup_exact(articles)

    # Layer 2: Fuzzy title dedup
    articles = dedup_fuzzy(articles)

    # Layer 3: Semantic dedup
    articles = dedup_semantic(articles)

    kept = sum(1 for a in articles if a.get("pipeline_status") != "duplicate")
    total_dupes = len(articles) - kept
    logger.info("Dedup complete: %d articles → %d kept, %d total duplicates", len(articles), kept, total_dupes)

    return articles
