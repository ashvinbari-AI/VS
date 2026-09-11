"""app/nlp/local_sentiment.py -- the optional offline transformer tier.
Pipeline calls are mocked (no real download in tests); the routing and
label-normalization logic is what's under test here."""

from __future__ import annotations

from app.config import get_settings
from app.nlp import local_sentiment

_REAL_LOGS_DIR = get_settings().logs_dir


class _FakeSettings:
    def __init__(self, sentiment_model=None, marathi_sentiment_model=None):
        self.sentiment_model = sentiment_model
        self.marathi_sentiment_model = marathi_sentiment_model
        self.logs_dir = _REAL_LOGS_DIR


def test_not_configured_when_both_env_vars_unset(monkeypatch):
    monkeypatch.setattr(local_sentiment, "get_settings", lambda: _FakeSettings())
    assert local_sentiment.is_configured() is False
    assert local_sentiment.classify("anything") is None


def test_latin_text_routes_to_sentiment_model(monkeypatch):
    monkeypatch.setattr(local_sentiment, "get_settings", lambda: _FakeSettings(
        sentiment_model="fake/multilingual", marathi_sentiment_model="fake/marathi"))
    seen = {}

    def fake_pipeline(model_name):
        seen["model"] = model_name
        return lambda text, truncation: [[{"label": "positive", "score": 0.9},
                                           {"label": "neutral", "score": 0.07},
                                           {"label": "negative", "score": 0.03}]]

    monkeypatch.setattr(local_sentiment, "_get_pipeline", fake_pipeline)
    result = local_sentiment.classify("great work by the government")
    assert seen["model"] == "fake/multilingual"
    assert result == {"sentiment": "Positive", "confidence": 0.9, "model": "transformer:fake/multilingual"}


def test_devanagari_text_routes_to_marathi_model(monkeypatch):
    monkeypatch.setattr(local_sentiment, "get_settings", lambda: _FakeSettings(
        sentiment_model="fake/multilingual", marathi_sentiment_model="fake/marathi"))
    seen = {}

    def fake_pipeline(model_name):
        seen["model"] = model_name
        return lambda text, truncation: [[{"label": "Negative", "score": 0.95},
                                           {"label": "Neutral", "score": 0.03},
                                           {"label": "Positive", "score": 0.02}]]

    monkeypatch.setattr(local_sentiment, "_get_pipeline", fake_pipeline)
    result = local_sentiment.classify("हे अपयश आहे, लाज वाटते")
    assert seen["model"] == "fake/marathi"
    assert result["sentiment"] == "Negative"
    assert result["model"] == "transformer:fake/marathi"


def test_unrecognised_label_falls_back_to_none_not_a_guess(monkeypatch):
    """A model with no human-readable id2label (bare LABEL_0/1/2) must not
    have its class order guessed -- that would be exactly the kind of
    invented value this codebase never allows."""
    monkeypatch.setattr(local_sentiment, "get_settings", lambda: _FakeSettings(
        sentiment_model="fake/opaque"))
    monkeypatch.setattr(local_sentiment, "_get_pipeline",
                         lambda model_name: (lambda text, truncation: [[{"label": "LABEL_0", "score": 0.99}]]))
    assert local_sentiment.classify("some text") is None


def test_pipeline_unavailable_returns_none(monkeypatch):
    """Missing package / model load failure -- _get_pipeline's own contract
    is to return None, and classify() must not crash on that."""
    monkeypatch.setattr(local_sentiment, "get_settings", lambda: _FakeSettings(
        sentiment_model="fake/model"))
    monkeypatch.setattr(local_sentiment, "_get_pipeline", lambda model_name: None)
    assert local_sentiment.classify("some text") is None


def test_pipeline_exception_is_caught(monkeypatch):
    monkeypatch.setattr(local_sentiment, "get_settings", lambda: _FakeSettings(
        sentiment_model="fake/model"))

    def raising_pipe(text, truncation):
        raise RuntimeError("boom")

    monkeypatch.setattr(local_sentiment, "_get_pipeline", lambda model_name: raising_pipe)
    assert local_sentiment.classify("some text") is None
