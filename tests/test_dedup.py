"""Tests for the de-duplication module."""

import pytest

from processing.dedup import dedup_exact, dedup_fuzzy, run_dedup


def _make_article(article_id, title, domain="test.com", published="2024-07-15T10:00:00Z"):
    """Helper to create a test article with required fields."""
    return {
        "id": article_id,
        "title": title,
        "url": f"https://{domain}/article/{article_id}",
        "source_domain": domain,
        "published_at": published,
        "raw_text": f"Sample text for {title}",
        "fetched_at": "2024-07-15T12:00:00Z",
        "source_api": "test",
    }


class TestExactDedup:
    """Tests for Layer 1: exact URL dedup."""

    def test_no_duplicates(self):
        articles = [
            _make_article("abc123", "Article One"),
            _make_article("def456", "Article Two"),
        ]
        result = dedup_exact(articles)
        kept = [a for a in result if a.get("pipeline_status") != "duplicate"]
        assert len(kept) == 2

    def test_removes_exact_duplicates(self):
        articles = [
            _make_article("abc123", "Article One", domain="reuters.com"),
            _make_article("abc123", "Article One Copy", domain="reuters.com"),
            _make_article("def456", "Article Two"),
        ]
        result = dedup_exact(articles)
        kept = [a for a in result if a.get("pipeline_status") != "duplicate"]
        assert len(kept) == 2

    def test_duplicate_marked_correctly(self):
        articles = [
            _make_article("abc123", "Original"),
            _make_article("abc123", "Duplicate"),
        ]
        result = dedup_exact(articles)
        dupes = [a for a in result if a.get("pipeline_status") == "duplicate"]
        assert len(dupes) == 1
        assert dupes[0]["duplicate_of"] == "abc123"


class TestFuzzyDedup:
    """Tests for Layer 2: fuzzy title matching."""

    def test_similar_titles_detected(self):
        articles = [
            _make_article("id1", "HUL acquires premium skincare brand for $500M"),
            _make_article("id2", "Hindustan Unilever acquires premium skincare brand for $500M"),
        ]
        result = dedup_fuzzy(articles)
        dupes = [a for a in result if a.get("pipeline_status") == "duplicate"]
        assert len(dupes) == 1

    def test_different_titles_kept(self):
        articles = [
            _make_article("id1", "HUL acquires premium skincare brand"),
            _make_article("id2", "ITC launches new biscuit product line"),
        ]
        result = dedup_fuzzy(articles)
        dupes = [a for a in result if a.get("pipeline_status") == "duplicate"]
        assert len(dupes) == 0

    def test_time_window_respected(self):
        articles = [
            _make_article("id1", "HUL acquires brand for $500M", published="2024-07-10T10:00:00Z"),
            _make_article("id2", "HUL acquires brand for $500M", published="2024-07-20T10:00:00Z"),
        ]
        result = dedup_fuzzy(articles)
        # Outside 72h window, so both should be kept
        dupes = [a for a in result if a.get("pipeline_status") == "duplicate"]
        assert len(dupes) == 0
