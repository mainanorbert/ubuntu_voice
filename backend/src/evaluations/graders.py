"""LLM-as-judge evaluators for independent RAG quality measurement."""

from __future__ import annotations

import json
from dataclasses import dataclass

from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field

from src.services.cost_monitoring import UsageCharge, usage_charge_from_openrouter_usage


class BooleanGrade(BaseModel):
    """Schema-constrained evaluator outcome with concise supporting evidence."""

    model_config = ConfigDict(extra="forbid")

    explanation: str = Field(..., description="A concise evidence-based explanation for the score.")
    passed: bool = Field(..., description="Whether the evaluated criterion passed.")


@dataclass(frozen=True)
class EvaluatorOutcome:
    """Validated evaluator result and optional provider usage charge."""

    passed: bool
    explanation: str
    usage_charge: UsageCharge | None


CORRECTNESS_PROMPT = """You grade factual correctness. Compare the STUDENT ANSWER only against the GROUND TRUTH ANSWER and reject conflicting claims. Extra information is acceptable only when consistent. Return a concise evidence-based explanation, not hidden chain-of-thought."""
RELEVANCE_PROMPT = """You grade answer relevance. Decide whether the STUDENT ANSWER directly and helpfully addresses the QUESTION. Return a concise evidence-based explanation, not hidden chain-of-thought."""
GROUNDEDNESS_PROMPT = """You grade groundedness. Decide whether the STUDENT ANSWER is supported by the supplied FACTS and contains no unsupported factual claims. Return a concise evidence-based explanation, not hidden chain-of-thought."""
RETRIEVAL_RELEVANCE_PROMPT = """You grade retrieval relevance. Decide whether the supplied FACTS contain keywords or semantic meaning relevant to the QUESTION. Some unrelated information is acceptable. Return a concise evidence-based explanation, not hidden chain-of-thought."""


async def run_boolean_grader(
    *,
    client: AsyncOpenAI,
    model: str,
    instructions: str,
    content: str,
) -> EvaluatorOutcome:
    """Invoke one strict structured-output judge and validate its result."""
    schema = BooleanGrade.model_json_schema()
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": instructions}, {"role": "user", "content": content}],
        temperature=0,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "rag_evaluation_grade", "strict": True, "schema": schema},
        },
    )
    raw = response.choices[0].message.content or ""
    grade = BooleanGrade.model_validate(json.loads(raw))
    return EvaluatorOutcome(
        passed=grade.passed,
        explanation=grade.explanation.strip()[:2000],
        usage_charge=usage_charge_from_openrouter_usage(getattr(response, "usage", None)),
    )


async def evaluate_correctness(
    client: AsyncOpenAI, model: str, *, question: str, answer: str, reference_answer: str
) -> EvaluatorOutcome:
    """Evaluate generated response against its reference answer."""
    return await run_boolean_grader(
        client=client,
        model=model,
        instructions=CORRECTNESS_PROMPT,
        content=f"QUESTION:\n{question}\n\nGROUND TRUTH ANSWER:\n{reference_answer}\n\nSTUDENT ANSWER:\n{answer}",
    )


async def evaluate_relevance(client: AsyncOpenAI, model: str, *, question: str, answer: str) -> EvaluatorOutcome:
    """Evaluate whether the generated response addresses the input."""
    return await run_boolean_grader(
        client=client,
        model=model,
        instructions=RELEVANCE_PROMPT,
        content=f"QUESTION:\n{question}\n\nSTUDENT ANSWER:\n{answer}",
    )


async def evaluate_groundedness(client: AsyncOpenAI, model: str, *, answer: str, facts: str) -> EvaluatorOutcome:
    """Evaluate whether the generated response is supported by retrieved facts."""
    return await run_boolean_grader(
        client=client,
        model=model,
        instructions=GROUNDEDNESS_PROMPT,
        content=f"FACTS:\n{facts or 'No facts were retrieved.'}\n\nSTUDENT ANSWER:\n{answer}",
    )


async def evaluate_retrieval_relevance(
    client: AsyncOpenAI, model: str, *, question: str, facts: str
) -> EvaluatorOutcome:
    """Evaluate whether retrieved facts are relevant to the input."""
    return await run_boolean_grader(
        client=client,
        model=model,
        instructions=RETRIEVAL_RELEVANCE_PROMPT,
        content=f"QUESTION:\n{question}\n\nFACTS:\n{facts or 'No facts were retrieved.'}",
    )
