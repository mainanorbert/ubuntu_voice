"""OpenAI Agents SDK RAG pipeline for tenant-scoped support.

Architecture
------------
Phase 1 - Query preparation:
    A small model call reads recent history and the current user message. It
    decides whether trusted document retrieval is needed, and rewrites only
    retrieval-worthy questions into a short, focused search query.

Phase 2 - Retrieval and answer:
    Retrieval runs only when the query-preparation prompt says it is needed.
    The answer model receives the current question, recent history, retrieval
    status, and trusted excerpts when available. The system prompt handles
    greetings, general questions, conflict reports, weak retrieval, and grounded
    answers without hardcoded response shortcuts.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from agents import Agent, OpenAIChatCompletionsModel, Runner, trace
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from src.services.cost_monitoring import (
    UsageCharge,
    fetch_openrouter_generation_charges,
    usage_charge_from_openrouter_usage,
)
from src.services.rag_retrieval import (
    build_context_from_chunks,
    embed_query,
    retrieve_chunks_from_db,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RagEvaluationOutput:
    """Detailed RAG output retained in memory for independent evaluation."""

    answer: str
    grounded: bool
    documents: list[dict]
    usage_charges: list[UsageCharge]

_QUERY_REWRITE_PROMPT = """
You are the retrieval-query planner for {company_name}. Decide whether the
latest user message needs trusted knowledge-base retrieval and, if so, write
one concise semantic-search query.

Current company/agent knowledge base: {company_name}

ALWAYS retrieve when the message reports or asks for help with any emergency
falling under one or more of these categories: Rights Violations, Casualties,
Displacements, or Severe Hunger. This includes armed people, assault, abuse,
injury or death, forced movement, refugees, asylum, human rights, hunger, food
insecurity, or an active conflict or emergency.
ALWAYS retrieve when the user asks for emergency help, police or NGO contacts,
protection services, reporting channels, rights information, or safety
protocols.

For every case in these categories, the query MUST seek all applicable
supporting information, not just the incident description:
1. relevant rules, rights, or procedures;
2. relevant NGO, humanitarian, and protection-organization contacts;
3. police and emergency-service contacts;
4. reporting, legal, medical, shelter, food, or other assistance; and
5. immediate safety protocols.
Preserve any place, date, people, and incident type. Adapt the support terms to
the emergency category; do not limit retrieval to one category or one type of
contact. Examples:
- "I saw 3 armed men assaulting women in Kismayo this morning" ->
  "emergency police contacts NGOs supporting survivors of violence and safety protocols"
- "I have been denied asylum after displacement" ->
  "rights of refugees and asylum seekers after displacement NGO humanitarian protection and legal assistance contacts"
- "Families were forced to flee and have no food" ->
  "displacement emergency contacts humanitarian food assistance and safety support"

Retrieve specific facts, contacts, services, policies, eligibility, locations,
deadlines, procedures, document-specific questions, and factual follow-ups.
Do not retrieve greetings, thanks, small talk, or broad low-risk concepts that
need no local or document-specific facts.

Use history only to resolve references such as "it", "there", or "those
contacts". Never invent a place, organization, or incident detail.

Return ONLY valid JSON in this exact shape:
{{"needs_retrieval": true, "query": "focused search query"}}

If retrieval is not needed, return:
{{"needs_retrieval": false, "query": ""}}
""".strip()

_ANSWER_AGENT_INSTRUCTIONS = """
You are Ubuntu Voice, a concise and safety-conscious support assistant for
{company_name}.

The user understands {language} as their primary language. Always respond in
{language} so communication is clear.

You are currently scoped only to {company_name}'s knowledge base. Do not answer
as if you know other companies, agents, organizations, countries, or external
knowledge bases unless trusted excerpts for them are provided here.

Current user question:
{user_question}

Recent conversation history:
{history}

Retrieval status:
{retrieval_status}

Trusted knowledge-base excerpts:
{context}

Rules:
- If the user is greeting you, thanking you, asking how you are, or asking what
  you can help with, respond naturally and briefly.
- For broad low-risk concepts that do not require local or document-specific
  facts, give a short general answer and invite the user to ask for support from
  the trusted documents if useful.
- Treat every report or request involving Rights Violations, Casualties,
  Displacements, or Severe Hunger as an emergency-support request. These four
  categories are handled by the same complete emergency workflow, including
  reports of assault, armed people, abuse, injury/death, forced movement,
  refugees, asylum, human rights, hunger, or active conflict.
- For emergency-support requests, briefly acknowledge the situation and
  prioritize immediate safety. Use the trusted excerpts as a checklist and
  provide every applicable item they contain: (1) the user's relevant rights,
  (2) named NGOs/humanitarian/protection organizations and their phone,
  email, address, or other contact details, (3) police/emergency contacts,
  (4) reporting or legal-assistance steps, and (5) safety protocols. Do not
  stop after generic advice when the excerpts contain contacts or rights.
  Include only supported information; never invent contact details, claim an
  authority was contacted, or promise follow-up.
- If immediate danger is possible, advise moving to a safer place if possible
  and contacting local emergency services, police, or trusted people. Make
  clear this is general guidance, not authoritative legal, medical, or security
  advice.
- For specific local facts, contacts, services, policies, eligibility,
  locations, deadlines, procedures, or document-specific questions, answer using
  ONLY the trusted excerpts.
- If the user asks a factual or document-specific question about a different
  company, agent, organization, country, place, or corpus than {company_name},
  clearly say that you are only aware of {company_name}'s knowledge base for
  now, and ask them to select or provide the relevant knowledge base if they
  want that answer.
- If retrieval was needed but no trusted excerpts were found, say you do not
  have enough trusted information in {company_name}'s knowledge base. For an
  emergency, still give brief general safety guidance and advise contacting
  local emergency services, police, or a trusted humanitarian organization;
  never invent contacts or say that anyone was notified.
- Be clear, direct, and brief. Default to 1-3 short sentences.
- Answer only what the user asked. Do not add background, examples, warnings,
  next steps, definitions, or related details unless the user asks for them.
- Use bullets only if the user asks for a list or the answer has multiple
  concrete items. Keep each bullet short.
- If the answer is yes/no, start with yes or no, then add only the needed detail.
- Never fabricate local facts, contacts, services, or instructions.
- Do not present security, legal, medical, or emergency guidance as
  authoritative advice.
- Do not minimize, investigate, verify, or make accusations about a reported
  incident. Do not delay available safety information with unnecessary
  follow-up questions.
- All responses should be in proper markdown with paragraphs and line breaks. Use bullets only when needed.
""".strip()


def format_chat_history(history: list[dict[str, str]], *, max_turns: int = 8) -> str:
    """Format recent chat turns for prompt context while keeping it compact."""
    parts: list[str] = []
    for item in history[-max_turns:]:
        role = item.get("role")
        content = re.sub(r"\s+", " ", item.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        parts.append(f"{role.title()}: {content[:1200]}")
    return "\n".join(parts) if parts else "None"


def parse_query_preparation(raw: str, *, fallback_query: str) -> tuple[bool, str]:
    """Parse query-preparation JSON, falling back to retrieval for safety."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return True, fallback_query

    if not isinstance(payload, dict):
        return True, fallback_query

    needs_retrieval = payload.get("needs_retrieval")
    query = payload.get("query")
    if needs_retrieval is False:
        return False, ""
    if needs_retrieval is True and isinstance(query, str) and query.strip():
        return True, query.strip()[:500]
    return True, fallback_query


async def prepare_retrieval_query(
    *,
    async_client: AsyncOpenAI,
    chat_model: str,
    company_name: str,
    user_message: str,
    history: list[dict[str, str]],
) -> tuple[bool, str, UsageCharge | None]:
    """Use prompt instructions to decide if retrieval is needed and rewrite the query."""
    response = await async_client.chat.completions.create(
        model=chat_model,
        messages=[
            {"role": "system", "content": _QUERY_REWRITE_PROMPT.format(company_name=company_name)},
            {
                "role": "user",
                "content": (
                    f"Conversation history:\n{format_chat_history(history)}\n\n"
                    f"Latest user message:\n{user_message}\n\n"
                    "Return the JSON retrieval decision now."
                ),
            },
        ],
        temperature=0,
        max_tokens=120,
    )
    usage_charge = usage_charge_from_openrouter_usage(getattr(response, "usage", None))
    raw = (response.choices[0].message.content or "").strip()
    needs_retrieval, query = parse_query_preparation(raw, fallback_query=user_message)
    return needs_retrieval, query, usage_charge


async def run_rag_agent_for_evaluation(
    *,
    async_client: AsyncOpenAI,
    db_session: Session,
    company_id: str,
    company_name: str,
    user_message: str,
    language: str,
    history: list[dict[str, str]] | None = None,
    chat_model: str,
    embedding_model: str,
    embedding_dimensions: int,
    top_k: int,
    similarity_threshold: float,
    openrouter_api_key: str,
    openrouter_base_url: str,
) -> RagEvaluationOutput:
    """Run the existing RAG pipeline while retaining retrieved chunks in memory."""
    usage_charges: list[UsageCharge] = []
    recent_history = history or []
    logger.info(
        "RAG pipeline start: company_id=%s company_name=%r query_len=%d history_turns=%d",
        company_id,
        company_name,
        len(user_message),
        len(recent_history),
    )

    needs_retrieval, retrieval_query, prep_usage_charge = await prepare_retrieval_query(
        async_client=async_client,
        chat_model=chat_model,
        company_name=company_name,
        user_message=user_message,
        history=recent_history,
    )
    if prep_usage_charge is not None:
        usage_charges.append(prep_usage_charge)

    chunks: list[dict] = []
    grounded = False
    retrieval_status = "Retrieval was not needed for this message."
    context = "No trusted excerpts were retrieved because retrieval was not needed."

    if needs_retrieval:
        logger.info(
            "RAG query prepared: company_id=%s original_len=%d retrieval_len=%d",
            company_id,
            len(user_message),
            len(retrieval_query),
        )
        query_vector, usage_charge = await embed_query(
            async_client,
            retrieval_query,
            model=embedding_model,
            dimensions=embedding_dimensions,
        )
        if usage_charge is not None:
            usage_charges.append(usage_charge)
        chunks = retrieve_chunks_from_db(
            db_session,
            company_id=company_id,
            query_vector=query_vector,
            top_k=top_k,
        )

        if chunks:
            best_similarity = float(chunks[0].get("similarity", 0.0))
            logger.info(
                "RAG: company_id=%s best_similarity=%.4f threshold=%.4f chunks=%d",
                company_id,
                best_similarity,
                similarity_threshold,
                len(chunks),
            )
            if best_similarity >= similarity_threshold:
                grounded = True
                context = build_context_from_chunks(chunks)
                retrieval_status = "Trusted excerpts were retrieved and passed the similarity threshold."
            else:
                retrieval_status = "Retrieval was needed, but no excerpts passed the similarity threshold."
                context = "No trusted excerpts passed the relevance threshold."
        else:
            logger.info("RAG: no chunks in DB for company_id=%s", company_id)
            retrieval_status = "Retrieval was needed, but no knowledge-base chunks were found."
            context = "No trusted excerpts were found in the knowledge base."

    openai_model = OpenAIChatCompletionsModel(
        model=chat_model,
        openai_client=async_client,
    )
    answer_agent = Agent(
        name=f"{company_name} Support Agent",
        instructions=_ANSWER_AGENT_INSTRUCTIONS.format(
            company_name=company_name,
            language=language,
            user_question=user_message,
            history=format_chat_history(recent_history),
            retrieval_status=retrieval_status,
            context=context,
        ),
        model=openai_model,
    )

    with trace(f"rag-answer:{company_id}"):
        logger.info("RAG answer agent starting for company_id=%s", company_id)
        result = await Runner.run(answer_agent, user_message)

    generation_ids = [
        response_id
        for response_id in [getattr(raw_response, "response_id", None) for raw_response in getattr(result, "raw_responses", [])]
        if isinstance(response_id, str) and response_id
    ]
    usage_charges.extend(
        await fetch_openrouter_generation_charges(
            api_key=openrouter_api_key,
            base_url=openrouter_base_url,
            generation_ids=generation_ids,
        )
    )

    reply = (result.final_output or "").strip()
    if not reply:
        reply = f"I do not have enough trusted information in {company_name}'s knowledge base to answer that."
        grounded = False

    logger.info(
        "RAG pipeline complete: company_id=%s grounded=%s reply_len=%d",
        company_id,
        grounded,
        len(reply),
    )
    return RagEvaluationOutput(
        answer=reply,
        grounded=grounded,
        documents=chunks if grounded else [],
        usage_charges=usage_charges,
    )


async def run_rag_agent(**kwargs) -> tuple[str, bool, list[UsageCharge]]:
    """Run the RAG pipeline using the backward-compatible chat response shape."""
    output = await run_rag_agent_for_evaluation(**kwargs)
    return output.answer, output.grounded, output.usage_charges
