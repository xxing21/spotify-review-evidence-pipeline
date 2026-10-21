# 500-review checkpoint: inspected limitations

The run completed all 500 original IDs with valid schemas and literal source
quotes. There were no new failed API attempts. The 100 earlier classifications
were reused under identical settings; 379 new distinct-text classifications and
21 exact-text aliases produced 400 additional completed original IDs.

Independent verification sampled 100 source IDs without seeing the first answer.
There were 18 topic/intent/severity disagreements and 53 differences in any field.
This is repeatability evidence, not an estimate of labeling accuracy. Same-model
verification can share errors; the nested 100- and 500-review samples are not
independent experiments. The human golden evaluation remains pending.

The ranking now places usability first, playback second and billing third. The
AI memo's numbers and cited IDs match the saved 500-review calculations. Its
recommendation is still provisional: the leading usability examples explicitly
mention paying for Premium to unlock controls. Under the shared taxonomy,
explicitly Premium-only controls belong to billing. This topic-boundary problem
was already identified in the 100-review development set and persists because
classification instructions were intentionally unchanged for this extension.

Examples requiring human inspection:

- `11ad400f-4487-4dfa-a9da-c8d624f4f107`: skip/selection limits explicitly tied to
  Premium, currently grouped under usability.
- `50626053-301c-42fa-91aa-2f88aef82e64`: mixes ad interruptions with paying to play
  songs in order; the primary topic requires the highest-severity/tie-break rubric.
- `16929558-ce1e-4b87-8738-a1de3f557f66`: paid subscription with music access still
  blocked is correctly supported as a billing/entitlement complaint in the traced
  example, rather than an inference from merely mentioning a paid plan.

105 records have needs_review=true; none were discarded from business aggregates.
The full list of model disagreements and both answers is saved beside this file.
Human quote support, entity usefulness, language interpretation and the final
argument still need review. This report is assistant inspection, not human labels.

No 10,000-review checkpoint, full-corpus run or deployment has been started.
