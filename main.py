"""
Pipeline principale: raccoglie annunci da tutte le fonti configurate, li
normalizza, deduplica, filtra con l'LLM, aggiorna data/jobs.json e manda
la notifica Telegram per i nuovi annunci rilevanti.

Pensato per girare come step di .github/workflows/scrape.yml, ma si puo'
lanciare anche in locale con:

    export ADZUNA_APP_ID=...
    export ADZUNA_APP_KEY=...
    export SERPAPI_KEY=...
    export ANTHROPIC_API_KEY=...
    export TELEGRAM_BOT_TOKEN=...      # opzionale
    export TELEGRAM_CHAT_ID=...        # opzionale
    python main.py
"""
import sys

from dotenv import load_dotenv

load_dotenv()  # in locale legge .env se presente; su GitHub Actions non fa nulla (le variabili arrivano dai secrets)

import dedup
import notify_telegram
import relevance_filter
import storage
from config.companies import COMPANIES
from config.search_queries import ADZUNA_QUERIES, GOOGLE_JOBS_QUERIES
from connectors import adzuna, custom_llm, google_jobs
from connectors.ats import greenhouse, lever, smartrecruiters, workable, workday


def collect_from_generalist_sources():
    jobs = []

    for what in ADZUNA_QUERIES:
        try:
            raw = adzuna.fetch_adzuna_jobs(what=what, where="Milano")
            jobs.extend(adzuna.to_job_postings(raw))
        except Exception as e:
            print(f"[adzuna] errore per query '{what}': {e}")

    for query in GOOGLE_JOBS_QUERIES:
        try:
            raw = google_jobs.fetch_google_jobs(query=query)
            jobs.extend(google_jobs.to_job_postings(raw))
        except Exception as e:
            print(f"[google_jobs] errore per query '{query}': {e}")

    return jobs


def _collect_one_company(company: dict) -> list:
    connector = company["connector"]
    name = company["name"]

    if connector == "greenhouse":
        raw = greenhouse.fetch_greenhouse_jobs(company["greenhouse_board_token"])
        return greenhouse.to_job_postings(raw, name)

    elif connector == "lever":
        raw = lever.fetch_lever_jobs(company["lever_slug"], eu=company.get("lever_eu", False))
        return lever.to_job_postings(raw, name)

    elif connector == "smartrecruiters":
        raw = smartrecruiters.fetch_smartrecruiters_jobs(company["smartrecruiters_id"])
        return smartrecruiters.to_job_postings(raw, name)

    elif connector == "workable":
        raw = workable.fetch_workable_jobs(company["workable_account"])
        return workable.to_job_postings(raw, name)

    elif connector == "workday":
        tenant = company["workday_tenant"]
        site = company["workday_site"]
        wd_server = company.get("workday_server", "wd1")
        applied_facets = company.get("workday_applied_facets", {})
        search_text = company.get("workday_search_text", "")
        raw = workday.fetch_workday_jobs(
            tenant=tenant, site=site, wd_server=wd_server, applied_facets=applied_facets, search_text=search_text
        )
        return workday.to_job_postings(raw, name, tenant, site, wd_server)

    elif connector == "custom_llm":
        jobs = []
        for url in company.get("careers_urls", []):
            jobs.extend(custom_llm.extract_jobs_with_llm(url, name))
        return jobs

    else:
        return []


def collect_from_companies():
    jobs = []

    for company in COMPANIES:
        connector = company.get("connector")
        name = company["name"]

        if connector is None:
            continue  # non ancora mappata, non serve loggare ad ogni run

        try:
            company_jobs = _collect_one_company(company)
            jobs.extend(company_jobs)
            print(f"  [{name}] ({connector}): {len(company_jobs)} annunci")
        except Exception as e:
            print(f"  [{name}] ({connector}): ERRORE - {type(e).__name__}: {e}")

    return jobs


def main():
    print("Raccolta da fonti generaliste (Adzuna, Google Jobs)...")
    jobs = collect_from_generalist_sources()
    print(f"  -> {len(jobs)} annunci grezzi")

    print("Raccolta dai siti aziendali configurati...")
    jobs += collect_from_companies()
    print(f"  -> {len(jobs)} annunci totali grezzi")

    print("Deduplica...")
    jobs = dedup.deduplicate(jobs)
    print(f"  -> {len(jobs)} annunci unici")

    print("Filtro di rilevanza con LLM...")
    jobs = relevance_filter.classify_jobs(jobs, min_score=50)
    print(f"  -> {len(jobs)} annunci rilevanti")

    print("Aggiornamento data/jobs.json...")
    new_ids, all_jobs = storage.merge_and_save(jobs)
    print(f"  -> {len(new_ids)} annunci nuovi")

    new_jobs = [j for j in all_jobs if j["id"] in new_ids]
    notify_telegram.notify_new_jobs(new_jobs)

    print("Fatto.")


if __name__ == "__main__":
    sys.exit(main())
