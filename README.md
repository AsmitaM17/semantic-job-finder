# Local Job Search Engine

A lightweight Streamlit app that searches job portals from a single local UI, stores results in SQLite, supports lightweight semantic ranking with ChromaDB, and can optionally use Ollama Gemma 2B for local fit notes.

The normal workflow is just:

1. Enter a role or keyword.
2. Enter a location.
3. Pick sources such as LinkedIn, Naukri, Indeed, Glassdoor, RemoteOK, or WeWorkRemotely.
4. Click **Search now**.

No manual URL copy-paste is needed for the main job portal search.

## Quick Start

If `.venv` already exists:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

First-time setup:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Optional Local LLM support:
```powershell
ollama pull gemma:2b
ollama serve

Then enable the Ollama option inside the app.

## Sources

Direct portal sources:

- LinkedIn
- Naukri
- Indeed
- Glassdoor
- RemoteOK
- WeWorkRemotely
- Python.org

Optional company career sources are available in the sidebar expander:

- Greenhouse company boards
- Lever company boards
- Generic company career pages

## Notes

- This app uses normal web requests plus BeautifulSoup parsers.
- LinkedIn, Naukri, Indeed, and Glassdoor often block automated requests or render results with JavaScript. When that happens, the app returns a one-click live search row for that portal instead of failing.
- SQLite cache lives in `data/jobs.sqlite3`.
- Chroma data lives in `data/chroma`.
- Chroma uses a tiny local hashing embedder to keep the app light.
- Ollama is optional and should stay off unless you want local LLM summaries.
- Keep source limits modest if your computer is low on RAM/CPU.