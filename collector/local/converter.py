"""Converte os JSONs crus coletados no navegador (IP residencial) para data/externos/<portal>.json.

Uso:
  python collector/local/converter.py wimoveis  caminho/para/wimoveis_bruto.json
  python collector/local/converter.py dfimoveis caminho/para/dfimoveis_bruto.json
Pode receber vários arquivos (chunks) do mesmo portal.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import MIN_QUARTOS, bairro_bonito, flags_from_text, novo_imovel, regiao_de, to_int  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
EXTERNOS = ROOT / "data" / "externos"
BRT = timezone(timedelta(hours=-3))


def _foto_wi(posting_id: str, pic: str, first: bool) -> str:
    p = posting_id.zfill(10)
    return (f"https://imgbr.imovelwebcdn.com/avisos/2/{p[0:2]}/{p[2:4]}/{p[4:6]}/{p[6:8]}/{p[8:10]}/720x532/{pic}.jpg"
            + ("?isFirstImage=true" if first else ""))


def conv_wimoveis(raw: dict) -> dict | None:
    quartos = to_int(raw.get("quartos"))
    preco = to_int(raw.get("preco"))
    if quartos is None or quartos < MIN_QUARTOS or not preco or preco < 300:
        return None
    bairro, cidade = raw.get("bairro"), raw.get("cidade")
    if raw.get("bairro_label") == "CIUDAD" or raw.get("bairro_cidade"):
        cidade, bairro = bairro, None
    pid = str(raw["id"])
    fotos = raw.get("fotos") or []
    if fotos and not str(fotos[0]).startswith("http"):
        raw["fotos"] = [_foto_wi(pid, str(f), i == 0) for i, f in enumerate(fotos)]
    url = raw.get("url") or ""
    if url and not url.startswith("http"):
        raw["url"] = "https://www.wimoveis.com.br/propriedades/" + url
    bairro = bairro_bonito(bairro, fallback=bairro_bonito(cidade or "Brasília"))
    return novo_imovel(
        portal="Wimoveis", id_portal=str(raw["id"]), titulo=raw.get("titulo"), preco=preco,
        condominio=to_int(raw.get("condominio")) or None, bairro=bairro,
        regiao=regiao_de(bairro, cidade, raw.get("endereco")), quartos=quartos,
        banheiros=to_int(raw.get("banheiros")), vagas=to_int(raw.get("vagas")), area_m2=to_int(raw.get("area")),
        fotos=[f for f in raw.get("fotos") or [] if f][:10], url=raw.get("url"), lat=raw.get("lat"), lng=raw.get("lng"),
        publicado_em=(raw.get("modificado") or "")[:10] or None, anunciante=raw.get("anunciante"),
        **flags_from_text(raw.get("texto") or ""),
    )


def conv_dfimoveis(raw: dict) -> dict | None:
    quartos = to_int(raw.get("quartos"))
    preco = to_int(raw.get("preco"))
    if quartos is None or quartos < MIN_QUARTOS or not preco or preco < 300:
        return None
    street = raw.get("street") or ""
    partes = [p.strip() for p in street.split(",") if p.strip()]
    bairro = partes[-1] if partes else None
    h2 = raw.get("h2") or ""
    hp = [p.strip() for p in h2.split(",") if p.strip()]
    if not bairro and len(hp) >= 2:
        bairro = hp[-2]
    bairro = bairro_bonito(bairro)
    url = raw.get("url") or ""
    if url.startswith("/"):
        url = "https://www.dfimoveis.com.br" + url
    pid = str(raw["id"])
    fotos_raw = raw.get("fotos") or []
    raw["fotos"] = [
        f if str(f).startswith("http") else
        f"https://img.dfimoveis.com.br/fotos/{pid}/{f if '.' in str(f) else str(f) + '.webp'}"
        for f in fotos_raw
    ]
    return novo_imovel(
        portal="DF Imóveis", id_portal=str(raw["id"]), titulo=raw.get("titulo") or "Casa para alugar", preco=preco,
        bairro=bairro, regiao=regiao_de(bairro, street, h2), quartos=quartos, vagas=to_int(raw.get("vagas")),
        area_m2=to_int(raw.get("area")), fotos=[f for f in raw.get("fotos") or [] if f][:12], url=url,
        lat=raw.get("lat"), lng=raw.get("lng"), publicado_em=raw.get("publicado"), anunciante=raw.get("anunciante") or None,
        **flags_from_text((raw.get("texto") or "") + " " + (raw.get("kw") or "")),
    )


CONV = {"wimoveis": ("Wimoveis", conv_wimoveis), "dfimoveis": ("DF Imóveis", conv_dfimoveis)}


def main() -> int:
    portal = sys.argv[1]
    nome, fn = CONV[portal]
    itens: dict[str, dict] = {}
    for arq in sys.argv[2:]:
        data = json.loads(Path(arq).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("itens") or data.get("imoveis") or []
        for raw in data:
            it = fn(raw)
            if it:
                itens.setdefault(it["id"], it)
    EXTERNOS.mkdir(parents=True, exist_ok=True)
    saida = {"portal": nome, "gerado_em": datetime.now(BRT).isoformat(timespec="seconds"), "total": len(itens),
             "imoveis": list(itens.values())}
    (EXTERNOS / f"{portal}.json").write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{nome}: {len(itens)} casas -> data/externos/{portal}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
