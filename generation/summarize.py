"""
Per-deal summarization using Groq (Llama 3.1).

Generates concise, business-reader-friendly summaries of individual deals
from article snippets. Falls back to a cleaned excerpt if LLM is unavailable.
"""

import json
import logging
import re

from config import GROQ_API_KEY, LLM_MODEL, LLM_TEMPERATURE

logger = logging.getLogger(__name__)


def _strip_json_fences(text: str) -> str:
    """Strip markdown code fences that LLMs sometimes add despite instructions."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _summarize_with_llm(article: dict) -> str:
    """
    Generate a 2-3 sentence summary using Groq.

    The prompt is designed to produce output a business user can skim quickly —
    lead with the deal, mention value if known, close with strategic context.
    """
    try:
        from groq import Groq

        client = Groq(api_key=GROQ_API_KEY)

        title = article.get("title", "")
        raw_text = article.get("raw_text", "")[:800]
        companies = ", ".join(article.get("companies_involved", []))
        deal_type = article.get("deal_type", "deal")

        system_prompt = (
            "You are a business news editor writing for a senior FMCG executive. "
            "Summarize the following deal-related article in exactly 2-3 sentences. "
            "Be factual and concise. Include:\n"
            "1. What happened (the deal/transaction)\n"
            "2. Deal value if mentioned, otherwise say 'undisclosed terms'\n"
            "3. Brief strategic significance (one clause)\n\n"
            "Write in professional business prose. No bullet points. No headers."
        )

        user_prompt = (
            f"Title: {title}\n"
            f"Companies: {companies}\n"
            f"Deal type: {deal_type}\n"
            f"Article text: {raw_text}"
        )

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=LLM_TEMPERATURE,
            max_tokens=256,
        )

        summary = response.choices[0].message.content.strip()

        # Sanity check: summary should be reasonable length
        if len(summary) < 20:
            logger.warning("LLM returned suspiciously short summary, using fallback")
            return _fallback_summary(article)

        return summary

    except Exception as e:
        logger.error("LLM summarization failed: %s", e)
        return _fallback_summary(article)


def _fallback_summary(article: dict) -> str:
    """
    Generate a simple summary from available metadata when LLM is unavailable.
    """
    title = article.get("title", "Untitled deal")
    companies = article.get("companies_involved", [])
    deal_type = article.get("deal_type", "deal").replace("_", " ")
    deal_value = article.get("deal_value", "undisclosed")

    if companies:
        company_str = " and ".join(companies[:3])
        summary = f"{company_str} involved in {deal_type}."
    else:
        summary = f"{title}."

    if deal_value and deal_value != "undisclosed":
        summary += f" Deal valued at {deal_value}."
    else:
        summary += " Deal value undisclosed."

    # Add first sentence of raw text as additional context
    raw = article.get("raw_text", "")
    if raw:
        first_sentence = raw.split(".")[0].strip()
        if len(first_sentence) > 20 and first_sentence != title:
            summary += f" {first_sentence}."

    return summary


def summarize_articles(articles: list[dict]) -> list[dict]:
    """
    Generate summaries for all 'kept' articles.

    Uses LLM if GROQ_API_KEY is set, falls back to metadata-based summary otherwise.
    Only processes articles with pipeline_status='kept'.
    """
    has_groq = bool(GROQ_API_KEY)
    if not has_groq:
        logger.warning("GROQ_API_KEY not set — using fallback summaries")

    summarized = 0
    for article in articles:
        if article.get("pipeline_status") != "kept":
            continue

        if has_groq:
            article["summary"] = _summarize_with_llm(article)
        else:
            article["summary"] = _fallback_summary(article)

        summarized += 1

    logger.info("Summarized %d articles", summarized)
    return articles
