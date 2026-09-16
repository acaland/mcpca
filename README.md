# MCPCA — sito di presentazione

Landing page bilingue (italiano, inglese) del plugin Moodle **MCPCA**
(*Moodle Course Authoring con l'assistente AI*), pubblicata su GitHub Pages:

- https://acaland.github.io/mcpca/ (italiano)
- https://acaland.github.io/mcpca/en/ (English)

Il plugin stesso vive in un repository separato e sarà rilasciato con licenza
GPL v3; questo repository contiene solo il sito.

## Struttura

```
build.py                    # Jinja2: templates + content/<lang>.json -> dist/
make_og.py                  # genera le anteprime dei link (static/og-*.png)
content/it.json             # testi italiani (sorgente primaria)
content/en.json             # traduzione inglese, stesse chiavi
templates/base.html.j2      # testata, piede, <head>: condivisi da tutte le pagine
templates/index.html.j2     # home
templates/case-study.html.j2 # il caso reale del corso di Ostetricia
templates/partials/         # macro e sprite delle icone SVG
static/                     # style.css, main.js, favicon.svg, og-*.png
static/case/                # screenshot del caso reale (facoltativi, vedi sotto)
.github/workflows/          # build + deploy su Pages a ogni push su main
```

Le pagine pubblicate sono quattro: `/` e `/en/` per la home, `/case-study/` e
`/en/case-study/` per il caso reale. Per aggiungerne altre basta una voce in
`PAGES` dentro `build.py` e un template che estende `base.html.j2`.

## Screenshot del caso reale

La sezione con le schermate del corso compare **solo se i file esistono**:
`build.py` legge `static/case/` e il template salta le figure mancanti. I nomi
attesi sono elencati in `case.figures.items` nei due file di contenuto
(`course-home.png`, `section-list.png`, `lesson-index.png`, `lesson-video.png`,
`questionbank.png`, `quiz-settings.png`). Mettendo i PNG in quella cartella e
rilanciando `python build.py`, la sezione appare da sola.

Nessun framework, nessun font esterno, nessun tracciamento: HTML, CSS e un
JavaScript minimo (tab e menu mobile), tutto funzionante anche senza JS.

## Sviluppo locale

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python build.py            # genera dist/
python build.py --check    # verifica che en.json rispecchi it.json
python -m http.server -d dist 8000
```

Poi apri http://localhost:8000/ e http://localhost:8000/en/.

## Aggiungere o modificare testi

Tutti i testi stanno nei due file JSON in `content/`. Le chiavi devono
coincidere; `build.py --check` segnala chiavi mancanti o liste di lunghezza
diversa. Entrambe le lingue sono complete: `build.py --check` deve stampare
`en: ok`. La chiave facoltativa `stub_notice` in `en.json` fa comparire un
avviso di "traduzione in arrivo" in cima alla pagina inglese, ed esiste per
pubblicare una lingua ancora incompleta; oggi non è presente.

Dopo aver cambiato i titoli dell'hero o le descrizioni, rigenera le immagini
di anteprima dei link con `python make_og.py`.

## Licenza

Codice (template, CSS, JS, build) con licenza MIT. I testi del sito sono
© Antonio Calanducci. Moodle è un marchio di Moodle Pty Ltd; Microsoft Teams,
Copilot ed Entra ID sono marchi di Microsoft Corporation.
