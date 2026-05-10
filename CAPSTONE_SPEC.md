# Capstone spec - Community Peace Support AI

## Problem statement
Conflict-affected communities across Africa, especially in the Sahel Region, Democratic Republic of the Congo, Sudan, and Mozambique, struggle to access trusted, localized, and actionable support information because knowledge systems are fragmented, languages vary, connectivity is limited, and people may fear exposure when engaging formal institutions. This project provides a privacy-first, low-bandwidth RAG platform that turns curated peacebuilding and civil society knowledge into real-time community support through community-defined AI agents.

## What success looks like
- [ ] A user can select a community-defined agent such as Sahel Peace Mediator, DRC Women Peacebuilders, or Resource Rights Advisor.
- [ ] An admin can upload curated local documents and attach them to the correct agent/corpus.
- [ ] A user can ask a question and receive a concise, localized answer grounded in retrieved documents.
- [] Supports voice chat, user can turn on voice chat instead of text chat
- Support multiple languages (when user choses fluent language, the assistant must answer only based on this language)
- [ ] Answers include source grounding or a clear "not enough trusted information" response when retrieval is weak.
- [ ] The platform avoids unnecessary personal data collection and does not expose secrets or sensitive user content in logs.
- [ ] Backend and frontend verification commands pass before submission.

## Architecture sketch
- Next.js frontend for low-bandwidth chat, agent selection, document upload, and monitoring views.
- FastAPI backend for auth, agent configuration, document ingestion, chunking, embeddings, RAG retrieval, guardrails, and chat responses.
- PostgreSQL with pgvector for document chunks and similarity search.
- Storage layer for uploaded documents, using current local/Supabase-compatible service patterns.
- Agent profile layer that maps each agent to region, languages, audience, safety scope, and document corpus.

## Tech stack
- Backend: Python 3.12, FastAPI, SQLAlchemy, Pydantic Settings, pgvector, pypdf, tiktoken, OpenAI/OpenRouter-compatible clients.
- Frontend: Next.js 16, React 19, TypeScript, Clerk, Tailwind, shadcn/radix, lucide-react.
- Database: PostgreSQL with pgvector.
- External services: Clerk, OpenRouter/OpenAI-compatible API, optional Supabase storage.

## Task list
1. [ ] Create Codex instruction files and this capstone spec.
2. [ ] Define agent profile data model for name, region, languages, audience, safety scope, and corpus.
3. [ ] Update document ingestion so documents are assigned to an agent/corpus with useful metadata.
4. [ ] Update RAG retrieval so chat queries search only the selected agent's trusted corpus.
5. [ ] Build frontend agent selector and low-bandwidth chat flow.
6. [ ] Add source-grounded answer display and unsupported-question fallback.
7. [ ] Add privacy and guardrail tests for sensitive data, weak retrieval, and unsafe advice.
8. [ ] Update monitoring to show usage, retrieval quality, and guardrail events.

## Out of scope for MVP
- Real-time emergency response dispatch.
- Legal, medical, or security advice presented as authoritative guidance.
- Automatic fine-tuning on user conversations.
- Offline-first mobile sync.
- Production deployment to field organizations without human review.

## Open questions
- Which country/community and language should be the first MVP target?
- What curated documents are approved for ingestion?
- Which users need admin access versus anonymous or low-friction community access?
- What exact safety policy should govern conflict, gender-based violence, and rights-related questions?
- Should the first demo use existing customer-support UI structure or a full rebrand in one pass?
