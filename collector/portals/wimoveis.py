"""Wimoveis / Imovelweb (mesma base Navent) — API JSON rplis-api/postings."""
from __future__ import annotations

from common import (MIN_QUARTOS, bairro_bonito, flags_from_text, get, novo_imovel,
                    post, regiao_de, session, to_int)

NOME = "Wimoveis"
BASE = "https://www.wimoveis.com.br"
API = f"{BASE}/rplis-api/postings"
PROVINCIA_DF = "247"
MAX_PAGINAS = 40


def _payload(pagina: int) -> dict:
    return {
        "q": None, "direccion": None, "moneda": None, "preciomin": None, "preciomax": None,
        "services": "", "general": "", "searchbykeyword": "", "amenidades": "",
        "caracteristicasprop": None, "comodidades": "", "disposicion": None, "roomType": "",
        "outside": "", "areaPrivativa": "", "areaComun": "", "multipleRets": "",
        "tipoDePropiedad": "1",  # casas
        "subtipoDePropiedad": None,
        "tipoDeOperacion": "2",  # aluguel
        "garages": None, "antiguedad": None, "expensasminimo": None, "expensasmaximo": None,
        "habitacionesminimo": str(MIN_QUARTOS), "habitacionesmaximo": "",
        "ambientesminimo": "", "ambientesmaximo": "", "banos": None,
        "superficieCubierta": 1, "idunidaddemedida": 1, "metroscuadradomin": None,
        "metroscuadradomax": None, "tipoAnunciante": "ALL", "grupoTipoDeMultimedia": "",
        "publicacion": None, "sort": "more_recent", "etapaDeDesarrollo": "", "auctions": None,
        "polygonApplied": None, "idInmobiliaria": None, "excludePostingContacted": "",
        "banks": "", "places": "", "condominio": "", "pagina": pagina, "city": None,
        "province": PROVINCIA_DF, "zone": None, "valueZone": None, "subZone": None,
        "coordenates": None,
    }


def _feature(p: dict, fid: str) -> int | None:
    f = (p.get("mainFeatures") or {}).get(fid)
    return to_int(f.get("value")) if f else None


def _parse(p: dict) -> dict | None:
    quartos = _feature(p, "CFT2")
    if quartos is None or quartos < MIN_QUARTOS:
        return None
    prices = ((p.get("priceOperationTypes") or [{}])[0].get("prices") or [{}])
    preco = to_int(prices[0].get("amount")) if prices else None
    if not preco or preco < 300:
        return None
    loc = (p.get("postingLocation") or {}).get("location") or {}
    bairro = loc.get("name")
    cidade = (loc.get("parent") or {}).get("name")
    # Quando a "zona" é a própria cidade (ex.: Brasília), usa endereço
    addr = ((p.get("postingLocation") or {}).get("address") or {}).get("name") or ""
    if loc.get("label") == "CIUDAD":
        cidade, bairro = bairro, None
    bairro = bairro_bonito(bairro, fallback=bairro_bonito(cidade or "Brasília"))
    regiao = regiao_de(bairro, cidade, addr)

    geo = ((p.get("postingLocation") or {}).get("postingGeolocation") or {}).get("geolocation") or {}
    fotos = []
    for pic in ((p.get("visiblePictures") or {}).get("pictures") or [])[:8]:
        u = pic.get("url730x532") or pic.get("url360x266")
        if u:
            fotos.append(u)
    gf = p.get("generalFeatures") or {}
    gf_text = " ".join(
        str(v.get("label", "")) for cat in gf.values() if isinstance(cat, dict) for v in cat.values() if isinstance(v, dict)
    )
    texto = f"{p.get('title','')} {p.get('descriptionNormalized','')} {gf_text}"
    flags = flags_from_text(texto)
    exp = (p.get("expenses") or {}).get("amount")
    return novo_imovel(
        portal=NOME,
        id_portal=str(p.get("postingId")),
        titulo=p.get("generatedTitle") or p.get("title"),
        preco=preco,
        condominio=to_int(exp) or None,
        bairro=bairro,
        regiao=regiao,
        quartos=quartos,
        banheiros=_feature(p, "CFT3"),
        vagas=_feature(p, "CFT7"),
        area_m2=_feature(p, "CFT100") or _feature(p, "CFT101"),
        fotos=fotos,
        url=BASE + p.get("url", ""),
        lat=geo.get("latitude"),
        lng=geo.get("longitude"),
        publicado_em=(p.get("modified_date") or "")[:10] or None,
        anunciante=(p.get("publisher") or {}).get("name"),
        **flags,
    )


def coletar() -> list[dict]:
    s = session()
    # Visita a listagem antes para receber cookies (Cloudflare)
    get(s, f"{BASE}/aluguel/casas/df/mais-de-2-quartos")
    s.headers.update({
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": f"{BASE}/aluguel/casas/df/mais-de-2-quartos",
        "Origin": BASE,
    })
    todos: dict[str, dict] = {}
    for pagina in range(1, MAX_PAGINAS + 1):
        r = post(s, API, json=_payload(pagina))
        if r.status_code != 200:
            raise RuntimeError(f"Wimoveis HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        lista = data.get("listPostings") or []
        for p in lista:
            it = _parse(p)
            if it:
                todos.setdefault(it["id"], it)
        if len(lista) < 30:
            break
    return list(todos.values())
