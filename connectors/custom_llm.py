"""
Fallback universale per i siti aziendali che non usano un ATS con API
pubblica nota. Invece di un parser HTML diverso per ogni sito, passiamo il
contenuto della pagina a Claude e gli chiediamo di restituire gli annunci
come JSON strutturato.

AGGIORNAMENTO dopo la ricognizione fatta a mano sui career site reali:
la maggior parte di questi siti (Coty, Shiseido, Beiersdorf, Kao, Mary Kay,
Clarins, Kering, Collistar, Angelini, Sodalis...) carica i risultati via
JavaScript dopo il caricamento iniziale della pagina (si vede dalle
chiamate fetch/xhr nel pannello Network). Una richiesta HTTP semplice
(requests.get) tornerebbe quindi una pagina vuota o incompleta.

Per questo il fetch di default usa un browser headless (Playwright): apre
la pagina, aspetta che la rete si calmi, e legge l'HTML gia' renderizzato.
Se Playwright fallisce per qualche motivo (sito che blocca i browser
automatizzati, timeout...) si tenta comunque una richiesta HTTP semplice
come ultima spiaggia, utile per i pochi siti gia' statici (es. Chromavis,
dove il titolo dell'annuncio e' gia' nell'HTML servito dal server).
"""
import json
import os
from typing import List
from urllib.parse import urljoin

import requests
from anthropic import Anthropic
from bs4 import BeautifulSoup

from shared.models import JobPosting

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

MODEL = "claude-haiku-4-5-20251001"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def _fetch_with_playwright(url: str, wait_ms: int = 2500) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, timeout=45000, wait_until="networkidle")
            page.wait_for_timeout(wait_ms)  # margine per eventuali render tardivi via JS
            return page.content()
        finally:
            browser.close()


def _fetch_with_requests(url: str) -> str:
    resp = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.text


def _clean_html(html: str, max_chars: int = 20000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "svg", "noscript", "head"]):
        tag.decompose()
    return str(soup)[:max_chars]


def fetch_page_content(url: str, max_chars: int = 20000) -> str:
    try:
        html = _fetch_with_playwright(url)
    except Exception as e:
        print(f"[custom_llm] Playwright fallito per {url} ({e}), provo una richiesta HTTP semplice")
        try:
            html = _fetch_with_requests(url)
        except Exception as e2:
            print(f"[custom_llm] anche la richiesta HTTP semplice e' fallita per {url}: {e2}")
            return ""
    return _clean_html(html, max_chars=max_chars)


def _build_extraction_prompt(content: str) -> str:
    # Costruito per concatenazione (non .format()/f-string sull'esempio JSON)
    # apposta: le parentesi graffe dell'esempio andrebbero in conflitto col templating.
    return (
        'Sei un estrattore di dati. Ti passo l\'HTML (ripulito da script e stili) di una '
        "pagina di ricerca annunci di lavoro di un'azienda del settore beauty/cosmetica. "
        "Estrai TUTTI gli annunci di lavoro visibili nella pagina, seguendo gli attributi "
        "href dei link per ricostruire l'URL di ciascun annuncio quando possibile.\n\n"
        "Rispondi SOLO con un array JSON valido, senza testo introduttivo e senza "
        "backtick, in questo formato:\n"
        '[{"title": "...", "location": "...", "url": "...", "contract_type": "..."}]\n\n'
        "Se un campo non e' disponibile usa null. Se non trovi nessun annuncio (pagina "
        "vuota, nessun risultato, o pagina di errore), rispondi con [].\n\n"
        "Contenuto pagina:\n---\n" + content + "\n---\n"
    )


def _clean_json_response(raw_text: str) -> str:
    text = raw_text.strip()
    text = text.removeprefix("```json").removeprefix("```")
    text = text.removesuffix("```")
    return text.strip()


def extract_jobs_with_llm(url: str, company_name: str) -> List[JobPosting]:
    content = fetch_page_content(url)
    if not content.strip():
        return []

    message = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": _build_extraction_prompt(content)}],
    )
    raw_text = "".join(block.text for block in message.content if block.type == "text")
    cleaned = _clean_json_response(raw_text)

    try:
        jobs_raw = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"[custom_llm] risposta non parsabile come JSON per {company_name}: {cleaned[:200]}")
        return []

    postings = []
    for j in jobs_raw:
        job_url = j.get("url") or url
        if job_url and not job_url.startswith("http"):
            job_url = urljoin(url, job_url)
        postings.append(
            JobPosting(
                company=company_name,
                title=j.get("title") or "",
                location=j.get("location") or "",
                url=job_url,
                source="custom_llm",
                contract_type=j.get("contract_type"),
            )
        )
    return postings
