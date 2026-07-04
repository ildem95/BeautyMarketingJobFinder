"""
Dashboard Streamlit. Pensata per girare su Streamlit Community Cloud
(gratuito), collegata allo stesso repo GitHub che la pipeline aggiorna.

Legge data/jobs.json direttamente da GitHub (raw.githubusercontent.com),
cosi' mostra sempre l'ultima versione committata dal workflow, senza bisogno
di redeploy manuali. Quando l'utente cambia lo stato di un annuncio, la
modifica viene scritta di nuovo su GitHub tramite l'API (serve un token con
permessi di scrittura, salvato nei secrets di Streamlit: vedi README).

Secrets richiesti su Streamlit Cloud (Settings -> Secrets):
    GITHUB_REPO = "tuo-utente/job-tracker-beauty"
    GITHUB_BRANCH = "main"
    GITHUB_TOKEN = "ghp_..."   # personal access token con permesso "repo"
"""
import base64
import json

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Annunci beauty & cosmetica", layout="wide")

GITHUB_REPO = st.secrets.get("GITHUB_REPO", "tuo-utente/job-tracker-beauty")
GITHUB_BRANCH = st.secrets.get("GITHUB_BRANCH", "main")
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
DATA_PATH_IN_REPO = "data/jobs.json"

RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{DATA_PATH_IN_REPO}"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{DATA_PATH_IN_REPO}"

STATUS_OPTIONS = ["nuovo", "da_vedere", "candidata", "scartato"]
STATUS_LABELS = {
    "nuovo": "🆕 Nuovo",
    "da_vedere": "👀 Da vedere",
    "candidata": "✅ Candidata",
    "scartato": "🗑️ Scartato",
}


@st.cache_data(ttl=60)
def load_jobs():
    try:
        resp = requests.get(RAW_URL, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Impossibile caricare gli annunci da GitHub: {e}")
        return []


def save_status(job_id: str, new_status: str, jobs: list) -> None:
    if not GITHUB_TOKEN:
        st.warning("GITHUB_TOKEN non configurato nei secrets di Streamlit: la modifica non verra' salvata in modo permanente.")
        return

    for j in jobs:
        if j["id"] == job_id:
            j["status"] = new_status

    content_bytes = json.dumps(jobs, ensure_ascii=False, indent=2).encode("utf-8")
    b64_content = base64.b64encode(content_bytes).decode("utf-8")

    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    current = requests.get(API_URL, headers=headers, timeout=15).json()
    sha = current.get("sha")

    payload = {
        "message": f"Aggiorna stato annuncio {job_id} -> {new_status}",
        "content": b64_content,
        "sha": sha,
        "branch": GITHUB_BRANCH,
    }
    resp = requests.put(API_URL, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    st.cache_data.clear()


st.title("💄 Annunci beauty & cosmetica")

jobs = load_jobs()
if not jobs:
    st.info("Ancora nessun annuncio raccolto. Aspetta il primo run della pipeline oppure lancialo manualmente da GitHub Actions (tab Actions -> Aggiorna annunci beauty -> Run workflow).")
    st.stop()

df = pd.DataFrame(jobs)

col1, col2, col3 = st.columns(3)
with col1:
    status_filter = st.multiselect(
        "Stato",
        options=STATUS_OPTIONS,
        default=["nuovo", "da_vedere"],
        format_func=lambda s: STATUS_LABELS.get(s, s),
    )
with col2:
    company_filter = st.multiselect("Azienda", options=sorted(df["company"].unique()))
with col3:
    min_score = st.slider("Punteggio minimo di rilevanza", 0, 100, 50)

filtered = df[df["status"].isin(status_filter)] if status_filter else df
if company_filter:
    filtered = filtered[filtered["company"].isin(company_filter)]
if "relevance_score" in filtered.columns:
    filtered = filtered[filtered["relevance_score"].fillna(0) >= min_score]

filtered = filtered.sort_values("first_seen", ascending=False)

st.caption(f"{len(filtered)} annunci mostrati su {len(df)} totali")

for _, row in filtered.iterrows():
    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"**{row['title']}** — {row['company']}")
            st.caption(
                f"{row['location']} · fonte: {row.get('source', '?')} · "
                f"punteggio: {row.get('relevance_score', '?')}/100"
            )
            if row.get("relevance_reason"):
                st.caption(f"_{row['relevance_reason']}_")
            st.markdown(f"[Vai all'annuncio]({row['url']})")
        with c2:
            current_status = row["status"] if row["status"] in STATUS_OPTIONS else "nuovo"
            new_status = st.selectbox(
                "Stato",
                options=STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(current_status),
                format_func=lambda s: STATUS_LABELS.get(s, s),
                key=f"status_{row['id']}",
                label_visibility="collapsed",
            )
            if new_status != row["status"]:
                save_status(row["id"], new_status, jobs)
                st.rerun()
