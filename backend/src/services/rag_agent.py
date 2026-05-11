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
import re

from agents import Agent, OpenAIChatCompletionsModel, Runner, function_tool, trace
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from src.services.conflict_alerts import should_send_conflict_alert
from src.services.cost_monitoring import UsageCharge, fetch_openrouter_generation_charges
from src.services.rag_retrieval import (
    build_context_from_chunks,
    embed_query,
    retrieve_chunks_from_db,
)

logger = logging.getLogger(__name__)

# ── Prompt templates ──────────────────────────────────────────────────────────

_OUT_OF_SCOPE_TEMPLATES = {
    "English": (
        "I don't have enough trusted information in {company_name}'s knowledge base to answer that. "
        "Would you like me to look for trusted reporting contacts or local support options in this agent's documents?"
    ),
    "Swahili": (
        "Sina taarifa za kutosha zilizoaminika kwenye hifadhidata ya {company_name} kujibu hilo. "
        "Ungependa nitafute mawasiliano ya kuaminika ya kuripoti au chaguo za msaada kwenye nyaraka za wakala huyu?"
    ),
    "French": "Je n'ai pas assez d'informations fiables dans la base de connaissances de {company_name} pour répondre à cela.",
}

_GENERAL_CONVERSATION_REPLIES = {
    "English": (
        "Hi, I'm here and ready to help. You can ask a general question, or ask me to look in "
        "{company_name}'s trusted documents for local details, reporting contacts, or support options."
    ),
    "Swahili": (
        "Habari, niko hapa kusaidia. Unaweza kuuliza swali la jumla, au kuniomba nitafute kwenye "
        "nyaraka zinazoaminika za {company_name} kwa maelezo ya eneo, mawasiliano ya kuripoti, au chaguo za msaada."
    ),
    "French": (
        "Bonjour, je suis la pour aider. Vous pouvez poser une question generale, ou me demander de chercher dans "
        "les documents fiables de {company_name} des details locaux, des contacts de signalement ou des options de soutien."
    ),
}

_CONFLICT_REPORT_REPLIES = {
    "English": (
        "I'm sorry you're seeing this. I can help you turn this into a short report, translate or summarize it, "
        "or look in {company_name}'s trusted documents for reporting contacts and local support options."
    ),
    "Swahili": (
        "Pole kwa hali unayoiona. Ninaweza kusaidia kuandika ripoti fupi, kuitafsiri au kuifupisha, "
        "au kutafuta kwenye nyaraka zinazoaminika za {company_name} mawasiliano ya kuripoti na chaguo za msaada wa eneo."
    ),
    "French": (
        "Je suis desole que vous voyiez cela. Je peux aider a rediger un court signalement, le traduire ou le resumer, "
        "ou chercher dans les documents fiables de {company_name} des contacts de signalement et des options de soutien local."
    ),
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
- If the user is only greeting you, thanking you, asking how you are, or asking
  what you can help with, respond naturally and briefly without forcing a
  document-based answer.
- For general, low-risk concepts that do not require local facts, such as
  what mediation or peacebuilding means, you may give a short general answer
  and invite the user to ask for document-specific support.
- If the user is simply reporting an emerging conflict or violence situation
  rather than asking for a specific local fact, acknowledge the report with
  care and offer to help draft, translate, summarize, or look up trusted
  reporting contacts in the agent documents.
- For specific local facts, contacts, services, policies, eligibility,
  locations, deadlines, or procedures, answer using ONLY the excerpts above.
- Be clear, direct, and brief. Default to 1-3 short sentences.
- Answer only what the user asked. Do not add background, examples, warnings,
  next steps, definitions, or related details unless the user asks for them.
- Use bullets only if the user asks for a list or the answer has multiple
  concrete items. Keep each bullet short.
- If the answer is yes/no, start with yes or no, then add only the needed detail.
- If the user asks for specific local details and the excerpts do not contain
  enough information, say:
  "{out_of_scope_reply}"
- Never fabricate local facts, contacts, services, or instructions.
- Do not present security, legal, medical, or emergency guidance as
  authoritative advice.
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

def is_general_conversation(message: str) -> bool:
    """Return true for lightweight chat that should not require RAG."""
    normalized = re.sub(r"\s+", " ", message.strip().lower())
    if not normalized or len(normalized) > 120:
        return False

    return bool(
        re.fullmatch(r"(hi|hello|hey|good morning|good afternoon|good evening)[!.? ]*", normalized)
        or re.fullmatch(r"(how are you|how are you doing|how's it going)[?.! ]*", normalized)
        or re.fullmatch(r"(thanks|thank you|okay|ok|cool)[!. ]*", normalized)
        or re.fullmatch(r"(help|can you help|what can you do|what can you help with)[?.! ]*", normalized)
    )


def build_general_conversation_reply(*, company_name: str, language: str) -> str:
    """Return a localized reply for greetings and lightweight support prompts."""
    template = _GENERAL_CONVERSATION_REPLIES.get(language, _GENERAL_CONVERSATION_REPLIES["English"])
    return template.format(company_name=company_name)


def is_simple_conflict_report(message: str) -> bool:
    """Return true when the user reports conflict without asking for local facts."""
    normalized = re.sub(r"\s+", " ", message.strip().lower())
    if "?" in normalized or not should_send_conflict_alert(normalized):
        return False
    request_terms = (
        "what",
        "who",
        "where",
        "when",
        "how",
        "which",
        "should",
        "can you",
        "could you",
        "would you",
        "tell me",
        "show me",
        "find",
        "give me",
        "contact",
        "contacts",
        "number",
    )
    return not any(term in normalized for term in request_terms)


def build_conflict_report_reply(*, company_name: str, language: str) -> str:
    """Return a courteous response for declarative emerging-conflict reports."""
    template = _CONFLICT_REPORT_REPLIES.get(language, _CONFLICT_REPORT_REPLIES["English"])
    return template.format(company_name=company_name)


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
    if is_general_conversation(user_message):
        logger.info("General conversation response: company_id=%s", company_id)
        return (
            build_general_conversation_reply(company_name=company_name, language=language),
            False,
            usage_charges,
        )

    if is_simple_conflict_report(user_message):
        logger.info("Simple conflict report response: company_id=%s", company_id)
        return (
            build_conflict_report_reply(company_name=company_name, language=language),
            False,
            usage_charges,
        )

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
