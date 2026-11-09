"""Sonda temporária (roda no Actions)."""
import json
import re
import traceback

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


def olx_ads(url):
    t = g(url).text
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', t, re.S)
    big = "".join(json.loads('"' + c + '"') for c in chunks)
    i = big.find('"ads":[')
    if i < 0:
        return None, big[:500]
    # extrai o array balanceado
    j = i + len('"ads":')
    depth = 0
    k = j
    while k < len(big):
        ch = big[k]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                break
        k += 1
    arr = json.loads(big[j:k + 1])
    m = re.search(r'"totalOfAds":(\d+)', big)
    return arr, (m.group(1) if m else None)


def olx():
    ads, total = olx_ads("https://www.olx.com.br/imoveis/aluguel/casas/estado-df?ros=2")
    print("n", len(ads or []), "total", total)
    print("AD0", json.dumps(ads[0], ensure_ascii=False)[:4000])
    print("KEYS", sorted(ads[0].keys()))
    ads2, _ = olx_ads("https://www.olx.com.br/imoveis/aluguel/casas/estado-df?ros=2&o=2")
    print("p2 n", len(ads2 or []), "first", ads2[0]["listId"] if ads2 else None, "vs p1", ads[0]["listId"])


def vivareal():
    def q(frm, size=24):
        u = ("https://glue-api.vivareal.com/v2/listings?addressCity=Bras%C3%ADlia&addressState=Distrito%20Federal"
             "&addressLocationId=BR%3EDistrito%20Federal%3ENULL%3EBrasilia&business=RENTAL&categoryPage=RESULT"
             "&listingType=USED&unitTypes=HOME,CONDOMINIUM&unitTypesV3=HOME,CONDOMINIUM&unitSubTypes=UnitSubType_NONE,SINGLE_STOREY_HOUSE,VILLAGE_HOUSE,KITNET,TWO_STORY_HOUSE|CONDOMINIUM&usageTypes=RESIDENTIAL"
             f"&bedrooms=2&size={size}&from={frm}&sort=updatedAt%20DESC&includeFields=search(result(listings(listing(id,title,address,bedrooms,bathrooms,parkingSpaces,usableAreas,totalAreas,pricingInfos,amenities,images,updatedAt,createdAt,unitTypes,unitSubTypes,description),link(href,name),account(name)),totalCount),totalCount)&__vt=")
        return g(u, **{"x-domain": "www.vivareal.com.br", "referer": "https://www.vivareal.com.br/", "origin": "https://www.vivareal.com.br"})
    r = q(0)
    print("status", r.status_code)
    j = r.json()
    print("top", json.dumps({k: (v if k != "search" else "...") for k, v in j.items()})[:300])
    res = j["search"]["result"]
    ls = res["listings"]
    print("n", len(ls), "totalCount", j["search"].get("totalCount"), res.get("totalCount"))
    types = {}
    for x in ls:
        for ut in x["listing"].get("unitTypes", []):
            types[ut] = types.get(ut, 0) + 1
    print("unitTypes", types)
    print("L0", json.dumps(ls[0], ensure_ascii=False)[:3000])
    r2 = q(24)
    print("p2 status", r2.status_code, "n", len(r2.json()["search"]["result"]["listings"]))
    r3 = q(0, 36)
    print("size36 status", r3.status_code, r3.text[:150] if r3.status_code != 200 else len(r3.json()["search"]["result"]["listings"]))


sec("OLX", olx)
sec("VIVAREAL", vivareal)
