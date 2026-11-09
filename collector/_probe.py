"""Sonda temporária (roda no Actions)."""
import json
import re
import time
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


def olx():
    for attempt in range(3):
        r = g("https://www.olx.com.br/imoveis/aluguel/casas/estado-df?ros=2")
        t = r.text
        print("status", r.status_code, "len", len(t), "next_f", t.count("__next_f"), "listId", t.count('listId'), "ads", t.count('\\"ads\\"'), t.count('"ads"'))
        ttl = re.search(r"<title>([^<]*)", t)
        print("title", ttl.group(1) if ttl else None)
        i = t.find("listId")
        print("ctx", t[max(0, i - 1500):i + 300].replace("\n", " ")[:1800])
        if t.count("listId") > 5:
            break
        time.sleep(3)
    # tenta script application/json
    for m in re.finditer(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', t, re.S):
        s = m.group(1)
        if "listId" in s:
            print("JSON SCRIPT len", len(s), s[:400])
            break


sec("OLX", olx)
