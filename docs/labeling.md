# Human labeling and evaluation

Read the common rubric in `spotify_pipeline/prompts/labels.md` and the complete
course boundaries in `GRADING_CONTRACT.md` before labeling. The source template
is preserved unchanged. Start the blind terminal helper:

```sh
python3 -m spotify_pipeline label-golden
```

The helper displays original text, definitions and blank fields, never model
answers. It saves completed cases to `evals/golden_labels.json`. Enter `q` to
stop at any prompt, then rerun to continue. Edit your own saved case to correct
it; it must retain valid labels, exact quote substrings, and explicit ambiguity.
You must choose the human labels yourself; generated labels must not be presented
as human work.

After all 50 are labeled, explicitly classify the held-out texts and evaluate:

```sh
python3 -m spotify_pipeline evaluate --run-id pilot-10000-v3 --execute-paid --budget-usd 2
```

Only the six original source fields enter the source store and only ID/text enter
the model request. Human labels and notes are never added to prompts, issue
discovery, examples or routing thresholds. Golden outputs are stored in a separate
evaluation run and excluded from pilot aggregates. This command uses the same
global spending ledger; it may stop if the remaining budget is insufficient.

Offline evaluation against already saved predictions is also available:

```sh
python3 -m spotify_pipeline evaluate --run-id pilot-10000-v3
```

Report topic/intent agreement, exact severity agreement and severity MAE,
sentiment MAE (predeclared; no tuned tolerance), per-topic counts, topic confusion,
ambiguity and per-case/per-field differences. Missing/invalid predictions count
as incorrect in agreement, with valid-only MAE clearly identified.

Exact quote membership and entity substring membership are checked by code.
A human must still inspect whether quotes support the chosen labels and whether
entities make sense. `needs_review` is evaluated as a predicted flag, not proof
of correctness. Inspect the generated `evals/error_analysis.md` and fill in your
interpretation of failures. If golden results influence prompt revisions, change
the disclosure and add fresh held-out cases before final evaluation.

Independent verification samples original input IDs before considering enrichment
success and never sees enrichment predictions. Its report distinguishes
topic/intent/severity disagreements from differences in any field (including
quote wording). Same-model verification can have correlated errors.

In the v2 pilot, quotes and entities are filled deterministically by code, shared
by enrichment and verification. Their agreement is a consistency check, not an
independent semantic judgment. Human golden quotes may be shorter than whole-text
model records: exact-quote agreement can be low despite valid source membership.
Inspect supporting meaning rather than treating wording equality as correctness.

Completed reference review: see `evals/golden_results.md`. Offline evaluation automatically locates predictions matching the target run configuration after all 50 human labels are valid. Original human labels remain unchanged; disagreements require adjudication.
