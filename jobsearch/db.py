from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import Job


class JobStore:
    def __init__(self, path: Path):
        self.path = path

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.path)

    def setup(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_key TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT,
                    location TEXT,
                    url TEXT NOT NULL,
                    source TEXT NOT NULL,
                    posted TEXT,
                    summary TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_title ON jobs(title)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_location ON jobs(location)")

    def upsert_jobs(self, jobs: list[Job]) -> list[Job]:
        deduped = {job.key: job for job in jobs if job.url and job.title}
        with self.connect() as conn:
            for key, job in deduped.items():
                conn.execute(
                    """
                    INSERT INTO jobs (job_key, title, company, location, url, source, posted, summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(job_key) DO UPDATE SET
                        title = excluded.title,
                        company = excluded.company,
                        location = excluded.location,
                        posted = excluded.posted,
                        summary = excluded.summary,
                        last_seen = CURRENT_TIMESTAMP
                    """,
                    (
                        key,
                        job.title,
                        job.company,
                        job.location,
                        job.url,
                        job.source,
                        job.posted,
                        job.summary,
                    ),
                )
        return list(deduped.values())

    def search_cached(self, keyword: str = "", location: str = "", limit: int = 200) -> list[Job]:
        clauses = []
        params: list[str | int] = []
        if keyword.strip():
            clauses.append("(title LIKE ? OR company LIKE ? OR summary LIKE ?)")
            pattern = f"%{keyword.strip()}%"
            params.extend([pattern, pattern, pattern])
        if location.strip():
            clauses.append("location LIKE ?")
            params.append(f"%{location.strip()}%")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT title, company, location, url, source, posted, summary
                FROM jobs
                {where}
                ORDER BY last_seen DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [
            Job(
                title=row[0] or "",
                company=row[1] or "",
                location=row[2] or "",
                url=row[3] or "",
                source=row[4] or "",
                posted=row[5] or "",
                summary=row[6] or "",
            )
            for row in rows
        ]