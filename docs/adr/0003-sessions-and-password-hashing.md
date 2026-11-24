# ADR 0003: Cookie sessions for people, bearer tokens for CI

- Status: accepted
- Date: 2026-11-24

## Context

Two kinds of clients call the API: people in the browser and CI jobs uploading reports.
Sprint 1 had no login, so anyone who could reach the server could read every run.

## Decision

- **People** log in with email and password. Passwords are hashed with scrypt from Python's
  standard library (per-password random salt, constant-time comparison). Login sets a signed
  JWT in an `httpOnly`, `SameSite=Lax` cookie (`Secure` in production), valid for 7 days.
  JavaScript cannot read the cookie, which limits the damage of a cross-site scripting bug,
  and `SameSite=Lax` stops other sites from sending it with cross-site POST requests.
- **CI jobs** keep using per-project bearer tokens (`fr_<prefix>_<secret>`, stored as SHA-256
  hashes), now created and revoked by the project owner in the web app.
- Every project has an owner. Read endpoints return 404, not 403, for projects owned by
  someone else, so project names do not leak.

## Consequences

- No extra hashing dependency; scrypt is memory-hard and supported by the standard library.
- Sessions cannot be revoked one by one before they expire; changing the server secret logs
  everyone out. Acceptable for this scale; revisit if teams and roles are added.
- Rate limiting of login attempts is still missing and is part of the Sprint 4 security review.
