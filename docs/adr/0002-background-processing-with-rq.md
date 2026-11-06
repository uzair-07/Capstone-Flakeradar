# ADR 0002: Parse uploads in the background with Redis + RQ

- Status: accepted
- Date: 2026-11-05

## Context

CI jobs upload JUnit XML reports that can contain thousands of test cases. Parsing and
storing them inside the HTTP request would make CI wait and would let one large report slow
the API for everyone.

## Decision

The API stores the raw file, records an `uploads` row and returns `202 Accepted` at once.
A job on a Redis-backed RQ queue parses the file and writes the results. Jobs are idempotent
(an upload already marked `done` is skipped), use the upload ID as the job ID so the same
upload is never queued twice, and retry up to three times on unexpected errors. Invalid
reports fail immediately with a readable reason instead of retrying.

Alternatives: Celery (more configuration than needed), Kafka (far beyond this scale), and
FastAPI background tasks (lost if the API process restarts).

## Consequences

- Uploads are fast and the API stays responsive.
- Redis becomes a required service; `/readyz` reports when it is unreachable.
- Clients that need the result poll `GET /api/v1/uploads/{id}` (the uploader's `--wait`).
