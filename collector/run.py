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
from portals import chavesnamao, dfimoveis, quintoandar, vivareal, wimoveis  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IMOVEIS_JSON = DATA / "imoveis.json"
STATUS_JSON = DATA / "status.json"
PUBLIC_DATA = ROOT / "public" / "data"

BRT = timezone(timedelta(hours=-3))
DIAS_PARA_INATIVAR = 3

# Portais coletados direto do GitHub Actions (respondem a IP de datacenter).
PORTAIS = [vivareal, quintoandar, chavesnamao]
# Wimoveis e DF Imóveis usam Cloudflare e só respondem a IP residencial: entram via
# data/externos/<portal>.json, gerados por uma coleta rodada no computador da família.
EXTERNOS_DIR = ROOT / "data" / "externos"
EXTERNOS_VALIDADE_DIAS = 4
# Ordem de prioridade para escolher o registro "principal" quando há duplicata
PRIORIDADE = {"QuintoAndar": 0, "Wimoveis": 1, "DF Imóveis": 2, "VivaReal": 3, "Chaves na Mão": 4}


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


def _dist_km(a: dict, b: dict) -> float | None:
    import math
    if not (a.get("lat") and a.get("lng") and b.get("lat") and b.get("lng")):
        return None
    dlat = math.radians(b["lat"] - a["lat"])
    dlng = math.radians(b["lng"] - a["lng"])
    la1, la2 = math.radians(a["lat"]), math.radians(b["lat"])
    h = math.sin(dlat / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlng / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _chave_dedup(it: dict) -> str:
    from common import slug
    preco = round((it["preco"] or 0) / 50) * 50
    return f"{slug(it.get('bairro') or '')}|{preco}|{it.get('quartos') or 0}"


def _subgrupos_por_distancia(grupo: list[dict], limite_km: float = 1.5) -> list[list[dict]]:
    """Separa anúncios que têm coordenadas e estão claramente longe uns dos outros."""
    subs: list[list[dict]] = []
    for it in grupo:
        alvo = None
        for s in subs:
            ds = [_dist_km(it, o) for o in s]
            conhecidas = [d for d in ds if d is not None]
            if not conhecidas or min(conhecidas) <= limite_km:
                alvo = s
                break
        if alvo is None:
            subs.append([it])
        else:
            alvo.append(it)
    return subs


def deduplicar(itens: list[dict]) -> list[dict]:
    grupos: dict[str, list[dict]] = {}
    for it in itens:
        it["assinatura"] = assinatura(it["regiao"], it["preco"], it["area_m2"], it["quartos"])
        grupos.setdefault(_chave_dedup(it), []).append(it)

    resultado: list[dict] = []
    for grupo0 in grupos.values():
        for grupo in _subgrupos_por_distancia(grupo0):
            if len(grupo) == 1:
                grupo[0]["tambem_em"] = []
                grupo[0]["anuncios"] = 1
                resultado.append(grupo[0])
                continue
            # Mesma casa anunciada mais de uma vez (portais ou imobiliárias diferentes)
            grupo.sort(key=lambda x: (-completude(x), PRIORIDADE.get(x["portal"], 9)))
            principal = dict(grupo[0])
            principal["tambem_em"] = [
                {"portal": o["portal"], "anunciante": o.get("anunciante"), "url": o["url"]} for o in grupo[1:]
            ]
            principal["anuncios"] = len(grupo)
            # Enriquecimento com campos vazios
            for o in grupo[1:]:
                for k, v in o.items():
                    if principal.get(k) in (None, "", [], False) and v not in (None, "", [], False):
                        if k not in ("id", "id_portal", "portal", "url", "tambem_em", "anuncios"):
                            principal[k] = v
            # Fotos: as do principal primeiro, depois as dos outros (únicas)
            fotos: list[str] = []
            for o in grupo:
                for f in o.get("fotos") or []:
                    if f not in fotos:
                        fotos.append(f)
            principal["fotos"] = fotos[:16]
            # Junta ids secundários para o merge com histórico encontrar first_seen
            principal["ids_fundidos"] = sorted({o["id"] for o in grupo})
            resultado.append(principal)
    return resultado


# DF Imóveis chega via coleta local já com fotos; só o Chaves na Mão precisa de detalhe aqui.
ENRIQUECEDORES = {chavesnamao.NOME: chavesnamao}
TETO_ENRIQUECIMENTO_S = 8 * 60


def enriquecer_fotos(coletados: list[dict], antigos: dict[str, dict]) -> None:
    import time
    from common import session as _session

    t0 = time.time()
    sess = _session()
    feitos = 0
    for it in coletados:
        mod = ENRIQUECEDORES.get(it["portal"])
        if not mod:
            continue
        velho = antigos.get(it["id"])
        if velho and len(velho.get("fotos") or []) > 1:
            # Já temos as fotos completas de uma rodada anterior
            it["fotos"] = velho["fotos"]
            for k in ("piscina", "aceita_pet", "mobiliada", "churrasqueira"):
                it[k] = it.get(k) or velho.get(k, False)
            continue
        if time.time() - t0 > TETO_ENRIQUECIMENTO_S:
            continue
        try:
            it["fotos"] = mod.fotos_detalhe(sess, it)
            feitos += 1
            time.sleep(0.4)
        except Exception as e:  # noqa: BLE001
            print(f"[fotos] {it['portal']} {it['id_portal']}: {e}", flush=True)
    print(f"[fotos] páginas de detalhe visitadas: {feitos} em {int(time.time()-t0)}s", flush=True)


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

    # Fontes externas (coletadas de IP residencial e commitadas em data/externos/)
    if EXTERNOS_DIR.exists():
        for f in sorted(EXTERNOS_DIR.glob("*.json")):
            try:
                ext = json.loads(f.read_text(encoding="utf-8"))
                nome = ext.get("portal") or f.stem
                gerado = datetime.fromisoformat(ext["gerado_em"])
                idade = (inicio - gerado).days
                itens = [it for it in ext.get("imoveis", []) if it.get("preco") and (it.get("quartos") or 0) >= 2]
                if idade > EXTERNOS_VALIDADE_DIAS:
                    status_portais[nome] = {"ok": False, "total": 0, "ultimo_sucesso": ext["gerado_em"],
                                            "erro": f"coleta local desatualizada ({idade} dias)"}
                    print(f"[externo] {nome}: desatualizado ({idade} dias), ignorado", flush=True)
                    continue
                coletados.extend(itens)
                status_portais[nome] = {"ok": True, "total": len(itens), "ultimo_sucesso": ext["gerado_em"], "erro": None,
                                        "origem": "coleta local"}
                print(f"[externo] {nome}: {len(itens)} casas (coletado {ext['gerado_em']})", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[externo] {f.name}: {e}", flush=True)

    portais_ok = {n for n, s in status_portais.items() if s["ok"]}

    # Enriquecimento de fotos: portais cuja listagem traz só 1 foto.
    # Só para anúncios que ainda não conhecemos (ou que têm <= 1 foto), com teto de tempo.
    enriquecer_fotos(coletados, antigos)

    novos = deduplicar(coletados)

    hoje = inicio
    finais: list[dict] = []
    vistos: set[str] = set()
    n_novos = 0
    for it in novos:
        ids = set(it.get("ids_fundidos") or []) | {it["id"]}
        velhos = [antigos[i] for i in ids if i in antigos]
        # Entre todos os anúncios fundidos, vale a entrada mais antiga na plataforma
        velho = min(velhos, key=lambda v: v.get("first_seen_at") or "9") if velhos else None
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
            # portal falhou hoje: preserva o registro como estava, por até 14 dias
            try:
                last = datetime.fromisoformat(it.get("last_seen_at") or it["first_seen_at"])
            except Exception:  # noqa: BLE001
                last = hoje
            if last >= hoje - timedelta(days=14):
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
