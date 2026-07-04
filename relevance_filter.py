"""
Filtro di rilevanza: invece di un matching rigido per keyword sul titolo
(che tagliava fuori titoli come "Category Manager" o "Responsabile di
Marca"), chiediamo a un LLM economico (Claude Haiku) di valutare ogni
annuncio contro il profilo della candidata e di segnalare esplicitamente
gli stage/tirocini anche quando non compaiono nel titolo.

Costo indicativo: con prompt brevi (~300-500 token di input, ~50-100 di
output a classificazione) e un volume di poche centinaia di annunci al
mese, il costo totale di questo step e' sotto l'euro al mese.

MODIFICA QUI il profilo se le priorita' della candidata cambiano (es. se
si apre anche a Torino/Roma, o se vuole includere ruoli di e-commerce).
"""
import json
import os
from typing import List

from anthropic import Anthropic

from shared.models import JobPosting

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

MODEL = "claude-haiku-4-5-20251001"

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


def _build_classify_prompt(job: JobPosting) -> str:
    description = (job.description or "")[:2000]
    return (
        "Valuta questo annuncio di lavoro rispetto al profilo della candidata.\n\n"
        "PROFILO CANDIDATA:\n" + PROFILE_DESCRIPTION + "\n\n"
        "ANNUNCIO:\n"
        f"Azienda: {job.company}\n"
        f"Titolo: {job.title}\n"
        f"Sede: {job.location}\n"
        f"Descrizione: {description}\n\n"
        "Rispondi SOLO con un JSON in questo formato, senza testo introduttivo "
        "e senza backtick:\n"
        '{"score": 0, "is_stage": false, "reason": "una frase breve in italiano"}\n'
        "score va da 0 (per niente pertinente) a 100 (perfetto). is_stage=true "
        "se e' uno stage/tirocinio/apprendistato, anche se non e' scritto nel titolo."
    )


def _clean_json_response(raw_text: str) -> str:
    text = raw_text.strip()
    text = text.removeprefix("```json").removeprefix("```")
    text = text.removesuffix("```")
    return text.strip()


def classify_job(job: JobPosting) -> dict:
    message = client.messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": _build_classify_prompt(job)}],
    )
    raw_text = "".join(b.text for b in message.content if b.type == "text")
    cleaned = _clean_json_response(raw_text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"[relevance_filter] risposta non parsabile per '{job.title}' @ {job.company}: {cleaned[:200]}")
        return {"score": 0, "is_stage": False, "reason": "errore di parsing della risposta LLM"}


def classify_jobs(jobs: List[JobPosting], min_score: int = 50) -> List[JobPosting]:
    relevant = []
    for job in jobs:
        result = classify_job(job)
        if result.get("is_stage"):
            continue
        job.relevance_score = result.get("score", 0)
        job.relevance_reason = result.get("reason", "")
        if job.relevance_score is not None and job.relevance_score >= min_score:
            relevant.append(job)
    return relevant
