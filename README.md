# Lightweight Job Search Engine

A local Streamlit app that searches multiple job boards and career portals in real time, stores results in SQLite, supports lightweight semantic search with ChromaDB, and can optionally use Ollama Gemma 2B for local summaries/ranking.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Optional local LLM support:

```powershell
ollama pull gemma:2b
ollama serve
```

Then enable the Ollama option inside the app.

## Notes

- This app uses normal web requests plus BeautifulSoup parsers. Some large job sites aggressively block scraping, so the app favors lightweight public pages and career portal patterns.
- SQLite cache lives in `data/jobs.sqlite3`.
- Chroma data lives in `data/chroma`.
- Keep source limits modest if your computer is low on RAM/CPU.