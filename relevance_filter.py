"""
Filtro di rilevanza: prima scarta localmente gli annunci chiaramente fuori
profilo, poi chiede a un LLM economico di valutare solo i possibili match.

Il pre-filtro e' volutamente conservativo: deve evitare chiamate LLM inutili
per stage, sedi palesemente fuori target o ruoli non marketing, senza fare
classificazioni fini. Gli annunci ambigui arrivano comunque al modello.

MODIFICA QUI il profilo se le priorita' della candidata cambiano (es. se
si apre anche a Torino/Roma, o se vuole includere ruoli di e-commerce).
"""
import json
import re
from dataclasses import dataclass
from typing import List

from shared.models import JobPosting
import llm_client

PROFILE_DESCRIPTION = """
Candidata con poco piu' di 3 anni di esperienza come Brand Manager / Brand
Specialist nel marketing. Vuole entrare nel settore beauty (cosmetica, cura
dei capelli, skincare, profumeria).

Ruoli target: Brand Manager, Assistant/Junior/Senior Brand Manager, Brand
Specialist, Product Manager, Marketing Manager, Category Manager, Trade
Marketing Manager, Responsabile di Marca, Communication Manager, Digital
Marketing Manager legato a un brand.

NON va bene:
- stage, tirocinio, apprendistato
- ruoli senior/director che richiedono 8-10+ anni di esperienza
- ruoli non di marketing/brand (vendite pure, IT, finance, supply chain)

Sede preferita: Milano, o ibrido/remoto con base a Milano. Altre citta'
italiane vanno bene solo se il ruolo e' particolarmente in linea.
""".strip()

DESCRIPTION_CHARS_FOR_LLM = 4000
PREFILTER_TEXT_CHARS = 3000

TARGET_LOCATION_TERMS = (
    "milano",
    "milan",
    "lombardia",
    "lombardy",
    "italia",
    "italy",
    "italian",
    "remote",
    "remoto",
    "hybrid",
    "ibrido",
    "monza",
    "brianza",
    "legnano",
    "assago",
    "segrate",
    "sesto san giovanni",
    "roma",
    "rome",
    "torino",
    "turin",
    "bologna",
    "firenze",
    "florence",
    "napoli",
    "verona",
    "parma",
    "bergamo",
    "como",
    "varese",
)

FOREIGN_LOCATION_TERMS = (
    "kuala lumpur",
    "malaysia",
    "singapore",
    "hong kong",
    "shanghai",
    "beijing",
    "tokyo",
    "seoul",
    "dubai",
    "riyadh",
    "doha",
    "london",
    "paris",
    "berlin",
    "hamburg",
    "munich",
    "muenchen",
    "frankfurt",
    "amsterdam",
    "rotterdam",
    "brussels",
    "bruxelles",
    "madrid",
    "barcelona",
    "lisbon",
    "zurich",
    "geneva",
    "vienna",
    "warsaw",
    "prague",
    "stockholm",
    "copenhagen",
    "new york",
    "los angeles",
    "san francisco",
    "toronto",
    "mexico city",
    "sao paulo",
    "brazil",
    "australia",
    "united states",
    "usa",
    "uk",
    "united kingdom",
    "germany",
    "france",
    "spain",
    "netherlands",
    "belgium",
    "switzerland",
    "austria",
    "poland",
    "czech",
    "sweden",
    "denmark",
)

TARGET_ROLE_TERMS = (
    "brand manager",
    "brand specialist",
    "brand lead",
    "brand activation",
    "product manager",
    "category manager",
    "marketing manager",
    "trade marketing",
    "digital marketing",
    "growth marketing",
    "communication manager",
    "communications manager",
    "marketing specialist",
    "marketing coordinator",
    "marketing executive",
    "responsabile marketing",
    "responsabile di marca",
    "comunicazione",
    "crm manager",
    "consumer marketing",
    "e-commerce manager",
    "ecommerce manager",
    "social media manager",
    "content manager",
)

BEAUTY_TERMS = (
    "beauty",
    "cosmetic",
    "cosmetica",
    "cosmetici",
    "skincare",
    "skin care",
    "haircare",
    "hair care",
    "profumeria",
    "fragrance",
    "make-up",
    "makeup",
    "dermocosmesi",
    "personal care",
)

NON_TARGET_ROLE_TERMS = (
    "sales assistant",
    "sales associate",
    "store manager",
    "store assistant",
    "retail assistant",
    "beauty advisor",
    "account executive",
    "account manager",
    "business development",
    "field sales",
    "area manager",
    "finance",
    "accountant",
    "controller",
    "legal",
    "hr ",
    "human resources",
    "recruiter",
    "it ",
    "software",
    "engineer",
    "developer",
    "data analyst",
    "supply chain",
    "logistics",
    "operations",
    "warehouse",
    "quality assurance",
    "regulatory affairs",
    "research scientist",
)

INTERNSHIP_PATTERNS = (
    r"\bstage\b",
    r"\btirocin",
    r"\binternship\b",
    r"\bintern\b",
    r"\bstagiaire\b",
    r"\bapprendistat",
    r"\bapprentice",
    r"\bcurricular",
    r"\bextracurricular",
)

TOO_SENIOR_PATTERNS = (
    r"\bdirector\b",
    r"\bhead of\b",
    r"\bvp\b",
    r"\bvice president\b",
    r"\bchief\b",
    r"\bcmo\b",
    r"\bgeneral manager\b",
    r"\b8\+?\s*(years|anni|yrs)\b",
    r"\b9\+?\s*(years|anni|yrs)\b",
    r"\b1[0-9]\+?\s*(years|anni|yrs)\b",
    r"\bat least\s+8\s+(years|yrs)\b",
    r"\balmeno\s+8\s+anni\b",
)


@dataclass
class PrefilterResult:
    should_classify: bool
    reason: str = ""


def _normalize(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _job_text(job: JobPosting, include_description: bool = True) -> str:
    parts = [job.title, job.company, job.location, job.contract_type or ""]
    if include_description:
        parts.append((job.description or "")[:PREFILTER_TEXT_CHARS])
    return _normalize(" ".join(parts))


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def prefilter_job(job: JobPosting) -> PrefilterResult:
    """Decide se vale la pena spendere una chiamata LLM su questo annuncio."""
    title_text = _normalize(job.title)
    location_text = _normalize(job.location)
    full_text = _job_text(job)

    if _matches_any(full_text, INTERNSHIP_PATTERNS):
        return PrefilterResult(False, "stage/tirocinio/apprendistato")

    if _matches_any(title_text, TOO_SENIOR_PATTERNS) or _matches_any(full_text, TOO_SENIOR_PATTERNS[-5:]):
        return PrefilterResult(False, "seniority troppo alta")

    has_target_location = not location_text or _contains_any(location_text, TARGET_LOCATION_TERMS)
    has_foreign_location = _contains_any(location_text, FOREIGN_LOCATION_TERMS)
    if has_foreign_location and not has_target_location:
        return PrefilterResult(False, f"sede fuori target: {job.location}")

    has_target_role = _contains_any(title_text, TARGET_ROLE_TERMS) or _contains_any(full_text, TARGET_ROLE_TERMS)
    has_beauty_context = _contains_any(full_text, BEAUTY_TERMS)
    has_non_target_title = _contains_any(title_text, NON_TARGET_ROLE_TERMS)

    if has_non_target_title and not has_target_role:
        return PrefilterResult(False, "ruolo non marketing/brand")

    if not has_target_role and not has_beauty_context:
        return PrefilterResult(False, "mancano segnali marketing/brand/beauty")

    return PrefilterResult(True)


def should_send_to_llm(job: JobPosting) -> bool:
    return prefilter_job(job).should_classify


def _build_classify_prompt(job: JobPosting) -> str:
    description = (job.description or "")[:DESCRIPTION_CHARS_FOR_LLM]
    return (
        "Valuta questo annuncio di lavoro rispetto al profilo della candidata.\n\n"
        "PROFILO CANDIDATA:\n" + PROFILE_DESCRIPTION + "\n\n"
        "ANNUNCIO:\n"
        f"Azienda: {job.company}\n"
        f"Titolo: {job.title}\n"
        f"Sede: {job.location}\n"
        f"Tipo contratto: {job.contract_type or 'non indicato'}\n"
        f"Descrizione: {description or 'non disponibile'}\n\n"
        "Regole importanti:\n"
        "- Se la sede e' chiaramente fuori Italia/Milano e non e' remoto/ibrido utile, score massimo 30.\n"
        "- Se non e' un ruolo marketing/brand/product/category/communication, score massimo 30.\n"
        "- Se e' stage, tirocinio o apprendistato, is_stage deve essere true.\n"
        "- Usa la descrizione completa quando disponibile, non solo titolo e sede.\n\n"
        "Rispondi SOLO con un JSON in questo formato, senza testo introduttivo "
        "e senza backtick:\n"
        '{"score": 0, "is_stage": false, "reason": "una frase breve in italiano"}\n'
        "score va da 0 (per niente pertinente) a 100 (perfetto). is_stage=true "
        "se e' uno stage/tirocinio/apprendistato, anche se non e' scritto nel titolo."
    )


def _clean_json_response(raw_text: str) -> str:
    text = (raw_text or "").strip()
    text = text.removeprefix("```json").removeprefix("```")
    text = text.removesuffix("```")
    return text.strip()


def classify_job(job: JobPosting) -> dict:
    raw_text = llm_client.complete(_build_classify_prompt(job), max_tokens=300)
    cleaned = _clean_json_response(raw_text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"[relevance_filter] risposta non parsabile per '{job.title}' @ {job.company}: {cleaned[:200]}")
        return {"score": 0, "is_stage": False, "reason": "errore di parsing della risposta LLM"}


def classify_jobs(jobs: List[JobPosting], min_score: int = 50) -> List[JobPosting]:
    relevant = []
    skipped_by_prefilter = 0
    sent_to_llm = 0

    for job in jobs:
        prefilter = prefilter_job(job)
        if not prefilter.should_classify:
            skipped_by_prefilter += 1
            print(f"[relevance_filter] skip pre-LLM '{job.title}' @ {job.company}: {prefilter.reason}")
            continue

        sent_to_llm += 1
        try:
            result = classify_job(job)
        except Exception as e:
            # un errore su un singolo annuncio (rate limit, timeout, chiave
            # mancante...) non deve far perdere tutti gli altri annunci gia' raccolti
            print(f"[relevance_filter] errore nel classificare '{job.title}' @ {job.company}: {e}")
            continue
        if result.get("is_stage"):
            continue
        job.relevance_score = result.get("score", 0)
        job.relevance_reason = result.get("reason", "")
        if job.relevance_score is not None and job.relevance_score >= min_score:
            relevant.append(job)

    print(
        f"[relevance_filter] pre-filtro: {skipped_by_prefilter} scartati, "
        f"{sent_to_llm} inviati al LLM"
    )
    return relevant
