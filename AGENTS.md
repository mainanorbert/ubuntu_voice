# PeaceTech Codex Instructions

## Setup
- This workspace has `backend/` for FastAPI and `frontend/` for Next.js.
- Backend install: `cd backend && uv sync`.
- Backend dev server: `cd backend && uv run python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000`.
- Frontend install: `cd frontend && npm ci`.
- Frontend dev server: `cd frontend && npm run dev`.
- Never print, commit, summarize, or expose values from `.env` or `.env.local`.

## Testing
- Backend verification: `cd backend && uv run pytest -q`.
- Frontend verification: `cd frontend && npm run lint && npm run typecheck && npm run build`.
- For multi-file changes, run the smallest relevant checks first, then the full checks above.

## Style
- Product direction: privacy-first, low-bandwidth RAG support for conflict-affected communities in Africa.
- Prioritize displaced populations, women, youth, civil society users, and peacebuilding organizations.
- Keep responses grounded in retrieved documents; cite sources when the UI/API surface supports it.
- Do not present AI output as legal, medical, security, or emergency advice.
- Minimize personal data collection and avoid storing sensitive conflict-related user details unless explicitly required.
- Include docstring for functions or clasess that perform medium to complex functionalities
- For simple functions include a 1 line comment

## Review
- For broad changes, plan first and wait for approval before editing.
- Keep diffs scoped to the requested task; do not perform unrelated rebrands or refactors.
- Show the final diff summary and list verification commands run.

## Logging
- Log all failed database connections at the `CRITICAL` level.
- Do not include PII (emails, passwords) in any logs.
- Do not log raw user prompts, chat transcripts, uploaded documents, or retrieved document excerpts.
- Include request IDs or correlation IDs in error logs when available, without adding user-identifying details.
- Use structured log fields for severity, component, and operation so incidents can be traced without exposing sensitive data.


- Always use the OpenAI developer documentation MCP
server if you need to work with the OpenAI API,
ChatGPT Apps SDK, Codex, or related docs without
me having to explicitly ask.


## Repo Map
- `backend/src/main.py` and `backend/main.py`: FastAPI entrypoints.
- `backend/src/api/v1/routers/`: API route handlers.
- `backend/src/api/v1/schemas/`: request/response schemas.
- `backend/src/core/`: config, auth, database, logging, shared dependencies.
- `backend/src/services/`: RAG, ingestion, embeddings, storage, WhatsApp, guardrails, monitoring.
- `backend/alembic/`: database migrations.
- `backend/tests/`: backend test suite.
- `frontend/app/`: Next.js routes, pages, and API route proxies.
- `frontend/components/`: shared React/UI components.
- `frontend/lib/`: frontend utilities and server helpers.
- `frontend/public/`: static assets.


## Definition Of Done
- Changes are scoped to the requested task.
- Relevant backend tests pass: `cd backend && uv run pytest -q`.
- Relevant frontend checks pass: `cd frontend && npm run lint && npm run typecheck && npm run build`.
- Privacy checks pass: no raw prompts, transcripts, retrieved excerpts, credentials, phone numbers, emails, or sensitive conflict details are logged.
- User-facing RAG answers remain grounded in retrieved documents and cite sources where supported.
- Final handoff includes changed files, verification commands run, and any known risks or skipped checks.

## Extra Guardrails
- Do not edit unrelated files or perform broad refactors without approval.
- Do not add new personal data collection unless explicitly required.
- Do not expose `.env`, `.env.local`, API keys, tokens, phone numbers, or email addresses.
- Do not log raw user content, uploaded document text, retrieved chunks, or provider payloads.