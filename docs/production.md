# Production and deployment

This describes completed `production-100k-v1`. Earlier single-worker notes describe historical pilots.

All 660,622 six-field rows were hashed/profiled using supplied checker helpers.
Seed `spotify-100k-planning-v1` ranks SHA-256(seed + "|" + original ID); the smallest
100,000 nonempty IDs form the selection. Records retain all six source strings
and instructor-compatible hashes. There are 78,288 distinct texts and 21,712 aliases.

Sixteen threads call the provider from a persistent SQLite queue after a real
single-request probe and process exit/restart. Each worker has its own SQLite
connection. Claims, reservations and validated responses survive restart. Local
rate limits conservatively use 600 requests/minute and 600,000 tokens/minute.
Prompts are versioned by content hashes. Models have no tools or credentials.

Enrichment uses Responses, batches of 20. Independent GPT Decisions uses batches
of ten, up to eight workers and seed `spotify-100k-verification-v2-5pct`.
Every question names its original ID; the verifier sees text and rubric only.
Its five sentiment levels define a score index from 0 to 4; fractional answers
are allowed. Code maps the score with index / 2 - 1 into the continuous -1 to +1
range. Sentiment MAE is reported; exact floating-score equality is not a useful
standalone quality measure.

Two batches exhausted their permitted invalid-output retry because one field
was refused on both attempts. Offline recovery requires exact question names,
order and answer types; it preserves nine complete rows per batch and two
partial rows separately. No replacement labels or extra attempts are inferred.
The original queue status remains `resolved_partial`, preserving the baseline.
A later explicitly authorized final attempt for those same two source IDs completed
both in one request. The reviewed verification artifact has all 5,000 complete
predictions and links to its supplemental run. Original failed calls and reports
remain unchanged; no fourth attempt or replacement source ID was allowed.

## Served application

Vercel hosts Next.js and route handlers. Neon Postgres stores a validated snapshot
of 100,000 reviews, 5,000 verification outcomes, 4,474 attempts, metadata and
analysis artifacts. Schema was tested on a child branch before applying it to a
new isolated production project. Existing unrelated database projects were untouched.

| Route | Behavior |
|---|---|
| `GET /api/health` | Database connectivity; no inference |
| `GET /api/summary` | Saved progress, aggregate ranking, claims, memo and quality |
| `GET /api/reviews` | Parameterized text/ID search, filters and pagination |
| `POST /api/import` | Server-secret authenticated, bounded, validated idempotent upload |

`DATABASE_URL` and `IMPORT_TOKEN` are server-only. No OpenAI key is on Vercel;
there is no endpoint that starts paid inference. Source reviews render as text.
Searches bind parameters and escape wildcard characters. Reads are public for
grading; writes require the import token.

The current deployment displays 5,000 complete verification predictions, zero
remaining partial answers, and the reserves for missing usage. The Method page
also displays the separate final-configuration human agreement of 74% topic,
86% intent and 72% severity. The served memo is the saved assistant-reviewed
revision; it acknowledges that the historical crash example was later fixed.
The original generated memo and original 4,998-complete baseline remain in the
public evidence. Live API verification checks the reviewed artifacts explicitly.

## Local dashboard

Dependencies are pinned in `dashboard-vercel/package-lock.json`; Node 24 is selected.

```sh
cd dashboard-vercel
npm ci
cp .env.example .env.local
# Set your own DATABASE_URL and IMPORT_TOKEN locally; never commit their values.
npm run typecheck
npm run build
npm run dev
```

Apply `db/001_schema.sql` to a fresh development database before upload. The
uploader reads its secret from hidden stdin, never command-line arguments.
The 200-record development-branch and live 100k checks are in `evals/dashboard/`.

The public package provides portable JSONL/CSV instead of the large operational
SQLite database. Original local state is preserved at `state/pipeline.sqlite3`;
the deployed snapshot persists in Postgres. Offline ranking and calculator replay
need neither database nor API credentials.
