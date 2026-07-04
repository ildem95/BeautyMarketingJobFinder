"""
Deduplica annunci arrivati da fonti diverse (es. stesso annuncio trovato
sia via Google Jobs sia via il connettore ATS diretto).

La chiave e' JobPosting.id, calcolato da azienda + titolo + sede normalizzati
(vedi shared/models.py) - non l'URL, perche' lo stesso annuncio ha quasi
sempre URL diversi a seconda della fonte che lo pubblica.
"""
from typing import List

from shared.models import JobPosting


def deduplicate(jobs: List[JobPosting]) -> List[JobPosting]:
    seen = {}
    for job in jobs:
        existing = seen.get(job.id)
        if existing is None:
            seen[job.id] = job
        elif len(job.description or "") > len(existing.description or ""):
            # se troviamo lo stesso annuncio con una descrizione piu' ricca
            # (es. dal connettore ATS diretto invece che da Google Jobs),
            # teniamo quella versione
            seen[job.id] = job
    return list(seen.values())
