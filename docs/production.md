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
Its five sentiment levels map to -1, -0.5, 0, 0.5, 1. Exact sentiment agreement
with a continuous enrichment score is not a useful standalone quality measure.

Two batches exhausted their permitted invalid-output retry because one field
was refused on both attempts. Offline recovery requires exact question names,
order and answer types; it preserves nine complete rows per batch and two
partial rows separately. No replacement labels or extra attempts are inferred.
Queue status is `resolved_partial`. Complete-prediction metrics use 4,998 rows.

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

The deployed version displays 5,000 verification outcomes. The public summary
also returns `quality.complete_prediction_count=4998`, `quality.refusal_count=2`
and cost reservation metadata. Later local UI edits place these caveats beside
the metric tiles. Their redeploy was declined, so the existing deployment was
preserved. README and saved reports explicitly disclose both caveats. This
source/deployment difference does not change saved results, ranking or memo.

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
