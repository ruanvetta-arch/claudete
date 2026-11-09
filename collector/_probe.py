"""Sonda temporária para descobrir a estrutura das fontes (roda no Actions)."""
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


def vivareal():
    u = ("https://glue-api.vivareal.com/v2/listings?addressCity=Bras%C3%ADlia&addressState=Distrito%20Federal"
         "&addressLocationId=BR%3EDistrito%20Federal%3ENULL%3EBrasilia&business=RENTAL&categoryPage=RESULT"
         "&listingType=USED&unitTypes=HOME&unitTypesV3=HOME&usageTypes=RESIDENTIAL&bedrooms=2&size=24&from=0"
         "&sort=updatedAt%20DESC&includeFields=search(result(listings(listing(id,title,address,bedrooms,bathrooms,"
         "parkingSpaces,usableAreas,totalAreas,pricingInfos,amenities,images,updatedAt,createdAt,unitTypes),"
         "link(href),account(name)),totalCount))")
    r = g(u, **{"x-domain": "www.vivareal.com.br", "referer": "https://www.vivareal.com.br/", "origin": "https://www.vivareal.com.br"})
    print("status", r.status_code)
    j = r.json()
    print("keys", list(j.keys()), "search keys", list(j.get("search", {}).keys()))
    res = j["search"]["result"]
    print("result keys", list(res.keys()))
    print("n", len(res.get("listings", [])), "total", j["search"].get("totalCount"))
    print("sample", json.dumps(res["listings"][0], ensure_ascii=False)[:2500])


def olx():
    r = g("https://www.olx.com.br/imoveis/aluguel/casas/estado-df?ros=2")
    t = r.text
    print("status", r.status_code, len(t))
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', t, re.S)
    print("nextdata", bool(m))
    if m:
        d = json.loads(m.group(1))
        pp = d.get("props", {}).get("pageProps", {})
        print("pp keys", list(pp.keys())[:30])
        s = json.dumps(pp, ensure_ascii=False)
        i = s.find('"ads"')
        print("ads ctx", s[i:i + 2500])
        return
    # Next 13+ app router: dados em self.__next_f.push
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', t, re.S)
    print("next_f chunks", len(chunks))
    big = "".join(c.encode().decode("unicode_escape", errors="ignore") for c in chunks)
    for key in ['"ads":', '"listId"', '"adList"', '"subject"', '"price"']:
        i = big.find(key)
        print(key, i, big[i:i + 1500] if i > 0 else "")
        if i > 0:
            break


def nestoria():
    r = g("https://www.nestoria.com.br/distrito-federal/casas/aluguel?bedrooms=2&sort=newest")
    t = r.text
    print("status", r.status_code, len(t))
    for pat in [r"__NEXT_DATA__", r"window\.__INITIAL_STATE__", r'"listings"', r"data-listing", r"wimoveis", r"dfimoveis", r"quintoandar", r'"lister_url"', r'"source"', r'application/ld\+json', r"listing-item", r'data-id']:
        print(f"  {pat}: {len(re.findall(pat, t))}")
    for key in ['"listings"', "__NEXT_DATA__", "window.__INITIAL"]:
        i = t.find(key)
        if i > 0:
            print("ctx", key, t[i:i + 2000])
            break
    # mostra o primeiro bloco que pareça card
    i = t.find("listing-item")
    print("card ctx", t[i - 300:i + 2500] if i > 0 else "")


def mitula():
    r = g("https://imoveis.mitula.com.br/imoveis/aluguel-casas-2-quartos-brasilia")
    t = r.text
    print("status", r.status_code, len(t))
    for pat in [r"__NEXT_DATA__", r'"listings"', r"wimoveis", r"dfimoveis", r"data-source", r"application/ld\+json", r"listing-card", r'data-id']:
        print(f"  {pat}: {len(re.findall(pat, t))}")
    m = re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, re.S)
    for x in m[:3]:
        print("ld", x[:1200])
    i = t.find("listing-card")
    print("card ctx", t[i - 300:i + 2500] if i > 0 else "")


sec("VIVAREAL", vivareal)
sec("OLX", olx)
sec("NESTORIA", nestoria)
sec("MITULA", mitula)
