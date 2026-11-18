# Survey Platform

A modern, professional survey platform. Built in phases so every feature is real, tested, and secure.

## Status

- **Phase 1 — Foundation** (this commit): folder structure, design system, minimal homepage, backend skeleton, initial database schema, configuration, documentation.
- Phase 2 — Visual frontend (auth pages, full homepage sections, dashboards).
- Phase 3 — Backend & database (models, migrations, auth, permissions).
- Phase 4 — Survey management & import.
- Phase 5 — Respondent experience.
- Phase 6 — Rewards & wallet.
- Phase 7 — Administration.
- Phase 8 — Testing, hardening, deployment, backups.

## Repository layout

- `frontend/` — static HTML, CSS, and vanilla JavaScript modules.
- `backend/` — FastAPI application, Alembic migrations, tests.
- `database/` — schema and seed SQL.
- `backups/` — backup policy and restoration notes (no real data).

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- A modern browser

## Local setup (backend)

1. Create a virtual environment:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate    # Windows: .venv\Scripts\activate
