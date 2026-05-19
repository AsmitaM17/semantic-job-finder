from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import streamlit as st

from jobsearch.db import JobStore
from jobsearch.llm import OllamaClient
from jobsearch.search import SearchRequest, SearchService
from jobsearch.semantic import SemanticIndex
from jobsearch.sources import SOURCE_REGISTRY


APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "jobs.sqlite3"
CHROMA_DIR = DATA_DIR / "chroma"


st.set_page_config(
    page_title="Local Job Search Engine",
    page_icon="",
    layout="wide",
)


@st.cache_resource
def get_store() -> JobStore:
    DATA_DIR.mkdir(exist_ok=True)
    store = JobStore(DB_PATH)
    store.setup()
    return store


@st.cache_resource
def get_semantic_index() -> SemanticIndex:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return SemanticIndex(CHROMA_DIR)


@st.cache_resource
def get_search_service() -> SearchService:
    return SearchService(list(SOURCE_REGISTRY.values()))


def dataframe_from_jobs(jobs):
    rows = []
    for job in jobs:
        rows.append(
            {
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "source": job.source,
                "posted": job.posted,
                "url": job.url,
                "summary": job.summary,
            }
        )
    return pd.DataFrame(rows)


store = get_store()
semantic_index = get_semantic_index()
search_service = get_search_service()

st.title("Local Job Search Engine")

with st.sidebar:
    st.header("Search")
    keyword = st.text_input("Role or keyword", value="python developer")
    location = st.text_input("Location", value="remote")
    max_per_source = st.slider("Max results per source", min_value=5, max_value=50, value=15, step=5)

    source_names = list(SOURCE_REGISTRY.keys())
    selected_sources = st.multiselect(
        "Sources",
        source_names,
        default=["LinkedIn", "Naukri", "Indeed", "Glassdoor", "RemoteOK", "WeWorkRemotely"],
    )

    with st.expander("Optional company career portals"):
        st.caption("Only needed when you want company-specific boards in addition to job portals.")
        greenhouse = st.text_area("Greenhouse company names", placeholder="openai, stripe, airbnb")
        lever = st.text_area("Lever company names", placeholder="netflix, scaleai")
        generic_pages = st.text_area(
            "Career page URLs",
            placeholder="https://example.com/careers, https://example.com/jobs",
        )

    st.divider()
    use_semantic = st.checkbox("Use Chroma semantic search", value=True)
    use_ollama = st.checkbox("Use Ollama Gemma 2B summary/ranking", value=False)
    ollama_model = st.text_input("Ollama model", value="gemma:2b", disabled=not use_ollama)

    search_clicked = st.button("Search now", type="primary", use_container_width=True)


def split_lines(value: str) -> list[str]:
    return [part.strip() for part in value.replace("\n", ",").split(",") if part.strip()]


tabs = st.tabs(["Live results", "Cached jobs", "About"])

with tabs[0]:
    if search_clicked:
        if not keyword.strip():
            st.warning("Add a keyword before searching.")
            st.stop()

        request = SearchRequest(
            keyword=keyword.strip(),
            location=location.strip(),
            max_per_source=max_per_source,
            selected_sources=selected_sources,
            greenhouse_boards=split_lines(greenhouse),
            lever_boards=split_lines(lever),
            generic_pages=split_lines(generic_pages),
        )

        progress = st.progress(0, text="Starting live search...")
        started = time.time()
        jobs = []
        errors = []

        for idx, update in enumerate(search_service.search_stream(request), start=1):
            progress.progress(update.progress, text=update.message)
            if update.job:
                jobs.append(update.job)
            if update.error:
                errors.append(update.error)

        unique_jobs = store.upsert_jobs(jobs)
        if unique_jobs:
            semantic_index.upsert(unique_jobs)

        if use_semantic and unique_jobs:
            shown_jobs = semantic_index.search(keyword, unique_jobs, limit=min(len(unique_jobs), 75))
        else:
            shown_jobs = unique_jobs

        if use_ollama and shown_jobs:
            client = OllamaClient(model=ollama_model)
            with st.spinner("Asking local Gemma for a short fit summary..."):
                shown_jobs = client.add_short_fit_notes(keyword, shown_jobs[:20]) + shown_jobs[20:]

        elapsed = time.time() - started
        progress.empty()

        st.success(f"Found {len(unique_jobs)} unique jobs in {elapsed:.1f}s.")

        if errors:
            with st.expander("Source warnings"):
                for error in errors:
                    st.write(error)

        if shown_jobs:
            df = dataframe_from_jobs(shown_jobs)
            st.dataframe(
                df,
                column_config={
                    "url": st.column_config.LinkColumn("url"),
                    "summary": st.column_config.TextColumn("summary", width="large"),
                },
                hide_index=True,
                use_container_width=True,
            )
            st.download_button(
                "Download CSV",
                df.to_csv(index=False).encode("utf-8"),
                file_name="job_results.csv",
                mime="text/csv",
            )
        else:
            st.info("No jobs came back from the selected sources. Try fewer filters or another keyword.")
    else:
        st.info("Choose sources and run a live search.")

with tabs[1]:
    cached = store.search_cached(keyword=keyword, location=location, limit=250)
    if cached:
        st.dataframe(
            dataframe_from_jobs(cached),
            column_config={"url": st.column_config.LinkColumn("url")},
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("No cached jobs yet.")

with tabs[2]:
    st.markdown(
        """
        This is a lightweight local aggregator. It searches public job portal result pages,
        optional company career portals, saves deduplicated results in SQLite, and indexes result
        text in ChromaDB using a tiny local hashing embedder.

        LinkedIn, Naukri, Indeed, and Glassdoor can throttle or block automated requests. When that
        happens, the app keeps searching the other sources and shows the blocked portal under source
        warnings.

        Ollama Gemma 2B is optional because local LLM calls are the slowest part. Turn it on only
        when you want a short fit note for the top results.
        """
    )