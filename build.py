#!/usr/bin/env python3
"""Build the MCPCA site: templates + content/<lang>.json -> dist/.

    python build.py            # render every page in every language into dist/
    python build.py --check    # verify that en.json mirrors it.json (same keys, same list lengths)

Italian is the primary language and lives at the site root; every other
language lives under dist/<lang>/.  Each extra page lives in its own folder so
its URL ends with a slash.  Relative asset paths, the language switch and the
hreflang links are computed per page, so the same templates work at any depth.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
DIST = ROOT / "dist"

SITE_URL = "https://acaland.github.io/mcpca/"
PRIMARY = "it"

# key -> template + folder (an empty slug is the language home page)
PAGES = [
    {"key": "index", "template": "index.html.j2", "slug": "", "og": "og-{lang}.png"},
    {"key": "case", "template": "case-study.html.j2", "slug": "case-study", "og": "og-case-{lang}.png"},
]


def load(lang: str) -> dict:
    with (CONTENT / f"{lang}.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def languages() -> list[str]:
    return sorted(p.stem for p in CONTENT.glob("*.json"))


def lang_dir(lang: str) -> str:
    """Path of a language's home, relative to the site root ('' for Italian)."""
    return "" if lang == PRIMARY else lang


def page_dir(lang: str, slug: str) -> str:
    return "/".join(p for p in (lang_dir(lang), slug) if p)


def page_url(lang: str, slug: str) -> str:
    d = page_dir(lang, slug)
    return f"{SITE_URL}{d}/" if d else SITE_URL


def rel(from_dir: str, to_dir: str) -> str:
    """Relative href from one site folder to another, always ending in '/'."""
    if from_dir == to_dir:
        return ""
    r = os.path.relpath(to_dir or ".", from_dir or ".")
    return "" if r == "." else r + "/"


def available_images() -> set[str]:
    """Screenshot file names actually present, so figures degrade to nothing."""
    case_dir = STATIC / "case"
    if not case_dir.is_dir():
        return set()
    return {p.name for p in case_dir.iterdir() if p.is_file() and not p.name.startswith(".")}


def build() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copytree(STATIC, DIST / "static")
    (DIST / ".nojekyll").write_text("")

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        undefined=StrictUndefined,
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # Macros are used by the base template and inside every child block, so they
    # are exposed globally: an import declared in a child template would not be
    # visible inside that template's blocks.
    env.globals["m"] = env.get_template("partials/macros.html.j2").module
    images = available_images()

    langs = languages()
    for lang in langs:
        t = load(lang)
        other = t["other_lang"]["code"]
        for page in PAGES:
            slug = page["slug"]
            here = page_dir(lang, slug)
            out_dir = DIST / here if here else DIST
            out_dir.mkdir(parents=True, exist_ok=True)

            meta = t["meta"] if page["key"] == "index" else t[page["key"]]["meta"]
            html = env.get_template(page["template"]).render(
                t=t,
                lang=lang,
                page_key=page["key"],
                meta=meta,
                root=rel(here, ""),
                home_href=rel(here, lang_dir(lang)),
                case_href=rel(here, page_dir(lang, "case-study")) or "./",
                lang_href=rel(here, page_dir(other, slug)) or "./",
                alternates={l: page_url(l, slug) for l in langs},
                page_url=page_url(lang, slug),
                site_url=SITE_URL,
                og_image=page["og"].format(lang=lang),
                available_images=images,
            )
            out = out_dir / "index.html"
            out.write_text(html, encoding="utf-8")
            print(f"  {lang}/{page['key']}: {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")

    if not images:
        print("  note: static/case/ holds no screenshots, so the figure section is skipped")


def diff_shape(a, b, path="") -> list[str]:
    """Return human-readable differences in structure between two JSON values."""
    problems: list[str] = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a:
            if k not in b:
                problems.append(f"missing key {path}/{k}")
            else:
                problems += diff_shape(a[k], b[k], f"{path}/{k}")
        for k in b:
            if k not in a and k != "stub_notice":
                problems.append(f"extra key {path}/{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            problems.append(f"list length {path}: {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            problems += diff_shape(x, y, f"{path}[{i}]")
    elif type(a) is not type(b):
        problems.append(f"type mismatch {path}: {type(a).__name__} vs {type(b).__name__}")
    return problems


def check() -> int:
    base = load(PRIMARY)
    status = 0
    for lang in languages():
        if lang == PRIMARY:
            continue
        other = load(lang)
        problems = diff_shape(base, other)
        untranslated = sum(
            1 for k in ("hero", "what", "usecases", "features", "dialogues", "faq", "case")
            if json.dumps(base.get(k), sort_keys=True) == json.dumps(other.get(k), sort_keys=True)
        )
        if other.get("stub_notice"):
            print(f"  {lang}: STUB (stub_notice present, {untranslated} major sections identical to {PRIMARY})")
            status = 1
        elif problems:
            print(f"  {lang}: {len(problems)} structural problem(s)")
            for p in problems[:40]:
                print("    -", p)
            status = 1
        elif untranslated:
            print(f"  {lang}: {untranslated} major section(s) identical to {PRIMARY} — still to translate")
            status = 1
        else:
            print(f"  {lang}: ok")
    return status


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="validate translations against it.json")
    args = ap.parse_args()
    if args.check:
        sys.exit(check())
    build()
