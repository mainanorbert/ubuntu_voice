"""OpenAI Agents SDK RAG pipeline for tenant-scoped customer support.

Architecture
------------
Phase 1 – Direct retrieval  (deterministic, no LLM)
    ``embed_query`` + ``retrieve_chunks_from_db`` always run unconditionally so
    there is no dependency on a model deciding to call a tool.  The similarity
    threshold is applied here; if no relevant chunks are found the pipeline
    returns a company-aware refusal immediately, skipping the LLM step.

Phase 2 – Answer agent  (OpenAI Agents SDK)
    The retrieved context is injected directly into the agent's instructions
    together with the company name and the user's question.  A
    ``search_knowledge_base`` ``function_tool`` is also attached so the model
    can request additional context if the initial excerpts are insufficient.
    This phase runs inside a named ``trace`` block for end-to-end observability.
"""

from __future__ import annotations

import logging

from agents import Agent, OpenAIChatCompletionsModel, Runner, function_tool, trace
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from src.services.cost_monitoring import UsageCharge, fetch_openrouter_generation_charges
from src.services.rag_retrieval import (
    build_context_from_chunks,
    embed_query,
    retrieve_chunks_from_db,
)

logger = logging.getLogger(__name__)

# ── Prompt templates ──────────────────────────────────────────────────────────

_OUT_OF_SCOPE_TEMPLATES = {
    "English": "I don't have enough trusted information in {company_name}'s knowledge base to answer that.",
    "Swahili": "Sina taarifa za kutosha zilizoaminika kwenye hifadhidata ya {company_name} kujibu hilo.",
    "French": "Je n'ai pas assez d'informations fiables dans la base de connaissances de {company_name} pour répondre à cela.",
}

_ANSWER_AGENT_INSTRUCTIONS = """
You are Ubuntu Voice, a concise support assistant for {company_name}.

The user understands {language} as their primary language. Always respond in
{language} so communication is clear.

The user has asked: "{user_question}"

The following excerpts have been retrieved from {company_name}'s knowledge base
and are the ONLY source of truth you may use to answer:

{context}

Rules:
- Answer the user's question using ONLY the information in the excerpts above.
- Be clear, direct, and brief. Default to 1-3 short sentences.
- Answer only what the user asked. Do not add background, examples, warnings,
  next steps, definitions, or related details unless the user asks for them.
- Use bullets only if the user asks for a list or the answer has multiple
  concrete items. Keep each bullet short.
- If the answer is yes/no, start with yes or no, then add only the needed detail.
- If the excerpts do not contain enough information, say:
  "{out_of_scope_reply}"
- Never fabricate facts or answer from general knowledge outside the excerpts.
- Call the `search_knowledge_base` tool only if a focused follow-up search is
  necessary to answer the exact user question.
""".strip()

_FOLLOWUP_TOOL_DESCRIPTION = (
    "Search {company_name}'s knowledge base for additional context. "
    "Call this if the initial excerpts do not fully answer the user's question."
)


def build_out_of_scope_reply(*, company_name: str, language: str) -> str:
    """Return the fixed no-context reply in the user's selected language."""
    template = _OUT_OF_SCOPE_TEMPLATES.get(language, _OUT_OF_SCOPE_TEMPLATES["English"])
    return template.format(company_name=company_name)


# ── Answer-agent tool (for follow-up sub-queries) ─────────────────────────────

def make_followup_tool(
    *,
    async_client: AsyncOpenAI,
    db_session: Session,
    company_id: str,
    company_name: str,
    embedding_model: str,
    embedding_dimensions: int,
    top_k: int,
    usage_charges: list[UsageCharge],
) -> object:
    """Return a ``function_tool`` the answer agent may call for extra context."""

    @function_tool
    async def search_knowledge_base(query: str) -> str:
        """Search the knowledge base for additional context on a specific query.

        Args:
            query: A focused search phrase targeting the missing information.

        Returns:
            Relevant text excerpts from the knowledge base, or a message
            indicating nothing relevant was found.
        """
        logger.info(
            "Follow-up tool called: company_id=%s query=%r",
            company_id,
            query[:120],
        )
        query_vector, usage_charge = await embed_query(
            async_client,
            query,
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
        if not chunks:
            return f"No additional information found in {company_name}'s knowledge base."
        return build_context_from_chunks(chunks)

    return search_knowledge_base


# ── Public pipeline entry point ───────────────────────────────────────────────

async def run_rag_agent(
    *,
    async_client: AsyncOpenAI,
    db_session: Session,
    company_id: str,
    company_name: str,
    user_message: str,
    language: str,
    chat_model: str,
    embedding_model: str,
    embedding_dimensions: int,
    top_k: int,
    similarity_threshold: float,
    openrouter_api_key: str,
    openrouter_base_url: str,
) -> tuple[str, bool, list[UsageCharge]]:
    """Run the two-phase RAG pipeline and return reply, grounding flag, and usage.

    Phase 1 – deterministic retrieval:
        Always embeds the user question and queries pgvector directly.  No LLM
        is involved; the threshold check happens here so refusals are fast and
        company-aware.

    Phase 2 – answer agent (OpenAI Agents SDK):
        Builds an ``Agent`` whose ``instructions`` already contain the company
        name, the user question, and the retrieved context.  A follow-up
        ``function_tool`` is attached so the model can request additional
        excerpts if needed.  The run is wrapped in a ``trace`` for visibility.

    Returns:
        (reply, grounded): grounded is True when the reply is based on
        retrieved context, False when the query is out of scope.
    """
    # ── Phase 1: deterministic retrieval ──────────────────────────────────────
    logger.info(
        "RAG pipeline start: company_id=%s company_name=%r query=%r",
        company_id,
        company_name,
        user_message[:120],
    )

    usage_charges: list[UsageCharge] = []
    out_of_scope_reply = build_out_of_scope_reply(company_name=company_name, language=language)

    query_vector, usage_charge = await embed_query(
        async_client,
        user_message,
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

    if not chunks:
        logger.info("RAG: no chunks in DB for company_id=%s", company_id)
        return out_of_scope_reply, False, usage_charges

    best_similarity = float(chunks[0].get("similarity", 0.0))
    logger.info(
        "RAG: company_id=%s best_similarity=%.4f threshold=%.4f chunks=%d",
        company_id,
        best_similarity,
        similarity_threshold,
        len(chunks),
    )

    if best_similarity < similarity_threshold:
        logger.info(
            "RAG: below threshold for company_id=%s (%.4f < %.4f)",
            company_id,
            best_similarity,
            similarity_threshold,
        )
        return out_of_scope_reply, False, usage_charges

    context = build_context_from_chunks(chunks)

    # ── Phase 2: answer agent with company-aware instructions ─────────────────
    openai_model = OpenAIChatCompletionsModel(
        model=chat_model,
        openai_client=async_client,
    )

    followup_tool = make_followup_tool(
        async_client=async_client,
        db_session=db_session,
        company_id=company_id,
        company_name=company_name,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        top_k=top_k,
        usage_charges=usage_charges,
    )

    answer_agent = Agent(
        name=f"{company_name} Support Agent",
        instructions=_ANSWER_AGENT_INSTRUCTIONS.format(
            company_name=company_name,
            language=language,
            user_question=user_message,
            context=context,
            out_of_scope_reply=out_of_scope_reply,
        ),
        tools=[followup_tool],
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
        return out_of_scope_reply, False, usage_charges

    logger.info(
        "RAG pipeline complete: company_id=%s grounded=True reply_len=%d",
        company_id,
        len(reply),
    )
    return reply, True, usage_charges
