import json, sys
sys.path.insert(0, 'collector')
from curl_cffi import requests as cr
from portals import quintoandar as Q, vivareal as V
# QuintoAndar: pede campos de data
p = Q._payload(0); p['fields'] = Q.FIELDS + ['createdAt','publishedAt','updatedAt','activationDate','listingCreatedAt','firstPublishedAt','availableAt','lastUpdatedAt']
p['pagination']['pageSize'] = 3
r = cr.post(Q.API, json=p, headers={'Accept':'application/json','Content-Type':'application/json','Origin':'https://www.quintoandar.com.br','Referer':'https://www.quintoandar.com.br/'}, impersonate='chrome', timeout=40)
print('QA status', r.status_code)
hits = r.json().get('hits',{}).get('hits',[])
for h in hits[:2]:
    src = h.get('_source',{})
    print('QA keys', sorted(src.keys()))
    print('QA dates', {k:v for k,v in src.items() if 'At' in k or 'Date' in k or 'date' in k})
    print('QA fields', h.get('fields'))
# QuintoAndar: página do imóvel tem data?
hid = hits[0]['_id'] if hits else None
if hid:
    r2 = cr.get(f'https://www.quintoandar.com.br/imovel/{hid}', impersonate='chrome', timeout=40, headers={'Accept-Language':'pt-BR'})
    t = r2.text; import re
    print('QA page', r2.status_code, len(t))
    for pat in [r'"createdAt":"[^"]+"', r'"publishedAt":"[^"]+"', r'"datePosted":"[^"]+"', r'"activationDate":"[^"]+"', r'Anunciado[^<]{0,60}', r'"listingDate":"[^"]+"']:
        m = re.findall(pat, t); print('  ', pat, m[:2])
# VivaReal createdAt completo
r = cr.get(V.API, params=V._params(0), headers=V.HDR, impersonate='chrome', timeout=40)
ls = r.json()['search']['result']['listings']
print('VR', [(x['listing'].get('createdAt'), x['listing'].get('updatedAt')) for x in ls[:3]])
