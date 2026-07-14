"""
Normalize raw articles from different sources into a common schema.

Every article — regardless of source — gets mapped to the same dict structure
so downstream processing doesn't need to know where it came from.
"""

import hashlib
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)


def _canonicalize_url(url: str) -> str:
    """
    Normalize a URL for deduplication: strip query params, fragments,
    trailing slashes, and force lowercase scheme + netloc.
    """
    try:
        parsed = urlparse(url)
        canonical = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",  # params
            "",  # query
            "",  # fragment
        ))
        return canonical
    except Exception:
        return url.strip().rstrip("/")


def _generate_id(url: str) -> str:
    """Generate a stable SHA-1 ID from the canonical URL."""
    canonical = _canonicalize_url(url)
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()


def _extract_domain(url: str) -> str:
    """Extract the domain from a URL, stripping www. prefix."""
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _parse_iso_date(date_str: str) -> str:
    """Parse various date formats into ISO 8601, fallback to now."""
    if not date_str:
        return datetime.now(timezone.utc).isoformat()

    try:
        dt = dateutil_parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except (ValueError, TypeError):
        return datetime.now(timezone.utc).isoformat()


def normalize_newsapi(article: dict) -> dict:
    """Normalize a NewsAPI article into common schema."""
    url = article.get("url", "")
    source_name = article.get("source", {}).get("name", "")

    # NewsAPI provides title, description, content (truncated)
    raw_text = article.get("description", "") or ""
    content = article.get("content", "")
    if content:
        raw_text = f"{raw_text} {content}".strip()

    return {
        "id": _generate_id(url),
        "title": article.get("title", "").strip(),
        "url": url,
        "source_domain": _extract_domain(url),
        "published_at": _parse_iso_date(article.get("publishedAt", "")),
        "raw_text": raw_text,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source_api": "newsapi",
    }


def normalize_gdelt(article: dict) -> dict:
    """Normalize a GDELT Doc API article into common schema."""
    url = article.get("url", "")

    # GDELT seendate format: "20240715T120000Z"
    seen_date = article.get("seendate", "")
    if seen_date and "T" in seen_date:
        try:
            dt = datetime.strptime(seen_date, "%Y%m%dT%H%M%SZ")
            dt = dt.replace(tzinfo=timezone.utc)
            published = dt.isoformat()
        except ValueError:
            published = _parse_iso_date(seen_date)
    else:
        published = _parse_iso_date(seen_date)

    return {
        "id": _generate_id(url),
        "title": article.get("title", "").strip(),
        "url": url,
        "source_domain": article.get("domain", _extract_domain(url)),
        "published_at": published,
        "raw_text": article.get("title", ""),  # GDELT doesn't return body text
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source_api": "gdelt",
    }


def normalize_rss(article: dict) -> dict:
    """Normalize an RSS feed article into common schema."""
    url = article.get("link", "")

    return {
        "id": _generate_id(url),
        "title": article.get("title", "").strip(),
        "url": url,
        "source_domain": _extract_domain(url),
        "published_at": _parse_iso_date(article.get("published", "")),
        "raw_text": article.get("summary", ""),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source_api": "rss",
    }


def normalize_all(
    newsapi_articles: list[dict],
    gdelt_articles: list[dict],
    rss_articles: list[dict],
) -> list[dict]:
    """
    Normalize articles from all sources into a single list with common schema.

    Args:
        newsapi_articles: Raw articles from NewsAPI
        gdelt_articles: Raw articles from GDELT
        rss_articles: Raw articles from RSS feeds

    Returns:
        Combined list of normalized article dicts
    """
    normalized = []

    for art in newsapi_articles:
        try:
            normalized.append(normalize_newsapi(art))
        except Exception as e:
            logger.warning("Failed to normalize NewsAPI article: %s", e)

    for art in gdelt_articles:
        try:
            normalized.append(normalize_gdelt(art))
        except Exception as e:
            logger.warning("Failed to normalize GDELT article: %s", e)

    for art in rss_articles:
        try:
            normalized.append(normalize_rss(art))
        except Exception as e:
            logger.warning("Failed to normalize RSS article: %s", e)

    logger.info(
        "Normalized %d articles total (NewsAPI=%d, GDELT=%d, RSS=%d)",
        len(normalized),
        len(newsapi_articles),
        len(gdelt_articles),
        len(rss_articles),
    )
    return normalized
