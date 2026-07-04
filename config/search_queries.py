"""
Query per le fonti generaliste (Adzuna, Google Jobs via SerpApi).

Tenerle volutamente larghe: il filtro di rilevanza con l'LLM
(relevance_filter.py) si occupa di scartare quello che non e' pertinente,
quindi qui e' meglio pescare largo piuttosto che perdere annunci buoni per
una keyword mancante.

Attenzione al budget SerpApi (piano gratuito: 250 ricerche/mese): con lo
schedule di default (2 run a settimana, vedi .github/workflows/scrape.yml)
questa lista da 4 query = circa 32 ricerche/mese, ben sotto la soglia.
Se ne aggiungi altre, ricontrolla i conti.
"""

ADZUNA_QUERIES = [
    "brand manager",
    "marketing manager cosmetics",
    "brand specialist",
    "product manager beauty",
]

GOOGLE_JOBS_QUERIES = [
    "brand manager beauty Milano",
    "marketing manager cosmetici Milano",
    "category manager beauty Milano",
    # Query mirata per isolare annunci pubblicati su LinkedIn (via indicizzazione Google)
    "brand manager site:linkedin.com/jobs/view Milano",
]
