"""VivaReal (Grupo OLX/ZAP) — API pública glue-api, funciona de datacenter."""
from __future__ import annotations

from curl_cffi import requests as cr

from common import MIN_QUARTOS, bairro_bonito, flags_from_text, novo_imovel, regiao_de, to_int

NOME = "VivaReal"
BASE = "https://www.vivareal.com.br"
API = "https://glue-api.vivareal.com/v2/listings"
PAGE = 24
MAX_PAGINAS = 40
TIPOS_CASA = {"HOME", "CONDOMINIUM", "COUNTRY_HOUSE", "VILLAGE_HOUSE", "TWO_STORY_HOUSE"}

HDR = {
    "x-domain": "www.vivareal.com.br",
    "referer": "https://www.vivareal.com.br/",
    "origin": "https://www.vivareal.com.br",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

AMEN = {
    "POOL": "piscina", "PETS_ALLOWED": "aceita_pet", "FURNISHED": "mobiliada",
    "BARBECUE_GRILL": "churrasqueira",
}


def _params(frm: int) -> dict:
    return {
        "business": "RENTAL", "categoryPage": "RESULT", "listingType": "USED",
        "unitTypes": "HOME,CONDOMINIUM", "unitTypesV3": "HOME,CONDOMINIUM", "usageTypes": "RESIDENTIAL",
        "addressState": "Distrito Federal", "addressLocationId": "BR>Distrito Federal",
        "bedrooms": str(MIN_QUARTOS), "size": str(PAGE), "from": str(frm), "sort": "updatedAt DESC",
        "includeFields": (
            "search(result(listings(listing(id,title,address,bedrooms,bathrooms,parkingSpaces,usableAreas,"
            "totalAreas,pricingInfos,amenities,medias,updatedAt,createdAt,unitTypes,description),"
            "link(href),medias(url),account(name)),totalCount),totalCount)"
        ),
    }


def _img(url_tpl: str) -> str | None:
    if not url_tpl or "youtube" in url_tpl or "vimeo" in url_tpl:
        return None
    return (url_tpl.replace("{description}", "imagem").replace("{action}", "fit-in")
            .replace("{width}", "870").replace("{height}", "653"))


def _iso_brt(ts: str | None) -> str | None:
    """'2026-11-08T13:15:33.501+00:00' -> '2026-11-08T10:15:33-03:00'."""
    if not ts:
        return None
    from datetime import datetime, timedelta, timezone
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return d.astimezone(timezone(timedelta(hours=-3))).isoformat(timespec="seconds")
    except Exception:  # noqa: BLE001
        return ts[:10] or None


def _first(v):
    if isinstance(v, list):
        return v[0] if v else None
    return v


def _parse(item: dict) -> dict | None:
    lst = item.get("listing") or {}
    tipos = set(lst.get("unitTypes") or [])
    if tipos and not (tipos & TIPOS_CASA):
        return None
    quartos = to_int(_first(lst.get("bedrooms")))
    if quartos is None or quartos < MIN_QUARTOS:
        return None
    preco = None
    cond = None
    for p in lst.get("pricingInfos") or []:
        if p.get("businessType") == "RENTAL":
            preco = to_int(p.get("price"))
            cond = to_int(p.get("monthlyCondoFee")) or None
            break
    if not preco or preco < 300:
        return None
    addr = lst.get("address") or {}
    if (addr.get("stateAcronym") or "DF") != "DF":
        return None
    bairro = bairro_bonito(addr.get("neighborhood") or addr.get("city") or "Brasília")
    regiao = regiao_de(addr.get("neighborhood"), addr.get("street"), addr.get("city"))
    amen = set(lst.get("amenities") or [])
    flags = flags_from_text(f"{lst.get('title','')} {lst.get('description','')}")
    for a, k in AMEN.items():
        if a in amen:
            flags[k] = True
    fotos = [u for u in (_img(m.get("url", "")) for m in (item.get("medias") or lst.get("medias") or [])) if u][:10]
    href = (item.get("link") or {}).get("href")
    url = (BASE + href) if href and href.startswith("/") else (href or f"{BASE}/imovel/-id-{lst.get('id')}/")
    pt = addr.get("point") or {}
    return novo_imovel(
        portal=NOME,
        id_portal=str(lst.get("id")),
        titulo=lst.get("title") or f"Casa com {quartos} quartos",
        preco=preco,
        condominio=cond,
        bairro=bairro,
        regiao=regiao,
        quartos=quartos,
        banheiros=to_int(_first(lst.get("bathrooms"))),
        vagas=to_int(_first(lst.get("parkingSpaces"))),
        area_m2=to_int(_first(lst.get("usableAreas"))) or to_int(_first(lst.get("totalAreas"))),
        fotos=fotos,
        url=url,
        lat=pt.get("lat"),
        lng=pt.get("lon"),
        publicado_em=_iso_brt(lst.get("createdAt")),
        anunciante=(item.get("account") or {}).get("name"),
        **flags,
    )


def coletar() -> list[dict]:
    todos: dict[str, dict] = {}
    for i in range(MAX_PAGINAS):
        r = cr.get(API, params=_params(i * PAGE), headers=HDR, impersonate="chrome", timeout=40)
        if r.status_code != 200:
            raise RuntimeError(f"VivaReal HTTP {r.status_code}: {r.text[:200]}")
        lista = (((r.json().get("search") or {}).get("result") or {}).get("listings")) or []
        for it in lista:
            p = _parse(it)
            if p:
                todos.setdefault(p["id"], p)
        if len(lista) < PAGE:
            break
    return list(todos.values())
