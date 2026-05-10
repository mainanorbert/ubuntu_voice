"""Deterministic character-window chunking for embedding pipelines."""


def chunk_plain_text(
    text: str,
    *,
    max_chars: int,
    overlap_chars: int,
    file_name: str,
) -> list[tuple[int, str, dict]]:
    """Split ``text`` into overlapping windows and return chunk rows.

    Each tuple is ``(chunk_index, chunk_text, metadata_dict)``. Metadata always
    includes the source ``file_name`` and character offsets in the original text.
    """
    stripped = text.strip()
    if not stripped:
        return []

    step = max(1, max_chars - overlap_chars)
    chunks: list[tuple[int, str, dict]] = []
    index = 0
    position = 0

    while position < len(stripped):
        end = min(len(stripped), position + max_chars)
        window = stripped[position:end]
        meta = {
            "file_name": file_name,
            "char_start": position,
            "char_end": end,
        }
        chunks.append((index, window, meta))
        index += 1
        if end == len(stripped):
            break
        position += step

    return chunks
