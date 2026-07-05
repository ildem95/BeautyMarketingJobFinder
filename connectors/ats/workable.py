"""
Connettore per Workable (https://apply.workable.com).

API pubblica "widget", verificata via ricerca: nessuna autenticazione
richiesta, endpoint GET https://apply.workable.com/api/v1/widget/accounts/{account}
Non supporta filtri via query string: restituisce SEMPRE tutte le posizioni
pubblicate dall'azienda (coerente con quanto notato durante la ricerca -
"il link non cambia quando selezioni il settore" su Huda Beauty). Il filtro
per pertinenza lo fa comunque relevance_filter.py a valle.

Per trovare l'account: e' il segmento dopo apply.workable.com/ nell'URL del
career site (es. https://apply.workable.com/hudabeauty/ -> "hudabeauty").

Nota: lo schema esatto restituito dal widget pubblico non e' documentato al
100% nei dettagli (l'API "ufficiale" con schema completo richiede una API
key privata dell'azienda, che ovviamente non abbiamo). La funzione
to_job_postings usa .get() con fallback multipli per essere tollerante a
piccole differenze di schema; se dopo il primo run reale qualche campo
risulta vuoto, guardiamo insieme la risposta JSON grezza e sistemiamo.
"""
from typing import List

import requests

from shared.models import JobPosting

BASE_URL = "https://apply.workable.com/api/v1/widget/accounts/{account}"


def fetch_workable_jobs(account: str) -> List[dict]:
    resp = requests.get(BASE_URL.format(account=account), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("jobs", [])


def _format_location(location) -> str:
    if isinstance(location, list):
        parts = [_format_location(loc) for loc in location]
        return "; ".join(p for p in parts if p)
    if isinstance(location, dict):
        # provo diversi nomi di campo possibili, gli schemi pubblici non sono documentati al 100%
        city = location.get("city") or location.get("location_str")
        region = location.get("region") or location.get("state")
        country = location.get("country") or location.get("country_code")
        parts = [city, region, country]
        return ", ".join(p for p in parts if p)
    if isinstance(location, str):
        return location
    return ""


def to_job_postings(raw_jobs: List[dict], company_name: str) -> List[JobPosting]:
    postings = []
    for j in raw_jobs:
        # provo sia "location" (singolare) sia "locations" (plurale): schemi diversi usano nomi diversi
        location_field = j.get("location") or j.get("locations") or j.get("workplace")
        location_str = _format_location(location_field) or ("Remoto" if j.get("telecommute") or j.get("remote") else "")
        postings.append(
            JobPosting(
                company=company_name,
                title=j.get("title", ""),
                location=location_str,
                url=j.get("url") or j.get("shortlink", ""),
                source="workable",
                contract_type=j.get("employment_type") or j.get("department"),
                posted_date=j.get("published_on") or j.get("created_at"),
            )
        )
    return postings
