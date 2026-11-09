"""Sonda: Chrome real (headed, xvfb) contra Cloudflare."""
import re
import sys
import time

from playwright.sync_api import sync_playwright

URLS = [
    "https://www.dfimoveis.com.br/aluguel/df/todos/casa?pagina=1",
    "https://www.wimoveis.com.br/aluguel/casas/df/mais-de-2-quartos",
]


def resumo(tag, html):
    t = html or ""
    title = re.search(r"<title>([^<]*)", t)
    print(f"== {tag}: len={len(t)} cards_df={t.count('RealEstateListing')} cards_wi={t.count('posting PROPERTY')} "
          f"cf={('Just a moment' in t) or ('Um momento' in t)} title={title.group(1)[:70] if title else None}", flush=True)


with sync_playwright() as p:
    for channel in ("chrome", None):
        try:
            b = p.chromium.launch(headless=False, channel=channel, args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        except Exception as e:  # noqa: BLE001
            print("launch", channel, "ERR", e)
            continue
        ctx = b.new_context(locale="pt-BR", timezone_id="America/Sao_Paulo", viewport={"width": 1366, "height": 768})
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        for u in URLS:
            pg = ctx.new_page()
            try:
                pg.goto(u, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:  # noqa: BLE001
                print("goto ERR", e)
            for i in range(6):
                time.sleep(5)
                html = pg.content()
                resumo(f"{channel} t+{(i+1)*5}s {u[8:30]}", html)
                if "RealEstateListing" in html or "posting PROPERTY" in html:
                    break
            cookies = ctx.cookies()
            print("cookies:", [c["name"] for c in cookies if "cf" in c["name"].lower()])
            pg.close()
        b.close()
