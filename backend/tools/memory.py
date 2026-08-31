"""Memory tools — vector-similarity search over past-incident fingerprints.

Real cosine similarity (see services/embedding.py) over locally-embedded
fingerprints. Returns ranked matches so the Memory agent can say
"seen 2x before, resolved in ~4m via rollback" with an actual similarity score.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.models import IncidentMemory
from backend.services.embedding import cosine_similarity, embed_text
from backend.services.storage import StorageService


@dataclass
class MemoryMatch:
    memory: IncidentMemory
    similarity: float


def search_memory(
    storage: StorageService, fingerprint: str, top_k: int = 3
) -> list[MemoryMatch]:
    query = embed_text(fingerprint)
    matches = [
        MemoryMatch(memory=m, similarity=round(cosine_similarity(query, m.embedding), 4))
        for m in storage.all_memories()
    ]
    matches.sort(key=lambda x: x.similarity, reverse=True)
    return matches[:top_k]
