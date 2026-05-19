from __future__ import annotations

import json

import requests

from .models import Job


class OllamaClient:
    def __init__(self, model: str = "gemma:2b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def generate(self, prompt: str) -> str:
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 80, "temperature": 0.2},
            },
            timeout=45,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()

    def add_short_fit_notes(self, keyword: str, jobs: list[Job]) -> list[Job]:
        enriched = []
        for job in jobs:
            prompt = (
                "Write one concise job-search fit note under 24 words. "
                "Do not invent requirements.\n\n"
                f"Search: {keyword}\n"
                f"Title: {job.title}\n"
                f"Company: {job.company}\n"
                f"Location: {job.location}\n"
                f"Description: {job.summary}\n"
            )
            try:
                note = self.generate(prompt)
            except (requests.RequestException, json.JSONDecodeError) as exc:
                note = f"Ollama unavailable: {exc}"
            enriched.append(
                Job(
                    title=job.title,
                    company=job.company,
                    location=job.location,
                    url=job.url,
                    source=job.source,
                    posted=job.posted,
                    summary=note or job.summary,
                )
            )
        return enriched