# Annotation format

This documents the manual-labeling schema (spec section 6). The files in
`evaluation/ground_truth/` are where completed annotations actually live —
this page is the format spec for filling them in, and for a review-queue
workflow if you build one later (spec section 66 describes an optional
`evaluation/review_queue.json` for flagging questionable AI output for a
human to confirm/correct/mark-ambiguous; not built yet — see the top-level
`evaluation/README.md` for what's implemented so far vs. still planned).

## Per post
| field | meaning |
|---|---|
| `content_id` | must match the real id in `data/processed/content.parquet` |
| `platform` | `instagram` \| `facebook` |
| `content_type` | `post` \| `reel` \| `video` \| `photo` |
| `caption` | copied from the real post, for the annotator's reference |
| `human_narrative` | one of the categories in `backend/app/nlp/categories.py::DEFAULT_NARRATIVES` |
| `human_sentiment` | `Positive` \| `Neutral` \| `Negative` \| `Mixed/Unclear` |
| `human_topics` | free-text list, optional |
| `human_location` | only if the post carries an explicit, real location tag — never guessed |
| `human_issue` | list from `backend/app/nlp/categories.py::PUBLIC_ISSUES`, may be empty |
| `annotator` | your name/id |
| `annotation_date` | `YYYY-MM-DD` |
| `notes` | anything ambiguous about this call |

## Per comment
| field | meaning |
|---|---|
| `comment_id` | must match the real id in `data/processed/comments.parquet` |
| `content_id` | the post this comment is on |
| `comment_text` | copied from the real comment |
| `human_sentiment` / `human_theme` / `human_issue` / `human_location` | same rules as above |
| `annotator` / `annotation_date` / `notes` | same as above |

## Multiple annotators

Label the same batch of records with two different `annotator` values (two
separate rows per record, or two separate files) to compute **Cohen's
Kappa** — how consistently two humans agree, not a model-quality metric.
`evaluation/metrics/classification.py::cohens_kappa(rater_a_labels,
rater_b_labels)` is implemented and unit-tested; a dedicated CLI command
to run it over two annotator files end-to-end is not built yet (see
`evaluation/README.md`'s "Not yet built" list).
