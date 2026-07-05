"""
Punto unico da cui passano tutte le chiamate LLM della pipeline, cosi'
relevance_filter.py e custom_llm.py non devono sapere quale provider e'
effettivamente in uso.

Si sceglie con la variabile d'ambiente LLM_PROVIDER:
  - "anthropic" (default, quello usato finora): Claude Haiku
  - "openrouter": modello configurabile via OPENROUTER_MODEL
    (default: openai/gpt-oss-120b)

Costi indicativi per la stessa quantita' di token (verificati il 4 luglio 2026):
  - Claude Haiku 4.5:          $1.00 / $5.00 per milione di token (input/output)
  - gpt-oss-120b via OpenRouter: ~$0.03-0.05 / ~$0.15-0.24 per milione
    (varia leggermente in base al provider su cui OpenRouter instrada
    la richiesta), quindi circa 15-20 volte piu' economico.

Per passare a OpenRouter: aggiungi OPENROUTER_API_KEY al tuo .env / ai
secrets, poi imposta LLM_PROVIDER=openrouter (stessa modalita': .env in
locale, secret su GitHub Actions). Consiglio: prova prima con
`python debug_companies.py` in locale per verificare che risponda bene,
prima di affidarti al run schedulato.
"""
import os

import requests
from anthropic import Anthropic

# .get() restituisce stringa vuota (non il default) se il secret GitHub Actions
# esiste ma e' vuoto: "or" gestisce sia il caso "non impostato" sia "impostato vuoto"
LLM_PROVIDER = (os.environ.get("LLM_PROVIDER") or "anthropic").lower()

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL") or "openai/gpt-oss-120b"

_anthropic_client = None


def _get_anthropic_client() -> Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _anthropic_client


def complete(prompt: str, max_tokens: int = 1000) -> str:
    """Manda il prompt al provider configurato, restituisce il testo della risposta."""
    if LLM_PROVIDER == "openrouter":
        return _complete_openrouter(prompt, max_tokens)
    return _complete_anthropic(prompt, max_tokens)


def _complete_anthropic(prompt: str, max_tokens: int) -> str:
    client = _get_anthropic_client()
    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in message.content if b.type == "text")


def _complete_openrouter(prompt: str, max_tokens: int) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY mancante (LLM_PROVIDER=openrouter richiede questa chiave)")

    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": OPENROUTER_MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    choice = (data.get("choices") or [{}])[0]
    # alcuni modelli "reasoning" (come gpt-oss) possono restituire content=None
    # in certi casi limite (es. finiscono i token mentre stanno ancora
    # "ragionando"): meglio una stringa vuota che un crash a valle
    content = (choice.get("message") or {}).get("content")
    return content or ""
