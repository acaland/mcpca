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

Nessun framework, nessun tracciamento e nessuna richiesta a terzi: HTML, CSS e
un JavaScript minimo (tab, menu mobile, parola che ruota nel titolo), tutto
funzionante anche senza JS.

## Font

Inter per il testo e Source Serif 4 per i titoli grandi, **ospitati in locale**
in `static/fonts/` con le `@font-face` in `static/fonts.css`. Entrambi hanno
licenza SIL Open Font License 1.1 (`static/fonts/OFL.txt`). Si riscaricano con:

```bash
python make_fonts.py
```

Sono in locale di proposito: un `<link>` a Google Fonts passerebbe l'indirizzo
IP di ogni visitatore a un terzo, e la pagina dichiara di non farlo.

## Evidenziazioni nei testi

I contenuti sono testo semplice, ma accettano quattro marcatori che il build
converte in HTML (`build.py`, funzione `rich`):

| Marcatore | Risultato | Quando usarlo |
|---|---|---|
| `**testo**` | grassetto | il termine portante di un paragrafo |
| `_testo_` | corsivo | un inciso, una precisazione |
| `==testo==` | evidenziato in accento | la frase che deve fermare l'occhio |
| `` `testo` `` | monospaziato | un nome di file, un comando, SQL |
| `[[MCPCA]]` | nome del progetto in evidenza | la prima menzione in una pagina, non tutte |
| `[testo](https://…)` | collegamento | l'unico HTML ammesso nei contenuti, solo http/https |

Servono a spezzare i blocchi lunghi. Non è Markdown completo ed è voluto:
nessun HTML nei file di contenuto, quindi nessun link o markup arbitrario.
I marcatori non vanno usati nei campi `meta`, che finiscono negli attributi e
nelle anteprime dei link.

## Chat di esempio con output formattato

Un messaggio nelle chat può avere `text` (una frase) oppure `blocks`, per
mostrare come l'assistente risponde davvero in Markdown:

```json
{"role": "agent", "tools": ["create_quiz"], "blocks": [
  {"type": "title", "text": "Fatto."},
  {"type": "ul", "items": ["prima voce", "seconda voce"]},
  {"type": "table", "head": ["Domanda", "Esito"], "rows": [["4", "errata"]]},
  {"type": "note", "text": "Lo rendo visibile?"}
]}
```

Tipi disponibili: `p`, `title`, `ul`, `ol`, `table`, `note`.

## Sviluppo locale

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python build.py            # genera dist/
python build.py --check    # verifica che en.json rispecchi it.json
python -m http.server -d dist 8000
```

Poi apri http://localhost:8000/ e http://localhost:8000/en/.

## Rileggere e correggere i testi

Il JSON resta la fonte di verità, ma non è il posto dove rileggere della prosa.
`content.py` esporta i testi in un foglio Markdown, si corregge quello e le
modifiche tornano indietro:

```bash
python content.py export                 # review/it.md, tutti i campi
python content.py export --lang both     # italiano e inglese affiancati
python content.py export --lang it --prose   # solo i testi lunghi (115 campi invece di 519)
python content.py import review/it.md --dry-run
python content.py import review/it.md
```

Il foglio ha un solo elemento di struttura, una riga `@ nome` davanti a ogni
campo; sotto c'è il testo, e **gli a capo non contano**: si può mandare a capo
dove si vuole, l'importazione ricompone la riga. I titoli `#` e `##` dicono a
che punto del contenuto ci si trova e servono allo script per rimettere le cose
al loro posto.

```markdown
## usecases.tabs[1].items[5] — Quando questa figura non c'è

@ title
Quando questa figura non c'è

@ text
È il caso più frequente. Le stesse domande — quali obiettivi, quali
prerequisiti, come si verifica — può porle l'assistente al docente.
```

L'importazione **non può aggiungere né togliere campi**: può solo cambiare il
testo di quelli che esistono già. Prima di scrivere controlla che i marcatori
siano chiusi, che i link abbiano la forma `[testo](https://…)`, che nessun campo
sia rimasto vuoto e che non finiscano marcatori nei campi `meta` né in quelli
che il template ripete dentro un attributo (`alt`, `window_title`,
`usecases.title`, `tech.title`, `hero.flow.caption`, `nav.menu_label`); se
qualcosa non va non tocca il JSON e dice cosa correggere. Il diff sul JSON risulta quindi
limitato alle righe davvero cambiate.

Restano fuori dal foglio i campi che non sono prosa: nomi di icone,
identificativi, nomi degli strumenti MCP, percorsi dei file. L'albero di
cartelle di Moodlecraft viaggia dentro un blocco ``` e conserva gli
allineamenti. `python content.py roundtrip` verifica che andata e ritorno non
perdano nulla.

La cartella `review/` è ignorata da git: i fogli si rigenerano quando servono.

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


## Farsi trovare

Il build genera `sitemap.xml` (tutte le pagine, con i rimandi fra le lingue) e
un `robots.txt`; ogni pagina ha canonical, `hreflang` e dati strutturati
JSON-LD. Lighthouse dà 100 su 100 in tutte e quattro le categorie.

Questo però non basta a comparire su Google: un sito su un sottopercorso di
`github.io`, senza link in entrata, può non essere scoperto per settimane.
I passi che restano, e che richiedono l'account di Antonio:

1. **Google Search Console** → aggiungi una proprietà di tipo *Prefisso URL*
   con `https://acaland.github.io/mcpca/`. Per la verifica scegli *file HTML*:
   scarica il `google….html` che ti propone, mettilo in `static/` e ricostruisci
   (finisce in `https://acaland.github.io/mcpca/google….html`). In alternativa
   passa il meta tag e lo aggiungo in `templates/base.html.j2`.
2. Verificata la proprietà, invia `sitemap.xml` e usa *Controllo URL →
   Richiedi indicizzazione* sulle due pagine principali.
3. **Link in entrata**: sono ciò che fa davvero muovere l'indicizzazione.
   I più facili sono il README del repository del plugin, il profilo GitHub
   (`acaland/acaland`) e il sito personale `acaland.github.io`.

### Dominio personalizzato

Per poter dettare l'indirizzo a voce conviene un dominio breve (al momento
risultano liberi `mcpca.it`, `mcpca.eu`, `moodlemcp.it`). Servono tre cose:

1. `SITE_URL` in `build.py` e il file `static/CNAME` con il dominio;
2. dal registrar: quattro record A verso `185.199.108–111.153` (e i rispettivi
   AAAA), oppure un CNAME verso `acaland.github.io` per un sottodominio;
3. su GitHub, *Settings → Pages → Custom domain*, poi *Enforce HTTPS*.

Dopo il cambio vanno rigenerate le anteprime (`python make_og.py`) e il QR,
perché contengono l'indirizzo assoluto.

### QR

`static/qr.png` punta alla home ed è pubblicato su
`https://acaland.github.io/mcpca/static/qr.png`. Serve per slide e locandine,
quando l'indirizzo va mostrato invece che dettato. Si rigenera con:

```bash
python -c "import segno; segno.make('https://acaland.github.io/mcpca/', error='h').save('static/qr.png', scale=10, border=3, dark='#0e7490', light='white')"
```
