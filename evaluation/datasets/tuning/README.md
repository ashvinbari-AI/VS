# Tuning dataset

**TUNING DATA — never mix with `datasets/golden/`.** Use this set while
iterating on a keyword list, a prompt, or a threshold: annotate here,
test against it as much as you like, and only check the final candidate
against the golden set once you're done. This is what prevents data
leakage (spec section 33): if the same records are used both to tune and
to report the final number, the reported number is inflated and no longer
trustworthy.

Empty until you add records here.
