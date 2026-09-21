#!/usr/bin/env python3
"""Esporta i testi del sito in Markdown per la revisione, e li riporta nel JSON.

    python content.py export                 # scrive review/it.md
    python content.py export --lang both     # italiano e inglese affiancati
    python content.py import review/it.md --dry-run
    python content.py import review/it.md
    python content.py roundtrip              # verifica che l'andata e ritorno non perda nulla

Il JSON resta l'unica fonte di verità: il Markdown è un foglio di lavoro che si
rigenera quando serve. L'importazione non può aggiungere né togliere campi, può
soltanto cambiare il testo di quelli che esistono già.

Nel Markdown ogni campo è preceduto da una riga «@ nome». Tutto ciò che sta fra
un marcatore e il successivo è il testo, e gli a capo non contano: si può
mandare a capo dove si vuole, l'importazione ricompone la riga. Fanno eccezione
i blocchi in ``` (l'albero di cartelle di Moodlecraft), che restano come sono.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
REVIEW = ROOT / "review"

# Campi che non sono testo da rileggere: nomi di icone, identificativi, nomi di
# strumenti MCP, percorsi di file. Restano nel JSON e non compaiono nel foglio.
SKIP_KEYS = {"icon", "id", "type", "role", "file", "href", "tools",
             "wide", "correct", "og_locale", "user", "domains"}
SKIP_PATHS = {"lang", "dir"}
# Liste da preservare carattere per carattere: gli allineamenti contano.
VERBATIM_KEYS = {"tree"}
# Da questi campi i marcatori vanno tenuti fuori: finiscono negli attributi HTML
# e nelle anteprime dei link.
PLAIN_PREFIXES = ("meta.",)
# Testi che il template ripete dentro un attributo (alt, aria-label): un
# marcatore vi genererebbe tag HTML in mezzo alle virgolette.
ATTRIBUTE_PATHS = {"usecases.title", "tech.title", "hero.flow.caption", "nav.menu_label"}
ATTRIBUTE_KEYS = {"alt", "window_title"}

# Una pagina del sito per foglio. Il caso reale vive tutto sotto «case»; menu,
# piede e marchio sono condivisi e stanno con la home.
PAGES = {
    "home": lambda top: top != "case",
    "caso": lambda top: top == "case",
    "tutto": lambda top: True,
}
PAGE_PREFIX = {"home": "", "caso": "caso-", "tutto": "tutto-"}

MARKER_LINE = re.compile(r"^@ ([A-Za-z_]\w*(?:\[\d+\])*)(?: \[(it|en)\])?\s*$")
HEADING2 = re.compile(r"^## ([\w.\[\]]+)")
LINKISH = re.compile(r"\[[^\[\]]+\]\([^)]*\)")
GOOD_LINK = re.compile(r"\[[^\[\]]+\]\(https?://[^\s)]+\)")


# ----------------------------------------------------------------- struttura --
def leaves(node, path=""):
    """Percorre l'albero e restituisce (percorso_contenitore, nome, valore)."""
    if isinstance(node, dict):
        for k, v in node.items():
            sub = f"{path}.{k}" if path else k
            if k in SKIP_KEYS or sub in SKIP_PATHS:
                continue
            if isinstance(v, list) and k in VERBATIM_KEYS:
                yield path, k, v
                continue
            if isinstance(v, (dict, list)):
                yield from leaves(v, sub)
            elif isinstance(v, str):
                yield path, k, v
    elif isinstance(node, list):
        for i, v in enumerate(node):
            sub = f"{path}[{i}]"
            if isinstance(v, (dict, list)):
                yield from leaves(v, sub)
            elif isinstance(v, str):
                # lista di stringhe: il contenitore è chi possiede la lista
                head, _, name = path.rpartition(".")
                yield head, f"{name}[{i}]", v


def top_of(container: str, name: str) -> str:
    return container.split(".")[0].split("[")[0] if container else name


def scoped(data, page: str):
    keep = PAGES[page]
    return ((c, n, v) for c, n, v in leaves(data) if keep(top_of(c, n)))


def get_in(data, container: str, name: str):
    node, key = descend(resolve(data, container), name)
    return node[key]


def set_in(data, container: str, name: str, value) -> None:
    node, key = descend(resolve(data, container), name)
    node[key] = value


def resolve(data, container: str):
    node = data
    if not container:
        return node
    for part in container.split("."):
        node, key = descend(node, part)
        node = node[key]
    return node


def descend(node, name: str):
    """Scende fino al penultimo passo e restituisce (contenitore, ultima chiave)."""
    key, *idx = split_name(name)
    for i in idx[:-1] if idx else []:
        node = node[key] if key is not None else node
        node, key = node[i], None
    if idx:
        node = node[key] if key is not None else node
        return node, idx[-1]
    return node, key


def split_name(name: str):
    m = re.fullmatch(r"(\w+)((?:\[\d+\])*)", name)
    if not m:
        return name, 
    idx = [int(n) for n in re.findall(r"\[(\d+)\]", m.group(2))]
    return (m.group(1), *idx)


def hint_for(data, container: str) -> str:
    """Una parola di contesto accanto al percorso, per capire cosa si sta leggendo."""
    if not container:
        return ""
    try:
        node = resolve(data, container)
    except (KeyError, IndexError, TypeError):
        return ""
    if isinstance(node, dict):
        for key in ("title", "label", "term", "q", "k", "window_title"):
            v = node.get(key)
            if isinstance(v, str) and v.strip():
                return re.sub(r"[*=`\[\]]", "", v)[:60]
    return ""


# --------------------------------------------------------------- esportazione --
def render(langs: list[str], data: dict[str, dict], minchars: int = 0,
           page: str = "home") -> str:
    base = data[langs[0]]
    out: list[str] = [
        f"<!-- generato da content.py · lingue: {', '.join(langs)} · pagina: {page}"
        f"{' · parziale' if minchars else ''} -->",
        "<!-- si modifica solo il testo sotto i marcatori @; i titoli ## e i",
        "     marcatori @ servono allo script per rimettere tutto al suo posto -->",
        "",
    ]
    section = None
    container_now = object()

    for container, name, value in scoped(base, page):
        if minchars and (isinstance(value, list) or len(value) < minchars):
            continue
        top = container.split(".")[0].split("[")[0] if container else name
        fresh = False
        if top != section:
            section = top
            container_now = section if container == section else object()
            out += ["", f"# {section}", ""]
            fresh = True
        if container != container_now:
            container_now = container
            # subito dopo il titolo di sezione il contenitore è già quello
            # giusto: ripeterlo sarebbe rumore
            if container and not (fresh and container == section):
                hint = hint_for(base, container) if container.endswith("]") else ""
                out.append(f"## {container}" + (f" — {hint}" if hint else ""))
                out.append("")
        for lang in langs:
            try:
                value = get_in(data[lang], container, name)
            except (KeyError, IndexError):
                value = None
            tag = f" [{lang}]" if len(langs) > 1 else ""
            out.append(f"@ {name}{tag}")
            if value is None:
                out += ["<!-- MANCANTE -->", ""]
            elif isinstance(value, list):
                out += ["```", *value, "```", ""]
            else:
                out += [value, ""]
    return "\n".join(out).replace("\n\n\n", "\n\n") + "\n"


def cmd_export(args) -> int:
    langs = ["it", "en"] if args.lang == "both" else [args.lang]
    data = {l: json.loads((CONTENT / f"{l}.json").read_text(encoding="utf-8"))
            for l in ("it", "en")}
    REVIEW.mkdir(exist_ok=True)
    minchars = args.min_chars if args.prose else 0
    suffix = "-prosa" if minchars else ""
    name = f"{PAGE_PREFIX[args.page]}{'-'.join(langs)}{suffix}.md"
    out = Path(args.out) if args.out else REVIEW / name
    text = render(langs, data, minchars, args.page)
    out.write_text(text, encoding="utf-8")
    fields = sum(1 for line in text.splitlines() if line.startswith("@ ")) // len(langs)
    shown = out.resolve().relative_to(ROOT) if out.resolve().is_relative_to(ROOT) else out
    print(f"{shown}: {fields} campi, {len(langs)} lingua/e, "
          f"{out.stat().st_size // 1024} KB")
    return 0


# -------------------------------------------------------------- importazione --
HEADER_LANGS = re.compile(r"<!-- generato da content\.py · lingue: ([a-z, ]+?)"
                          r"(?: · pagina: (\w+))?( · parziale)? -->")


def parse(text: str):
    """Legge il foglio: restituisce {(lingua, contenitore, nome): valore}."""
    values, errors = {}, []
    header = HEADER_LANGS.search(text)
    if not header:
        errors.append("manca l'intestazione generata da content.py: non so di che lingua si tratta")
        return values, errors
    default_lang = header.group(1).split(",")[0].strip()
    # i fogli generati prima delle pagine contenevano tutto il sito
    page = header.group(2) or "tutto"
    if page not in PAGES:
        errors.append(f"pagina sconosciuta nell'intestazione: {page}")
        return values, errors
    values[("__partial__", "", "")] = bool(header.group(3))
    values[("__page__", "", "")] = page
    container, marker, buf, fence = "", None, [], False

    def flush():
        if marker is None:
            return
        lang, cont, name = marker
        body = [l for l in buf if l.strip()]
        if body and body[0].strip().startswith("```"):
            # blocco recintato: si preserva riga per riga, spazi compresi
            value = [l for l in body if not l.strip().startswith("```")]
        else:
            value = re.sub(r"\s+", " ", " ".join(l.strip() for l in body)).strip()
        values[(lang, cont, name)] = value

    for n, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("```"):
            fence = not fence
            buf.append(line)
            continue
        if not fence:
            m = MARKER_LINE.match(line)
            if m:
                flush()
                name, lang = m.group(1), m.group(2) or default_lang
                marker, buf = (lang, container, name), []
                continue
            h = HEADING2.match(line)
            if h:
                flush()
                container, marker, buf = h.group(1), None, []
                continue
            if line.startswith("# "):
                # inizio sezione: i campi che seguono stanno in cima ad essa,
                # finché un titolo ## non scende più in basso
                flush()
                container, marker, buf = line[2:].strip(), None, []
                continue
            if line.startswith("<!--"):
                continue
        if marker is not None:
            buf.append(line)
    flush()

    # i blocchi con la recinzione sono liste: si riconoscono a posteriori
    for key, value in list(values.items()):
        if isinstance(value, str) and value.startswith("```"):
            errors.append(f"blocco ``` malformato in {key}")
    return values, errors


def validate(path: str, value) -> list[str]:
    if isinstance(value, list):
        return []
    bad = []
    for marker, label in (("**", "grassetto"), ("==", "evidenziato"), ("`", "codice")):
        if value.count(marker) % 2:
            bad.append(f"{label} non chiuso ({marker})")
    if value.count("[[") != value.count("]]"):
        bad.append("[[nome prodotto]] non chiuso")
    for link in LINKISH.findall(value):
        if not GOOD_LINK.fullmatch(link):
            bad.append(f"link non valido: {link[:40]} (serve [testo](https://…))")
    markers = re.search(r"\*\*|==|\[\[|`|\]\(", value)
    if path.startswith(PLAIN_PREFIXES) and markers:
        bad.append("i campi meta non accettano marcatori: finiscono negli attributi")
    key = path.rpartition(".")[2].split("[")[0]
    if (path in ATTRIBUTE_PATHS or key in ATTRIBUTE_KEYS) and markers:
        bad.append("questo testo finisce anche in un attributo HTML (alt, aria-label): "
                   "niente marcatori")
    return [f"{path}: {b}" for b in bad]


def cmd_import(args) -> int:
    src = Path(args.file)
    text = src.read_text(encoding="utf-8")
    values, errors = parse(text)
    partial = values.pop(("__partial__", "", ""), False)
    page = values.pop(("__page__", "", ""), "tutto")
    langs = sorted({lang for lang, _, _ in values})
    data = {l: json.loads((CONTENT / f"{l}.json").read_text(encoding="utf-8"))
            for l in langs}

    known = {l: {(c, n) for c, n, _ in leaves(data[l])} for l in langs}
    expected = {l: {(c, n) for c, n, _ in scoped(data[l], page)} for l in langs}
    changes, problems = [], list(errors)

    for (lang, container, name), new in sorted(values.items()):
        path = f"{container}.{name}" if container else name
        if (container, name) not in known[lang]:
            problems.append(f"[{lang}] {path}: campo che non esiste nel JSON")
            continue
        old = get_in(data[lang], container, name)
        if isinstance(old, list) != isinstance(new, list):
            problems.append(f"[{lang}] {path}: tipo cambiato")
            continue
        if not new:
            problems.append(f"[{lang}] {path}: testo vuoto")
            continue
        problems += [f"[{lang}] {p}" for p in validate(path, new)]
        if old != new:
            changes.append((lang, path, old, new))

    if not partial:
        for lang in langs:
            missing = expected[lang] - {(c, n) for l, c, n in values if l == lang}
            for container, name in sorted(missing):
                problems.append(f"[{lang}] {container}.{name}: campo assente dal foglio")

    for p in problems:
        print(f"  ✗ {p}")
    if problems and not args.force:
        print(f"\n{len(problems)} problemi: nulla è stato scritto. "
              f"Correggi il foglio, o riprova con --force per ignorare gli avvisi.")
        return 1

    for lang, path, old, new in changes:
        print(f"  • [{lang}] {path}")
        if not isinstance(old, list):
            print(f"      − {old[:110]}")
            print(f"      + {new[:110]}")

    if not changes:
        print("Nessuna differenza rispetto al JSON.")
        return 0
    if args.dry_run:
        print(f"\n{len(changes)} campi cambierebbero (prova senza --dry-run per scrivere).")
        return 0

    for lang, path, _, new in changes:
        container, _, name = path.rpartition(".")
        if not name:
            container, name = "", path
        set_in(data[lang], container, name, new)
    for lang in langs:
        (CONTENT / f"{lang}.json").write_text(
            json.dumps(data[lang], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{len(changes)} campi aggiornati in {', '.join(f'{l}.json' for l in langs)}. "
          f"Ora: python build.py --check && python build.py")
    return 0


# ----------------------------------------------------------------- controllo --
def cmd_roundtrip(args) -> int:
    data = {l: json.loads((CONTENT / f"{l}.json").read_text(encoding="utf-8"))
            for l in ("it", "en")}
    bad = 0
    for page in PAGES:
        for langs in (["it"], ["en"], ["it", "en"]):
            for minchars in (0, 120):
                values, errors = parse(render(langs, data, minchars, page))
                values.pop(("__partial__", "", ""), None)
                values.pop(("__page__", "", ""), None)
                bad += len(errors)
                for (lang, container, name), new in values.items():
                    old = get_in(data[lang], container, name)
                    if old != new:
                        bad += 1
                        print(f"  ✗ [{lang}] {container}.{name}\n      − {old!r}\n      + {new!r}")
                if minchars:
                    continue  # il foglio di prosa è parziale per definizione
                covered = {(l, c, n) for l, c, n in values}
                for lang in langs:
                    for c, n, _ in scoped(data[lang], page):
                        if (lang, c, n) not in covered:
                            bad += 1
                            print(f"  ✗ [{lang}] {c}.{n}: perso nell'esportazione")
            print(f"  {page:5} {'-'.join(langs):5}: {len(values)} campi nella prosa, errori {len(errors)}")
    # ogni campo sta in una e una sola pagina
    for lang in ("it", "en"):
        home = {(c, n) for c, n, _ in scoped(data[lang], "home")}
        caso = {(c, n) for c, n, _ in scoped(data[lang], "caso")}
        tutto = {(c, n) for c, n, _ in scoped(data[lang], "tutto")}
        if home & caso or (home | caso) != tutto:
            bad += 1
            print(f"  ✗ [{lang}] home e caso non si spartiscono esattamente i campi")
    print("andata e ritorno senza perdite" if not bad else f"{bad} differenze")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("export", help="scrive il foglio di revisione")
    e.add_argument("--lang", choices=["it", "en", "both"], default="it")
    e.add_argument("--out")
    e.add_argument("--page", choices=list(PAGES), default="home",
                   help="home (default), caso (la pagina del caso reale) o tutto")
    e.add_argument("--prose", action="store_true",
                   help="solo i testi lunghi: una rilettura di prosa, senza etichette e voci di menu")
    e.add_argument("--min-chars", type=int, default=120,
                   help="soglia di --prose (default 120 caratteri)")
    e.set_defaults(func=cmd_export)

    i = sub.add_parser("import", help="riporta il foglio nel JSON")
    i.add_argument("file")
    i.add_argument("--dry-run", action="store_true")
    i.add_argument("--force", action="store_true", help="scrive anche con avvisi aperti")
    i.set_defaults(func=cmd_import)

    r = sub.add_parser("roundtrip", help="verifica che nulla si perda")
    r.set_defaults(func=cmd_roundtrip)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
