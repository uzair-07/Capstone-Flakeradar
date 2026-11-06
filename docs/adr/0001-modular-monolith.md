# ADR 0001: One API service and one worker (modular monolith)

- Status: accepted
- Date: 2026-11-05

## Context

FlakeRadar is built by one developer in about eight weeks and runs on a single server.
It has clear functional areas (ingestion, analytics, quarantine, accounts) but low traffic.

## Decision

Build one FastAPI application with internal modules (`app/ingest`, `app/runs`,
`app/projects`, later `app/auth` and `app/analytics`) plus one background worker process
running the same codebase. Modules talk through function calls and share one PostgreSQL
database.

## Consequences

- One deployable image, one set of migrations, simple local setup (`docker compose up`).
- Module boundaries are kept by convention and code review rather than by the network.
- If one area ever needs to scale separately, its module can be split out later.
