"""
Connettore per Greenhouse (https://boards-api.greenhouse.io).
API pubblica, nessuna autenticazione richiesta per le GET.

Per trovare il board_token di un'azienda: se il career site e' del tipo
https://boards.greenhouse.io/nomeazienda oppure incorpora
boards-api.greenhouse.io/v1/boards/nomeazienda/... nel sorgente della pagina,
"nomeazienda" e' il board_token da mettere in config/companies.py.
"""
from typing import List

import requests

from shared.models import JobPosting

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"


def fetch_greenhouse_jobs(board_token: str) -> List[dict]:
    url = BASE_URL.format(board_token=board_token)
    resp = requests.get(url, params={"content": "true"}, timeout=30)
    resp.raise_for_status()
    return resp.json().get("jobs", [])


def to_job_postings(raw_jobs: List[dict], company_name: str) -> List[JobPosting]:
    postings = []
    for j in raw_jobs:
        location = j.get("location") or {}
        postings.append(
            JobPosting(
                company=company_name,
                title=j.get("title", ""),
                location=location.get("name", ""),
                url=j.get("absolute_url", ""),
                source="greenhouse",
                description=j.get("content", "") or "",
                posted_date=j.get("updated_at"),
            )
        )
    return postings
