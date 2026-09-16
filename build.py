#!/usr/bin/env python3
"""Build the MCPCA site: templates + content/<lang>.json -> dist/.

    python build.py            # render every language into dist/
    python build.py --check    # verify that en.json mirrors it.json (same keys, same list lengths)

Italian is the primary language and lives at the site root; every other
language lives at dist/<lang>/.  Relative asset paths are computed per page so
the same template works at any depth and under any base URL.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
DIST = ROOT / "dist"

SITE_URL = "https://acaland.github.io/mcpca-site/"
PRIMARY = "it"


def load(lang: str) -> dict:
    with (CONTENT / f"{lang}.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def languages() -> list[str]:
    return sorted(p.stem for p in CONTENT.glob("*.json"))


def render(env: Environment, lang: str) -> Path:
    t = load(lang)
    is_primary = lang == PRIMARY
    root = "" if is_primary else "../"
    page_url = SITE_URL if is_primary else f"{SITE_URL}{lang}/"
    out_dir = DIST if is_primary else DIST / lang
    out_dir.mkdir(parents=True, exist_ok=True)

    html = env.get_template("index.html.j2").render(
        t=t, lang=lang, root=root, site_url=SITE_URL, page_url=page_url,
    )
    out = out_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


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
    for lang in languages():
        out = render(env, lang)
        print(f"  {lang}: {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")


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
            1 for k in ("hero", "what", "usecases", "features", "dialogues", "faq")
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
