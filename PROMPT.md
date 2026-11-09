# Prompt — claudete

Construa uma plataforma de busca de casas para aluguel em Brasília-DF chamada **claudete**,
para uso familiar (uma única usuária, Ana Cláudia), sem nenhum custo: GitHub (código, dados e
coleta diária via Actions) + Vercel (site estático, plano gratuito), publicada em
**claudete.vercel.app**.

## Busca fixa
Casas (incluindo casas de condomínio) para alugar no Distrito Federal, com **2 quartos ou mais**.
Sem apartamentos. Não há tela de busca livre: a plataforma já abre nas casas.

## Fontes
- Coletadas direto pelo GitHub Actions (aceitam IP de datacenter): **VivaReal** (API glue),
  **QuintoAndar** (API house-listing-search), **Chaves na Mão** (HTML).
- Coletadas de IP residencial, pelo navegador do app do Claude no computador da família, via
  tarefa agendada diária (bloqueiam datacenter com Cloudflare): **Wimoveis** (API rplis-api,
  mesma base do Imovelweb) e **DF Imóveis** (HTML + JSON-LD). Entram em `data/externos/`.
- Cada fonte é isolada: se uma falhar, as outras seguem e o site avisa "X não respondeu hoje".

## Dados de cada casa
preço (R$/mês, campo principal), condomínio, **bairro** (apenas o bairro, não o endereço
completo) normalizado para região administrativa do DF, quartos, banheiros, vagas, área,
piscina, aceita pet, mobiliada, churrasqueira, **todas as fotos do anúncio** (até 12),
link do anúncio original, portal de origem, `first_seen_at` (momento em que entrou aqui).

## Deduplicação
Mesma região + preço (±R$ 50) + área (±5 m²) + quartos em portais diferentes = a mesma casa:
vira um card só, com o registro mais completo e "Também em: <outros portais>" com os links.
Casa que some de todos os portais por 3 dias é retirada.

## Interface (mobile-first, extremamente simples)
- Tela principal **"Mais recentes"**: agrupada por dia (Hoje, Ontem, Sexta-feira, 2 de
  novembro…) e, dentro do dia, ordenada pelo horário em que a casa entrou na plataforma
  (há 10 min antes de há 3 horas). Badge "Nova" em casas de até 24 h; "Baixou" quando o
  preço caiu.
- Card: fotos em carrossel por toque, **preço grande**, **bairro em negrito** (+ região),
  ícones de quartos / m² / vagas / banheiros, pills Piscina / Aceita pet / Mobiliada /
  Churrasqueira, origem e "há X min". Botões: **Ver anúncio** (abre o portal), **WhatsApp**
  (compartilha preço, bairro e link) e **Já vi** (esconde, reversível).
- Coração para favoritar; abas fixas Recentes · Favoritos · Já vi (tudo salvo no celular,
  sem login).
- Busca por bairro no topo; chips de um toque (Filtros, Piscina, Aceita pet, regiões mais
  frequentes com contagem); folha "Filtros" com Região, Preço por mês, Quartos, Tem que ter,
  Ordenar por, Site de origem, botão "Ver N casas".
- Rodapé de status: "Atualizado hoje às 07:04 · 1394 casas de 5 sites · 46 novas".
- Fonte 18 px, alvos de toque 48 px, contraste alto, verde cerrado como cor de ação,
  carregamento progressivo (24 cards por vez), PWA (adicionar à tela inicial).

## Automação
- GitHub Actions `coletar.yml`: 07:00 e 13:00 (Brasília) + manual. Roda `collector/run.py`,
  funde fontes diretas + `data/externos/`, deduplica, preserva `first_seen_at`, grava
  `data/` e `public/data/`, commita → a Vercel faz redeploy sozinha.
- Tarefa agendada do Claude (06:20, neste computador): executa
  `collector/local/browser_*.js` no navegador do app, converte com
  `collector/local/converter.py`, commita `data/externos/` e dispara o workflow.
