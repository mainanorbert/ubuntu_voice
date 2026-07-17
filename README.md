# Ubuntu Voice

Ubuntu Voice is a privacy-first, low-bandwidth RAG platform for community peace support. It helps conflict-affected communities, civil society groups, women, youth, and displaced populations access trusted local information through community-defined AI agents across web text chat, WhatsApp, SMS/text messaging, and private email workflows.

## Demo Links

- [Evaluation demo](https://www.awesomescreenshot.com/video/53310423?key=ca040dc0ce523077c0dd6cd103060e76)
- [Project functional features demo](https://www.awesomescreenshot.com/video/52685415?key=9ffcc28ae89115643f739778fab83759)

## Table of Contents

- [Project Problem](#project-problem)
- [Project Solution](#project-solution)
- [App Features](#app-features)
- [How It Works](#how-it-works)
- [Dashboard And Monitoring](#dashboard-and-monitoring)
- [Evaluation Workflow](#evaluation-workflow)
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
- **Operator dashboard:** A signed-in dashboard gives operators a single workspace for account details, usage monitoring, guardrail review, and independent RAG evaluations.

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

## Dashboard And Monitoring

Signed-in operators can open `/dashboard` from the home page. The dashboard is the monitoring workspace for account and quality operations.

### Dashboard overview

- **`/dashboard`:** Shows the signed-in operator profile, email, and account creation date.
- **`/usage`:** Shows cumulative spend, tracked users, request volume, and token totals. The page aggregates prompt tokens, completion tokens, total tokens, request count, and USD cost per user.
- **`/guardrails`:** Shows recent blocked or monitored safety events with event type, action taken, matched rules, token count, and truncated prompt/response audit metadata.
- **`/evaluations`:** Lets the operator build a test dataset per agent and run independent RAG evaluations against that dataset.

## Evaluation Workflow

Ubuntu Voice evaluates one agent at a time. Each agent has its own evaluation dataset and latest retained run.

### How evaluation is done

1. Open `/evaluations`.
2. Select the target agent.
3. Add test items to that agent's dataset. Each item has:
   - a **question**
   - a **reference answer**
4. Click **Run evaluation**.
5. The backend runs the same RAG pipeline used by the product for each question, including retrieval against that agent's uploaded documents.
6. For every question, Ubuntu Voice stores:
   - the generated answer
   - the retrieved source file names and similarity scores
   - pass/fail grades with explanations
7. The latest run remains visible in the dashboard for review.

### Evaluation criteria

Each result is graded independently across four criteria:

- **Correctness:** Does the generated answer agree with the reference answer?
- **Relevance:** Does the generated answer directly answer the question?
- **Groundedness:** Is the generated answer supported by the retrieved document facts, without unsupported claims?
- **Retrieval relevance:** Did the retrieval step bring back facts that are relevant to the question?

### How users should build evaluation questions

Users create their own evaluation dataset from the knowledge they uploaded for an agent. A good evaluation item is based on information that should already exist in the agent's trusted documents.

For each question:

1. Read the uploaded source documents for that agent.
2. Write a realistic user question that the agent should be able to answer from those documents.
3. Write a concise reference answer grounded in the same documents.
4. Add the pair to the test dataset in `/evaluations`.
5. Re-run the evaluation after document updates, prompt changes, retrieval tuning, or guardrail changes.

### Dataset limits and operating notes

- Each agent can store up to **50 evaluation questions**.
- Dataset edits are blocked while an evaluation run is active.
- The dashboard keeps the **latest retained run** for each agent.
- Evaluation quality depends on the quality of the uploaded documents and the quality of the reference answers written by the user.

### Sample dataset file

A starter sample is included at the project root in evaluation_dataset_samples.md

Use it as follows:

1. Review the sample structure.
2. Copy one sample question and its reference answer into the `/evaluations` dataset form for the matching agent.
3. Replace placeholder contact details with the exact values from your own verified source documents where needed.
4. Add more questions that reflect the documents you uploaded for that agent.
5. Run the evaluation and review which criteria pass or fail.

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
|-- evaluation_dataset_samples.md  # Example evaluation questions and reference answers
`-- README.md             # Root project documentation
```

## Installation

### Backend

From the project root:

```bash
cd backend
uv sync
```

Create the backend environment file from the example at `backend/.env.example`.

From the project root:

```bash
cp backend/.env.example backend/.env
```

Then open `backend/.env`, replace the placeholder values with your real credentials and service URLs, and keep that file out of version control. The example file lives at `backend/.env.example`.

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
