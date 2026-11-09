// Recebe a coleta feita pela extensão no computador da família (Wimoveis, DF Imóveis, OLX)
// e grava em data/bruto/<portal>.json no GitHub. O workflow "Coletar casas" converte e publica.
// Precisa de GITHUB_TOKEN com Contents: leitura e escrita (e Actions: leitura e escrita).
// Tudo é validado e limpo: só entram campos conhecidos, números, textos curtos e caminhos seguros.

const PORTAIS = {
  wimoveis: ["id", "titulo", "preco", "condominio", "bairro", "cidade", "endereco", "quartos", "banheiros", "vagas", "area", "fotos", "url", "lat", "lng", "modificado", "antiguidade", "anunciante", "texto", "bairro_cidade"],
  dfimoveis: ["id", "titulo", "preco", "street", "h2", "quartos", "area", "vagas", "fotos", "url", "lat", "lng", "publicado", "anunciante", "kw"],
  olx: ["id", "titulo", "preco", "condominio", "bairro", "cidade", "quartos", "banheiros", "vagas", "area", "fotos", "url", "publicado", "profissional", "texto"],
};
const NUMEROS = new Set(["preco", "condominio", "quartos", "banheiros", "vagas", "area", "lat", "lng"]);

function limparTexto(v, max = 200) {
  if (v == null) return null;
  return String(v).replace(/[<>"'`\u0000-\u001f]/g, " ").replace(/\s+/g, " ").trim().slice(0, max) || null;
}
function limparNumero(v) {
  if (v == null || v === "") return null;
  const n = Number(String(v).replace(",", "."));
  return Number.isFinite(n) ? n : null;
}
function limparFoto(v) {
  const s = String(v || "");
  if (/^[A-Za-z0-9_.-]{1,80}$/.test(s)) return s;
  // DF Imóveis pode mandar a URL completa da primeira foto
  if (/^https:\/\/img\.dfimoveis\.com\.br\/fotos\/\d+\/[a-f0-9]+\.(webp|jpe?g|png)$/.test(s)) return s;
  return null;
}
function limparUrl(v) {
  const s = String(v || "");
  return /^[A-Za-z0-9/._!~%+:$,-]{1,300}$/.test(s) ? s : null;
}
function limparItem(portal, raw) {
  if (!raw || typeof raw !== "object") return null;
  const it = {};
  for (const k of PORTAIS[portal]) {
    const v = raw[k];
    if (k === "fotos") it.fotos = (Array.isArray(v) ? v : []).slice(0, 16).map(limparFoto).filter(Boolean);
    else if (k === "url") it.url = limparUrl(v);
    else if (k === "publicado" && portal === "olx") it.publicado = limparNumero(v);
    else if (NUMEROS.has(k)) it[k] = limparNumero(v);
    else if (k === "profissional" || k === "bairro_cidade") it[k] = !!v;
    else it[k] = limparTexto(v, k === "texto" || k === "kw" ? 400 : 120);
  }
  if (!it.id || !/^\d{1,15}$/.test(String(it.id)) || !it.url) return null;
  return it;
}

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") { res.status(405).json({ ok: false, mensagem: "Use POST." }); return; }
  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.GITHUB_REPO || "ruanvetta-arch/claudete";
  if (!token) { res.status(500).json({ ok: false, mensagem: "sem token" }); return; }

  let corpo = req.body;
  if (typeof corpo === "string") { try { corpo = JSON.parse(corpo); } catch (e) { corpo = null; } }
  const portal = corpo && corpo.portal;
  if (!PORTAIS[portal]) { res.status(400).json({ ok: false, mensagem: "portal desconhecido" }); return; }
  const brutos = Array.isArray(corpo.itens) ? corpo.itens.slice(0, 4000) : [];
  const itens = brutos.map((r) => limparItem(portal, r)).filter(Boolean);
  if (itens.length < 50) { res.status(400).json({ ok: false, mensagem: `poucos anúncios válidos (${itens.length})` }); return; }
  const coletado = new Date(corpo.coletado_em || Date.now());
  const coletado_em = isNaN(coletado) || Math.abs(Date.now() - coletado) > 6 * 3600 * 1000 ? new Date().toISOString() : coletado.toISOString();

  const caminho = `data/bruto/${portal}.json`;
  const api = `https://api.github.com/repos/${repo}/contents/${caminho}`;
  const hdr = { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json", "User-Agent": "claudete", "Content-Type": "application/json" };
  const conteudo = Buffer.from(JSON.stringify({ portal, coletado_em, origem: "extensao", total: itens.length, itens })).toString("base64");
  try {
    for (let tentativa = 0; tentativa < 3; tentativa++) {
      const atual = await fetch(`${api}?ref=main`, { headers: hdr });
      const sha = atual.status === 200 ? (await atual.json()).sha : undefined;
      const r = await fetch(api, {
        method: "PUT", headers: hdr,
        body: JSON.stringify({ message: `dados: ${portal} coletado pelo navegador (${itens.length} casas)`, content: conteudo, sha, branch: "main" }),
      });
      if (r.status === 200 || r.status === 201) { res.status(200).json({ ok: true, total: itens.length }); return; }
      if (r.status !== 409 && r.status !== 422) {
        const txt = await r.text();
        res.status(502).json({ ok: false, mensagem: `GitHub ${r.status}: ${txt.slice(0, 120)}` });
        return;
      }
    }
    res.status(502).json({ ok: false, mensagem: "conflito ao gravar, tente de novo" });
  } catch (e) {
    res.status(500).json({ ok: false, mensagem: String(e).slice(0, 160) });
  }
};
