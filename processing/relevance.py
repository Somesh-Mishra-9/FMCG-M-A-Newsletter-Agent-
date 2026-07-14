"""
Relevance filtering — two-stage approach.

Stage 1: Keyword pre-filter — fast, zero-cost check for FMCG entity + deal keyword
Stage 2: LLM classification — Groq (Llama 3.1) for nuanced relevance + deal metadata
"""

import json
import logging
import re

from config import (
    FMCG_ENTITIES,
    FMCG_SECTOR_TERMS,
    DEAL_KEYWORDS,
    GROQ_API_KEY,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    RELEVANCE_CONFIDENCE_MIN,
)

logger = logging.getLogger(__name__)


def _keyword_prefilter(article: dict) -> bool:
    """
    Quick check: does the article mention at least one FMCG entity/sector term
    AND at least one deal-type keyword?

    Runs on title + raw_text. Zero API cost.
    """
    text = f"{article.get('title', '')} {article.get('raw_text', '')}".lower()

    has_fmcg = any(
        entity.lower() in text
        for entity in FMCG_ENTITIES + FMCG_SECTOR_TERMS
    )
    has_deal = any(kw.lower() in text for kw in DEAL_KEYWORDS)

    return has_fmcg and has_deal


def _strip_json_fences(text: str) -> str:
    """
    Strip markdown code fences from LLM output.
    Models sometimes wrap JSON in ```json ... ``` despite instructions.
    """
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _classify_with_llm(article: dict) -> dict:
    """
    Use Groq (Llama 3.1) to classify whether an article is about an FMCG deal
    and extract structured deal metadata.

    Returns a dict with: is_fmcg_deal, deal_type, companies_involved, confidence
    """
    try:
        from groq import Groq

        client = Groq(api_key=GROQ_API_KEY)

        title = article.get("title", "")
        snippet = article.get("raw_text", "")[:500]

        system_prompt = (
            "You are a financial news classifier specializing in FMCG (Fast-Moving Consumer Goods) "
            "mergers, acquisitions, and investment deals. Given a news article title and snippet, "
            "determine if it's about an FMCG-related deal and extract key information.\n\n"
            "Return ONLY valid JSON with these fields:\n"
            '{"is_fmcg_deal": bool, "deal_type": string, "companies_involved": [string], '
            '"deal_value": string, "confidence": float}\n\n'
            "deal_type must be one of: acquisition, merger, stake_sale, funding, divestment, ipo, jv, other\n"
            'deal_value should be the stated value or "undisclosed"\n'
            "confidence should be 0.0 to 1.0\n\n"
            "Return ONLY the JSON object. No other text."
        )

        user_prompt = f"Title: {title}\n\nSnippet: {snippet}"

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )

        raw_output = response.choices[0].message.content
        cleaned = _strip_json_fences(raw_output)
        result = json.loads(cleaned)

        return {
            "is_fmcg_deal": result.get("is_fmcg_deal", False),
            "deal_type": result.get("deal_type", "other"),
            "companies_involved": result.get("companies_involved", []),
            "deal_value": result.get("deal_value", "undisclosed"),
            "confidence": float(result.get("confidence", 0.0)),
        }

    except json.JSONDecodeError as e:
        logger.warning("LLM returned invalid JSON for '%s': %s", article.get("title", "")[:50], e)
        return {
            "is_fmcg_deal": False,
            "deal_type": "other",
            "companies_involved": [],
            "deal_value": "undisclosed",
            "confidence": 0.0,
        }
    except Exception as e:
        logger.error("LLM classification failed for '%s': %s", article.get("title", "")[:50], e)
        return {
            "is_fmcg_deal": False,
            "deal_type": "other",
            "companies_involved": [],
            "deal_value": "undisclosed",
            "confidence": 0.0,
        }


def run_relevance_filter(articles: list[dict]) -> list[dict]:
    """
    Two-stage relevance filter on non-duplicate articles.

    Stage 1: Keyword pre-filter (fast, free)
    Stage 2: LLM classification (only for pre-filter survivors)

    Updates each article's pipeline_status and deal metadata in-place.
    """
    has_groq = bool(GROQ_API_KEY)
    if not has_groq:
        logger.warning("GROQ_API_KEY not set — using keyword-only relevance filtering")

    prefilter_pass = 0
    llm_pass = 0
    irrelevant = 0
    low_confidence = 0

    for article in articles:
        # Skip already-marked duplicates
        if article.get("pipeline_status") == "duplicate":
            continue

        # Stage 1: keyword pre-filter
        if not _keyword_prefilter(article):
            article["pipeline_status"] = "irrelevant"
            article["is_fmcg_deal"] = False
            article["deal_type"] = "other"
            article["companies_involved"] = []
            article["deal_value"] = "undisclosed"
            article["relevance_confidence"] = 0.0
            irrelevant += 1
            continue

        prefilter_pass += 1

        # Stage 2: LLM classification (if API key available)
        if has_groq:
            result = _classify_with_llm(article)
            article["is_fmcg_deal"] = result["is_fmcg_deal"]
            article["deal_type"] = result["deal_type"]
            article["companies_involved"] = result["companies_involved"]
            article["deal_value"] = result["deal_value"]
            article["relevance_confidence"] = result["confidence"]

            if not result["is_fmcg_deal"] or result["confidence"] < RELEVANCE_CONFIDENCE_MIN:
                article["pipeline_status"] = "low_confidence"
                low_confidence += 1
            else:
                article["pipeline_status"] = "kept"
                llm_pass += 1
        else:
            # Without LLM, trust keyword matching with moderate confidence
            article["pipeline_status"] = "kept"
            article["is_fmcg_deal"] = True
            article["deal_type"] = "other"
            article["companies_involved"] = []
            article["deal_value"] = "undisclosed"
            article["relevance_confidence"] = 0.7
            llm_pass += 1

    logger.info(
        "Relevance filter: %d passed pre-filter, %d kept after LLM, "
        "%d irrelevant, %d low_confidence",
        prefilter_pass, llm_pass, irrelevant, low_confidence,
    )
    return articles
