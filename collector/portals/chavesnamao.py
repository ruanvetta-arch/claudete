"""Chaves na Mão — HTML server-side; o título do link do card já traz tudo."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from common import (MIN_QUARTOS, bairro_bonito, flags_from_text, get, novo_imovel,
                    regiao_de, session, to_int)

NOME = "Chaves na Mão"
BASE = "https://www.chavesnamao.com.br"
LISTA = "/casas-para-alugar/df/"
MAX_PAGINAS = 15

# "Casa com 2 quartos para alugar na Chácara Chácara, 43, Riacho Fundo I, Brasília, 150 m2 por R$ 2.950"
TITLE_RE = re.compile(
    r"(?P<tipo>.+?) com (?P<q>\d+) quartos? para alugar (?:na|no|em) (?P<loc>.+?)(?:, (?P<area>\d+) m2)? por R\$ (?P<preco>[\d.]+)",
    re.I,
)


def _parse_pagina(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    itens: list[dict] = []
    for card in soup.select("div[id^=rc-]"):
        a = card.select_one("a[href*='/imovel/']")
        if not a:
            continue
        href = a.get("href", "")
        m_id = re.search(r"/id-(\d+)/", href)
        if not m_id:
            continue
        ident = m_id.group(1)
        title = a.get("title") or a.get_text(" ", strip=True)
        m = TITLE_RE.search(title)
        texto = card.get_text(" ", strip=True)
        if m:
            quartos = to_int(m.group("q"))
            preco = to_int(m.group("preco"))
            area = to_int(m.group("area"))
            loc = m.group("loc")
        else:
            mq = re.search(r"(\d+)\s*quartos?", texto, re.I)
            mp = re.search(r"R\$\s*([\d.]+)", texto)
            ma = re.search(r"(\d+)\s*m²", texto)
            quartos = to_int(mq.group(1)) if mq else None
            preco = to_int(mp.group(1)) if mp else None
            area = to_int(ma.group(1)) if ma else None
            loc = ""
        if quartos is None or quartos < MIN_QUARTOS or not preco or preco < 300:
            continue
        # loc: "Chácara Chácara, 43, Riacho Fundo I, Brasília"
        partes = [p.strip() for p in loc.split(",") if p.strip()]
        bairro = None
        if len(partes) >= 2:
            bairro = partes[-2] if partes[-1].lower().startswith("bras") else partes[-1]
        elif partes:
            bairro = partes[0]
        # Linha "Riacho Fundo I, Brasília/DF" no card é mais confiável
        ml = re.search(r"([^,]+?),\s*Bras[íi]lia\s*/\s*DF", texto)
        if ml:
            bairro = ml.group(1).strip()
        bairro = bairro_bonito(bairro)
        regiao = regiao_de(bairro, loc, href)
        img = card.select_one("img[src*='/imn/']")
        fotos = [img["src"].replace("/0400X0262/", "/0800X0524/")] if img else []
        itens.append(
            novo_imovel(
                portal=NOME,
                id_portal=ident,
                titulo=title.split(" para alugar")[0] if title else "Casa para alugar",
                preco=preco,
                bairro=bairro,
                regiao=regiao,
                quartos=quartos,
                area_m2=area,
                fotos=fotos,
                url=BASE + href if href.startswith("/") else href,
                **flags_from_text(f"{title} {texto}"),
            )
        )
    return itens


def fotos_detalhe(s, it: dict, max_fotos: int = 12) -> list[str]:
    """Página do anúncio: JSON-LD traz todas as fotos em 1200x800."""
    import json as _json

    r = get(s, it["url"])
    if r.status_code != 200:
        return it.get("fotos") or []
    soup = BeautifulSoup(r.text, "html.parser")
    fotos: list[str] = []
    for sc in soup.select('script[type="application/ld+json"]'):
        txt = sc.string or ""
        if '"image"' not in txt:
            continue
        try:
            data = _json.loads(txt)
        except Exception:  # noqa: BLE001
            continue
        nodes = data.get("@graph", [data]) if isinstance(data, dict) else data
        for node in nodes if isinstance(nodes, list) else []:
            img = node.get("image") if isinstance(node, dict) else None
            if isinstance(img, str):
                img = [img]
            for u in img or []:
                if isinstance(u, str) and f"/{it['id_portal']}/" in u and u not in fotos:
                    fotos.append(u)
    if not fotos:
        for m in re.finditer(r"https://www\.chavesnamao\.com\.br/imn/1200x0800/[^\"'\s\\]+?\.jpg", r.text):
            if f"/{it['id_portal']}/" in m.group(0) and m.group(0) not in fotos:
                fotos.append(m.group(0))
    flags = flags_from_text(soup.get_text(" ", strip=True)[:50000])
    for k, v in flags.items():
        if v:
            it[k] = True
    return fotos[:max_fotos] or (it.get("fotos") or [])


def coletar() -> list[dict]:
    s = session()
    todos: dict[str, dict] = {}
    for pagina in range(1, MAX_PAGINAS + 1):
        url = f"{BASE}{LISTA}" + (f"?pagina={pagina}" if pagina > 1 else "")
        r = get(s, url)
        if r.status_code != 200:
            break
        itens = _parse_pagina(r.text)
        n_cards = r.text.count('id="rc-')
        novos = 0
        for it in itens:
            if it["id"] not in todos:
                todos[it["id"]] = it
                novos += 1
        if n_cards == 0 or (pagina > 1 and novos == 0):
            break
    return list(todos.values())
