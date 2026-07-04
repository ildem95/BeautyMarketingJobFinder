"""
Notifica su Telegram quando la pipeline trova annunci nuovi.

Setup (5 minuti):
  1. Su Telegram, cerca @BotFather, manda /newbot e segui le istruzioni:
     ottieni un TELEGRAM_BOT_TOKEN.
  2. Apri una chat con il bot appena creato e mandagli un messaggio
     qualsiasi (es. "ciao").
  3. Vai su https://api.telegram.org/bot<IL_TUO_TOKEN>/getUpdates nel
     browser: nel JSON trovi "chat": {"id": ...} -> quello e' il
     TELEGRAM_CHAT_ID.
  4. Salva entrambi come secret nel repo GitHub (vedi README).
"""
import os

import requests

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def send_telegram_message(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("[notify_telegram] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID non configurati, salto la notifica.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=15,
    )
    resp.raise_for_status()


def notify_new_jobs(jobs: list) -> None:
    """jobs: lista di dict (come salvati in data/jobs.json)."""
    if not jobs:
        return

    lines = [f"<b>{len(jobs)} nuovi annunci trovati</b>"]
    for j in jobs[:15]:
        lines.append(
            f"\n• <b>{j['title']}</b> — {j['company']} ({j['location']})\n"
            f"  {j['url']}\n"
            f"  punteggio: {j.get('relevance_score', '?')}/100"
        )
    if len(jobs) > 15:
        lines.append(f"\n...e altri {len(jobs) - 15}. Vedi la dashboard per la lista completa.")

    send_telegram_message("\n".join(lines))
