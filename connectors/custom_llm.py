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
import re
import time
from typing import List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from shared.models import JobPosting
import llm_client

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def _apply_dynamic_filters(page, url: str) -> None:
    if "davinesgroup.com" not in url:
        return

    # Il widget Allibo non riflette filtri e paginazione nell'URL. Il filtro
    # via select non sempre fa refresh, ma la paginazione e' affidabile.
    try:
        page.locator("#cassie-widget").evaluate("node => node.remove()")
    except Exception:
        pass


def _collect_paginated_content(page, url: str, max_pages: int = 10) -> str:
    pages = [page.content()]
    if "davinesgroup.com" not in url:
        return pages[0]

    seen_markers = {_normalize_text(page.locator(".aw_jobPosting").first.inner_text()) if page.locator(".aw_jobPosting").count() else ""}
    for _ in range(max_pages - 1):
        next_link = page.locator("a[id^='pageNavNext']").first
        if not next_link.count():
            break

        try:
            next_link.click(force=True, timeout=5000)
            page.wait_for_timeout(2500)
        except Exception:
            break

        marker = _normalize_text(page.locator(".aw_jobPosting").first.inner_text()) if page.locator(".aw_jobPosting").count() else ""
        if not marker or marker in seen_markers:
            break
        seen_markers.add(marker)
        pages.append(page.content())

    return "\n".join(pages)


def _fetch_with_playwright(url: str, wait_ms: int = 3000) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # --disable-blink-features=AutomationControlled riduce le probabilita'
        # che un sito con protezioni anti-bot (Cloudflare, Akamai...) rilevi
        # subito che si tratta di un browser automatizzato
        browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        try:
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1366, "height": 850},
                locale="it-IT",
                timezone_id="Europe/Rome",
            )
            page = context.new_page()
            page.goto(url, timeout=45000, wait_until="networkidle")
            _apply_dynamic_filters(page, url)
            page.wait_for_timeout(wait_ms)  # margine per eventuali render tardivi via JS
            return _collect_paginated_content(page, url)
        finally:
            browser.close()


def _fetch_with_requests(url: str) -> str:
    resp = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.text


def _fetch_raw_html(url: str) -> str:
    last_error = None
    for attempt in range(2):
        try:
            return _fetch_with_playwright(url)
        except Exception as e:
            last_error = e
            if attempt == 0:
                time.sleep(2)

    print(f"[custom_llm] Playwright fallito per {url} ({last_error}), provo una richiesta HTTP semplice")
    try:
        return _fetch_with_requests(url)
    except Exception as e2:
        print(f"[custom_llm] anche la richiesta HTTP semplice e' fallita per {url}: {e2}")
        return ""


def _normalize_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _clean_html(html: str, max_chars: int = 20000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "svg", "noscript", "head"]):
        tag.decompose()

    priority_selectors = [
        "section.module--search-jobs",
        ".section__content__results",
        ".searchResultsShell",
        "table.searchResults",
        "tr.data-row",
        "ul.cw-jobs",
        "li.cw-job",
        ".aw_jobPosting",
        ".aw_pages",
        "article",
        "[class*=job]",
        "[class*=Job]",
        "[class*=result]",
        "[class*=Result]",
        "a[href*='/job']",
        "a[href*='JobDetail']",
    ]
    snippets = []
    seen = set()
    for selector in priority_selectors:
        for node in soup.select(selector):
            rendered = str(node)
            key = rendered[:500]
            if key in seen:
                continue
            seen.add(key)
            snippets.append(rendered)

    if snippets:
        focused = "\n".join(snippets)
        if len(focused) >= max_chars:
            return focused[:max_chars]
        page_tail = str(soup)
        return (focused + "\n\n--- resto pagina ---\n" + page_tail)[:max_chars]

    return str(soup)[:max_chars]


def fetch_page_content(url: str, max_chars: int = 20000) -> str:
    html = _fetch_raw_html(url)
    if not html:
        return ""
    return _clean_html(html, max_chars=max_chars)


def _near_text(node, selector: str) -> str:
    found = node.select_one(selector)
    return _normalize_text(found.get_text(" ", strip=True)) if found else ""


def _looks_like_job_link(href: str, title: str) -> bool:
    href_lower = (href or "").lower()
    title_lower = (title or "").lower()
    if not title or len(title) < 4:
        return False
    if any(skip in href_lower for skip in ("/content/", "/search/", "locale=", "createjobalert")):
        return False
    return (
        "/job/" in href_lower
        or "jobdetail" in href_lower
        or "jobtitle-link" in title_lower
        or bool(re.search(r"/\d{5,}/?$", href_lower))
    )


def _extract_from_loreal_article(article, page_url: str) -> dict | None:
    title_link = article.select_one(".article__header__text__title a, h3 a, a[href*='JobDetail']")
    if not title_link:
        return None

    title = _normalize_text(title_link.get_text(" ", strip=True).strip('"'))
    href = title_link.get("href") or ""
    if not _looks_like_job_link(href, title):
        return None

    subtitle = _near_text(article, ".article__header__text__subtitle")
    content = _near_text(article, ".article__content")
    article_text = _normalize_text(article.get_text(" ", strip=True))
    location = subtitle
    posted_date = None
    match = re.search(r"Pubblicato\s+([0-9]{1,2}[-/ ][A-Za-z]{3,9}[-/ ][0-9]{4})", article_text, re.I)
    if match:
        posted_date = match.group(1)
        if location:
            location = _normalize_text(re.sub(r"\bPubblicato\s+.*$", "", location, flags=re.I))
        if not location:
            before_date = article_text[: match.start()]
            location = before_date.replace(title, "").strip(" -|")

    return {
        "title": title,
        "location": location,
        "url": urljoin(page_url, href),
        "description": content,
        "posted_date": posted_date,
        "contract_type": None,
    }


def _extract_from_shiseido_row(row, page_url: str) -> dict | None:
    title_link = row.select_one("a.jobTitle-link, a.jobTitle-link-page, .jobTitle a, a[href*='/job/']")
    if not title_link:
        return None

    title = _normalize_text(title_link.get_text(" ", strip=True))
    href = title_link.get("href") or ""
    if not _looks_like_job_link(href, title):
        return None

    location = _near_text(row, ".jobFacility")
    if not location:
        location = _near_text(row, "td.colFacility")
    posted_date = _near_text(row, ".jobDate")
    if not posted_date:
        posted_date = _near_text(row, "td.colDate")

    return {
        "title": title,
        "location": location,
        "url": urljoin(page_url, href),
        "description": "",
        "posted_date": posted_date,
        "contract_type": None,
    }


def _extract_from_beiersdorf_item(item, page_url: str) -> dict | None:
    link = item.select_one("a[href*='/career/jobs/']")
    if not link:
        return None

    title = _near_text(item, ".cw-job-title")
    if not title:
        title = _normalize_text(link.get_text(" ", strip=True).split("|")[0])
    href = link.get("href") or ""
    if not title or not href:
        return None

    spans = [_normalize_text(span.get_text(" ", strip=True)) for span in link.select("span")]
    details = [value for value in spans if value and value != "|" and value != title]
    location_parts = [value for value in details if value.lower() not in {"professional", "hybrid"}]

    return {
        "title": title,
        "location": " / ".join(location_parts),
        "url": urljoin(page_url, href),
        "description": " | ".join(details),
        "posted_date": None,
        "contract_type": next((value for value in details if value.lower() == "professional"), None),
    }


def _extract_from_allibo_posting(posting, page_url: str) -> dict | None:
    title = _near_text(posting, ".aw_title, h3")
    location = _near_text(posting, ".aw_location")
    href = posting.get("data-pv") or posting.get("data-url") or ""
    onclick = posting.get("onclick") or ""
    if not href:
        match = re.search(r"link\s*:\s*'([^']+)'", onclick)
        if match:
            href = match.group(1)
    if not href:
        link = posting.select_one("a[href]")
        href = link.get("href") if link else ""
    if not title or not href:
        return None

    return {
        "title": title,
        "location": location,
        "url": urljoin(page_url, href),
        "description": "",
        "posted_date": None,
        "contract_type": None,
    }


def _extract_jobs_from_html(html: str, page_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    for article in soup.select("article.article--result, article"):
        job = _extract_from_loreal_article(article, page_url)
        if job:
            jobs.append(job)

    for row in soup.select("tr.data-row, table.searchResults tr"):
        job = _extract_from_shiseido_row(row, page_url)
        if job:
            jobs.append(job)

    for item in soup.select("li.cw-job"):
        job = _extract_from_beiersdorf_item(item, page_url)
        if job:
            jobs.append(job)

    for posting in soup.select(".aw_jobPosting"):
        job = _extract_from_allibo_posting(posting, page_url)
        if job:
            jobs.append(job)

    if not jobs:
        for link in soup.select("a[href*='/job/'], a[href*='JobDetail']"):
            title = _normalize_text(link.get_text(" ", strip=True))
            href = link.get("href") or ""
            if _looks_like_job_link(href, title):
                jobs.append(
                    {
                        "title": title,
                        "location": "",
                        "url": urljoin(page_url, href),
                        "description": "",
                        "posted_date": None,
                        "contract_type": None,
                    }
                )

    unique_jobs = []
    seen = set()
    for job in jobs:
        key = (job["title"].lower(), job["url"].lower())
        if key in seen:
            continue
        seen.add(key)
        unique_jobs.append(job)
    return unique_jobs


def _to_postings(jobs_raw: list[dict], company_name: str, fallback_url: str) -> List[JobPosting]:
    postings = []
    for j in jobs_raw:
        job_url = j.get("url") or fallback_url
        if job_url and not job_url.startswith("http"):
            job_url = urljoin(fallback_url, job_url)
        postings.append(
            JobPosting(
                company=company_name,
                title=j.get("title") or "",
                location=j.get("location") or "",
                url=job_url,
                source="custom_llm",
                description=j.get("description") or "",
                contract_type=j.get("contract_type"),
                posted_date=j.get("posted_date"),
            )
        )
    return postings


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
    text = (raw_text or "").strip()
    text = text.removeprefix("```json").removeprefix("```")
    text = text.removesuffix("```")
    return text.strip()


def extract_jobs_with_llm(url: str, company_name: str) -> List[JobPosting]:
    html = _fetch_raw_html(url)
    if not html.strip():
        print(f"[custom_llm] {company_name}: pagina vuota o non raggiungibile ({url})")
        return []

    direct_jobs = _extract_jobs_from_html(html, url)
    if direct_jobs:
        return _to_postings(direct_jobs, company_name, url)

    content = _clean_html(html)
    raw_text = llm_client.complete(_build_extraction_prompt(content), max_tokens=2000)
    cleaned = _clean_json_response(raw_text)

    try:
        jobs_raw = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"[custom_llm] risposta non parsabile come JSON per {company_name}: {cleaned[:200]}")
        return []

    return _to_postings(jobs_raw, company_name, url)
