# Coleta local (Wimoveis, DF Imóveis e OLX)

Esses três portais usam Cloudflare/anti-robô e bloqueiam IPs de datacenter (GitHub Actions, Vercel).
Só respondem a um IP residencial — por isso a coleta roda no navegador do app do Claude,
no computador da família, por uma tarefa agendada diária.

## Passo a passo (o que a tarefa agendada faz)

1. Adiciona o repositório `ruanvetta-arch/claudete` à sessão (`add_repo`, acesso push) e clona em `/home/claude/claudete`.
2. Abre o navegador do app (`Claude_Browser__preview_start`) em
   `https://www.wimoveis.com.br/aluguel/casas/df/mais-de-2-quartos`, espera ~3 s e executa
   `collector/local/browser_wimoveis.js` com `javascript_tool` (colar o conteúdo do arquivo; o
   resultado fica em `window.__claudete_wi`).
3. Traz os dados em pedaços de ~180 itens: `JSON.stringify(window.__claudete_wi.slice(a,b))`.
   O resultado grande é salvo pela ferramenta em um arquivo `tool-results/...txt`; decodificar com
   `python3 collector/local/save_chunk.py <arquivo.txt> /tmp/wi_N.json`.
4. Navega para `https://www.dfimoveis.com.br/aluguel/df/todos/casa`, executa
   `collector/local/browser_dfimoveis.js` (demora até ~10 min por causa do limite de requisições
   do site; o resultado fica em `window.__claudete_df`) e traz em pedaços de ~200 itens do
   mesmo jeito (`/tmp/df_N.json`).
4b. Navega para `https://www.olx.com.br/imoveis/aluguel/casas/estado-df?ros=2&ros=3&ros=4&ros=5&sf=1`,
   executa `collector/local/browser_olx.js` (resultado em `window.__claudete_olx`; a data `publicado`
   é o horário exato do anúncio), compacta as fotos e traz em pedaços de ~160 (`/tmp/olx_N.json`).
5. Converte (também `python3 collector/local/converter.py olx /tmp/olx_*.json`): `python3 collector/local/converter.py wimoveis /tmp/wi_*.json` e
   `python3 collector/local/converter.py dfimoveis /tmp/df_*.json` → grava `data/externos/*.json`.
6. Commit + push de `data/externos/` e dispara `gh workflow run coletar.yml --ref main`, que
   funde tudo, deduplica e publica (a Vercel faz redeploy sozinha).

Se o computador estiver desligado, a tarefa não roda nesse dia; o site segue mostrando os
anúncios anteriores desses portais (válidos por 4 dias) e marca "não respondeu hoje".
