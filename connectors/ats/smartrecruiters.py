"""
Connettore per SmartRecruiters (https://api.smartrecruiters.com).
Posting API pubblica, nessuna autenticazione richiesta.

Verificato durante la ricerca: LVMH Perfumes & Cosmetics (Dior, Guerlain,
Benefit, Fenty...) usa questa piattaforma, company identifier
"lvmhperfumescosmetics" (dal suo career site
careers.smartrecruiters.com/lvmhperfumescosmetics).

Nota: l'endpoint "postings" (lista) non include la descrizione completa.
Per non moltiplicare le chiamate, qui recuperiamo solo i campi della lista;
se in futuro serve la descrizione completa per il filtro di rilevanza,
aggiungiamo una chiamata a fetch_posting_detail() solo per gli annunci che
superano un primo filtro leggero (es. per titolo).
"""
from typing import List

import requests

from shared.models import JobPosting

BASE_URL = "https://api.smartrecruiters.com/v1/companies/{company_identifier}/postings"


def fetch_smartrecruiters_jobs(company_identifier: str, page_size: int = 100) -> List[dict]:
    url = BASE_URL.format(company_identifier=company_identifier)
    all_jobs: List[dict] = []
    offset = 0
    while True:
        resp = requests.get(url, params={"limit": page_size, "offset": offset}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content", [])
        all_jobs.extend(content)
        offset += page_size
        if not content or offset >= data.get("totalFound", 0):
            break
    return all_jobs


def fetch_posting_detail(company_identifier: str, posting_id: str) -> dict:
    url = f"{BASE_URL.format(company_identifier=company_identifier)}/{posting_id}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def to_job_postings(raw_jobs: List[dict], company_name: str) -> List[JobPosting]:
    postings = []
    for j in raw_jobs:
        location = j.get("location") or {}
        loc_str = ", ".join(
            filter(None, [location.get("city"), location.get("region"), location.get("country")])
        )
        company_identifier = (j.get("company") or {}).get("identifier", "")
        postings.append(
            JobPosting(
                company=company_name,
                title=j.get("name", ""),
                location=loc_str,
                url=f"https://jobs.smartrecruiters.com/{company_identifier}/{j.get('id', '')}",
                source="smartrecruiters",
                posted_date=j.get("releasedDate"),
            )
        )
    return postings
