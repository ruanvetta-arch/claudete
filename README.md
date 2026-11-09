# claudete

Casas para alugar em Brasília (2+ quartos), reunidas de vários sites e atualizadas automaticamente.
Uso familiar, sem custo: GitHub Actions coleta os dados e a Vercel publica o site estático.

## Como funciona

```
GitHub Actions (07h e 13h, Brasília)
  └─ collector/run.py
       ├─ portals/vivareal.py      (API glue — direto do Actions)
       ├─ portals/quintoandar.py   (API house-listing-search — direto do Actions)
       ├─ portals/chavesnamao.py   (HTML — direto do Actions)
       └─ data/externos/*.json     (Wimoveis, DF Imóveis, OLX — coleta local diária pelo navegador
                                    do app do Claude no computador da família; ver collector/local/)
       → deduplica, preserva first_seen_at, grava data/ e public/data/
  └─ commit + push  →  Vercel faz redeploy  →  claudete.vercel.app
```

- **Mais recentes** ordena por `first_seen_at` (quando a casa entrou aqui), agrupado por dia.
- **Duplicadas**: mesma região + preço (±R$ 50) + área (±5 m²) + quartos em portais diferentes viram um card só ("Também em…").
- Casa que some de todos os portais por 3 dias é removida.
- Favoritos e "Já vi" ficam no celular (localStorage), sem login.

## Rodar local

```bash
pip install -r collector/requirements.txt
python collector/run.py          # gera data/imoveis.json e public/data/
cd public && python -m http.server 8000
```

## Atualização automática ao abrir o site

- **Qualquer aparelho**: se os dados têm mais de 20 minutos, a página chama `/api/atualizar`, que dispara o
  workflow "Coletar casas" (VivaReal, QuintoAndar, Chaves na Mão). A faixa "Procurando casas novas…" aparece
  e a lista se atualiza sozinha quando termina.
- **Computador da família** (com a extensão `extensao/` instalada — página `/instalar`): ao abrir o site, a
  extensão abre Wimoveis, OLX e DF Imóveis em abas de fundo, coleta pela conexão de casa, envia para
  `/api/receber` (que grava `data/bruto/<portal>.json` no GitHub) e dispara o workflow. Repete no máximo a cada 30 min.
- `GITHUB_TOKEN` na Vercel: token fine-grained só do repo `claudete` com **Actions** e **Contents** em leitura e escrita.
- Os horários 07h e 13h continuam como reserva.

## Forçar uma coleta agora

GitHub → Actions → "Coletar casas" → Run workflow.

## Se um portal quebrar

Cada portal roda isolado; o site mostra "X não respondeu hoje". Ajuste só o módulo em `collector/portals/`.
