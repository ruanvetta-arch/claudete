"""Sonda temporária (roda no Actions)."""
import json
import re
import traceback

from bs4 import BeautifulSoup
from curl_cffi import requests as cr

H = {"Accept-Language": "pt-BR,pt;q=0.9"}


def g(u, **h):
    return cr.get(u, impersonate="chrome", timeout=40, headers={**H, **h})


def sec(nome, fn):
    print(f"\n######## {nome}")
    try:
        fn()
    except Exception:  # noqa: BLE001
        traceback.print_exc()


def dump_card(soup, sel, n=1):
    cards = soup.select(sel)
    print("cards", sel, len(cards))
    for c in cards[:n]:
        html = str(c)
        html = re.sub(r"<svg.*?</svg>", "<svg/>", html, flags=re.S)
        html = re.sub(r'style="[^"]*"', "", html)
        print("CARD", html[:3500])
        print("TEXT", c.get_text(" | ", strip=True)[:600])


def mitula():
    r = g("https://imoveis.mitula.com.br/imoveis/aluguel-casas-2-quartos-brasilia?order=date")
    t = r.text
    print("status", r.status_code, len(t))
    soup = BeautifulSoup(t, "html.parser")
    dump_card(soup, "[class*='listing-card']", 1)
    links = [a.get("href") for a in soup.select("a[href]") if a.get("href") and ("/imovel" in a.get("href") or "/anuncio" in a.get("href") or "redirect" in a.get("href"))]
    print("links", len(links), links[:5])
    ld = soup.select_one('script[type="application/ld+json"]')
    if ld:
        d = json.loads(ld.string)
        ab = d.get("about") or []
        print("about n", len(ab))
        print("about0", json.dumps(ab[0], ensure_ascii=False)[:1200] if ab else None)
    # paginação
    pag = [a.get("href") for a in soup.select("a[href]") if re.search(r"[?&]page=\d|/\d+$|pagina", a.get("href") or "")]
    print("pag", pag[:6])


def nestoria():
    r = g("https://www.nestoria.com.br/distrito-federal/casas/aluguel?bedrooms=2&sort=newest")
    t = r.text
    print("status", r.status_code, len(t))
    soup = BeautifulSoup(t, "html.parser")
    dump_card(soup, "[data-id]", 1)
    links = [a.get("href") for a in soup.select("a[href]") if a.get("href") and "/detalhe" in a.get("href")]
    print("links", len(links), links[:3])
    ld = soup.select_one('script[type="application/ld+json"]')
    print("ld", (ld.string or "")[:800] if ld else None)


def trovit():
    r = g("https://imoveis.trovit.com.br/aluguel-casa-2-quartos-distrito-federal")
    t = r.text
    print("status", r.status_code, len(t))
    soup = BeautifulSoup(t, "html.parser")
    for sel in ["[data-test='snippet']", "article", "[class*='snippet']", "[class*='card']"]:
        if soup.select(sel):
            dump_card(soup, sel, 1)
            break
    print("wimoveis mentions", t.lower().count("wimoveis"), "dfimoveis", t.lower().count("dfimoveis"))


sec("MITULA", mitula)
sec("NESTORIA", nestoria)
sec("TROVIT", trovit)
