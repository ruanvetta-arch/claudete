// Roda DENTRO de uma aba do dfimoveis.com.br (IP residencial passa pelo Cloudflare).
// Lê a listagem de casas e casas de condomínio para alugar no DF (todas as páginas),
// filtra 2+ quartos e busca as fotos completas na página do anúncio para quem ainda não tem.
// window.__claudete_df_conhecidos (opcional): array de ids que já têm fotos (pula o detalhe).
(async () => {
  const LISTAS = ["/aluguel/df/todos/casa", "/aluguel/df/todos/casa-condominio"];
  const conhecidos = new Set(window.__claudete_df_conhecidos || []);
  const out = new Map();
  const parser = new DOMParser();
  for (const lista of LISTAS) {
    for (let pagina = 1; pagina <= 60; pagina++) {
      const r = await fetch(`${lista}?pagina=${pagina}`);
      if (!r.ok) break;
      const doc = parser.parseFromString(await r.text(), "text/html");
      const ld = {};
      for (const s of doc.querySelectorAll('script[type="application/ld+json"]')) {
        try { const d = JSON.parse(s.textContent); if (d && d["@type"] === "ItemList") for (const el of d.itemListElement || []) { const it = el.item || {}; if (it.identifier) ld[String(it.identifier)] = it; } } catch (e) {}
      }
      const cards = doc.querySelectorAll('article[itemtype*="RealEstateListing"]');
      if (!cards.length) break;
      for (const art of cards) {
        const a = art.querySelector('a[href*="/imovel/"]'); if (!a) continue;
        const href = a.getAttribute("href").split("?")[0];
        const m = href.match(/-(\d+)$/); if (!m) continue;
        const id = m[1]; if (out.has(id)) continue;
        const it = ld[id] || {};
        const texto = art.innerText.replace(/\s+/g, " ").trim();
        const q = it.numberOfBedrooms ?? (texto.match(/(\d+)\s*Quartos?/i) || [])[1];
        const quartos = q ? parseInt(q) : null;
        if (!quartos || quartos < 2) continue;
        const h2 = art.querySelector("h2[itemprop=name]");
        const img = art.querySelector("img[src*='img.dfimoveis']");
        const anun = art.querySelector(".imovel-anunciante img");
        out.set(id, {
          id, titulo: it.name || (h2 ? h2.textContent.trim() : null),
          preco: it.offers ? Number(it.offers.price) : null,
          street: (it.address || {}).streetAddress || null,
          h2: h2 ? h2.textContent.trim() : null,
          quartos, area: it.floorSize ? Number(it.floorSize.value) : null,
          vagas: (texto.match(/(\d+)\s*Vagas?/i) || [])[1] ? parseInt((texto.match(/(\d+)\s*Vagas?/i) || [])[1]) : null,
          fotos: (it.image || []).concat(img ? [img.src] : []).filter((v, i, arr) => v && arr.indexOf(v) === i),
          url: "https://www.dfimoveis.com.br" + href,
          lat: (it.geo || {}).latitude || null, lng: (it.geo || {}).longitude || null,
          publicado: it.datePosted || null,
          anunciante: anun ? anun.getAttribute("alt") : null,
          texto: ((it.name || "") + " " + (it.description || "") + " " + texto).slice(0, 600),
        });
      }
      if (cards.length < 30) break;
    }
  }
  // Fotos completas (só para quem não é conhecido), 1 por vez, respeitando HTTP 429.
  const KW = /(piscina|aceita (?:pets?|animais)|pets? permitid|animais permitid|pet friendly|mobiliad[ao]|churrasqueira)/gi;
  const t0 = Date.now();
  let detalhes = 0;
  for (const it of out.values()) {
    if (conhecidos.has(it.id)) continue;
    if (Date.now() - t0 > 10 * 60 * 1000) break;
    let html = null;
    for (let tent = 0; tent < 4 && html === null; tent++) {
      try {
        const r = await fetch(it.url);
        if (r.status === 429) { await new Promise(res => setTimeout(res, 3000 * (tent + 1))); continue; }
        html = await r.text();
      } catch (e) { break; }
    }
    if (html) {
      const re = new RegExp("https://img\\.dfimoveis\\.com\\.br/fotos/" + it.id + "/([a-f0-9]+)\\.(webp|jpe?g|png)", "g");
      const seen = new Set(); const fotos = [];
      for (const m of html.matchAll(re)) { if (!seen.has(m[1])) { seen.add(m[1]); fotos.push(m[1] + (m[2] === "webp" ? "" : "." + m[2])); } if (fotos.length >= 12) break; }
      if (fotos.length) it.fotos = fotos;
      const t = html.replace(/<script[\s\S]*?<\/script>/g, " ").replace(/<[^>]+>/g, " ");
      it.kw = [...new Set((t.match(KW) || []).map(s => s.toLowerCase()))].join(" ");
      detalhes++;
    }
    await new Promise(res => setTimeout(res, 700));
  }
  // Compacta para transporte: fotos viram só o hash (o conversor reconstrói a URL)
  window.__claudete_df = [...out.values()].map(o => {
    const kw = [...new Set(((o.texto || "").match(KW) || []).map(s => s.toLowerCase()).concat((o.kw || "").split(" ").filter(Boolean)))].join(" ");
    const fotos = (o.fotos || []).map(u => { const m = String(u).match(/\/fotos\/\d+\/([a-f0-9]+)\.(webp|jpe?g|png)/); return m ? m[1] + (m[2] === "webp" ? "" : "." + m[2]) : u; });
    const { texto, ...r } = o; return { ...r, kw, fotos };
  });
  return { total: window.__claudete_df.length, detalhes, bytes: JSON.stringify(window.__claudete_df).length };
})();
