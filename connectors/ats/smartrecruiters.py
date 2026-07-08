"""
Connettore per SmartRecruiters (https://api.smartrecruiters.com).
Posting API pubblica, nessuna autenticazione richiesta.

Verificato durante la ricerca: LVMH Perfumes & Cosmetics (Dior, Guerlain,
Benefit, Fenty...) usa questa piattaforma, company identifier
"lvmhperfumescosmetics" (dal suo career site
careers.smartrecruiters.com/lvmhperfumescosmetics).

L'endpoint "postings" (lista) non include sempre la descrizione completa.
Quando serve uno scoring piu' accurato, to_job_postings(..., include_details=True)
chiama il dettaglio per annuncio e salva il testo completo in JobPosting.description.
"""
from typing import List

from bs4 import BeautifulSoup
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


def _clean_text(value) -> str:
    if isinstance(value, list):
        return "\n".join(_clean_text(item) for item in value if item)
    if isinstance(value, dict):
        return "\n".join(_clean_text(item) for item in value.values() if item)
    if not isinstance(value, str):
        return ""
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)


def _extract_description(job: dict) -> str:
    job_ad = job.get("jobAd") or {}
    sections = job_ad.get("sections") or {}
    parts = []

    if isinstance(sections, dict):
        for key in (
            "companyDescription",
            "jobDescription",
            "qualifications",
            "additionalInformation",
        ):
            text = _clean_text(sections.get(key))
            if text:
                parts.append(text)
    elif isinstance(sections, list):
        for section in sections:
            text = _clean_text(section)
            if text:
                parts.append(text)

    for key in ("description", "jobDescription", "summary"):
        text = _clean_text(job.get(key))
        if text:
            parts.append(text)

    seen = set()
    unique_parts = []
    for part in parts:
        marker = part[:200]
        if marker in seen:
            continue
        seen.add(marker)
        unique_parts.append(part)
    return "\n\n".join(unique_parts)


def _location_to_string(location) -> str:
    if isinstance(location, dict):
        return ", ".join(
            filter(None, [location.get("city"), location.get("region"), location.get("country")])
        )
    if isinstance(location, str):
        return location
    return ""


def _posting_url(job: dict, company_identifier: str, posting_id: str) -> str:
    for key in ("applyUrl", "url", "ref"):
        value = job.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    return f"https://jobs.smartrecruiters.com/{company_identifier}/{posting_id}"


def to_job_postings(raw_jobs: List[dict], company_name: str, include_details: bool = False) -> List[JobPosting]:
    postings = []
    for j in raw_jobs:
        company_identifier = (j.get("company") or {}).get("identifier", "")
        posting_id = j.get("id", "")
        job_data = j
        if include_details and company_identifier and posting_id:
            try:
                detail = fetch_posting_detail(company_identifier, posting_id)
                if detail:
                    job_data = {**j, **detail}
            except Exception as e:
                print(f"[smartrecruiters] dettaglio non disponibile per {posting_id}: {e}")

        location = job_data.get("location") or j.get("location") or {}
        postings.append(
            JobPosting(
                company=company_name,
                title=job_data.get("name") or j.get("name", ""),
                location=_location_to_string(location),
                url=_posting_url(job_data, company_identifier, posting_id),
                source="smartrecruiters",
                description=_extract_description(job_data),
                posted_date=job_data.get("releasedDate") or j.get("releasedDate"),
            )
        )
    return postings
