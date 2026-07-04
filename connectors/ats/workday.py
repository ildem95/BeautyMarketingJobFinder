"""
Connettore per Workday. Ogni tenant pubblico espone un feed JSON via POST a un
URL prevedibile: https://{tenant}.{wd_server}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs

Per trovare tenant/site/wd_server: apri il career site Workday dell'azienda
(URL tipo https://nomeazienda.wd1.myworkdayjobs.com/en-US/External), il
tenant e' "nomeazienda", wd_server e' "wd1" (o wd3, wd5...), site e'
l'ultimo segmento del percorso ("External" nell'esempio).

LIMITE NOTO: alcuni tenant Workday hanno protezioni anti-bot (Akamai) che
bloccano le richieste dirette senza sessione browser. Se ricevi errori 403
persistenti per un'azienda, quel tenant va gestito con un browser headless
(Playwright) invece che con requests: fammelo sapere e aggiungiamo quella
variante solo per i tenant che ne hanno bisogno.
"""
from typing import List

import requests

from shared.models import JobPosting

HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


def fetch_workday_jobs(
    tenant: str,
    site: str,
    wd_server: str = "wd1",
    search_text: str = "",
    applied_facets: dict = None,
    page_size: int = 20,
    max_results: int = 200,
) -> List[dict]:
    """applied_facets: dict tipo {"jobFamilyGroup": ["<id>"]}, per replicare un
    filtro gia' impostato manualmente sul sito (l'id si legge dalla query
    string dell'URL del career site quando il filtro e' attivo, es.
    ?jobFamilyGroup=<id> -> applied_facets={"jobFamilyGroup": ["<id>"]})."""
    applied_facets = applied_facets or {}
    base_url = f"https://{tenant}.{wd_server}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    all_jobs: List[dict] = []
    offset = 0
    while offset < max_results:
        payload = {"appliedFacets": applied_facets, "limit": page_size, "offset": offset, "searchText": search_text}
        resp = requests.post(base_url, json=payload, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        postings = data.get("jobPostings", [])
        if not postings:
            break
        all_jobs.extend(postings)
        offset += page_size
        if offset >= data.get("total", 0):
            break
    return all_jobs


def to_job_postings(
    raw_jobs: List[dict],
    company_name: str,
    tenant: str,
    site: str,
    wd_server: str = "wd1",
) -> List[JobPosting]:
    postings = []
    for j in raw_jobs:
        path = j.get("externalPath", "")
        url = f"https://{tenant}.{wd_server}.myworkdayjobs.com/en-US/{site}{path}"
        postings.append(
            JobPosting(
                company=company_name,
                title=j.get("title", ""),
                location=j.get("locationsText") or j.get("primaryLocation") or "",
                url=url,
                source="workday",
                posted_date=j.get("postedOn"),
            )
        )
    return postings
