# Ground truth

Every file in this folder starts as `[]` and **stays empty until a human
manually verifies real records and fills it in.** Nothing here is
auto-generated from scraped output — doing that would make the evaluation
grade the production system against itself, which proves nothing (see
`evaluation/README.md` §"Why ground truth is never auto-generated").

Every evaluator degrades to "not enough ground truth to evaluate this
module yet" when its file is empty — that's the correct, honest state for
a freshly-cloned copy of this evaluation system, not a bug.

## `posts_ground_truth.json`
One object per manually verified post.
```json
{
  "content_id": "ig_DdF4BgoG-jt",
  "person": "Devendra Fadnavis",
  "platform": "instagram",
  "content_type": "reel",
  "published_at": "2026-09-01T18:30:00+00:00",
  "likes": 10000,
  "comments": 500,
  "shares": null,
  "caption": "...",
  "hashtags": ["Farmers"],
  "mentions": [],
  "expected_narrative": "Infrastructure",
  "expected_sentiment": "Positive"
}
```
`content_id` must match the real `content_id` from `data/processed/content.parquet`
(or the raw `post_id` the scraper wrote) so the evaluator can join to production
output — a fabricated id can never match anything and will just show as "missing".

## `comments_ground_truth.json`
```json
{
  "comment_id": "ig_x_c1",
  "content_id": "ig_DdF4BgoG-jt",
  "comment_text": "...",
  "expected_sentiment": "Positive",
  "expected_theme": "Praise",
  "expected_issues": ["Roads", "Water"]
}
```

## `profiles_ground_truth.json`
```json
{ "person": "Devendra Fadnavis", "platform": "instagram", "run_id": "run_...",
  "expected_followers": 2900000, "expected_posts_scanned": 25 }
```

## `sentiment_ground_truth.json` / `narrative_ground_truth.json`
Same shape as the `expected_*` fields on posts/comments above, kept as their
own files when you want a sentiment- or narrative-only annotation pass:
```json
{ "record_id": "ig_DdF4BgoG-jt", "record_type": "post", "human_label": "Positive",
  "annotator": "your_name", "annotation_date": "2026-09-11", "notes": "" }
```

## `issues_ground_truth.json`
Multi-label — `human_issues` is a list, and may be empty:
```json
{ "record_id": "ig_x_c1", "record_type": "comment",
  "human_issues": ["Roads", "Water"], "annotator": "your_name",
  "annotation_date": "2026-09-11", "notes": "" }
```

## `comparison_ground_truth.json`
A controlled scenario with known-correct expected winners (spec §24):
```json
{ "scenario": "person_a_more_content", "person_a": {"total_content": 10, "average_likes": 10000},
  "person_b": {"total_content": 20, "average_likes": 8000},
  "expected_winner": {"total_content": "person_b", "average_likes": "person_a"} }
```

## `duplicate_pairs_ground_truth.json`
Manually labeled pairs, for the duplicate-detection evaluator (spec §10):
```json
{ "content_id_a": "ig_abc", "content_id_b": "ig_abc_reimport", "is_duplicate": true }
```

## What's deliberately *not* here: Geography

Spec §23 calls for a `geography_ground_truth.json` and a geography evaluator.
This app's Geography feature (and its `location` field) was removed from
the production system in this project earlier — there is nothing left to
evaluate. If Geography is reintroduced later, add
`geography_ground_truth.json` (same `record_id`/`human_location` shape as
above) and `evaluators/geography.py` then; adding them now would be
building an evaluator for a feature that doesn't exist.
