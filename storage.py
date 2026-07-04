"""
Persistenza su data/jobs.json, il file che il workflow GitHub Actions
committa nel repo ad ogni run e che la dashboard Streamlit legge.

Ogni run unisce i nuovi annunci raccolti con quelli gia' salvati, senza
perdere lo stato che la candidata ha impostato dalla dashboard
(nuovo / da_vedere / candidata / scartato) ne' la data in cui un annuncio
e' stato visto per la prima volta.
"""
import json
import os
from datetime import datetime, timezone
from typing import List, Tuple

from shared.models import JobPosting

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "jobs.json")


def load_existing() -> dict:
    if not os.path.exists(DATA_PATH):
        return {}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {item["id"]: item for item in raw}


def merge_and_save(new_jobs: List[JobPosting]) -> Tuple[List[str], List[dict]]:
    """Aggiorna data/jobs.json con i nuovi annunci.

    Ritorna (lista_id_nuovi, lista_completa_annunci_come_dict).
    """
    existing = load_existing()
    now = datetime.now(timezone.utc).isoformat()
    new_ids = []

    for job in new_jobs:
        d = job.to_dict()
        if d["id"] in existing:
            # mantieni stato e data di prima comparsa gia' salvati
            d["status"] = existing[d["id"]].get("status", "nuovo")
            d["first_seen"] = existing[d["id"]].get("first_seen", now)
        else:
            d["first_seen"] = now
            new_ids.append(d["id"])
        existing[d["id"]] = d

    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(list(existing.values()), f, ensure_ascii=False, indent=2)

    return new_ids, list(existing.values())
