#!/usr/bin/env python3
"""Mede o acervo de planos do TxDOT sem baixar nenhum arquivo.

Percorre as listagens de pasta do servidor (so HTML das listagens), registra
cada arquivo com tamanho e data, e gera um relatorio de volume.

Uso:
    python3 measure.py                      # usa a URL e credenciais padrao
    python3 measure.py --out dados/         # pasta de saida
    python3 measure.py --max-dirs 50        # teste rapido
    python3 measure.py --head-missing       # HEAD nos arquivos sem tamanho

A varredura pode ser interrompida e retomada: diretorios ja lidos ficam em
<out>/listing.jsonl e sao pulados na proxima execucao.
"""

import argparse
import base64
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict, deque
from datetime import datetime
from html import unescape
from pathlib import Path

DEFAULT_URL = "https://ftp.txdot.gov/plans/"
# Credenciais publicas divulgadas pelo proprio TxDOT para o acervo de planos.
DEFAULT_USER = "planuser"
DEFAULT_PASS = "txdotplans"

ANCHOR_RE = re.compile(r'<a\s[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")
ROW_SPLIT_RE = re.compile(r"<br\s*/?>|<tr[\s>]|\n", re.I)

DATE_PATTERNS = [
    # IIS: 1/5/2024  3:12 PM
    (re.compile(r"(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2})\s*([AP]M)", re.I), "%m/%d/%Y %I:%M %p"),
    # IIS longo: Friday, January 5, 2024 3:12 PM
    (re.compile(r"\w+day,\s+(\w+ \d{1,2}, \d{4})\s+(\d{1,2}:\d{2})\s*([AP]M)", re.I), "%B %d, %Y %I:%M %p"),
    # Apache: 2024-01-05 15:12
    (re.compile(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})"), "%Y-%m-%d %H:%M"),
    # nginx: 05-Jan-2024 15:12
    (re.compile(r"(\d{2}-\w{3}-\d{4})\s+(\d{2}:\d{2})"), "%d-%b-%Y %H:%M"),
]
DIR_MARK_RE = re.compile(r"&lt;dir&gt;|<dir>", re.I)
SIZE_RE = re.compile(r"(?<![\d:/.-])(\d+(?:\.\d+)?)([KMGT]?)(?![\d:/.-])", re.I)
UNITS = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}


def parse_date(text):
    for rx, fmt in DATE_PATTERNS:
        m = rx.search(text)
        if m:
            raw = " ".join(g for g in m.groups() if g)
            try:
                return datetime.strptime(raw, fmt), m
            except ValueError:
                continue
    return None, None


def parse_size(text):
    """Primeiro numero do texto que parece tamanho (bytes ou 12M/3.4G)."""
    for m in SIZE_RE.finditer(text):
        num, unit = m.groups()
        return int(float(num) * UNITS[unit.upper()])
    return None


def parse_listing(html, page_url):
    """Extrai entradas de uma listagem IIS, Apache ou nginx.

    Retorna lista de dicts: url, name, is_dir, size, modified.
    """
    base = urllib.parse.urlparse(page_url)
    entries = []
    # Cada linha da listagem e uma entrada: IIS separa por <br>, Apache por
    # <tr>, nginx por quebra de linha. Data e tamanho ficam na mesma linha.
    for row in ROW_SPLIT_RE.split(html):
        a = ANCHOR_RE.search(row)
        if not a:
            continue
        href = unescape(a.group(1))
        name = unescape(TAG_RE.sub("", a.group(2))).strip()
        if href.startswith(("?", "#", "mailto:", "javascript:")):
            continue
        url = urllib.parse.urljoin(page_url, href)
        target = urllib.parse.urlparse(url)
        # So entradas filhas diretas da pasta atual.
        if target.netloc != base.netloc or not target.path.startswith(base.path):
            continue
        rest = target.path[len(base.path):].strip("/")
        if not rest or "/" in rest:
            continue

        meta = row[:a.start()] + " " + row[a.end():]
        is_dir = href.endswith("/") or bool(DIR_MARK_RE.search(meta))
        text = unescape(TAG_RE.sub(" ", meta))
        modified, m = parse_date(text)
        size = None
        if not is_dir:
            remainder = text[:m.start()] + " " + text[m.end():] if m else text
            size = parse_size(remainder)
        if is_dir and not url.endswith("/"):
            url += "/"
        entries.append({
            "url": url,
            "name": name or urllib.parse.unquote(rest),
            "is_dir": is_dir,
            "size": size,
            "modified": modified.isoformat() if modified else None,
        })
    return entries


class Client:
    def __init__(self, user, password, delay, retries=4):
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {token}",
            "User-Agent": "txdot-plans-measure/1.0 (catalogo pessoal; baixa so listagens)",
        }
        self.delay = delay
        self.retries = retries

    def request(self, url, method="GET"):
        last = None
        for attempt in range(self.retries + 1):
            if self.delay:
                time.sleep(self.delay)
            req = urllib.request.Request(url, headers=self.headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = resp.read() if method == "GET" else b""
                    return resp.status, dict(resp.headers), body
            except urllib.error.HTTPError as e:
                if e.code in (401, 403, 404):
                    raise
                last = e
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last = e
            time.sleep(2 ** (attempt + 1))
        raise last


def crawl(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    listing_path = out / "listing.jsonl"
    errors_path = out / "errors.jsonl"

    done = set()
    if listing_path.exists():
        with listing_path.open() as f:
            for line in f:
                done.add(json.loads(line)["dir"])

    client = Client(args.user, args.password, args.delay)
    root = args.url if args.url.endswith("/") else args.url + "/"
    queue = deque([root])
    seen = {root}
    visited = 0

    # Na retomada, reenfileira os filhos dos diretorios ja lidos.
    if done:
        with listing_path.open() as f:
            for line in f:
                for e in json.loads(line)["entries"]:
                    if e["is_dir"] and e["url"] not in seen:
                        seen.add(e["url"])
                        queue.append(e["url"])

    with listing_path.open("a") as lf, errors_path.open("a") as ef:
        while queue:
            d = queue.popleft()
            if d in done:
                continue
            if args.max_dirs and visited >= args.max_dirs:
                print(f"Limite de {args.max_dirs} pastas atingido; rode de novo para continuar.")
                break
            try:
                _, _, body = client.request(d)
            except Exception as e:  # registra e segue
                ef.write(json.dumps({"dir": d, "error": repr(e)}) + "\n")
                ef.flush()
                print(f"  ERRO {d}: {e}", file=sys.stderr)
                continue
            html = body.decode("utf-8", "replace")
            if visited == 0 and not done:
                (out / "sample_root.html").write_text(html)
            entries = parse_listing(html, d)
            if args.head_missing:
                for e in entries:
                    if not e["is_dir"] and e["size"] is None:
                        try:
                            _, h, _ = client.request(e["url"], method="HEAD")
                            if h.get("Content-Length"):
                                e["size"] = int(h["Content-Length"])
                            if not e["modified"] and h.get("Last-Modified"):
                                e["modified"] = datetime.strptime(
                                    h["Last-Modified"], "%a, %d %b %Y %H:%M:%S GMT"
                                ).isoformat()
                        except Exception as ex:
                            ef.write(json.dumps({"file": e["url"], "error": repr(ex)}) + "\n")
            lf.write(json.dumps({"dir": d, "entries": entries}) + "\n")
            lf.flush()
            done.add(d)
            visited += 1
            for e in entries:
                if e["is_dir"] and e["url"] not in seen:
                    seen.add(e["url"])
                    queue.append(e["url"])
            if visited % 25 == 0:
                print(f"  {len(done)} pastas lidas, {len(queue)} na fila")
    return root


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:,.1f} {unit}"
        n /= 1024


def report(args, root):
    out = Path(args.out)
    files = {}
    dirs = 0
    with (out / "listing.jsonl").open() as f:
        for line in f:
            rec = json.loads(line)
            dirs += 1
            for e in rec["entries"]:
                if not e["is_dir"]:
                    files[e["url"]] = e

    with (out / "catalog.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["path", "name", "ext", "size_bytes", "modified", "top_folder"])
        for e in files.values():
            path = urllib.parse.unquote(e["url"][len(root):])
            ext = Path(e["name"]).suffix.lower()
            w.writerow([path, e["name"], ext, e["size"] or "", e["modified"] or "", path.split("/")[0]])

    cutoff_year = datetime.now().year - args.years
    total = sum(e["size"] or 0 for e in files.values())
    no_size = sum(1 for e in files.values() if e["size"] is None)
    by_year = defaultdict(lambda: [0, 0])
    by_ext = defaultdict(lambda: [0, 0])
    by_top = defaultdict(lambda: [0, 0])
    recent = [0, 0]
    for e in files.values():
        s = e["size"] or 0
        year = e["modified"][:4] if e["modified"] else "sem data"
        ext = Path(e["name"]).suffix.lower() or "(sem ext)"
        top = urllib.parse.unquote(e["url"][len(root):]).split("/")[0]
        for bucket, key in ((by_year, year), (by_ext, ext), (by_top, top)):
            bucket[key][0] += 1
            bucket[key][1] += s
        if e["modified"] and int(e["modified"][:4]) > cutoff_year:
            recent[0] += 1
            recent[1] += s

    largest = sorted(files.values(), key=lambda e: e["size"] or 0, reverse=True)[:15]
    summary = {
        "root": root,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "dirs": dirs,
        "files": len(files),
        "files_without_size": no_size,
        "total_bytes": total,
        f"last_{args.years}_years": {"files": recent[0], "bytes": recent[1]},
        "by_year": dict(sorted(by_year.items())),
        "by_extension": dict(sorted(by_ext.items(), key=lambda kv: -kv[1][1])),
        "by_top_folder": dict(sorted(by_top.items(), key=lambda kv: -kv[1][1])),
        "largest": [{"url": e["url"], "size": e["size"]} for e in largest],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    lines = [
        "# Medicao do acervo TxDOT",
        "",
        f"- Origem: {root}",
        f"- Gerado em: {summary['generated']}",
        f"- Pastas lidas: {dirs:,}",
        f"- Arquivos: {len(files):,} ({no_size:,} sem tamanho na listagem)",
        f"- Volume total: **{human(total)}**",
        f"- Ultimos {args.years} anos (data do arquivo > {cutoff_year}): "
        f"**{recent[0]:,} arquivos, {human(recent[1])}**",
        "",
        "## Por ano (data de modificacao)",
        "",
        "| Ano | Arquivos | Volume |",
        "|---|---:|---:|",
        *[f"| {k} | {v[0]:,} | {human(v[1])} |" for k, v in sorted(by_year.items())],
        "",
        "## Por pasta de primeiro nivel",
        "",
        "| Pasta | Arquivos | Volume |",
        "|---|---:|---:|",
        *[f"| {k} | {v[0]:,} | {human(v[1])} |" for k, v in summary["by_top_folder"].items()],
        "",
        "## Por extensao",
        "",
        "| Extensao | Arquivos | Volume |",
        "|---|---:|---:|",
        *[f"| {k} | {v[0]:,} | {human(v[1])} |" for k, v in list(summary["by_extension"].items())[:20]],
        "",
        "## Maiores arquivos",
        "",
        *[f"- {human(e['size'] or 0)} — {urllib.parse.unquote(e['url'][len(root):])}" for e in largest],
        "",
    ]
    (out / "REPORT.md").write_text("\n".join(lines))
    print("\n".join(lines[:9]))
    print(f"\nRelatorio completo: {out / 'REPORT.md'}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--user", default=DEFAULT_USER)
    p.add_argument("--password", default=DEFAULT_PASS)
    p.add_argument("--out", default="txdot-measure")
    p.add_argument("--delay", type=float, default=0.3, help="pausa entre requisicoes (s)")
    p.add_argument("--max-dirs", type=int, default=0, help="limite de pastas nesta execucao")
    p.add_argument("--years", type=int, default=5, help="janela do recorte 'ultimos N anos'")
    p.add_argument("--head-missing", action="store_true", help="HEAD em arquivos sem tamanho")
    p.add_argument("--report-only", action="store_true", help="so regenera o relatorio")
    args = p.parse_args()

    root = args.url if args.url.endswith("/") else args.url + "/"
    if not args.report_only:
        crawl(args)
    report(args, root)


if __name__ == "__main__":
    main()
