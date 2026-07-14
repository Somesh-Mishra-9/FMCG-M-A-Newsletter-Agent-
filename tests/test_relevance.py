"""Tests for the relevance filtering module."""

import pytest

from processing.relevance import _keyword_prefilter


def _make_article(title, raw_text=""):
    """Helper to create a test article."""
    return {
        "title": title,
        "raw_text": raw_text,
    }


class TestKeywordPrefilter:
    """Tests for the keyword-based pre-filter."""

    def test_fmcg_deal_detected(self):
        article = _make_article(
            "HUL completes acquisition of skincare startup",
            "Hindustan Unilever has completed the acquisition of a D2C brand."
        )
        assert _keyword_prefilter(article) is True

    def test_fmcg_no_deal_rejected(self):
        article = _make_article(
            "HUL launches new marketing campaign",
            "Hindustan Unilever announced a new advertising initiative."
        )
        assert _keyword_prefilter(article) is False

    def test_deal_no_fmcg_rejected(self):
        article = _make_article(
            "Tech startup raises $50M in Series B funding",
            "A SaaS platform has secured funding from venture capital."
        )
        assert _keyword_prefilter(article) is False

    def test_sector_term_with_deal(self):
        article = _make_article(
            "FMCG sector sees major acquisition wave",
            "Consumer goods companies are actively pursuing mergers."
        )
        assert _keyword_prefilter(article) is True

    def test_case_insensitive(self):
        article = _make_article(
            "itc acquires snack brand",
            "ITC Limited completed the ACQUISITION."
        )
        assert _keyword_prefilter(article) is True

    def test_empty_text_rejected(self):
        article = _make_article("", "")
        assert _keyword_prefilter(article) is False

    def test_global_fmcg_company(self):
        article = _make_article(
            "Unilever divests tea business in landmark deal",
            "Unilever has agreed to sell its tea division."
        )
        assert _keyword_prefilter(article) is True
