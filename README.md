# Ubuntu Voice

Ubuntu Voice is a privacy-first, low-bandwidth RAG platform for community peace support. It helps conflict-affected communities, civil society groups, women, youth, and displaced populations access trusted local information through community-defined AI agents across web text chat, WhatsApp, SMS/text messaging, and private email workflows.

## Table of Contents

- [Project Problem](#project-problem)
- [Project Solution](#project-solution)
- [App Features](#app-features)
- [How It Works](#how-it-works)
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

## App Features

- **Community-defined AI agents:** Configure agents for specific communities, regions, languages, audiences, safety scopes, and trusted document collections.
- **Low-bandwidth web text chat:** Let users ask questions through a lightweight chat interface and receive concise answers grounded in the selected agent's documents.
- **WhatsApp support:** Receive and answer WhatsApp messages through a secure Twilio webhook, routed to the correct agent by the destination WhatsApp number.
- **SMS/text notifications:** Send short text-message updates through a secure messaging integration for approved community-support workflows.
- **Private email messaging:** Send sensitive email messages through Resend while protecting recipient details and message content from logs.
- **Document-grounded RAG:** Upload curated PDF documents, extract and chunk text, create embeddings, and answer only from trusted retrieved sources.
- **Language-aware responses:** Support selected-language answers for English, Swahili, French, Arabic, and Portuguese.
- **Incident statistics classifier:** Run a separate non-blocking classifier agent on incoming reports to detect recordable incident statistics by place and category without slowing chat responses.
- **Regional statistics dashboard:** Show per-agent incident counts by place, description, category, total count, and last update time.
- **Privacy and safety guardrails:** Avoid unnecessary personal data collection, block oversized prompts, audit risky outputs, and return a clear fallback when trusted context is insufficient.
- **Monitoring and usage tracking:** Track usage, model cost, retrieval quality, and guardrail events without logging raw prompts, transcripts, retrieved excerpts, or sensitive contact details.

## How It Works

### Text Chat

Users select a community-defined agent and preferred language in the web app, then ask a question in the low-bandwidth chat interface. The backend scopes retrieval to that agent's trusted document corpus, builds a concise grounded response, and returns either a sourced answer or a clear fallback when there is not enough trusted information.

### WhatsApp

Community members can message a configured WhatsApp number directly. Twilio sends the inbound message to the Ubuntu Voice webhook, the backend matches the destination number to the correct agent, runs the same tenant-scoped RAG pipeline used by web chat, and replies through WhatsApp without logging Twilio credentials or user phone numbers.

### SMS/Text Messaging

Approved workflows can send short SMS/text notifications through a secure messaging provider. These messages are intended for low-bandwidth outreach and updates, with logging protections that avoid exposing phone numbers, raw message bodies, or sensitive conflict-related details.

### Email

Ubuntu Voice can send private email messages with Resend for approved alert or support workflows. Email delivery is designed to protect recipient details and sensitive message content from logs while keeping communication tied to trusted agent and document workflows.

### Documents and Retrieval

Admins upload curated PDF documents for the correct agent or corpus. The backend stores the file, extracts text, splits it into chunks, creates embeddings, and stores searchable vectors in PostgreSQL with pgvector. During chat or messaging flows, the selected agent only retrieves from its own trusted corpus.

### Incident Statistics

When a web chat or WhatsApp prompt passes input guardrails, Ubuntu Voice queues a separate background classifier agent. The classifier returns strict JSON only, using the allowed categories `Rights Violations`, `Displacements`, `Casualties`, and `Severe Hunger`. The backend validates the JSON, sanitizes the description, normalizes the place, and upserts a per-agent `incident_statistics` row. Existing `(agent, place, type)` rows increment `total_count` by one report; new combinations start at one.

The statistics view reads only the signed-in user's agent rows and displays a compact regional table at `/statistics`.

## Tech Stack

- **Backend:** FastAPI, Python 3.12, SQLAlchemy, Pydantic Settings, pgvector, pypdf, tiktoken, OpenAI Agents SDK
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
|   |   |-- services/     # RAG, ingestion, incident statistics, storage, and app services
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
