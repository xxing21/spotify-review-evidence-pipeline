# Approved 100k plan: 5% independent verification

Planned only. No 100k paid execution has started. All 100,000 original IDs would still be classified; 5,000 would receive independent model checks.

The user approved reducing future verification from 20% to 5%. The assignment requires a declared independent random sample without a minimum percentage. Completed pilots retain their original 20% samples, prompts, labels, calls and timings.

Estimates combine measured 16-worker/20-review Luna enrichment with measured ten-review GPT Decisions verification batches. The proposed 100k inputs contain 78,288 distinct texts and 21,712 exact-text duplicates. Sustained rate limits are included; this is not a timed 100k run.

| Scenario | Estimated minutes | Estimated API cost | Including existing work/reservations |
|---|---:|---:|---:|
| base_exact_reuse | 72.6 | US$4.12 | US$4.83 |
| conservative_exact_reuse | 119.6 | US$4.53 | US$5.25 |
| base_no_reuse | 89.9 | US$5.09 | US$5.81 |
| conservative_no_reuse | 148.1 | US$5.60 | US$6.32 |

The conservative case includes at least 10% retries and 50% slower throughput. Local/hosting costs and unmeasured larger-run overhead are separate. Under two hours remains a target rather than a guarantee.

Keep the 50 human labels/evaluation, planted-error and injection tests, and disagreement inspection. Lower verification checks fewer individual records and does not establish higher label accuracy.

The US$10 shared API cap includes all prior spend and unresolved reservations. Full-run execution mode remains to be implemented.

Regenerate without a key or model calls:

```sh
python3 scripts/refresh_100k_plan.py
```
