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