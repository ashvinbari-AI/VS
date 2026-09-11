"""Regression test for the RLock deadlock found while validating this
project against real scraped comments (put_many() calling save_cache(),
which re-acquired the same lock) -- see app/nlp/cache.py."""

from __future__ import annotations

import threading

from app.nlp import cache as nlp_cache


def test_put_many_does_not_deadlock(tmp_path, monkeypatch):
    fake_path = tmp_path / "nlp_cache.json"
    monkeypatch.setattr(nlp_cache, "_path", lambda: fake_path)

    done = threading.Event()

    def _work():
        nlp_cache.put_many({"content_1": {"narrative": "Development"}})
        done.set()

    t = threading.Thread(target=_work)
    t.start()
    t.join(timeout=5)
    assert done.is_set(), "put_many() deadlocked (RLock regression)"


def test_cached_result_is_reused(tmp_path, monkeypatch):
    fake_path = tmp_path / "nlp_cache.json"
    monkeypatch.setattr(nlp_cache, "_path", lambda: fake_path)

    nlp_cache.put_many({"c1": {"narrative": "Farmers", "model": "rule_based_v1"}})
    cached = nlp_cache.get_cached("c1")
    assert cached is not None
    assert cached["narrative"] == "Farmers"
    assert nlp_cache.get_cached("missing") is None
