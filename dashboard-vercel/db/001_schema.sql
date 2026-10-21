CREATE TABLE "artifacts" (
	"run_id" text NOT NULL,
	"name" text NOT NULL,
	"value" text NOT NULL,
	PRIMARY KEY("run_id", "name")
);
;
CREATE TABLE "attempts" (
	"run_id" text NOT NULL,
	"id" text NOT NULL,
	"value" text NOT NULL,
	PRIMARY KEY("run_id", "id")
);
;
CREATE TABLE "checks" (
	"run_id" text NOT NULL,
	"id" text NOT NULL,
	"value" text NOT NULL,
	PRIMARY KEY("run_id", "id")
);
;
CREATE TABLE "reviews" (
	"run_id" text NOT NULL,
	"id" text NOT NULL,
	"topic" text NOT NULL,
	"intent" text NOT NULL,
	"severity" integer NOT NULL,
	"sentiment" double precision NOT NULL,
	"body" text NOT NULL,
	"evidence" text NOT NULL,
	"needs_review" integer NOT NULL,
	"entities" text NOT NULL,
	"source_hash" text NOT NULL,
	"cache_origin" text,
	"source" text NOT NULL,
	PRIMARY KEY("run_id", "id")
);
;
CREATE INDEX "reviews_topic" ON "reviews" ("run_id","topic","severity");;
CREATE INDEX "reviews_intent" ON "reviews" ("run_id","intent");;
CREATE TABLE "runs" (
	"id" text PRIMARY KEY NOT NULL,
	"status" text NOT NULL,
	"target" integer NOT NULL,
	"updated_at" text NOT NULL,
	"metadata" text NOT NULL
);
