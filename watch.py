#!/usr/bin/env python3
"""Anteprima dal vivo: salvi il foglio di revisione e il browser si aggiorna.

    python watch.py              # http://localhost:8000
    python watch.py --port 8010 --open

Tiene d'occhio review/*.md, content/*.json, templates/ e static/. Quando salvi:

1. un foglio in review/ → content.py import; se l'import fallisce (marcatore
   aperto, link malformato…) l'errore compare in un riquadro in cima alla pagina
   e il JSON non viene toccato;
2. se l'import riesce, rigenera gli altri fogli di review/, che altrimenti
   resterebbero fotografie del testo precedente;
3. python build.py, poi ricarica le pagine aperte, tornando allo stesso punto
   della pagina e alla stessa scheda dei casi d'uso.

Solo libreria standard: il server serve dist/ e aggiunge al volo alle pagine
HTML un piccolo script che ascolta gli aggiornamenti. dist/ resta pulita, e ciò
che si pubblica non contiene nulla di questo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
REVIEW = ROOT / "review"
PY = sys.executable

# ------------------------------------------------------------- canale eventi --
class Channel:
    """Ultimo evento e un contatore: ogni pagina aperta aspetta che cambi."""

    def __init__(self):
        self.cond = threading.Condition()
        self.version = 0
        self.event, self.data = "ok", ""

    def publish(self, event: str, data: str = "") -> None:
        with self.cond:
            self.version += 1
            self.event, self.data = event, data
            self.cond.notify_all()


CHANNEL = Channel()

SNIPPET = b"""
<script>/* iniettato da watch.py, non esiste nel sito pubblicato */
(() => {
  const KEY = "__watch_state";
  const save = () => {
    const tab = document.querySelector('[role="tab"][aria-selected="true"]');
    try { sessionStorage.setItem(KEY, JSON.stringify({ tab: tab && tab.id, y: scrollY, path: location.pathname })); } catch (e) {}
  };
  addEventListener("load", () => {
    let s = null;
    try { s = JSON.parse(sessionStorage.getItem(KEY)); sessionStorage.removeItem(KEY); } catch (e) {}
    if (!s || s.path !== location.pathname) return;
    const tab = s.tab && document.getElementById(s.tab);
    if (tab && tab.getAttribute("aria-selected") !== "true") tab.click();
    requestAnimationFrame(() => scrollTo(0, s.y));
  });

  let box = null;
  const show = (title, text) => {
    if (!box) {
      box = document.createElement("div");
      box.setAttribute("role", "alert");
      box.style.cssText = "position:fixed;inset:12px 12px auto 12px;z-index:99999;max-height:45vh;overflow:auto;" +
        "background:#fff1f0;color:#5c0b05;border:1px solid #e4a09a;border-radius:10px;padding:14px 16px;" +
        "font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;box-shadow:0 8px 30px rgba(0,0,0,.18);white-space:pre-wrap";
      document.body.appendChild(box);
    }
    box.textContent = "";
    const h = document.createElement("strong");
    h.textContent = title + "\\n\\n";
    box.append(h, text);
  };
  const hide = () => { if (box) { box.remove(); box = null; } };

  let lost = false;
  const es = new EventSource("/__watch");
  es.addEventListener("reload", () => { save(); location.reload(); });
  es.addEventListener("fail", e => { const d = JSON.parse(e.data); show(d.title, d.text); });
  es.addEventListener("ok", hide);
  es.onerror = () => { lost = true; };
  es.onopen = () => { if (lost) { save(); location.reload(); } };  /* watch.py riavviato */
})();
</script>
"""


# ------------------------------------------------------------------- server --
class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # mai dalla cache: ogni ricarica deve vedere il CSS e l'HTML appena costruiti
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):  # il terminale serve per gli eventi, non per le richieste
        pass

    def do_GET(self):
        url = self.path.split("?", 1)[0]
        if url == "/__watch":
            return self.stream()
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            if not url.endswith("/"):
                return super().do_GET()  # redirect con la barra finale
            path = os.path.join(path, "index.html")
        if path.endswith(".html") and os.path.isfile(path):
            body = Path(path).read_bytes().replace(b"</body>", SNIPPET + b"</body>", 1)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        with CHANNEL.cond:
            seen = CHANNEL.version
            pending = (CHANNEL.event, CHANNEL.data) if CHANNEL.event == "fail" else None
        try:
            if pending:  # pagina aperta mentre un errore è ancora da correggere
                self.send_event(*pending)
            while True:
                with CHANNEL.cond:
                    CHANNEL.cond.wait_for(lambda: CHANNEL.version != seen, timeout=15)
                    changed = CHANNEL.version != seen
                    seen, event, data = CHANNEL.version, CHANNEL.event, CHANNEL.data
                if changed:
                    self.send_event(event, data)
                else:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return

    def send_event(self, event: str, data: str) -> None:
        payload = data.replace("\n", "\ndata: ") if data else ""
        self.wfile.write(f"event: {event}\ndata: {payload}\n\n".encode())
        self.wfile.flush()


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # il browser che chiude una connessione mentre ricarica non è un errore
        if isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)


# ---------------------------------------------------------------- sorgenti --
def sources() -> dict[Path, float]:
    files = list(REVIEW.glob("*.md")) + list((ROOT / "content").glob("*.json"))
    for folder in ("templates", "static"):
        files += [p for p in (ROOT / folder).rglob("*") if p.is_file() and not p.name.startswith(".")]
    out = {}
    for p in files:
        try:
            out[p] = p.stat().st_mtime
        except FileNotFoundError:
            pass  # salvataggio atomico dell'editor: il file riappare al giro dopo
    return out


def json_digest() -> str:
    h = hashlib.sha256()
    for p in sorted((ROOT / "content").glob("*.json")):
        h.update(p.read_bytes())
    return h.hexdigest()


def export_args(sheet: Path) -> list[str] | None:
    """Ricostruisce le opzioni di export dal nome del foglio (it.md, it-en-prosa.md…)."""
    stem = sheet.stem
    prose = stem.endswith("-prosa")
    langs = stem.removesuffix("-prosa")
    lang = {"it": "it", "en": "en", "it-en": "both"}.get(langs)
    if not lang:
        return None
    return ["export", "--lang", lang] + (["--prose"] if prose else [])


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY, *args], cwd=ROOT, capture_output=True, text=True)


def stamp() -> str:
    return time.strftime("%H:%M:%S")


def fail(title: str, proc: subprocess.CompletedProcess) -> None:
    text = (proc.stdout + proc.stderr).strip()
    print(f"[{stamp()}] ✗ {title}\n{text}\n")
    CHANNEL.publish("fail", json.dumps({"title": title, "text": text}, ensure_ascii=False))


def cycle(changed: list[Path]) -> None:
    sheets = [p for p in changed if p.parent == REVIEW and p.exists()]
    before = json_digest()

    for sheet in sheets:
        proc = run("content.py", "import", str(sheet))
        if proc.returncode:
            fail(f"import di review/{sheet.name} non riuscito — il JSON non è stato toccato", proc)
            return
        for line in proc.stdout.splitlines():
            if line.strip().startswith("•"):
                print(f"[{stamp()}] {line.strip()}")

    json_changed = json_digest() != before
    others_changed = any(p.parent != REVIEW for p in changed)

    if json_changed:
        # gli altri fogli ora descrivono un testo che non c'è più: si rigenerano
        edited = {s.name for s in sheets}
        for other in sorted(REVIEW.glob("*.md")):
            args = export_args(other)
            if other.name not in edited and args:
                run("content.py", *args)
        print(f"[{stamp()}]   rigenerati gli altri fogli di review/")

    if not (json_changed or others_changed):
        print(f"[{stamp()}] nessuna differenza")
        CHANNEL.publish("ok")
        return

    t0 = time.time()
    proc = run("build.py")
    if proc.returncode:
        fail("build non riuscita", proc)
        return
    print(f"[{stamp()}] ✓ build in {time.time() - t0:.1f}s, pagina ricaricata")
    CHANNEL.publish("reload")


def watch(interval: float = 0.3, settle: float = 0.25) -> None:
    known = sources()
    while True:
        time.sleep(interval)
        now = sources()
        changed = [p for p, m in now.items() if known.get(p) != m]
        if not changed:
            known = now
            continue
        # aspetta che l'editor abbia finito di scrivere (salvataggi in più passi)
        time.sleep(settle)
        cycle(sorted(set(changed)))
        known = sources()  # ciò che il ciclo stesso ha scritto non va rielaborato


def main() -> int:
    ap = argparse.ArgumentParser(description="anteprima dal vivo del sito")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--open", action="store_true", help="apre il browser all'avvio")
    args = ap.parse_args()
    # riga per riga anche quando l'output non va a un terminale (tee, log, IDE)
    sys.stdout.reconfigure(line_buffering=True)

    REVIEW.mkdir(exist_ok=True)
    if not any(REVIEW.glob("*.md")):
        run("content.py", "export", "--lang", "it", "--prose")
        print("review/ era vuota: generato review/it-prosa.md")

    proc = run("build.py")
    if proc.returncode:
        print((proc.stdout + proc.stderr).strip())
        return 1

    handler = partial(Handler, directory=str(DIST))
    try:
        server = Server(("127.0.0.1", args.port), handler)
    except OSError:
        print(f"La porta {args.port} è occupata: riprova con --port {args.port + 1}")
        return 1
    threading.Thread(target=server.serve_forever, daemon=True).start()

    url = f"http://localhost:{args.port}/"
    print(f"Anteprima su {url}  (inglese: {url}en/)")
    print("Salva un file in review/ e la pagina si aggiorna. Ctrl-C per uscire.\n")
    if args.open:
        webbrowser.open(url)
    try:
        watch()
    except KeyboardInterrupt:
        print("\nfine")
    return 0


if __name__ == "__main__":
    sys.exit(main())
