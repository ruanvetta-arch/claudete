import json, sys
sys.path.insert(0, 'collector')
from curl_cffi import requests as cr
from portals import vivareal as V

def q(extra, frm, size=24):
    p = V._params(frm); p.update(extra); p['size'] = str(size)
    r = cr.get(V.API, params=p, headers=V.HDR, impersonate='chrome', timeout=40)
    if r.status_code != 200:
        return None, r.text[:120]
    j = r.json(); res = j['search']['result']
    return res.get('listings', []), j['search'].get('totalCount')

for nome, extra in {
    'atual': {},
    'sem-bedrooms': {'bedrooms': None},
    'city-brasilia': {'addressCity': 'Brasília', 'addressLocationId': 'BR>Distrito Federal>NULL>Brasilia'},
    'so-HOME': {'unitTypes': 'HOME', 'unitTypesV3': 'HOME'},
    'so-CONDO': {'unitTypes': 'CONDOMINIUM', 'unitTypesV3': 'CONDOMINIUM'},
    'size30': {},
}.items():
    extra = {k: v for k, v in extra.items() if v is not None}
    if nome == 'sem-bedrooms':
        pass
    size = 30 if nome == 'size30' else 24
    tot_pages = []
    kept = 0
    for i in range(6):
        p = V._params(i*size); p.update(extra); p['size'] = str(size)
        if nome == 'sem-bedrooms': p.pop('bedrooms', None)
        r = cr.get(V.API, params=p, headers=V.HDR, impersonate='chrome', timeout=40)
        if r.status_code != 200:
            tot_pages.append(f'ERR{r.status_code}'); break
        j = r.json(); ls = j['search']['result'].get('listings', [])
        tot_pages.append(len(ls))
        kept += sum(1 for it in ls if V._parse(it))
        if i == 0:
            tc = j['search'].get('totalCount')
            types = {}
            for it in ls:
                for t in it['listing'].get('unitTypes', []): types[t] = types.get(t, 0) + 1
        if len(ls) < size: break
    print(nome, 'total', tc, 'pages', tot_pages, 'kept', kept, 'types', types, flush=True)
