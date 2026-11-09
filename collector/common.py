"""Utilitários compartilhados pelos coletores."""
from __future__ import annotations

import hashlib
import re
import time
import unicodedata
from typing import Any

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
}

MIN_QUARTOS = 2


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def get(s: requests.Session, url: str, retries: int = 3, **kw) -> requests.Response:
    last = None
    for i in range(retries):
        try:
            r = s.get(url, timeout=40, **kw)
            if r.status_code < 500:
                return r
            last = RuntimeError(f"HTTP {r.status_code}")
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(2 * (i + 1))
    raise last  # type: ignore[misc]


def post(s: requests.Session, url: str, retries: int = 3, **kw) -> requests.Response:
    last = None
    for i in range(retries):
        try:
            r = s.post(url, timeout=40, **kw)
            if r.status_code < 500:
                return r
            last = RuntimeError(f"HTTP {r.status_code}")
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(2 * (i + 1))
    raise last  # type: ignore[misc]


def strip_accents(txt: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn"
    )


def slug(txt: str) -> str:
    txt = strip_accents(txt or "").lower()
    txt = re.sub(r"[^a-z0-9]+", "-", txt).strip("-")
    return txt


def to_int(v: Any) -> int | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    m = re.search(r"\d[\d.]*(?:,\d+)?", str(v))
    if not m:
        return None
    n = m.group(0).replace(".", "").replace(",", ".")
    try:
        return int(float(n))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Regiões administrativas do DF: normalização de bairro -> região
# ---------------------------------------------------------------------------

REGIOES: dict[str, list[str]] = {
    "Plano Piloto": ["asa sul", "asa norte", "plano piloto", "brasilia", "setor sudoeste", "sudoeste", "noroeste", "octogonal", "cruzeiro", "setor de mansoes", "vila planalto", "granja do torto", "sqs", "sqn", "shcgn", "sqsw", "sqnw", "sres"],
    "Lago Sul": ["lago sul", "shis", "ql ", "qi "],
    "Lago Norte": ["lago norte", "shin", "setor de habitacoes individuais norte", "taquari"],
    "Jardim Botânico": ["jardim botanico", "jardim botânico", "altiplano", "sao bartolomeu", "quintas do sol", "ville de montagne", "estancia", "mansoes itaipu", "jardins mangueiral", "mangueiral"],
    "Park Way": ["park way", "parkway", "smpw", "nucleo bandeirante"],
    "Águas Claras": ["aguas claras", "areal", "arniqueira", "arniqueiras", "vereda da cruz"],
    "Vicente Pires": ["vicente pires", "colonia agricola samambaia", "colonia agricola vicente pires"],
    "Taguatinga": ["taguatinga"],
    "Guará": ["guara", "guará", "qe ", "qi 2", "lucio costa", "setor de industria e abastecimento"],
    "Sobradinho": ["sobradinho", "grande colorado", "colorado", "contagem", "nova colina", "mansoes colorado", "setor de mansoes sobradinho"],
    "Planaltina": ["planaltina", "arapoanga", "vale do amanhecer", "mestre d'armas"],
    "Samambaia": ["samambaia"],
    "Ceilândia": ["ceilandia", "ceilândia", "sol nascente", "por do sol", "pôr do sol"],
    "Gama": ["gama"],
    "Santa Maria": ["santa maria"],
    "Recanto das Emas": ["recanto das emas"],
    "Riacho Fundo": ["riacho fundo"],
    "São Sebastião": ["sao sebastiao", "são sebastião", "morro da cruz", "bela vista"],
    "Paranoá": ["paranoa", "paranoá", "itapoa", "itapoã"],
    "Candangolândia": ["candangolandia", "candangolândia"],
    "Brazlândia": ["brazlandia", "brazlândia"],
    "Varjão": ["varjao", "varjão"],
    "Fercal": ["fercal"],
    "SIA / SCIA": ["scia", "estrutural", "sia "],
    "SIA / SCIA": ["estrutural", "scia"],
}

_ALL_PATTERNS = [(slug(p), reg) for reg, pats in REGIOES.items() for p in pats]
# padrões mais longos primeiro (ex: "lago sul" antes de "brasilia")
_ALL_PATTERNS.sort(key=lambda x: -len(x[0]))


def regiao_de(*candidatos: str | None) -> str:
    """Devolve a região administrativa a partir de bairro/endereço/cidade."""
    texto = " | ".join(slug(c) for c in candidatos if c)
    texto = f" {texto.replace('-', ' ')} "
    for pat, reg in _ALL_PATTERNS:
        pat_s = f" {pat.replace('-', ' ').strip()} "
        if pat_s in texto:
            return reg
    return "Outras regiões"


def bairro_bonito(bairro: str | None, fallback: str = "Brasília") -> str:
    if not bairro:
        return fallback
    b = re.sub(r"\s+", " ", bairro).strip(" ,-")
    if b.isupper() or b.islower():
        b = b.title()
    # Pequenas correções comuns
    b = b.replace(" Df", "").replace(" De ", " de ").replace(" Do ", " do ").replace(" Da ", " da ")
    return b or fallback


PISCINA_RE = re.compile(r"piscina", re.I)
PET_RE = re.compile(r"(aceita|permite|permitid[oa]s?)\s+(animais|pets?)|pet\s*friendly|pets?\s+permitid|animais\s+permitid", re.I)
MOBILIADA_RE = re.compile(r"mobiliad[ao]", re.I)
CHURRASQ_RE = re.compile(r"churrasqueira", re.I)


def flags_from_text(texto: str) -> dict[str, bool]:
    t = texto or ""
    return {
        "piscina": bool(PISCINA_RE.search(t)),
        "aceita_pet": bool(PET_RE.search(t)),
        "mobiliada": bool(MOBILIADA_RE.search(t)) and not re.search(r"(sem|nao|não)\s+mobiliad", t, re.I),
        "churrasqueira": bool(CHURRASQ_RE.search(t)),
    }


def assinatura(regiao: str, preco: int | None, area: int | None, quartos: int | None) -> str:
    """Assinatura para detectar a mesma casa em portais diferentes."""
    p = round((preco or 0) / 50) * 50
    a = round((area or 0) / 5) * 5
    raw = f"{slug(regiao)}|{p}|{a}|{quartos or 0}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def novo_imovel(**kw) -> dict[str, Any]:
    base = {
        "id": None,
        "portal": None,
        "id_portal": None,
        "titulo": None,
        "preco": None,
        "condominio": None,
        "iptu": None,
        "bairro": None,
        "regiao": None,
        "quartos": None,
        "suites": None,
        "banheiros": None,
        "vagas": None,
        "area_m2": None,
        "piscina": False,
        "aceita_pet": False,
        "mobiliada": False,
        "churrasqueira": False,
        "fotos": [],
        "url": None,
        "lat": None,
        "lng": None,
        "publicado_em": None,
        "anunciante": None,
    }
    base.update(kw)
    if base["id_portal"] and base["portal"]:
        base["id"] = f"{slug(base['portal'])}-{base['id_portal']}"
    return base
