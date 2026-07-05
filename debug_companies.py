"""
Script di debug per testare i connettori aziendali uno per uno in locale,
senza aspettare un run schedulato su GitHub Actions o cercare nei log.

Per ogni azienda con connector gia' configurato:
  - chiama il connettore e mostra quanti annunci grezzi arrivano
  - se il conteggio e' 0 (per i connettori "API dirette": smartrecruiters,
    workable, workday), ispeziona anche la risposta grezza per capire se il
    problema e' un nome di campo sbagliato nel nostro codice (es. la vera
    chiave JSON e' "data" invece di "jobs") oppure se l'azienda ha davvero
    zero posizioni aperte in questo momento
  - per i siti custom_llm, mostra ogni URL provato e quanti annunci Claude
    ha estratto da ciascuno

Uso:
    python debug_companies.py                  # testa tutte le aziende configurate
    python debug_companies.py aesop             # testa solo le aziende il cui nome contiene "aesop"
"""
import sys

from dotenv import load_dotenv

load_dotenv()

import requests

from config.companies import COMPANIES
from connectors import custom_llm
from connectors.ats import greenhouse, lever, smartrecruiters, workable, workday


def _inspect_raw_response(company: dict) -> None:
    connector = company["connector"]
    try:
        if connector == "smartrecruiters":
            url = f"https://api.smartrecruiters.com/v1/companies/{company['smartrecruiters_id']}/postings"
            r = requests.get(url, timeout=30)
        elif connector == "workable":
            url = f"https://apply.workable.com/api/v1/widget/accounts/{company['workable_account']}"
            r = requests.get(url, timeout=30)
        elif connector == "workday":
            tenant, site = company["workday_tenant"], company["workday_site"]
            wd_server = company.get("workday_server", "wd1")
            url = f"https://{tenant}.{wd_server}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
            payload = {"appliedFacets": company.get("workday_applied_facets", {}), "limit": 5, "offset": 0, "searchText": ""}
            r = requests.post(url, json=payload, timeout=30)
        else:
            return

        print(f"     [ispezione grezza] URL: {url}")
        print(f"     [ispezione grezza] status HTTP: {r.status_code}")
        if r.ok:
            try:
                data = r.json()
                if isinstance(data, dict):
                    print(f"     [ispezione grezza] chiavi top-level della risposta: {list(data.keys())}")
                elif isinstance(data, list):
                    print(f"     [ispezione grezza] la risposta e' una lista con {len(data)} elementi")
            except ValueError:
                print(f"     [ispezione grezza] risposta non JSON, primi 300 caratteri: {r.text[:300]}")
        else:
            print(f"     [ispezione grezza] corpo risposta (primi 300 caratteri): {r.text[:300]}")
    except Exception as e:
        print(f"     [ispezione grezza] impossibile ispezionare: {type(e).__name__}: {e}")


def debug_one(company: dict) -> None:
    name = company["name"]
    connector = company.get("connector")
    print(f"\n{'=' * 60}\n{name}  (connector: {connector})\n{'=' * 60}")

    if connector is None:
        print("  -> non ancora configurata, salto")
        return

    postings = []
    try:
        if connector == "greenhouse":
            raw = greenhouse.fetch_greenhouse_jobs(company["greenhouse_board_token"])
            print(f"  -> {len(raw)} annunci grezzi da Greenhouse")
            postings = greenhouse.to_job_postings(raw, name)

        elif connector == "lever":
            raw = lever.fetch_lever_jobs(company["lever_slug"], eu=company.get("lever_eu", False))
            print(f"  -> {len(raw)} annunci grezzi da Lever")
            postings = lever.to_job_postings(raw, name)

        elif connector == "smartrecruiters":
            raw = smartrecruiters.fetch_smartrecruiters_jobs(company["smartrecruiters_id"])
            print(f"  -> {len(raw)} annunci grezzi da SmartRecruiters")
            postings = smartrecruiters.to_job_postings(raw, name)

        elif connector == "workable":
            raw = workable.fetch_workable_jobs(company["workable_account"])
            print(f"  -> {len(raw)} annunci grezzi da Workable (TUTTE le posizioni, filtriamo noi dopo)")
            postings = workable.to_job_postings(raw, name)
            if raw and not postings[0].location:
                import json
                print("     [ispezione grezza] location vuota, ecco il JSON del primo annuncio:")
                print("    ", json.dumps(raw[0], indent=2, ensure_ascii=False)[:1500])

        elif connector == "workday":
            tenant, site = company["workday_tenant"], company["workday_site"]
            wd_server = company.get("workday_server", "wd1")
            applied_facets = company.get("workday_applied_facets", {})
            search_text = company.get("workday_search_text", "")
            raw = workday.fetch_workday_jobs(
                tenant=tenant, site=site, wd_server=wd_server, applied_facets=applied_facets, search_text=search_text
            )
            print(f"  -> {len(raw)} annunci grezzi da Workday")
            postings = workday.to_job_postings(raw, name, tenant, site, wd_server)

        elif connector == "custom_llm":
            for url in company.get("careers_urls", []):
                print(f"  -> provo {url}")
                found = custom_llm.extract_jobs_with_llm(url, name)
                print(f"     estratti {len(found)} annunci da questo URL")
                postings.extend(found)
        else:
            print(f"  -> connector sconosciuto: {connector}")
            return

        for p in postings[:5]:
            print(f"     - {p.title} | {p.location} | {p.url}")
        if len(postings) > 5:
            print(f"     ... e altri {len(postings) - 5}")

        if not postings and connector in ("smartrecruiters", "workable", "workday"):
            print("  -> ATTENZIONE: zero annunci. Ispeziono la risposta grezza dell'API per capire se e' un problema di nomi di campo o se l'azienda ha davvero zero posizioni ora:")
            _inspect_raw_response(company)

    except Exception as e:
        print(f"  -> ERRORE: {type(e).__name__}: {e}")
        if connector in ("smartrecruiters", "workable", "workday"):
            _inspect_raw_response(company)


def main():
    filter_name = sys.argv[1].lower() if len(sys.argv) > 1 else None
    for company in COMPANIES:
        if filter_name and filter_name not in company["name"].lower():
            continue
        debug_one(company)


if __name__ == "__main__":
    main()
