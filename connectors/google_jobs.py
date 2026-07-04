"""
Connettore per Google Jobs tramite SerpApi (https://serpapi.com).

Perche' questo invece di scrapare LinkedIn direttamente:
  - Google Jobs aggrega automaticamente annunci da moltissime fonti,
    incluse LinkedIn, Indeed, ZipRecruiter e i siti aziendali Workday.
  - Non tocchiamo mai linkedin.com direttamente: zero rischio di ban,
    zero anti-bot da aggirare.
  - Piano gratuito SerpApi: 250 ricerche/mese. Con poche query mirate a
    settimana (vedi config/search_queries.py) si resta ben sotto la soglia.

Per isolare annunci specificamente da LinkedIn, si puo' usare l'operatore
Google "site:linkedin.com/jobs/view" dentro alla query stessa (vedi
GOOGLE_JOBS_QUERIES in config/search_queries.py).
"""
import os
from typing import List

import requests

from shared.models import JobPosting

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
SERPAPI_URL = "https://serpapi.com/search"


def fetch_google_jobs(query: str, location: str = "Milano, Italy") -> List[dict]:
    if not SERPAPI_KEY:
        raise RuntimeError("SERPAPI_KEY mancante nelle variabili d'ambiente")

    params = {
        "engine": "google_jobs",
        "q": query,
        "location": location,
        "hl": "it",
        "api_key": SERPAPI_KEY,
    }
    resp = requests.get(SERPAPI_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("jobs_results", [])


def to_job_postings(raw_results: List[dict]) -> List[JobPosting]:
    postings = []
    for r in raw_results:
        apply_link = ""
        apply_options = r.get("apply_options") or []
        if apply_options:
            apply_link = apply_options[0].get("link", "")

        postings.append(
            JobPosting(
                company=r.get("company_name", "N/D"),
                title=r.get("title", ""),
                location=r.get("location", ""),
                url=apply_link or r.get("share_link", ""),
                source=f"google_jobs:{r.get('via', 'sconosciuto')}",
                description=r.get("description", ""),
            )
        )
    return postings
