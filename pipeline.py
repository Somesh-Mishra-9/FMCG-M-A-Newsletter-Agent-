"""
Pipeline orchestrator — the single entry point that wires all stages together.

Stages: Ingestion → Dedup → Credibility → Relevance → Summarization → Newsletter

Saves intermediate results and the final output with full decision trails.
"""

import json
import logging
import os
from datetime import datetime, timezone

import pandas as pd

from ingestion.newsapi_source import fetch_newsapi_articles
from ingestion.gdelt_source import fetch_gdelt_articles
from ingestion.rss_source import fetch_rss_articles
from ingestion.normalize import normalize_all
from processing.dedup import run_dedup
from processing.credibility import score_credibility
from processing.relevance import run_relevance_filter
from generation.summarize import summarize_articles
from generation.newsletter_builder import build_markdown_newsletter, build_docx_newsletter

logger = logging.getLogger(__name__)

# Ensure data directories exist
os.makedirs("data/raw", exist_ok=True)
os.makedirs("data/processed", exist_ok=True)


def run_pipeline() -> dict:
    """
    Execute the full newsletter generation pipeline.

    Returns a dict with:
        - articles: full list with pipeline decisions
        - newsletter_md: markdown newsletter text
        - newsletter_docx_path: path to generated .docx file
        - stats: pipeline statistics (counts at each stage)
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stats = {}

    # ── Stage 1: Ingestion ──────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STAGE 1: INGESTION")
    logger.info("=" * 60)

    newsapi_raw = fetch_newsapi_articles()
    gdelt_raw = fetch_gdelt_articles()
    rss_raw = fetch_rss_articles()

    stats["newsapi_raw"] = len(newsapi_raw)
    stats["gdelt_raw"] = len(gdelt_raw)
    stats["rss_raw"] = len(rss_raw)

    # Normalize all sources into common schema
    articles = normalize_all(newsapi_raw, gdelt_raw, rss_raw)
    stats["total_raw"] = len(articles)

    # Save raw ingested data
    raw_path = f"data/raw/ingestion_{timestamp}.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False, default=str)
    logger.info("Raw data saved to %s", raw_path)

    if not articles:
        logger.warning("No articles ingested — check API keys and network connectivity")
        return {
            "articles": [],
            "newsletter_md": "# No Data\n\nNo articles were ingested. Check API keys and try again.",
            "newsletter_docx_path": None,
            "stats": stats,
        }

    # ── Stage 2: De-duplication ─────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STAGE 2: DE-DUPLICATION")
    logger.info("=" * 60)

    articles = run_dedup(articles)
    stats["after_dedup"] = sum(
        1 for a in articles if a.get("pipeline_status") != "duplicate"
    )
    stats["duplicates_removed"] = stats["total_raw"] - stats["after_dedup"]

    # ── Stage 3: Credibility Scoring ────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STAGE 3: CREDIBILITY SCORING")
    logger.info("=" * 60)

    articles = score_credibility(articles)

    # ── Stage 4: Relevance Filtering ────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STAGE 4: RELEVANCE FILTERING")
    logger.info("=" * 60)

    articles = run_relevance_filter(articles)
    stats["after_relevance"] = sum(
        1 for a in articles if a.get("pipeline_status") == "kept"
    )
    stats["irrelevant"] = sum(
        1 for a in articles if a.get("pipeline_status") == "irrelevant"
    )
    stats["low_confidence"] = sum(
        1 for a in articles if a.get("pipeline_status") == "low_confidence"
    )

    # ── Stage 5: Summarization ──────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STAGE 5: SUMMARIZATION")
    logger.info("=" * 60)

    articles = summarize_articles(articles)

    # ── Stage 6: Newsletter Generation ──────────────────────────────────────
    logger.info("=" * 60)
    logger.info("STAGE 6: NEWSLETTER GENERATION")
    logger.info("=" * 60)

    newsletter_md = build_markdown_newsletter(articles)

    docx_path = f"data/processed/newsletter_{timestamp}.docx"
    build_docx_newsletter(articles, docx_path)

    # ── Save processed data with full decision trail ────────────────────────
    processed_json_path = f"data/processed/pipeline_output_{timestamp}.json"
    with open(processed_json_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False, default=str)

    # Also save as CSV for easy analysis
    processed_csv_path = f"data/processed/pipeline_output_{timestamp}.csv"
    df = pd.DataFrame(articles)
    # Convert list fields to strings for CSV compatibility
    for col in ["companies_involved"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: "; ".join(x) if isinstance(x, list) else str(x))
    df.to_csv(processed_csv_path, index=False, encoding="utf-8")

    # Save a "latest" copy for easy access
    latest_json = "data/processed/pipeline_output.json"
    with open(latest_json, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False, default=str)

    latest_csv = "data/processed/pipeline_output.csv"
    df.to_csv(latest_csv, index=False, encoding="utf-8")

    stats["final_kept"] = stats["after_relevance"]
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("Stats: %s", json.dumps(stats, indent=2))
    logger.info("=" * 60)

    return {
        "articles": articles,
        "newsletter_md": newsletter_md,
        "newsletter_docx_path": docx_path,
        "stats": stats,
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    result = run_pipeline()
    print("\n" + "=" * 60)
    print("Pipeline Statistics:")
    for key, val in result["stats"].items():
        print(f"  {key}: {val}")
    print("=" * 60)
