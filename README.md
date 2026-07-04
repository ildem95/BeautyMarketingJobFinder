# Job tracker beauty & cosmetica

Pipeline che raccoglie annunci di lavoro in ambito marketing/brand nel
settore beauty, li filtra per rilevanza con un LLM, e li mostra in una
dashboard con notifiche Telegram per i nuovi annunci.

## Come funziona (in breve)

1. **GitHub Actions** esegue `main.py` due volte a settimana (lunedi' e
   giovedi').
2. `main.py` raccoglie annunci da:
   - **Adzuna** (API generalista, gratuita)
   - **Google Jobs via SerpApi** (aggrega LinkedIn, Indeed, ecc.)
   - **Connettori ATS diretti** per le aziende gia' mappate in
     `config/companies.py`: Greenhouse, Lever, SmartRecruiters, Workday,
     Workable
   - **Estrazione via LLM** per i siti aziendali "custom" (un browser
     headless apre la pagina, poi Claude legge l'HTML e restituisce gli
     annunci come JSON) — usata per la maggior parte delle 29+ aziende,
     visto che quasi nessuna usa un ATS con API pubblica documentata
3. Gli annunci vengono deduplicati, poi valutati uno per uno da Claude
   Haiku contro il profilo della candidata (`relevance_filter.py`).
4. Il risultato viene salvato in `data/jobs.json` e committato nel repo.
5. Per i nuovi annunci rilevanti parte una notifica Telegram.
6. La **dashboard Streamlit** (`dashboard/app.py`) legge `data/jobs.json`
   e permette di marcare ogni annuncio come nuovo / da vedere / candidata
   / scartato.

## Setup

### 0. Le chiavi API sono gia' pronte per i test in locale

Le chiavi che mi hai passato sono gia' in un file `.env` nella cartella del
progetto (escluso da git tramite `.gitignore`, non finira' mai in un
commit). Manca solo `TELEGRAM_CHAT_ID`: apri una chat con il tuo bot su
Telegram, mandagli un messaggio qualsiasi, poi apri nel browser
`https://api.telegram.org/bot<IL_TUO_TOKEN>/getUpdates` e cerca `"chat":
{"id": ...}` nella risposta — incollalo nel file `.env`.

**Importante**: queste chiavi sono ora anche nella cronologia della
conversazione con Claude. Se in futuro condividi questa chat con qualcuno
o il repo diventa pubblico, rigenerale (sono tutte gratuite e ci vuole un
minuto): Adzuna e SerpApi dal loro pannello, Anthropic da
console.anthropic.com, Telegram parlando di nuovo con @BotFather.

### 1. Crea il repository

Carica tutti questi file su un repository GitHub (va bene anche privato).
Il file `.env` NON va caricato (e' gia' escluso): su GitHub le chiavi
vivono come Secrets (punto 3).

### 2. Procurati le chiavi (se devi rigenerarle)

| Servizio | Dove ottenerla | Note |
|---|---|---|
| Adzuna | https://developer.adzuna.com -> registrati -> App ID + App Key | Gratuito |
| SerpApi | https://serpapi.com -> registrati | Piano gratuito: 250 ricerche/mese |
| Anthropic | https://console.anthropic.com -> API Keys | Costo stimato: sotto 1€/mese per questo volume |
| Telegram | @BotFather su Telegram -> /newbot | Gratuito, opzionale ma consigliato |

### 3. Configura i secrets su GitHub

Nel repository: **Settings -> Secrets and variables -> Actions -> New repository secret**.
Aggiungi (stessi valori del tuo `.env` locale):

- `ADZUNA_APP_ID`
- `ADZUNA_APP_KEY`
- `SERPAPI_KEY`
- `ANTHROPIC_API_KEY`
- `TELEGRAM_BOT_TOKEN` (opzionale)
- `TELEGRAM_CHAT_ID` (opzionale)

### 4. Prova la pipeline

Vai su **Actions -> Aggiorna annunci beauty -> Run workflow** per lanciarla
manualmente la prima volta, invece di aspettare lo schedule. Controlla i
log: se qualcosa va storto per una singola azienda, la pipeline continua
comunque sulle altre fonti e stampa l'errore specifico.

### 5. Completa le aziende ancora da mappare

12 aziende in `config/companies.py` hanno ancora `connector: None`
(Unilever, Revlon, e.l.f. Beauty, Puig, Inter Parfums, Innisfree, Laneige,
Glossier, Too Faced, Rare Beauty, Drunk Elephant, The Ordinary). Stessa
procedura che hai gia' usato per le altre: apri il career site, imposta i
filtri che vuoi, guarda l'URL e il pannello Network delle devtools per
capire se e' un ATS noto o serve il fallback custom_llm.

### 6. Deploya la dashboard

1. Vai su https://share.streamlit.io, collega il tuo account GitHub.
2. Crea una nuova app puntando a questo repo, file `dashboard/app.py`.
3. In **Settings -> Secrets** dell'app Streamlit, aggiungi:
   ```toml
   GITHUB_REPO = "tuo-utente/nome-repo"
   GITHUB_BRANCH = "main"
   GITHUB_TOKEN = "ghp_xxxxxxxxxxxx"
   ```
   Il `GITHUB_TOKEN` serve un Personal Access Token con permesso `repo`
   (Settings -> Developer settings -> Personal access tokens su GitHub),
   necessario perche' la dashboard possa salvare i cambi di stato
   (candidata/scartato) scrivendo di nuovo su `data/jobs.json`.

Da questo momento la dashboard si aggiorna da sola ogni volta che la
pipeline fa un nuovo commit.

## Testare in locale

```bash
pip install -r requirements.txt
playwright install --with-deps chromium   # una tantum, serve al connettore custom_llm
python main.py    # legge automaticamente le chiavi da .env
```

Per testare un singolo connettore senza lanciare tutta la pipeline, da una
shell Python:

```python
from connectors.ats import workable
raw = workable.fetch_workable_jobs("hudabeauty")
print(len(raw), "annunci trovati")
```

## Limiti noti / prossimi passi

- **Rendering JavaScript**: la maggior parte dei siti aziendali mappati
  (Coty, Shiseido, Beiersdorf, Kao, Mary Kay, Clarins, Kering, Collistar,
  Angelini, Sodalis...) carica i risultati via JavaScript, quindi
  `connectors/custom_llm.py` ora usa un browser headless (Playwright) per
  leggerli. E' piu' lento di una richiesta HTTP semplice ma molto piu'
  affidabile; se Playwright fallisce su un sito specifico, il connettore
  ripiega automaticamente su una richiesta HTTP semplice.
- **Workable**: l'API pubblica restituisce sempre TUTTE le posizioni
  dell'azienda (Huda Beauty, Charlotte Tilbury), senza possibilita' di
  filtrare via URL: il filtro lo fa comunque `relevance_filter.py` a valle,
  quindi non e' un problema, solo qualche annuncio in piu' da classificare.
- **Schema Workable non verificato al 100%**: l'API pubblica non ha una
  documentazione dei campi cosi' dettagliata come Greenhouse/Lever. Se dopo
  il primo run reale la sede o il tipo di contratto risultano vuoti per gli
  annunci Workable, guardiamo insieme la risposta JSON grezza.
- **RVB LAB e Diego Dalla Palma Group**: rimosse su tua indicazione.
- **Aziende ancora da mappare**: 12 aziende in `config/companies.py` hanno
  ancora `connector: None` (vedi punto 5 del setup).
- **SmartRecruiters**: l'endpoint di lista non include la descrizione
  completa dell'annuncio (serve una chiamata di dettaglio per singolo
  annuncio, vedi `fetch_posting_detail` in `connectors/ats/smartrecruiters.py`).
