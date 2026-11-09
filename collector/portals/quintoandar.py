"""QuintoAndar — API pública house-listing-search/v3/search/list."""
from __future__ import annotations

from common import (MIN_QUARTOS, bairro_bonito, flags_from_text, novo_imovel, post,
                    regiao_de, session, to_int)

NOME = "QuintoAndar"
API = "https://apigw.prod.quintoandar.com.br/house-listing-search/v3/search/list"
SLUG = "brasilia-df-brasil"
PAGE = 50
MAX_PAGINAS = 20

FIELDS = [
    "id", "coverImage", "rent", "totalCost", "iptuPlusCondominium", "area", "imageList",
    "address", "regionName", "city", "type", "forRent", "bedrooms", "parkingSpaces",
    "suites", "listingTags", "neighbourhood", "bathrooms", "isFurnished", "installations",
    "amenities", "shortRentDescription",
]


def _payload(offset: int) -> dict:
    return {
        "slug": SLUG,
        "topics": [],
        "fields": FIELDS,
        "sorting": {"criteria": "RELEVANCE", "order": "DESC"},
        "pagination": {"pageSize": PAGE, "offset": offset},
        "context": {"listShowing": True, "mapShowing": False, "numPhotos": 12, "isSSR": False},
        "filters": {
            "businessContext": "RENT",
            "location": {"coordinate": {}, "viewport": {}, "neighborhoods": [], "countryCode": "BR"},
            "priceRange": [],
            "availability": "ANY",
            "occupancy": "ANY",
            "partnerIds": [],
            "specialConditions": [],
            "excludedSpecialConditions": [],
            "blocklist": [],
            "selectedHouses": [],
            "categories": [],
            "houseSpecs": {
                "area": {"range": {}},
                "houseTypes": ["HOUSE"],
                "amenities": [],
                "installations": [],
                "bathrooms": {"range": {}},
                "bedrooms": {"range": {"min": MIN_QUARTOS}},
                "parkingSpace": {"range": {}},
                "suites": {"range": {}},
            },
            "origin": "HYBRID",
        },
        "locationDescriptions": [{"description": SLUG}],
    }


def _img(name: str) -> str:
    name = name if name.startswith("original") else f"original{name}"
    return f"https://www.quintoandar.com.br/img/crop/landscape/1200x800/{name}"


def _parse(hit: dict) -> dict | None:
    src = hit.get("_source") or {}
    if (src.get("type") or "").lower() not in ("casa", "house", "casa de condomínio", "casa de condominio"):
        if src.get("type"):
            return None
    quartos = to_int(src.get("bedrooms"))
    if quartos is None or quartos < MIN_QUARTOS:
        return None
    preco = to_int(src.get("rent"))
    if not preco or preco < 300:
        return None
    # Filtra fora do DF (a API às vezes relaxa localização)
    cidade = src.get("city") or ""
    if cidade and "bras" not in cidade.lower() and "df" not in cidade.lower():
        return None
    bairro = bairro_bonito(src.get("neighbourhood") or src.get("regionName"))
    regiao = regiao_de(bairro, src.get("regionName"), src.get("address"))
    amen = " ".join((src.get("amenities") or []) + (src.get("installations") or []))
    texto = f"{src.get('shortRentDescription','')} {amen}"
    flags = flags_from_text(texto)
    if "PODE_TER_ANIMAIS_DE_ESTIMACAO" in amen:
        flags["aceita_pet"] = True
    if "PISCINA" in amen:
        flags["piscina"] = True
    if src.get("isFurnished"):
        flags["mobiliada"] = True
    fotos = [_img(n) for n in (src.get("imageList") or [])[:8]]
    if not fotos and src.get("coverImage"):
        fotos = [_img(src["coverImage"])]
    ident = str(src.get("id") or hit.get("_id"))
    return novo_imovel(
        portal=NOME,
        id_portal=ident,
        titulo=src.get("shortRentDescription") or f"Casa com {quartos} quartos",
        preco=preco,
        condominio=to_int(src.get("iptuPlusCondominium")) or None,
        bairro=bairro,
        regiao=regiao,
        quartos=quartos,
        suites=to_int(src.get("suites")),
        banheiros=to_int(src.get("bathrooms")),
        vagas=to_int(src.get("parkingSpaces")),
        area_m2=to_int(src.get("area")),
        fotos=fotos,
        url=f"https://www.quintoandar.com.br/imovel/{ident}",
        anunciante="QuintoAndar",
        **flags,
    )


def coletar() -> list[dict]:
    s = session()
    s.headers.update({
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://www.quintoandar.com.br",
        "Referer": "https://www.quintoandar.com.br/",
    })
    todos: dict[str, dict] = {}
    for i in range(MAX_PAGINAS):
        r = post(s, API, json=_payload(i * PAGE))
        if r.status_code != 200:
            raise RuntimeError(f"QuintoAndar HTTP {r.status_code}: {r.text[:200]}")
        hits = ((r.json().get("hits") or {}).get("hits")) or []
        for h in hits:
            it = _parse(h)
            if it:
                todos.setdefault(it["id"], it)
        if len(hits) < PAGE:
            break
    return list(todos.values())
