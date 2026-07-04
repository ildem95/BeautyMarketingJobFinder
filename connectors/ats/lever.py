"""
Connettore per Lever (https://api.lever.co). API pubblica senza autenticazione.

Per trovare lo slug: il career site e' del tipo https://jobs.lever.co/nomeazienda
-> "nomeazienda" e' il company_slug da mettere in config/companies.py.
Alcune aziende europee usano l'istanza EU (api.eu.lever.co): se l'API
principale restituisce vuoto ma il sito ha annunci, prova con eu=True.
"""
from typing import List

import requests

from shared.models import JobPosting

US_BASE = "https://api.lever.co"
EU_BASE = "https://api.eu.lever.co"


def fetch_lever_jobs(company_slug: str, eu: bool = False) -> List[dict]:
    base = EU_BASE if eu else US_BASE
    url = f"{base}/v0/postings/{company_slug}"
    resp = requests.get(url, params={"mode": "json"}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def to_job_postings(raw_jobs: List[dict], company_name: str) -> List[JobPosting]:
    postings = []
    for j in raw_jobs:
        categories = j.get("categories") or {}
        postings.append(
            JobPosting(
                company=company_name,
                title=j.get("text", ""),
                location=categories.get("location", ""),
                url=j.get("hostedUrl", ""),
                source="lever",
                description=j.get("descriptionPlain") or j.get("description") or "",
                contract_type=categories.get("commitment"),
                posted_date=str(j.get("createdAt", "")) or None,
            )
        )
    return postings
