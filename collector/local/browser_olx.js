// Roda DENTRO de uma aba do www.olx.com.br (IP residencial; de datacenter a OLX bloqueia).
// Lê todas as páginas de casas para alugar no DF com 2+ quartos. Resultado em window.__claudete_olx.
(async () => {
  const BASE = "/imoveis/aluguel/casas/estado-df?ros=2&ros=3&ros=4&ros=5&sf=1";
  function balanced(big, key) {
    let i = big.indexOf(key); if (i < 0) return null;
    let j = i + key.length; while (big[j] !== "[" && big[j] !== "{") j++;
    const op = big[j], cl = op === "[" ? "]" : "}"; let d = 0, ins = false, esc = false;
    for (let k = j; k < big.length; k++) {
      const ch = big[k];
      if (ins) { if (esc) esc = false; else if (ch === "\\") esc = true; else if (ch === '"') ins = false; }
      else { if (ch === '"') ins = true; else if (ch === op) d++; else if (ch === cl) { d--; if (d === 0) return JSON.parse(big.slice(j, k + 1)); } }
    }
    return null;
  }
  function adsDe(html) {
    const chunks = [...html.matchAll(/self\.__next_f\.push\(\[1,"(.*?)"\]\)/gs)].map(m => m[1]);
    let big = ""; for (const c of chunks) { try { big += JSON.parse('"' + c + '"'); } catch (e) { big += c; } }
    return { ads: balanced(big, '"ads":') || [], total: (big.match(/"totalOfAds":(\d+)/) || [])[1] };
  }
  const prop = (a, n) => { const p = (a.properties || []).find(x => x.name === n); return p ? p.value : null; };
  const num = (s) => { if (s == null) return null; const m = String(s).replace(/\./g, "").match(/\d+/); return m ? parseInt(m[0]) : null; };
  const out = new Map(); let total = null; let erro = null;
  for (let pagina = 1; pagina <= 30; pagina++) {
    const url = BASE + (pagina > 1 ? `&o=${pagina}` : "");
    let html = null;
    for (let tent = 0; tent < 3 && html === null; tent++) {
      try { const r = await fetch(url); if (r.status === 429 || r.status === 403) { await new Promise(res => setTimeout(res, 4000 * (tent + 1))); continue; } html = await r.text(); }
      catch (e) { erro = String(e); break; }
    }
    if (!html) break;
    const { ads, total: t } = adsDe(html); if (t) total = t;
    if (!ads.length) break;
    for (const a of ads) {
      if (!a.listId || out.has(String(a.listId))) continue;
      const quartos = num(prop(a, "rooms"));
      if (!quartos || quartos < 2) continue;
      const loc = a.locationDetails || {};
      if (loc.uf && loc.uf !== "DF") continue;
      out.set(String(a.listId), {
        id: String(a.listId),
        titulo: (a.subject || "").slice(0, 80),
        preco: num(a.priceValue || a.price),
        condominio: num(prop(a, "condominio")),
        bairro: (loc.neighbourhood || "").slice(0, 60),
        cidade: loc.municipality || null,
        quartos, banheiros: num(prop(a, "bathrooms")), vagas: num(prop(a, "garage_spaces")),
        area: num(prop(a, "size")),
        fotos: (a.images || []).slice(0, 12).map(i => i.originalWebp || i.original).filter(Boolean),
        url: a.url,
        publicado: a.date || null,  // unix seconds
        profissional: !!a.professionalAd,
        texto: [a.subject, prop(a, "re_features"), prop(a, "re_complex_features"), prop(a, "real_estate_type")].filter(Boolean).join(" ").slice(0, 400),
      });
    }
    await new Promise(res => setTimeout(res, 800));
  }
  window.__claudete_olx = [...out.values()];
  return { total: window.__claudete_olx.length, totalPortal: total, erro, bytes: JSON.stringify(window.__claudete_olx).length };
})();
