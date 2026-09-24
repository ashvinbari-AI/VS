"""POST /api/analysis/run -- ingestion (raw JSONL -> Parquet) then, unless
skip_nlp, an NLP pass over new content/comments (spec section 47)."""

from __future__ import annotations

import math

from fastapi import APIRouter
from pydantic import BaseModel

from app.ingestion.ingest import run_ingestion
from app.jobs.manager import Job, create_job, run_job, set_status_message
from app.models.common import ApiResponse
from app.nlp.engine import analyze_comments_df, analyze_content_df
from app.storage.parquet_store import read_comments, read_content, write_comments, write_content

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _clean_records(df) -> list[dict]:
    """Parquet has no native "missing int": a None written through
    NormalizedContent/NormalizedComment.model_dump() comes back from
    read_content()/read_comments() as NaN once that column round-trips
    through pandas/pyarrow as float64 -- and a float64 column can't hold
    None, so `df.where(pd.notnull(df), None)` silently keeps the NaN right
    back. NaN then fails pydantic's finite_number check on the int|None
    fields (e.g. view_count) when the row is rebuilt into a model. Walking
    the plain dicts value-by-value is the only thing that actually clears
    it -- same pattern already used in routers/content.py."""
    records = df.to_dict(orient="records")
    for r in records:
        for k, v in r.items():
            if isinstance(v, float) and math.isnan(v):
                r[k] = None
    return records


class AnalysisRunRequest(BaseModel):
    skip_nlp: bool = False
    force_reanalyze: bool = False


@router.post("/run")
def run_analysis(payload: AnalysisRunRequest) -> ApiResponse:
    job = create_job("analysis")

    def _work(job: Job) -> dict:
        set_status_message(job, "Ingesting raw data...")
        ingest_result = run_ingestion()

        nlp_result = {"skipped": True}
        if not payload.skip_nlp:
            set_status_message(job, "Running NLP analysis on content...")
            content_df = read_content()
            content_df = analyze_content_df(content_df, force=payload.force_reanalyze)
            write_content_records = _clean_records(content_df)
            from app.models.content import NormalizedContent
            write_content([NormalizedContent(**{k: v for k, v in r.items()
                                                 if k in NormalizedContent.model_fields})
                            for r in write_content_records])

            set_status_message(job, "Running NLP analysis on comments...")
            comments_df = read_comments()
            comments_df = analyze_comments_df(comments_df, force=payload.force_reanalyze)
            from app.models.content import NormalizedComment
            write_comments([NormalizedComment(**{k: v for k, v in r.items()
                                                  if k in NormalizedComment.model_fields})
                             for r in _clean_records(comments_df)])
            nlp_result = {"skipped": False, "content_rows": len(content_df),
                          "comments_rows": len(comments_df)}

        return {"ingestion": ingest_result, "nlp": nlp_result}

    run_job(job, _work)
    return ApiResponse.ok({"job_id": job.id})
