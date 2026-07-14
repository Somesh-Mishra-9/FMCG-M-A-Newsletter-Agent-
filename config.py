"""
Configuration for the FMCG M&A Newsletter Agent.

Contains entity lists, keyword dictionaries, source credibility tiers,
and pipeline thresholds used across all modules.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── API Keys ───────────────────────────────────────────────────────────────
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ─── FMCG Companies & Brands ────────────────────────────────────────────────
# Major FMCG players — used for keyword matching during ingestion & relevance
FMCG_ENTITIES = [
    # Indian majors
    "Hindustan Unilever", "HUL", "ITC Limited", "ITC",
    "Nestlé India", "Nestle India", "Britannia Industries", "Britannia",
    "Dabur India", "Dabur", "Marico", "Godrej Consumer",
    "Godrej Consumer Products", "GCPL",
    "Procter & Gamble India", "P&G India",
    "Colgate-Palmolive India", "Colgate India",
    "Emami", "Patanjali", "Tata Consumer Products", "Tata Consumer",
    "Adani Wilmar", "Zydus Wellness",
    # Global majors (often involved in India/emerging market deals)
    "Unilever", "Procter & Gamble", "P&G",
    "Nestlé", "Nestle", "PepsiCo", "Coca-Cola",
    "Mondelez", "Danone", "Reckitt Benckiser", "Reckitt",
    "Kraft Heinz", "General Mills", "Kellogg", "Kellanova",
    "Mars", "Ferrero", "Henkel", "Church & Dwight",
    "Colgate-Palmolive", "Edgewell", "Spectrum Brands",
    "Hershey", "Campbell Soup", "Conagra Brands",
    "Smucker", "Treehouse Foods", "Revlon",
    "Estée Lauder", "L'Oréal", "Beiersdorf",
]

# ─── Deal-type Keywords ─────────────────────────────────────────────────────
DEAL_KEYWORDS = [
    "acquisition", "acquire", "acquired", "acquiring",
    "merger", "merge", "merged", "merging",
    "stake", "stake sale", "stake purchase",
    "buyout", "buy out", "takeover", "take over",
    "investment", "invest", "invested",
    "funding", "fund raise", "fundraise", "fundraising",
    "divestment", "divest", "divested", "divestiture",
    "IPO", "initial public offering",
    "joint venture", "JV", "partnership",
    "deal", "transaction", "bid", "offer",
    "M&A", "mergers and acquisitions",
    "private equity", "PE deal", "venture capital", "VC funding",
]

# Generic sector terms — supplement entity matching
FMCG_SECTOR_TERMS = [
    "FMCG", "fast-moving consumer goods", "consumer goods",
    "consumer products", "packaged foods", "packaged goods",
    "consumer staples", "personal care", "home care",
    "food and beverage", "F&B", "CPG",
    "consumer packaged goods", "retail brands",
]

# ─── Source Credibility Tiers ────────────────────────────────────────────────
# Tier 1 = major financial/business press, Tier 2 = reputable industry/tech,
# Tier 3 = everything else (unknown or niche sources)
SOURCE_CREDIBILITY = {
    # Tier 1 — Major business & financial publications
    "reuters.com": 1,
    "bloomberg.com": 1,
    "economictimes.indiatimes.com": 1,
    "livemint.com": 1,
    "business-standard.com": 1,
    "ft.com": 1,
    "wsj.com": 1,
    "cnbc.com": 1,
    "bbc.com": 1,
    "bbc.co.uk": 1,
    "theguardian.com": 1,
    "ndtv.com": 1,
    "hindustantimes.com": 1,
    "thehindu.com": 1,

    # Tier 2 — Reputable business/industry sources
    "moneycontrol.com": 2,
    "yourstory.com": 2,
    "inc42.com": 2,
    "vccircle.com": 2,
    "entrackr.com": 2,
    "techcrunch.com": 2,
    "forbes.com": 2,
    "fortune.com": 2,
    "investopedia.com": 2,
    "thehindubusinessline.com": 2,
    "financialexpress.com": 2,
    "firstpost.com": 2,
    "news18.com": 2,
    "zeebiz.com": 2,
    "outlookindia.com": 2,
    "retail.economictimes.indiatimes.com": 2,
}

# Tier score mapping
CREDIBILITY_SCORES = {1: 1.0, 2: 0.7, 3: 0.4}

DEFAULT_CREDIBILITY_TIER = 3

# ─── RSS Feeds ───────────────────────────────────────────────────────────────
RSS_FEEDS = [
    {
        "name": "ET Retail",
        "url": "https://retail.economictimes.indiatimes.com/rss/topstories",
        "category": "retail",
    },
    {
        "name": "Mint Companies",
        "url": "https://www.livemint.com/rss/companies",
        "category": "business",
    },
    {
        "name": "Business Standard Companies",
        "url": "https://www.business-standard.com/rss/companies-702.rss",
        "category": "business",
    },
    {
        "name": "Moneycontrol M&A",
        "url": "https://www.moneycontrol.com/rss/business.xml",
        "category": "business",
    },
    {
        "name": "NDTV Profit",
        "url": "https://feeds.feedburner.com/ndtvprofit-latest",
        "category": "business",
    },
    {
        "name": "Economic Times Markets",
        "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "category": "markets",
    },
]

# ─── Pipeline Thresholds ────────────────────────────────────────────────────
FUZZY_DEDUP_THRESHOLD = 85          # rapidfuzz token_sort_ratio cutoff
SEMANTIC_DEDUP_THRESHOLD = 0.88     # cosine similarity cutoff
DEDUP_TIME_WINDOW_HOURS = 72        # only compare articles within this window
RELEVANCE_CONFIDENCE_MIN = 0.6      # LLM confidence below this → low_confidence
INGESTION_LOOKBACK_DAYS = 30        # how far back to fetch news

# ─── LLM Settings ───────────────────────────────────────────────────────────
LLM_MODEL = "llama-3.1-8b-instant"  # Groq model identifier
LLM_TEMPERATURE = 0.1               # low temperature for structured output
LLM_MAX_TOKENS = 512

# ─── Embedding Model ────────────────────────────────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
