"""
Phase E: AI features must degrade visibly. When no LLM key is configured the
functions return ai_available=False with an honest "not configured" message —
distinct from a data-absent or request-failed state.
"""
import pandas as pd

import llm_analysis


def test_sentiment_not_configured(monkeypatch):
    monkeypatch.setattr(llm_analysis, "_has_any_llm", lambda: False)
    r = llm_analysis.analyze_news_sentiment(["Some headline"], "MRNA")
    assert r["ai_generated"] is False
    assert r["ai_available"] is False
    assert "not configured" in r["interpretation"].lower()


def test_pipeline_summary_not_configured(monkeypatch):
    monkeypatch.setattr(llm_analysis, "_has_any_llm", lambda: False)
    df = pd.DataFrame([{"title": "T", "phase": "Phase 2", "status": "RECRUITING"}])
    r = llm_analysis.summarize_pipeline(df, "Moderna")
    assert r["ai_generated"] is False
    assert r["ai_available"] is False
    assert "not configured" in r["summary"].lower()


def test_research_not_configured(monkeypatch):
    monkeypatch.setattr(llm_analysis, "_has_any_llm", lambda: False)
    r = llm_analysis.research_full_pipeline("MRNA", "Moderna")
    assert r["ai_generated"] is False
    assert r["ai_available"] is False
    assert r["programs"] == []
    assert "not configured" in r["pipeline_summary"].lower()
