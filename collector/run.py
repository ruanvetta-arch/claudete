"""Coletor principal da claudete.

Roda todos os portais, deduplica, preserva `first_seen_at` de quem já existia e
grava data/imoveis.json + data/status.json.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from common import assinatura  # noqa: E402
from portals import chavesnamao, dfimoveis, quintoandar, wimoveis  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IMOVEIS_JSON = DATA / "imoveis.json"
STATUS_JSON = DATA / "status.json"
PUBLIC_DATA = ROOT / "public" / "data"

BRT = timezone(timedelta(hours=-3))
DIAS_PARA_INATIVAR = 3

PORTAIS = [dfimoveis, wimoveis, quintoandar, chavesnamao]
# Ordem de prioridade para escolher o registro "principal" quando há duplicata
PRIORIDADE = {"QuintoAndar": 0, "Wimoveis": 1, "DF Imóveis": 2, "Chaves na Mão": 3}


def agora() -> datetime:
    return datetime.now(BRT)


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def carregar_anterior() -> dict:
    if IMOVEIS_JSON.exists():
        try:
            return json.loads(IMOVEIS_JSON.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {"gerado_em": None, "imoveis": []}


def completude(it: dict) -> int:
    score = 0
    for k in ("area_m2", "vagas", "banheiros", "condominio", "lat"):
        if it.get(k) not in (None, 0, ""):
            score += 1
    score += min(len(it.get("fotos") or []), 5)
    return score


def deduplicar(itens: list[dict]) -> list[dict]:
    grupos: dict[str, list[dict]] = {}
    for it in itens:
        sig = assinatura(it["regiao"], it["preco"], it["area_m2"], it["quartos"])
        it["assinatura"] = sig
        grupos.setdefault(sig, []).append(it)

    resultado: list[dict] = []
    for sig, grupo in grupos.items():
        # Mesma assinatura e mesmo portal = anúncios distintos (ex.: casas iguais num condomínio)
        por_portal: dict[str, list[dict]] = {}
        for it in grupo:
            por_portal.setdefault(it["portal"], []).append(it)
        if len(por_portal) == 1:
            for it in grupo:
                it["tambem_em"] = []
            resultado.extend(grupo)
            continue
        # Portais diferentes: funde em um só registro
        grupo.sort(key=lambda x: (-completude(x), PRIORIDADE.get(x["portal"], 9)))
        principal = dict(grupo[0])
        principal["tambem_em"] = [
            {"portal": o["portal"], "url": o["url"]} for o in grupo[1:] if o["portal"] != principal["portal"]
        ]
        # Enriquecimento com campos vazios
        for o in grupo[1:]:
            for k, v in o.items():
                if principal.get(k) in (None, "", [], False) and v not in (None, "", [], False):
                    if k not in ("id", "id_portal", "portal", "url", "tambem_em"):
                        principal[k] = v
        # Fotos: concatena únicas
        fotos: list[str] = []
        for o in grupo:
            for f in o.get("fotos") or []:
                if f not in fotos:
                    fotos.append(f)
        principal["fotos"] = fotos[:10]
        # Junta ids secundários para o merge com histórico encontrar first_seen
        principal["ids_fundidos"] = sorted({o["id"] for o in grupo})
        resultado.append(principal)
    return resultado


def main() -> int:
    inicio = agora()
    anterior = carregar_anterior()
    antigos: dict[str, dict] = {}
    for it in anterior.get("imoveis", []):
        antigos[it["id"]] = it
        for alt in it.get("ids_fundidos") or []:
            antigos.setdefault(alt, it)

    status_anterior = {}
    if STATUS_JSON.exists():
        try:
            status_anterior = json.loads(STATUS_JSON.read_text(encoding="utf-8")).get("portais", {})
        except Exception:  # noqa: BLE001
            status_anterior = {}

    coletados: list[dict] = []
    status_portais: dict[str, dict] = {}
    for mod in PORTAIS:
        nome = mod.NOME
        t0 = agora()
        try:
            itens = mod.coletar()
            coletados.extend(itens)
            status_portais[nome] = {
                "ok": True,
                "total": len(itens),
                "ultimo_sucesso": iso(t0),
                "erro": None,
            }
            print(f"[ok] {nome}: {len(itens)} casas", flush=True)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            prev = status_anterior.get(nome, {})
            status_portais[nome] = {
                "ok": False,
                "total": 0,
                "ultimo_sucesso": prev.get("ultimo_sucesso"),
                "erro": f"{type(e).__name__}: {str(e)[:200]}",
            }
            print(f"[erro] {nome}: {e}", flush=True)

    portais_ok = {n for n, s in status_portais.items() if s["ok"]}
    novos = deduplicar(coletados)

    hoje = inicio
    finais: list[dict] = []
    vistos: set[str] = set()
    n_novos = 0
    for it in novos:
        ids = set(it.get("ids_fundidos") or []) | {it["id"]}
        velho = None
        for i in ids:
            if i in antigos:
                velho = antigos[i]
                break
        if velho:
            it["first_seen_at"] = velho.get("first_seen_at") or iso(hoje)
            if velho.get("preco") and velho["preco"] != it["preco"]:
                it["preco_anterior"] = velho["preco"]
            elif velho.get("preco_anterior"):
                it["preco_anterior"] = velho["preco_anterior"]
        else:
            it["first_seen_at"] = iso(hoje)
            n_novos += 1
        it["last_seen_at"] = iso(hoje)
        it["inativo"] = False
        finais.append(it)
        vistos |= ids

    # Quem sumiu: mantém por alguns dias (só de portais que rodaram OK hoje)
    limite = hoje - timedelta(days=DIAS_PARA_INATIVAR)
    for it in anterior.get("imoveis", []):
        if it["id"] in vistos:
            continue
        if it.get("portal") not in portais_ok:
            # portal falhou hoje: preserva o registro como estava
            finais.append(it)
            continue
        try:
            last = datetime.fromisoformat(it.get("last_seen_at") or it["first_seen_at"])
        except Exception:  # noqa: BLE001
            last = hoje
        if last >= limite:
            it["inativo"] = True
            finais.append(it)
        # senão: descarta de vez

    finais.sort(key=lambda x: x.get("first_seen_at") or "", reverse=True)

    saida = {
        "gerado_em": iso(agora()),
        "total": len([f for f in finais if not f.get("inativo")]),
        "novos_hoje": n_novos,
        "imoveis": finais,
    }
    DATA.mkdir(exist_ok=True)
    IMOVEIS_JSON.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    status = {
        "gerado_em": iso(agora()),
        "duracao_s": int((agora() - inicio).total_seconds()),
        "total_ativos": saida["total"],
        "novos_hoje": n_novos,
        "portais": status_portais,
    }
    STATUS_JSON.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    # Cópia para a pasta pública servida pela Vercel
    PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
    (PUBLIC_DATA / "imoveis.json").write_text(IMOVEIS_JSON.read_text(encoding="utf-8"), encoding="utf-8")
    (PUBLIC_DATA / "status.json").write_text(STATUS_JSON.read_text(encoding="utf-8"), encoding="utf-8")

    print(json.dumps(status, ensure_ascii=False, indent=2))
    # Falha o job só se TODOS os portais falharam
    return 0 if portais_ok else 1


if __name__ == "__main__":
    sys.exit(main())
