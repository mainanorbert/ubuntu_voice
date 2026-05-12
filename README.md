# Ubuntu Voice

Ubuntu Voice is a privacy-first, low-bandwidth RAG platform for community peace support. It helps conflict-affected communities, civil society groups, women, youth, and displaced populations access trusted local information through community-defined AI agents.

## Table of Contents

- [Project Problem](#project-problem)
- [Project Solution](#project-solution)
- [Tech Stack](#tech-stack)
- [Folder Structure](#folder-structure)
- [Installation](#installation)
- [Running the App](#running-the-app)
- [Verification](#verification)

## Project Problem

Conflict-affected communities across Africa often struggle to access trusted and localized support information. Knowledge is spread across disconnected documents and organizations, languages vary by community, connectivity can be limited, and people may avoid formal institutions because sharing sensitive details can create risk.

## Project Solution

Ubuntu Voice turns curated peacebuilding and civil society knowledge into grounded AI support. Users can choose a community-defined agent, ask questions in a low-bandwidth chat experience, and receive concise answers based on trusted uploaded documents. When the system does not have enough reliable information, it should say so instead of guessing.

The platform is designed to minimize personal data collection, avoid exposing sensitive conflict-related details in logs, and keep AI responses grounded in retrieved sources.

## Tech Stack

- **Backend:** FastAPI, Python 3.12, SQLAlchemy, Pydantic Settings, pgvector, pypdf, tiktoken
- **Frontend:** Next.js 16, React 19, TypeScript, Tailwind CSS, shadcn/radix, Clerk
- **Database:** PostgreSQL with pgvector
- **AI services:** OpenAI/OpenRouter-compatible clients
- **Storage:** Local or Supabase-compatible document storage patterns

## Folder Structure

```text
ubuntu_voice/
|-- backend/
|   |-- alembic/          # Database migrations
|   |-- docs/             # Backend architecture and design notes
|   |-- scripts/          # Backend utility scripts
|   |-- src/              # FastAPI application code
|   |   |-- api/          # API routes
|   |   |-- core/         # Core configuration and shared setup
|   |   |-- domain/       # Domain models and business rules
|   |   |-- models/       # Database models
|   |   |-- services/     # RAG, ingestion, storage, and app services
|   |   `-- workers/      # Background or async processing code
|   |-- storage/          # Local uploaded document storage
|   |-- tests/            # Backend test suite
|   |-- main.py           # FastAPI entrypoint
|   `-- pyproject.toml    # Python dependencies and project metadata
|-- frontend/
|   |-- app/              # Next.js app routes and pages
|   |-- components/       # Shared React components
|   |-- hooks/            # Shared React hooks
|   |-- lib/              # Frontend utilities and server helpers
|   |-- public/           # Static frontend assets
|   `-- package.json      # Frontend scripts and dependencies
|-- AGENTS.md             # Codex project instructions
|-- CAPSTONE_SPEC.md      # Product direction and MVP scope
`-- README.md             # Root project documentation
```

## Installation

### Backend

From the project root:

```bash
cd backend
uv sync
```

Create the required backend environment file from your local secret source. Do not commit `.env` values.

### Frontend

From the project root:

```bash
cd frontend
npm ci
```

Create the required frontend environment file from your local secret source. Do not commit `.env.local` values.

## Running the App

### Backend Development Server

```bash
cd backend
uv run python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend runs on `http://localhost:8000`.

### Frontend Development Server

```bash
cd frontend
npm run dev
```

The frontend runs on the local URL printed by Next.js, usually `http://localhost:3000`.

## Verification

Run backend tests:

```bash
cd backend
uv run pytest -q
```

Run frontend checks:

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```
