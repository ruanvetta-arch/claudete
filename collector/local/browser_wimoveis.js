// Roda DENTRO de uma aba do wimoveis.com.br (IP residencial passa pelo Cloudflare).
// Retorna lista compacta de casas 2+ quartos para alugar no DF.
// Uso: colar/executar via javascript_tool; resultado em window.__claudete_wi.
(async () => {
  const PROV = "247"; // Distrito Federal
  const body = (pagina) => ({
    tipoDePropiedad: "1", tipoDeOperacion: "2", habitacionesminimo: "2", sort: "more_recent",
    pagina, province: PROV, superficieCubierta: 1, idunidaddemedida: 1, tipoAnunciante: "ALL",
    q: null, direccion: null, moneda: null, preciomin: null, preciomax: null, services: "", general: "",
    searchbykeyword: "", amenidades: "", caracteristicasprop: null, comodidades: "", disposicion: null,
    roomType: "", outside: "", areaPrivativa: "", areaComun: "", multipleRets: "", subtipoDePropiedad: null,
    garages: null, antiguedad: null, expensasminimo: null, expensasmaximo: null, habitacionesmaximo: "",
    ambientesminimo: "", ambientesmaximo: "", banos: null, metroscuadradomin: null, metroscuadradomax: null,
    grupoTipoDeMultimedia: "", publicacion: null, etapaDeDesarrollo: "", auctions: null, polygonApplied: null,
    idInmobiliaria: null, excludePostingContacted: "", banks: "", places: "", condominio: "", city: null,
    zone: null, valueZone: null, subZone: null, coordenates: null,
  });
  const feat = (p, id) => { const f = (p.mainFeatures || {})[id]; return f ? f.value : null; };
  const out = [];
  const seen = new Set();
  for (let pagina = 1; pagina <= 40; pagina++) {
    const r = await fetch("/rplis-api/postings", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body(pagina)) });
    if (!r.ok) { window.__claudete_wi_err = "HTTP " + r.status + " p" + pagina; break; }
    const j = await r.json();
    const lista = j.listPostings || [];
    for (const p of lista) {
      if (seen.has(p.postingId)) continue;
      seen.add(p.postingId);
      const loc = (p.postingLocation || {}).location || {};
      const geo = (((p.postingLocation || {}).postingGeolocation || {}).geolocation) || {};
      const gf = p.generalFeatures || {};
      const gfText = Object.values(gf).flatMap(c => (c && typeof c === "object") ? Object.values(c).map(v => v && v.label).filter(Boolean) : []).join(" ");
      out.push({
        id: String(p.postingId),
        titulo: p.generatedTitle || p.title,
        // Só o preço da operação ALUGUEL (id 2); anúncios de venda+aluguel vêm com a venda primeiro
        preco: ((((p.priceOperationTypes || []).find(o => String((o.operationType || {}).operationTypeId) === "2") || {}).prices || [])[0] || {}).amount || null,
        operacoes: (p.priceOperationTypes || []).map(o => (o.operationType || {}).name).join("/"),
        condominio: (p.expenses || {}).amount || null,
        bairro: loc.name || null,
        bairro_label: loc.label || null,
        cidade: (loc.parent || {}).name || null,
        endereco: ((p.postingLocation || {}).address || {}).name || null,
        quartos: feat(p, "CFT2"), banheiros: feat(p, "CFT3"), vagas: feat(p, "CFT7"),
        area: feat(p, "CFT100") || feat(p, "CFT101"),
        fotos: ((p.visiblePictures || {}).pictures || []).slice(0, 10).map(x => x.url730x532 || x.url360x266).filter(Boolean),
        url: "https://www.wimoveis.com.br" + (p.url || ""),
        lat: geo.latitude || null, lng: geo.longitude || null,
        modificado: p.modified_date || null,
        antiguidade: p.antiquity || null,
        anunciante: (p.publisher || {}).name || null,
        texto: ((p.title || "") + " " + (p.descriptionNormalized || "") + " " + gfText).slice(0, 600),
      });
    }
    if (lista.length < 30) break;
  }
  // Compacta para transporte (o conversor reconstrói URLs de foto e do anúncio)
  const KW = /(piscina|aceita (?:pets?|animais)|pets? permitid|animais permitid|pet friendly|mobiliad[ao]|churrasqueira)/gi;
  window.__claudete_wi = out.map(o => {
    const ids = o.fotos.map(u => (u.match(/\/(\d+)\.jpg/) || [])[1]).filter(Boolean);
    const r = { ...o, fotos: ids.slice(0, 8), url: o.url.replace("https://www.wimoveis.com.br/propriedades/", ""),
      texto: [...new Set((o.texto.match(KW) || []).map(s => s.toLowerCase()))].join(" "),
      titulo: (o.titulo || "").slice(0, 80), endereco: (o.endereco || "").slice(0, 60),
      anunciante: (o.anunciante || "").slice(0, 40), modificado: (o.modificado || "").slice(0, 25), antiguidade: (o.antiguidade || "").slice(0, 40) };
    if (r.bairro_label === "CIUDAD") r.bairro_cidade = true;
    delete r.bairro_label;
    return r;
  });
  return { total: window.__claudete_wi.length, erro: window.__claudete_wi_err || null, bytes: JSON.stringify(window.__claudete_wi).length };
})();
