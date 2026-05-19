from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import cast

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from .models import Job


class HashEmbeddingFunction(EmbeddingFunction):
    """Tiny deterministic embedder for low-resource machines."""

    def __init__(self, dimensions: int = 128):
        self.dimensions = dimensions

    def __call__(self, input: Documents) -> Embeddings:
        return cast(
            Embeddings,
            [self.embed(document) for document in input]
        )

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = [token.lower() for token in text.split() if token.strip()]
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[idx] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class SemanticIndex:
    def __init__(self, path: Path):
        self.embedder = HashEmbeddingFunction()
        self.client = chromadb.PersistentClient(path=str(path))
        self.collection = self.client.get_or_create_collection(
            "jobs",
            embedding_function=self.embedder,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, jobs: list[Job]) -> None:
        if not jobs:
            return
        self.collection.upsert(
            ids=[job.key for job in jobs],
            documents=[job.searchable_text for job in jobs],
            metadatas=[
                {
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "url": job.url,
                    "source": job.source,
                    "posted": job.posted,
                    "summary": job.summary,
                }
                for job in jobs
            ],
        )

    def search(self, query: str, fallback_jobs: list[Job], limit: int = 50) -> list[Job]:
        if not fallback_jobs:
            return []
        allowed = {job.key: job for job in fallback_jobs}
        result = self.collection.query(
            query_texts=[query],
            n_results=min(max(limit, 1), len(fallback_jobs)),
            include=["metadatas"],
        )
        ordered = []
        for job_id in result.get("ids", [[]])[0]:
            if job_id in allowed:
                ordered.append(allowed[job_id])
        seen = {job.key for job in ordered}
        ordered.extend(job for job in fallback_jobs if job.key not in seen)
        return ordered[:limit]