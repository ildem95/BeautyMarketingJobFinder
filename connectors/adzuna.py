"""
Connettore per l'API di Adzuna (https://developer.adzuna.com).
Gratuito, copertura generalista. Country code Italia = "it".

Cause piu' comuni di "non escono risultati" (dal debug fatto insieme):
  1. manca il parametro content-type=application/json -> risposta non JSON
  2. query troppo stretta (what + where insieme) su ruoli di nicchia:
     partire larghi e stringere dopo aver verificato che la pipeline funzioni
  3. results_per_page oltre 50 senza gestire la paginazione -> troncamento
  4. app_id / app_key con spazi o non ancora attivati sul portale Adzuna
"""
import os
from typing import List, Optional

import requests

from shared.models import JobPosting

ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY")
BASE_URL = "https://api.adzuna.com/v1/api/jobs/it/search/{page}"


def fetch_adzuna_jobs(
    what: str,
    where: str = "Milano",
    max_pages: int = 3,
    results_per_page: int = 50,
) -> List[dict]:
    """Restituisce i risultati grezzi (dict) dell'API Adzuna per una query."""
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        raise RuntimeError(
            "ADZUNA_APP_ID / ADZUNA_APP_KEY mancanti nelle variabili d'ambiente"
        )

    all_results: List[dict] = []
    for page in range(1, max_pages + 1):
        params = {
            "app_id": ADZUNA_APP_ID,
            "app_key": ADZUNA_APP_KEY,
            "what": what,
            "where": where,
            "results_per_page": results_per_page,
            "content-type": "application/json",
        }
        resp = requests.get(BASE_URL.format(page=page), params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            break
        all_results.extend(results)
        if len(results) < results_per_page:
            break  # ultima pagina raggiunta

    return all_results


def to_job_postings(raw_results: List[dict]) -> List[JobPosting]:
    postings = []
    for r in raw_results:
        company: Optional[dict] = r.get("company") or {}
        location: Optional[dict] = r.get("location") or {}
        postings.append(
            JobPosting(
                company=company.get("display_name", "N/D"),
                title=r.get("title", ""),
                location=location.get("display_name", ""),
                url=r.get("redirect_url", ""),
                source="adzuna",
                description=r.get("description", ""),
                contract_type=r.get("contract_time") or r.get("contract_type"),
                posted_date=r.get("created"),
            )
        )
    return postings
