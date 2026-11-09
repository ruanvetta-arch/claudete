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
    "Lago Sul": ["lago sul", "shis", "shdb", "setor de habitacoes individuais sul", "setor habitacional dom bosco", "dom bosco", "setor de mansoes dom bosco", "smdb"],
    "Lago Norte": ["lago norte", "shin", "setor de habitacoes individuais norte", "taquari", "setor de mansoes do lago norte", "smln"],
    "Jardim Botânico": ["jardim botanico", "altiplano", "sao bartolomeu", "quintas do sol", "ville de montagne", "estancia", "mansoes itaipu", "jardins mangueiral", "mangueiral", "tororo", "setor habitacional tororo", "jardim botanico vi", "solar de brasilia", "privé"],
    "Park Way": ["park way", "parkway", "smpw", "nucleo bandeirante", "setor de mansoes park way"],
    "Plano Piloto": ["asa sul", "asa norte", "plano piloto", "setor sudoeste", "sudoeste", "noroeste", "octogonal", "cruzeiro", "vila planalto", "granja do torto", "sqs", "sqn", "shcgn", "sqsw", "sqnw", "sres", "shcs", "shcn", "setor de habitacoes coletivas", "vila telebrasilia", "setor militar urbano"],
    "Águas Claras": ["aguas claras", "areal", "arniqueira", "arniqueiras", "vereda da cruz", "setor habitacional arniqueira"],
    "Vicente Pires": ["vicente pires", "colonia agricola samambaia", "colonia agricola vicente pires", "setor habitacional vicente pires"],
    "Taguatinga": ["taguatinga", "qnl", "qnm", "qsd", "qsa", "qsb", "qsc", "qse", "qsf", "qnj", "qng", "qnh", "qni", "qna", "qnb", "qnc", "qnd", "qne", "qnf"],
    "Guará": ["guara", "qe ", "qi ", "lucio costa", "setor de industria e abastecimento"],
    "Sobradinho": ["sobradinho", "grande colorado", "colorado", "contagem", "nova colina", "mansoes colorado", "setor de mansoes sobradinho", "alto da boa vista", "rk ", "vale das acacias"],
    "Planaltina": ["planaltina", "arapoanga", "vale do amanhecer", "mestre d'armas", "mestre darmas"],
    "Samambaia": ["samambaia", "setor de mansoes sudeste"],
    "Ceilândia": ["ceilandia", "sol nascente", "por do sol", "qnn", "qno", "qnp", "qnq", "qnr", "expansao do setor o"],
    "Gama": ["gama"],
    "Santa Maria": ["santa maria"],
    "Recanto das Emas": ["recanto das emas"],
    "Riacho Fundo": ["riacho fundo"],
    "São Sebastião": ["sao sebastiao", "morro da cruz", "bela vista", "residencial oeste", "vila nova"],
    "Paranoá": ["paranoa", "itapoa"],
    "Candangolândia": ["candangolandia"],
    "Brazlândia": ["brazlandia"],
    "Varjão": ["varjao"],
    "Fercal": ["fercal"],
    "SIA / SCIA": ["estrutural", "scia", "sia "],
}

_ALL_PATTERNS = [(slug(p).replace("-", " ").strip(), reg) for reg, pats in REGIOES.items() for p in pats]
# padrões mais longos primeiro
_ALL_PATTERNS.sort(key=lambda x: -len(x[0]))
# Genéricos que só valem como último recurso
_GENERICOS = {"brasilia": "Plano Piloto", "distrito federal": None, "df": None}


def _match(texto: str) -> str | None:
    t = f" {slug(texto).replace('-', ' ')} "
    for pat, reg in _ALL_PATTERNS:
        if f" {pat} " in t or (pat.endswith(" ") and f" {pat}" in t):
            return reg
    return None


def regiao_de(*candidatos: str | None) -> str:
    """Região administrativa a partir de (bairro, endereço, cidade...), nessa ordem de prioridade.

    Termos genéricos ("Brasília") só decidem se nada mais bateu.
    """
    cands = [c for c in candidatos if c]
    for c in cands:
        s = slug(c).replace("-", " ").strip()
        if s in _GENERICOS:
            continue
        r = _match(c)
        if r:
            return r
    for c in cands:
        s = slug(c).replace("-", " ").strip()
        if s in _GENERICOS and _GENERICOS[s]:
            return _GENERICOS[s]
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
        "publicado_em": None,   # data (YYYY-MM-DD) ou data+hora ISO em que o portal publicou
        "publicado_txt": None,  # texto quando o portal só dá algo vago ("há mais de 1 ano")
        "anunciante": None,
    }
    base.update(kw)
    if base["id_portal"] and base["portal"]:
        base["id"] = f"{slug(base['portal'])}-{base['id_portal']}"
    return base
