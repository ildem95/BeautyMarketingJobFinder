"""
Aziende target. Per ognuna serve sapere quale connector usare:

  "smartrecruiters" -> serve: smartrecruiters_id
  "workable"         -> serve: workable_account
  "workday"          -> serve: workday_tenant, workday_site, workday_server,
                        opzionale workday_applied_facets (dict)
  "custom_llm"       -> serve: careers_urls (LISTA di url, anche con un solo
                        elemento) - pagina/e gia' filtrate se possibile,
                        cosi' Claude ha meno contenuto da processare
  None               -> ancora da verificare

Le voci sotto "VERIFICATE A MANO" vengono dalla ricognizione fatta aprendo
ogni career site e controllando il pannello Network/Fetch delle devtools:
- Se il sito espone gia' un ATS noto con URL riconoscibile (workable.com,
  myworkdayjobs.com, smartrecruiters.com...) usiamo il connector dedicato.
- Altrimenti usiamo custom_llm con l'URL di ricerca gia' filtrato che hai
  trovato: molte di queste pagine (Coty, Shiseido, Beiersdorf, Kao, Mary
  Kay, Clarins, Kering, Collistar, Angelini, Sodalis...) caricano i
  risultati via JavaScript, per questo custom_llm.py ora usa un browser
  headless per leggerle (vedi commenti nel file).

RVB LAB, Diego Dalla Palma Group, Innisfree, Laneige, Too Faced, Drunk
Elephant e The Ordinary sono stati rimossi su tua indicazione (i primi due
per scelta, gli altri cinque perche' verificato che non servono / sono
duplicati di gruppi gia' in lista). Aggiunte MiiN Cosmetics e Kering, non
erano nella lista originale.
"""

COMPANIES = [
    # --- Gia' configurate in precedenza ---
    {
        "name": "LVMH (Dior, Guerlain, Benefit, Fenty...)",
        "connector": "smartrecruiters",
        "smartrecruiters_id": "lvmhperfumescosmetics",
        "notes": "Career site della divisione Perfumes & Cosmetics su SmartRecruiters",
    },
    {
        "name": "L'Oreal",
        "connector": "custom_llm",
        "careers_urls": ["https://careers.loreal.com/it_IT/jobs/SearchJobs?3_110_3=18035&3_4_3=485894367,108,485894597,485894559"],
        "notes": "Piattaforma custom, non un ATS standard con API pubblica",
    },
    {
        "name": "Estee Lauder Companies",
        "connector": "custom_llm",
        "careers_urls": ["https://careers.elcompanies.com/careers?domain=elcompanies.com&start=0&location=Milano%2CIT-MI%2CItaly&pid=1168273055416&sort_by=distance&filter_distance=80&filter_include_remote=1&filter_department=Marketing"],
        "notes": "URL corretto (careers.elcompanies.com - jobs.elcompanies.com non risolve, era sbagliato). Piattaforma Eightfold.ai. Copre anche Too Faced, The Ordinary/DECIEM, Dr.Jart+",
    },

    # --- VERIFICATE A MANO (dal documento con gli screenshot devtools) ---
    {
        "name": "Chromavis",
        "connector": "custom_llm",
        "careers_urls": ["https://www.chromavis.com/it/work"],
        "notes": "Sito CSS-based ma renderizzato lato server: il titolo dell'annuncio e' gia' nell'HTML, dovrebbe funzionare bene anche senza JS",
    },
    {
        "name": "Davines Group",
        "connector": "custom_llm",
        "careers_urls": ["https://davinesgroup.com/gruppo-davines/lavora-con-noi"],
        "notes": "Al momento della ricognizione risultava un solo annuncio marketing, non in Italia: aspettati spesso zero risultati rilevanti",
    },
    {
        "name": "Collistar",
        "connector": "custom_llm",
        "careers_urls": [
            "https://jobs.boltongroup.net/search/?createNewAlert=false&q=&locationsearch=&optionsFacetsDD_customfield1=Marketing+%26+Communication&optionsFacetsDD_country=&optionsFacetsDD_city=&optionsFacetsDD_customfield2=Bolton+Home%2C+Personal+Care+%26+Beauty&optionsFacetsDD_customfield5="
        ],
        "notes": "Career site del gruppo Bolton, filtro Marketing & Communication gia' applicato nell'URL",
    },
    {
        "name": "Angelini Beauty",
        "connector": "custom_llm",
        "careers_urls": [
            "https://careers.angelinipharma.com/search/?createNewAlert=false&q=&optionsFacetsDD_customfield2=Commercial%2C+Marketing"
        ],
        "notes": "Filtro Commercial/Marketing gia' applicato nell'URL",
    },
    {
        "name": "Sodalis Group",
        "connector": "custom_llm",
        "careers_urls": [
            "https://careers.sodalisgroup.com/search/?createNewAlert=false&q=marketing&locationsearch=&optionsFacetsDD_city=&optionsFacetsDD_lang="
        ],
        "notes": "Ricerca 'marketing' gia' impostata nell'URL",
    },
    {
        "name": "Coty",
        "connector": "custom_llm",
        "careers_urls": [
            "https://careers.coty.com/search/?createNewAlert=false&q=&optionsFacetsDD_department=Marketing&optionsFacetsDD_country=&optionsFacetsDD_city=&optionsFacetsDD_customfield5="
        ],
        "notes": "Country lasciato su 'All' perche' al momento della ricognizione non c'erano posizioni Marketing in Italia",
    },
    {
        "name": "Shiseido",
        "connector": "custom_llm",
        "careers_urls": [
            "https://careers.shiseido.com/search/?createNewAlert=false&q=marketing&locationsearch=italy&optionsFacetsDD_country=&optionsFacetsDD_customfield4=&optionsFacetsDD_customfield3="
        ],
        "notes": "Ricerca 'marketing' + sede Italy gia' impostate nell'URL. Copre probabilmente anche Drunk Elephant",
    },
    {
        "name": "Beiersdorf",
        "connector": "custom_llm",
        "careers_urls": [
            "https://www.beiersdorf.com/career/your-application/job-search?level=Professional&country=France%2CGermany%2CItaly%2CSpain&function=Marketing%20%2F%20Market%20Research&count=10&sort=date"
        ],
        "notes": "Filtro su Francia/Germania/Italia/Spagna + funzione Marketing gia' impostato nell'URL",
    },
    {
        "name": "Kao Corporation",
        "connector": "custom_llm",
        "careers_urls": [
            "https://kao.voyse.io/en/?keywords=&category=Marketing&locationLabel=&seniorityType=&nestedLocationSearch=true&locationGeo=9.1113509617797&locationGeo=45.4542119&locationGeoSearchInput=Milan,%20Italy&distance=100",
            "https://kao.voyse.io/en/?keywords=&category=Marketing&locationLabel=&seniorityType=&nestedLocationSearch=true&locationGeo=12.4829321&locationGeo=41.8933203&locationGeoSearchInput=Rome,%20Roma%20Capitale,%20Italy&distance=100",
        ],
        "notes": "Due URL: ricerca su Milano e su Roma, entrambe con categoria Marketing gia' impostata",
    },
    {
        "name": "Mary Kay",
        "connector": "custom_llm",
        "careers_urls": ["https://marykay.referrals.selectminds.com/et/RjbtFNK1/landingpages/marketing-opportunities-at-mary-kay-17"],
        "notes": "Landing page gia' dedicata alle opportunita' di marketing",
    },
    {
        "name": "Clarins",
        "connector": "custom_llm",
        "careers_urls": ["https://www.groupeclarins.com/job-offers/?txt=&functions%5B%5D=7485"],
        "notes": "Filtro per funzione (id 7485 = presumibilmente Marketing/Communication) gia' impostato nell'URL",
    },
    {
        "name": "Huda Beauty",
        "connector": "workable",
        "workable_account": "hudabeauty",
        "notes": "API pubblica Workable: restituisce tutte le posizioni, il filtro per reparto non e' passabile via URL quindi filtriamo lato nostro",
    },
    {
        "name": "Charlotte Tilbury Beauty",
        "connector": "workable",
        "workable_account": "charlotte-tilbury",
        "notes": "Stessa piattaforma di Huda Beauty (Workable). Alla ricognizione risultavano 2 annunci di tipo marketing",
    },
    {
        "name": "Aesop",
        "connector": "workday",
        "workday_tenant": "aesop",
        "workday_site": "aesopcareers",
        "workday_server": "wd3",
        "workday_applied_facets": {"jobFamilyGroup": ["ee02a196cfd8013dc160e11c7432b356"]},
        "notes": "Facet jobFamilyGroup preso dalla query string dell'URL trovato durante la ricognizione (probabile categoria Marketing)",
    },

    # --- Aggiunte non presenti nella lista originale ---
    {
        "name": "MiiN Cosmetics",
        "connector": "custom_llm",
        "careers_urls": ["https://empleos.miin-cosmetics.com/jobs?location=&subcategory=marketing&aggregation_id="],
        "notes": "Aggiunta durante la ricognizione. Filtro sottocategoria marketing gia' impostato nell'URL",
    },
    {
        "name": "Kering",
        "connector": "custom_llm",
        "careers_urls": ["https://www.kering.com/it/talenti/offerte-di-lavoro/?countriesList=Italy&jobFamiliesList=Communication_%26_Marketing"],
        "notes": "Aggiunta durante la ricognizione (non era nella lista originale). Filtro Italia + Communication & Marketing gia' impostato",
    },

    # --- Trovate con ricerca web (non richiedono verifica manuale delle devtools) ---
    {
        "name": "Unilever (Dove, TRESemme, Simple...)",
        "connector": "workday",
        "workday_tenant": "unilever",
        "workday_site": "Unilever_Experienced_Professionals",
        "workday_server": "wd3",
        "workday_search_text": "Marketing",
        "notes": "Trovato via ricerca web, non verificato con devtools: se restituisce 0 o errori, va controllato il tenant/site esatto aprendo il sito",
    },
    {
        "name": "e.l.f. Beauty",
        "connector": "lever",
        "lever_slug": "elfbeauty",
        "notes": "Trovato via ricerca web. Azienda USA, aspettati poche/nessuna posizione Italia ma qualche ruolo remoto potrebbe comparire",
    },
    {
        "name": "Glossier",
        "connector": "greenhouse",
        "greenhouse_board_token": "glossier",
        "notes": "Trovato via ricerca web. Azienda USA, stesso discorso di e.l.f. Beauty",
    },
    {
        "name": "Revlon",
        "connector": "greenhouse",
        "greenhouse_board_token": "revloncorporate",
        "notes": "Trovato via ricerca web (board 'revloncorporate'). Nota: la divisione hair tools di Revlon e' passata a Helen of Troy con career site separato, non coperto qui",
    },
    {
        "name": "Puig",
        "connector": "custom_llm",
        "careers_urls": ["https://careers.puig.com/en/opportunities", "https://careers.puig.com/opportunities?q=brand+manager", "https://careers.puig.com/opportunities?q=&country=9888&workArea=9249", "https://careers.puig.com/opportunities?q=&country=9888&workArea=9258"],
        "notes": "Trovato via ricerca web, piattaforma non identificata con certezza (probabile SuccessFactors), usa il fallback custom_llm. Copre probabilmente anche Charlotte Tilbury",
    },
    {
        "name": "Inter Parfums",
        "connector": "custom_llm",
        "careers_urls": ["https://www.interparfumsinc.com/openpositions"],
        "notes": "Trovato via ricerca web, sito custom (sembra Wix)",
    },
    {
        "name": "Rare Beauty",
        "connector": "custom_llm",
        "careers_urls": ["https://careers.jobscore.com/careers/rarebeauty"],
        "notes": "Trovato via ricerca web (piattaforma JobScore). Al momento della ricerca risultava senza posizioni aperte",
    },

]
