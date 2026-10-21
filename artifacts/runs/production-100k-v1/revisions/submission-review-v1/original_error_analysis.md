# Production verification: concrete disagreements

5,000 original IDs were sampled independently; 4,998 have complete predictions, two have explicit partial refusals. There are 1,680 complete cases with at least one topic/intent/severity disagreement. Topic agreement is 88.30%, intent 93.00%, severity 79.43%; severity MAE 0.2173, sentiment MAE 0.1163. This measures same-model-family consistency, not human accuracy. The five-level verifier sentiment scale differs from enrichment's continuous score; MAE is more meaningful than exact equality.

The following are saved comparisons, not new ground-truth judgments. No production labels were automatically replaced.

| Original ID | Original comment | Enrichment topic / intent / severity | Independent verification | Interpretation to inspect |
|---|---|---|---|---|
| 774f169a-9400-471a-8fd7-cb34e6c1a79b | “Exceptional service. Love that I can download music to play anywhere as I live in the country. Great recommendations and introduction to new music. No ads is my favorite thing. Oh and the best podcast going.” | downloads / praise / 1 | other / praise / 1 | Several praised features; primary-topic choice is ambiguous. |
| 1451bfd3-2b1d-40d0-a635-3090cb129154 | “I love this app it entertains me and each songs even have its own lyrics to look at and sing. I'm so happy I can downloaded it thank you so much 💗” | catalog / praise / 1 | other / praise / 1 | Specific lyrics praise versus generic app praise. |
| f9f1e333-7e2a-4c38-b4e6-e7371ed3b8cb | “GIVE US BASIC FEATURES TO A MUSIC APP YOU MORONS” | other / request / 1 | usability / complaint / 1 | Request/complaint boundary and unspecified feature. |
| 650f6437-42a5-4c51-8bd4-b1cc13bc802a | “Overall Spoti is good. Biggest beef is being asked to UPGRADE all the f'ng time. 2nd biggest beef is all the ads. If I was residing outside of CA and in a State or Country that actually cares about it's citizens I wouldn't have to deal with this BS!!” | billing / complaint / 2 | usability / complaint / 2 | Upgrade prompts/paywall versus ads/controls; competing topics. |
| 3ecb8c75-d0a9-48da-90ce-f0c36fbce2df | “No problem I feel better now” | other / praise / 1 | other / unclear / 1 | Little product-specific context. |
| 5e0a5433-989a-4e85-96e9-f9754964ae40 | “My Spotify erased all of my playlists and I wouldn't recommend it. I would recommend YouTube music. Much more reliable and it pauses and won't play music. It used to be a good app not anymore.” | downloads / complaint / 4 | downloads / complaint / 3 | Functional loss/data-loss severity boundary; several problems. |
| f6915da5-242c-43f2-9c08-4e20a9714924 | “Too lock mods” | usability / unclear / 1 | other / unclear / 1 | Short, ambiguous language should remain uncertain. |
| f3f48892-351e-4800-ac7c-2b80a14e9508 | “Bakwaas” | other / complaint / 2 | other / unclear / 1 | Language interpretation and generic criticism; human context would help. |

All quotes/entities are code-grounded source spans, so 100% verifier agreement on those fields is deterministic and not a semantic quality result. Further human checks should cover billing, access and downloads, which the original 50 human references did not cover, plus multilingual short texts, paywall-versus-ads cases and resolved updates.

## Refusals and real failures

- `a3480188-eba3-4f97-bcf5-280691f7ed43`: sentiment refused on both allowed attempts. Other raw answers retained; excluded from complete-prediction metrics.
- `537ae160-c12d-45c5-bc6a-f157c094e626`: topic refused on both allowed attempts. Other raw answers retained; excluded from complete-prediction metrics.
- Eighteen complete rows were recovered from those two raw response pairs without additional API calls. Exact question-name/type/order checks were required; no refused label was guessed. Original failed attempts remain failed.
- Enrichment: 7 invalid-output failures and 48 transient failures. The 48 requests with unavailable usage retain US$0.174263125 in reserves. The scoped checker therefore reports 96 missing usage fields; this is not a clean checker pass.
- All 100,000 enrichment records completed; no selected review is quarantined or pending. Synthetic provider failures, injection tests and planted errors live in separate diagnostic artifacts and do not enter business aggregates.
