"""DF Imóveis — HTML server-side com JSON-LD (schema.org ItemList)."""
from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from common import (MIN_QUARTOS, bairro_bonito, flags_from_text, get, novo_imovel,
                    regiao_de, session, to_int)

NOME = "DF Imóveis"
BASE = "https://www.dfimoveis.com.br"
LISTAS = [
    "/aluguel/df/todos/casa",
    "/aluguel/df/todos/casa-condominio",
]
MAX_PAGINAS = 60


def _parse_pagina(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    itens: list[dict] = []

    # 1) JSON-LD (dados ricos)
    ld_items: dict[str, dict] = {}
    for sc in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(sc.string or "")
        except Exception:  # noqa: BLE001
            continue
        if isinstance(data, dict) and data.get("@type") == "ItemList":
            for el in data.get("itemListElement", []):
                it = el.get("item") or {}
                ident = str(it.get("identifier") or "")
                if ident:
                    ld_items[ident] = it

    # 2) Cards HTML (para vagas, condomínio, texto extra)
    for art in soup.select('article[itemtype*="RealEstateListing"]'):
        a = art.select_one("a[href*='/imovel/']")
        if not a:
            continue
        href = a.get("href", "")
        m = re.search(r"-(\d+)$", href.split("?")[0])
        if not m:
            continue
        ident = m.group(1)
        ld = ld_items.get(ident, {})
        texto = art.get_text(" ", strip=True)

        quartos = to_int(ld.get("numberOfBedrooms"))
        if quartos is None:
            mq = re.search(r"(\d+)\s*Quartos?", texto, re.I)
            quartos = to_int(mq.group(1)) if mq else None
        if quartos is None or quartos < MIN_QUARTOS:
            continue

        preco = to_int((ld.get("offers") or {}).get("price"))
        if preco is None:
            mp = re.search(r"R\$\s*([\d.]+)", texto)
            preco = to_int(mp.group(1)) if mp else None
        if not preco or preco < 300:
            continue

        area = to_int((ld.get("floorSize") or {}).get("value"))
        if area is None:
            ma = re.search(r"(\d+)\s*m²", texto)
            area = to_int(ma.group(1)) if ma else None

        mv = re.search(r"(\d+)\s*Vagas?", texto, re.I)
        vagas = to_int(mv.group(1)) if mv else None

        addr = ld.get("address") or {}
        street = addr.get("streetAddress") or ""
        # "Avenida do Sol, Jardim Botânico" -> bairro é a última parte
        partes = [p.strip() for p in street.split(",") if p.strip()]
        bairro = partes[-1] if partes else None
        h2 = art.select_one("h2[itemprop=name]")
        if h2:
            # "Avenida do Sol, JARDIM BOTANICO, BRASILIA"
            hp = [p.strip() for p in h2.get_text().split(",") if p.strip()]
            if len(hp) >= 2:
                bairro = bairro or hp[-2]
        bairro = bairro_bonito(bairro)
        regiao = regiao_de(bairro, street, h2.get_text() if h2 else None)

        desc = ld.get("description") or ""
        flags = flags_from_text(f"{ld.get('name','')} {desc} {texto}")

        fotos = [u for u in (ld.get("image") or []) if isinstance(u, str)]
        if not fotos:
            img = art.select_one("img[src*='img.dfimoveis']")
            if img:
                fotos = [img["src"]]

        geo = ld.get("geo") or {}
        anunciante_img = art.select_one(".imovel-anunciante img")
        itens.append(
            novo_imovel(
                portal=NOME,
                id_portal=ident,
                titulo=(ld.get("name") or h2.get_text(strip=True) if h2 else "Casa para alugar"),
                preco=preco,
                bairro=bairro,
                regiao=regiao,
                quartos=quartos,
                vagas=vagas,
                area_m2=area,
                fotos=fotos[:8],
                url=BASE + href.split("?")[0] if href.startswith("/") else href,
                lat=geo.get("latitude"),
                lng=geo.get("longitude"),
                publicado_em=ld.get("datePosted"),
                anunciante=anunciante_img.get("alt") if anunciante_img else None,
                **flags,
            )
        )
    return itens


FOTO_RE = re.compile(r"https://img\.dfimoveis\.com\.br/fotos/(\d+)/[a-f0-9]+\.(?:webp|jpg)")


def fotos_detalhe(s, it: dict, max_fotos: int = 12) -> list[str]:
    """Abre a página do anúncio e devolve todas as fotos (a listagem traz só 1)."""
    r = get(s, it["url"])
    if r.status_code != 200:
        return it.get("fotos") or []
    vistos: list[str] = []
    for m in FOTO_RE.finditer(r.text):
        if m.group(1) != it["id_portal"]:
            continue
        u = m.group(0)
        if u not in vistos:
            vistos.append(u)
        if len(vistos) >= max_fotos:
            break
    # Complementa flags com o texto completo do anúncio
    flags = flags_from_text(re.sub(r"<[^>]+>", " ", r.text[:200000]))
    for k, v in flags.items():
        if v:
            it[k] = True
    return vistos or (it.get("fotos") or [])


def coletar() -> list[dict]:
    s = session()
    todos: dict[str, dict] = {}
    for lista in LISTAS:
        vazias = 0
        for pagina in range(1, MAX_PAGINAS + 1):
            url = f"{BASE}{lista}?pagina={pagina}"
            r = get(s, url)
            if r.status_code != 200:
                break
            itens = _parse_pagina(r.text)
            n_cards = r.text.count('itemtype="https://schema.org/RealEstateListing"')
            for it in itens:
                todos.setdefault(it["id"], it)
            if n_cards == 0:
                vazias += 1
                if vazias >= 2:
                    break
            elif n_cards < 30:
                break
    return list(todos.values())
