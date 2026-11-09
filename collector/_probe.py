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


def next_f(t):
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', t, re.S)
    out = []
    for c in chunks:
        try:
            out.append(json.loads('"' + c + '"'))
        except Exception:  # noqa: BLE001
            out.append(c.encode("utf-8", "surrogatepass").decode("unicode_escape", "ignore"))
    return "".join(out)


def balanced(big, key):
    i = big.find(key)
    if i < 0:
        return None
    j = i + len(key)
    while big[j] not in "[{":
        j += 1
    opener = big[j]
    closer = "]" if opener == "[" else "}"
    depth = 0
    k = j
    in_str = False
    esc = False
    while k < len(big):
        ch = big[k]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return json.loads(big[j:k + 1])
        k += 1
    return None


def olx():
    t = g("https://www.olx.com.br/imoveis/aluguel/casas/estado-df?ros=2").text
    big = next_f(t)
    print("big len", len(big), "ads idx", big.find('"ads":'))
    ads = balanced(big, '"ads":')
    print("n", len(ads or []))
    m = re.search(r'"totalOfAds":(\d+)', big)
    print("total", m.group(1) if m else None)
    if ads:
        print("AD0", json.dumps(ads[0], ensure_ascii=False)[:5000])
        print("KEYS", sorted(ads[0].keys()))
    t2 = g("https://www.olx.com.br/imoveis/aluguel/casas/estado-df?ros=2&o=2").text
    ads2 = balanced(next_f(t2), '"ads":')
    print("p2 n", len(ads2 or []), "first", ads2[0].get("listId") if ads2 else None, "p1 first", ads[0].get("listId") if ads else None)


def vivareal():
    base = ("https://glue-api.vivareal.com/v2/listings?business=RENTAL&categoryPage=RESULT&listingType=USED"
            "&unitTypes=HOME,CONDOMINIUM&unitTypesV3=HOME,CONDOMINIUM&usageTypes=RESIDENTIAL&size=24&sort=updatedAt%20DESC"
            "&includeFields=search(result(listings(listing(id,title,address,bedrooms,bathrooms,parkingSpaces,usableAreas,totalAreas,pricingInfos,amenities,medias,updatedAt,createdAt,unitTypes,description,listingsCount),link(href,name),medias(url),account(name,logoUrl)),totalCount),totalCount)")
    hdr = {"x-domain": "www.vivareal.com.br", "referer": "https://www.vivareal.com.br/", "origin": "https://www.vivareal.com.br"}
    variants = {
        "city+bed2": "&addressCity=Bras%C3%ADlia&addressState=Distrito%20Federal&addressLocationId=BR%3EDistrito%20Federal%3ENULL%3EBrasilia&bedrooms=2&from=0",
        "city": "&addressCity=Bras%C3%ADlia&addressState=Distrito%20Federal&addressLocationId=BR%3EDistrito%20Federal%3ENULL%3EBrasilia&from=0",
        "state": "&addressState=Distrito%20Federal&addressLocationId=BR%3EDistrito%20Federal&from=0",
        "state+bed2": "&addressState=Distrito%20Federal&addressLocationId=BR%3EDistrito%20Federal&bedrooms=2&from=0",
    }
    for k, v in variants.items():
        r = g(base + v, **hdr)
        if r.status_code != 200:
            print(k, r.status_code, r.text[:150])
            continue
        j = r.json()
        ls = j["search"]["result"]["listings"]
        print(k, "n", len(ls), "total", j["search"].get("totalCount"))
        if k == "state":
            print("L0", json.dumps(ls[0], ensure_ascii=False)[:3500])
    # testa URL por id
    r = g("https://www.vivareal.com.br/imovel/-id-2916019662/", allow_redirects=True)
    print("url-by-id", r.status_code, r.url)


sec("OLX", olx)
sec("VIVAREAL", vivareal)
