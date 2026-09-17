# Golden dataset

**FINAL EVALUATION DATA.** Used only for the final, reported evaluation
run — never for tuning a prompt, a keyword list, or a threshold. If you
change anything in `backend/app/nlp/` because a result here looked wrong,
that's a legitimate finding to report, not a reason to edit this dataset
to match the new output.

Protected from prompt tuning means: don't loop "tweak prompt -> re-run
against golden -> tweak again" — do that loop against `datasets/tuning/`
instead, then check the final candidate against golden once.

Empty until you promote annotated records here from
`evaluation/ground_truth/` (or `datasets/tuning/`) with `golden_v1.0`-style
versioning (spec section 67) — e.g. `golden_posts.json`, `golden_comments.json`.
