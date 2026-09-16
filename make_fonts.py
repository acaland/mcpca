#!/usr/bin/env python3
"""Scarica i font del sito e li ospita in locale.

    python make_fonts.py

Prende da Google Fonts i soli sottoinsiemi latin e latin-ext di Inter (testo) e
Source Serif 4 (titoli), li salva in static/fonts/ e rigenera static/fonts.css
con le @font-face che puntano ai file locali.

Perché in locale e non dal CDN: il sito dichiara di non fare richieste a terzi
né di usare cookie. Un <link> a fonts.googleapis.com contraddirebbe entrambe le
cose, perché ogni visita passerebbe l'indirizzo IP a un servizio esterno.

Entrambe le famiglie hanno licenza SIL Open Font License 1.1 (static/fonts/OFL.txt),
che consente la redistribuzione.
"""
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "static" / "fonts"
CSS = ROOT / "static" / "fonts.css"

UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")}

FAMILIES = [
    ("Inter", "inter", "family=Inter:ital,wght@0,400..700;1,400..700"),
    ("Source Serif 4", "source-serif-4", "family=Source+Serif+4:opsz,wght@8..60,400..700"),
]
SUBSETS = {"latin", "latin-ext"}


def fetch(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA)).read()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    faces, total = [], 0

    for family, slug, query in FAMILIES:
        css = fetch(f"https://fonts.googleapis.com/css2?{query}&display=swap").decode()
        for subset, body in re.findall(r"/\* (\S+) \*/\s*@font-face \{(.*?)\}", css, re.S):
            if subset not in SUBSETS:
                continue
            src = re.search(r"url\((https://[^)]+\.woff2)\)", body).group(1)
            style = re.search(r"font-style: (\w+)", body).group(1)
            weight = re.search(r"font-weight: ([^;]+);", body).group(1).strip()
            rng = re.search(r"unicode-range: ([^;]+);", body).group(1).strip()

            name = f"{slug}-{style}-{subset}.woff2"
            data = fetch(src)
            (OUT / name).write_bytes(data)
            faces.append((family, style, weight, name, rng))
            total += len(data)
            print(f"  {name}: {len(data) // 1024} KB")

    lines = [
        "/* Font self-hosted: nessuna richiesta a terzi, nessun cookie.",
        "   Inter e Source Serif 4, entrambi con licenza SIL Open Font License 1.1.",
        "   Sottoinsiemi latin e latin-ext soltanto. Rigenerabili con make_fonts.py. */",
        "",
    ]
    for family, style, weight, name, rng in faces:
        lines += [
            "@font-face {",
            f"  font-family: '{family}';",
            f"  font-style: {style};",
            f"  font-weight: {weight};",
            "  font-display: swap;",
            f"  src: url('fonts/{name}') format('woff2');",
            f"  unicode-range: {rng};",
            "}",
            "",
        ]
    CSS.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{len(faces)} file, {total // 1024} KB in totale; scritto {CSS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
