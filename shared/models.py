"""
Schema comune per un annuncio di lavoro, indipendentemente dalla fonte
(Adzuna, Google Jobs, Greenhouse, Lever, SmartRecruiters, Workday, siti custom).

Tutti i connettori in connectors/ restituiscono liste di JobPosting, cosi'
il resto della pipeline (dedup, filtro LLM, storage) lavora sempre sullo
stesso oggetto senza bisogno di conoscere la fonte originale.
"""
from dataclasses import dataclass, asdict
from typing import Optional
import hashlib


@dataclass
class JobPosting:
    company: str
    title: str
    location: str
    url: str
    source: str

    description: str = ""
    contract_type: Optional[str] = None
    posted_date: Optional[str] = None

    # calcolato automaticamente se non fornito: stessa azienda + stesso
    # titolo + stessa sede => stesso id, indipendentemente dalla fonte.
    # E' la chiave usata per la deduplica tra fonti diverse.
    id: str = ""

    # popolati dalle fasi successive della pipeline (relevance_filter, storage)
    relevance_score: Optional[float] = None
    relevance_reason: Optional[str] = None
    first_seen: Optional[str] = None
    status: str = "nuovo"  # nuovo | da_vedere | candidata | scartato

    def __post_init__(self):
        if not self.id:
            self.id = self._make_id()

    def _make_id(self) -> str:
        key = f"{self.company.strip().lower()}|{self.title.strip().lower()}|{self.location.strip().lower()}"
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict:
        return asdict(self)
