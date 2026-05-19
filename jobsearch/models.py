from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Job:
    title: str
    company: str
    location: str
    url: str
    source: str
    posted: str = ""
    summary: str = ""

    @property
    def key(self) -> str:
        return f"{self.source}|{self.url}".lower().strip()

    @property
    def searchable_text(self) -> str:
        return " ".join(
            part
            for part in [self.title, self.company, self.location, self.source, self.summary]
            if part
        )