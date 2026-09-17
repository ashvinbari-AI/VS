"""
The ONLY file in this package that reaches into backend/. Every evaluator
imports the production code through here rather than reimplementing it --
this evaluation system tests the real app.analytics/app.ingestion/app.nlp
modules, not a parallel copy of their logic (master-prompt rule: "the
evaluation system must test the production system, not modify the
production system to make the tests pass").

Run evaluation with the backend's own virtualenv interpreter so pandas/
pyarrow/pydantic are already present -- no separate evaluation venv:

    backend\\.venv\\Scripts\\python.exe -m evaluation.run

This module makes `backend/` importable (as `app`) regardless of the
current working directory, without installing the backend package or
touching its own code.
"""

from __future__ import annotations

import sys
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = EVAL_ROOT.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def load_production_modules():
    """Import and return the actual production modules under evaluation,
    as a namespace-like object. Imported lazily (not at module load time)
    so that importing backend_bridge itself never requires the backend's
    dependencies to be installed -- only calling this does."""
    from app.analytics import comparison as comparison_engine
    from app.analytics import engine as analytics_engine
    from app.ingestion import dedupe, normalize
    from app.nlp import categories as nlp_categories
    from app.storage import data_source, parquet_store

    return {
        "analytics_engine": analytics_engine,
        "comparison_engine": comparison_engine,
        "dedupe": dedupe,
        "normalize": normalize,
        "nlp_categories": nlp_categories,
        "data_source": data_source,
        "parquet_store": parquet_store,
    }
