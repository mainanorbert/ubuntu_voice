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

_QUERY_REWRITE_PROMPT = """
You prepare the user's latest message for a knowledge-base retrieval pipeline.

Decide whether the latest message needs trusted document retrieval from the
current company/agent knowledge base.

Current company/agent knowledge base: {company_name}

Retrieval is NOT needed for greetings, thanks, small talk, simple help prompts,
or broad low-risk concepts that can be answered generally.

Retrieval is also NOT needed when the user is clearly asking for facts about a
different company, country, organization, topic, or place than the current
company/agent knowledge base. For example, if the current knowledge base is
about Congo and the user asks "what happened between 1996-1997 in USA", return
needs_retrieval=false because the question is clear but outside the current
knowledge-base scope.

Retrieval IS needed for specific facts, contacts, services, policies,
eligibility, locations, deadlines, procedures, document-specific questions, or
follow-up questions that depend on facts from the current company/agent
knowledge base.

When retrieval is needed, rewrite the latest message into one short, specific
search query. Use conversation history only to resolve references like "it",
"that program", "there", "those contacts", or vague follow-ups. Preserve
important entities, places, dates, services, and constraints. Add missing
context from history when it improves retrieval, for example turn "What caused
this war?" after a discussion about Congo Kinshasa into "causes of the war in Congo kinshasa".

Return ONLY valid JSON in this exact shape:
{{"needs_retrieval": true, "query": "focused search query"}}

If retrieval is not needed, return:
{{"needs_retrieval": false, "query": ""}}
""".strip()

_ANSWER_AGENT_INSTRUCTIONS = """
You are Ubuntu Voice, a concise support assistant for {company_name}.

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
- If the user reports an emerging conflict or violence situation without asking
  for a specific local fact, acknowledge the issue with care and invite them to
  use trusted local channels or ask for document-specific reporting contacts.
- For specific local facts, contacts, services, policies, eligibility,
  locations, deadlines, procedures, or document-specific questions, answer using
  ONLY the trusted excerpts.
- If the user asks a factual or document-specific question about a different
  company, agent, organization, country, place, or corpus than {company_name},
  clearly say that you are only aware of {company_name}'s knowledge base for
  now, and ask them to select or provide the relevant knowledge base if they
  want that answer.
- If retrieval was needed but no trusted excerpts were found, or the excerpts do
  not answer the question, say you do not have enough trusted information in
  {company_name}'s knowledge base to answer that. Offer to look for trusted
  reporting contacts or local support options in the documents if useful.
- Be clear, direct, and brief. Default to 1-3 short sentences.
- Answer only what the user asked. Do not add background, examples, warnings,
  next steps, definitions, or related details unless the user asks for them.
- Use bullets only if the user asks for a list or the answer has multiple
  concrete items. Keep each bullet short.
- If the answer is yes/no, start with yes or no, then add only the needed detail.
- Never fabricate local facts, contacts, services, or instructions.
- Do not present security, legal, medical, or emergency guidance as
  authoritative advice.
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


async def run_rag_agent(
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
) -> tuple[str, bool, list[UsageCharge]]:
    """Run history-aware query preparation, optional retrieval, and answering."""
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
    return reply, grounded, usage_charges
