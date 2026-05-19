from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import Job


@dataclass
class SearchRequest:
    keyword: str
    location: str
    max_per_source: int
    selected_sources: list[str]
    greenhouse_boards: list[str]
    lever_boards: list[str]
    generic_pages: list[str]


@dataclass
class SearchUpdate:
    progress: float
    message: str
    job: Job | None = None
    error: str | None = None


class SearchService:
    def __init__(self, sources):
        self.sources = sources

    def enabled_sources(self, request: SearchRequest):
        selected = set(request.selected_sources)
        for source in self.sources:
            if source.name in selected:
                yield source

    def search_stream(self, request: SearchRequest) -> Iterable[SearchUpdate]:
        sources = list(self.enabled_sources(request))
        total_steps = max(len(sources), 1)
        finished = 0

        for source in sources:
            yield SearchUpdate(
                progress=finished / total_steps,
                message=f"Searching {source.name}...",
            )
            try:
                for job in source.search(request):
                    yield SearchUpdate(
                        progress=min((finished + 0.5) / total_steps, 0.98),
                        message=f"Found {job.title} at {job.company or job.source}",
                        job=job,
                    )
            except Exception as exc:  # Streamlit should keep going when one source flakes.
                yield SearchUpdate(
                    progress=min((finished + 1) / total_steps, 0.98),
                    message=f"{source.name} had an issue.",
                    error=f"{source.name}: {exc}",
                )
            finished += 1

        yield SearchUpdate(progress=1.0, message="Search complete.")