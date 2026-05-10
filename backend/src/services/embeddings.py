"""OpenRouter-compatible synchronous embedding calls."""

from __future__ import annotations

from openai import OpenAI

from src.services.cost_monitoring import UsageCharge, merge_usage_charges, usage_charge_from_openrouter_usage


def embed_texts_sync(
    client: OpenAI,
    texts: list[str],
    *,
    model: str,
    expected_dimensions: int,
    batch_size: int,
) -> tuple[list[list[float]], UsageCharge | None]:
    """Return embedding vectors plus cumulative billed usage for the batch set.

    Calls the OpenAI-compatible ``/v1/embeddings`` endpoint in batches of at most
    ``batch_size`` strings. Each vector length must match ``expected_dimensions``.
    """
    if not texts:
        return [], None

    all_vectors: list[list[float]] = []
    usage_charges: list[UsageCharge] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = client.embeddings.create(model=model, input=batch)
        rows = sorted(response.data, key=lambda row: row.index)
        usage_charge = usage_charge_from_openrouter_usage(getattr(response, "usage", None))
        if usage_charge is not None:
            usage_charges.append(usage_charge)
        for row in rows:
            vector = list(row.embedding)
            if len(vector) != expected_dimensions:
                msg = (
                    f"Embedding dimension mismatch: model returned {len(vector)} floats, "
                    f"expected {expected_dimensions}. Check embedding_model / embedding_dimensions."
                )
                raise ValueError(msg)
            all_vectors.append(vector)

    return all_vectors, merge_usage_charges(usage_charges) if usage_charges else None
