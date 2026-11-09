// claudete — coletor de casas (extensão do Chrome, roda no computador da família)
// Quando a página da claudete abre, busca Wimoveis, OLX e DF Imóveis pela conexão de casa
// (esses sites bloqueiam servidores) e envia para https://claudete.vercel.app/api/receber.
// Depois pede a coleta do servidor, que junta tudo, tira repetidas e republica o site.

const SITE = "https://claudete.vercel.app";
const INTERVALO_MIN = 30; // não repete a coleta se a última foi há menos de 30 minutos
let rodando = null;

chrome.runtime.onMessage.addListener((m, sender, reply) => {
  if (!m || m.tipo !== "coletar") return;
  (async () => {
    if (rodando) { reply({ fase: "andamento", msg: "Procurando casas novas…" }); return; }
    const st = await chrome.storage.local.get(["ultima"]);
    if (!m.forcar && st.ultima && Date.now() - st.ultima < INTERVALO_MIN * 60000) {
      reply({ fase: "recente" });
      return;
    }
    reply({ fase: "inicio", msg: "Procurando casas novas…" });
    const tabPagina = sender.tab ? sender.tab.id : null;
    rodando = coletar(tabPagina).finally(() => { rodando = null; });
  })();
  return true;
});

function avisarPagina(tabId, fase, msg) {
  if (tabId == null) return;
  chrome.tabs.sendMessage(tabId, { claudeteColetor: { fase, msg } }).catch(() => {});
}

async function coletar(tabPagina) {
  const manterVivo = setInterval(() => chrome.runtime.getPlatformInfo(() => {}), 20000);
  const erros = [];
  const resultados = {};
  try {
    // DF Imóveis: ids que o site já tem com fotos completas (não precisa abrir o anúncio de novo)
    const conhecidos = [];
    try {
      const d = await fetch(`${SITE}/data/imoveis.json?v=${Date.now()}`).then((r) => r.json());
      for (const it of d.imoveis || []) {
        if ((it.fotos || []).length <= 1) continue;
        for (const id of [it.id, ...(it.ids_fundidos || [])]) {
          if (String(id).startsWith("df-imoveis-")) conhecidos.push(String(id).slice("df-imoveis-".length));
        }
      }
    } catch (e) { /* segue sem a lista */ }

    const portais = [
      ["wimoveis", "Wimoveis", "https://www.wimoveis.com.br/aluguel/casas/df/mais-de-2-quartos", coletarWimoveis, []],
      ["olx", "OLX", "https://www.olx.com.br/imoveis/aluguel/casas/estado-df?ros=2&ros=3&ros=4&ros=5&sf=1", coletarOlx, []],
      ["dfimoveis", "DF Imóveis", "https://www.dfimoveis.com.br/aluguel/df/todos/casa", coletarDfImoveis, [conhecidos]],
    ];
    for (const [portal, nome, url, fn, args] of portais) {
      avisarPagina(tabPagina, "portal", `Procurando casas novas no ${nome}…`);
      try {
        const itens = await rodarNoSite(url, fn, args);
        if (!Array.isArray(itens) || itens.length < 50) throw new Error(`poucos resultados (${itens && itens.length})`);
        const r = await fetch(`${SITE}/api/receber`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ portal, coletado_em: new Date().toISOString(), itens }),
        });
        const j = await r.json().catch(() => ({}));
        if (!r.ok || !j.ok) throw new Error(j.mensagem || `HTTP ${r.status}`);
        resultados[portal] = itens.length;
      } catch (e) {
        erros.push(nome);
        console.warn("claudete:", nome, e);
      }
    }
    avisarPagina(tabPagina, "portal", "Juntando as casas de todos os sites…");
    await fetch(`${SITE}/api/atualizar`, { method: "POST" }).catch(() => {});
    await chrome.storage.local.set({ ultima: Date.now(), resultados, erros });
    const nomes = erros.length > 1 ? `${erros.slice(0, -1).join(", ")} e ${erros[erros.length - 1]}` : erros[0];
    avisarPagina(tabPagina, "enviado", erros.length
      ? `Juntando as casas… (${nomes} ${erros.length > 1 ? "não responderam" : "não respondeu"} agora)`
      : "Juntando as casas de todos os sites…");
  } finally {
    clearInterval(manterVivo);
  }
}

// Abre o site numa aba em segundo plano, espera passar a verificação, roda a coleta e fecha a aba.
async function rodarNoSite(url, fn, args) {
  const tab = await chrome.tabs.create({ url, active: false });
  try {
    await esperarCarregar(tab.id);
    for (let i = 0; i < 10; i++) {
      const [t] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: () => document.title });
      if (t && t.result && !/um momento|just a moment|attention required/i.test(t.result)) break;
      await new Promise((r) => setTimeout(r, 2000));
    }
    await new Promise((r) => setTimeout(r, 1500));
    const [res] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, world: "MAIN", func: fn, args });
    return res ? res.result : null;
  } finally {
    chrome.tabs.remove(tab.id).catch(() => {});
  }
}

function esperarCarregar(tabId) {
  return new Promise((resolve) => {
    const limite = setTimeout(fim, 45000);
    function fim() { clearTimeout(limite); chrome.tabs.onUpdated.removeListener(ouvir); resolve(); }
    function ouvir(id, info) { if (id === tabId && info.status === "complete") fim(); }
    chrome.tabs.onUpdated.addListener(ouvir);
  });
}

// ---------------------------------------------------------------------------
// Coletores: rodam DENTRO da página de cada site (mesma origem), por isso são autocontidos.
// Devolvem listas compactas; o conversor do servidor reconstrói URLs de fotos e anúncios.
// ---------------------------------------------------------------------------

async function coletarWimoveis() {
  const body = (pagina) => ({
    tipoDePropiedad: "1", tipoDeOperacion: "2", habitacionesminimo: "2", sort: "more_recent", pagina, province: "247",
    superficieCubierta: 1, idunidaddemedida: 1, tipoAnunciante: "ALL", q: null, direccion: null, moneda: null,
    preciomin: null, preciomax: null, services: "", general: "", searchbykeyword: "", amenidades: "",
    caracteristicasprop: null, comodidades: "", disposicion: null, roomType: "", outside: "", areaPrivativa: "",
    areaComun: "", multipleRets: "", subtipoDePropiedad: null, garages: null, antiguedad: null, expensasminimo: null,
    expensasmaximo: null, habitacionesmaximo: "", ambientesminimo: "", ambientesmaximo: "", banos: null,
    metroscuadradomin: null, metroscuadradomax: null, grupoTipoDeMultimedia: "", publicacion: null,
    etapaDeDesarrollo: "", auctions: null, polygonApplied: null, idInmobiliaria: null, excludePostingContacted: "",
    banks: "", places: "", condominio: "", city: null, zone: null, valueZone: null, subZone: null, coordenates: null,
  });
  const feat = (p, id) => { const f = (p.mainFeatures || {})[id]; return f ? f.value : null; };
  const KW = /(piscina|aceita (?:pets?|animais)|pets? permitid|animais permitid|pet friendly|mobiliad[ao]|churrasqueira)/gi;
  const out = []; const seen = new Set();
  for (let pagina = 1; pagina <= 40; pagina++) {
    const r = await fetch("/rplis-api/postings", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body(pagina)) });
    if (!r.ok) break;
    const lista = (await r.json()).listPostings || [];
    for (const p of lista) {
      if (seen.has(p.postingId)) continue; seen.add(p.postingId);
      const loc = (p.postingLocation || {}).location || {};
      const geo = (((p.postingLocation || {}).postingGeolocation || {}).geolocation) || {};
      const gf = p.generalFeatures || {};
      const gfText = Object.values(gf).flatMap((c) => (c && typeof c === "object") ? Object.values(c).map((v) => v && v.label).filter(Boolean) : []).join(" ");
      const aluguel = (p.priceOperationTypes || []).find((o) => String((o.operationType || {}).operationTypeId) === "2");
      const texto = `${p.title || ""} ${p.descriptionNormalized || ""} ${gfText}`;
      const it = {
        id: String(p.postingId),
        titulo: (p.generatedTitle || p.title || "").slice(0, 80),
        preco: ((((aluguel || {}).prices || [])[0] || {}).amount) || null,
        condominio: (p.expenses || {}).amount || null,
        bairro: loc.name || null, cidade: (loc.parent || {}).name || null,
        endereco: (((p.postingLocation || {}).address || {}).name || "").slice(0, 60),
        quartos: feat(p, "CFT2"), banheiros: feat(p, "CFT3"), vagas: feat(p, "CFT7"), area: feat(p, "CFT100") || feat(p, "CFT101"),
        fotos: ((p.visiblePictures || {}).pictures || []).slice(0, 10).map((x) => ((x.url730x532 || x.url360x266 || "").match(/\/(\d+)\.jpg/) || [])[1]).filter(Boolean).slice(0, 8),
        url: (p.url || "").replace(/^\/propriedades\//, ""),
        lat: geo.latitude || null, lng: geo.longitude || null,
        modificado: (p.modified_date || "").slice(0, 25), antiguidade: (p.antiquity || "").slice(0, 40),
        anunciante: ((p.publisher || {}).name || "").slice(0, 40),
        texto: [...new Set((texto.match(KW) || []).map((s) => s.toLowerCase()))].join(" "),
      };
      if (loc.label === "CIUDAD") it.bairro_cidade = true;
      out.push(it);
    }
    if (lista.length < 30) break;
  }
  return out;
}

async function coletarOlx() {
  const BASE = "/imoveis/aluguel/casas/estado-df?ros=2&ros=3&ros=4&ros=5&sf=1";
  function balanced(big, key) {
    const i = big.indexOf(key); if (i < 0) return null;
    let j = i + key.length; while (big[j] !== "[" && big[j] !== "{") j++;
    const op = big[j], cl = op === "[" ? "]" : "}"; let d = 0, ins = false, esc = false;
    for (let k = j; k < big.length; k++) {
      const ch = big[k];
      if (ins) { if (esc) esc = false; else if (ch === "\\") esc = true; else if (ch === '"') ins = false; }
      else { if (ch === '"') ins = true; else if (ch === op) d++; else if (ch === cl) { d--; if (d === 0) return JSON.parse(big.slice(j, k + 1)); } }
    }
    return null;
  }
  function anuncios(html) {
    const chunks = [...html.matchAll(/self\.__next_f\.push\(\[1,"(.*?)"\]\)/gs)].map((m) => m[1]);
    let big = ""; for (const c of chunks) { try { big += JSON.parse('"' + c + '"'); } catch (e) { big += c; } }
    return balanced(big, '"ads":') || [];
  }
  const prop = (a, n) => { const p = (a.properties || []).find((x) => x.name === n); return p ? p.value : null; };
  const num = (s) => { if (s == null) return null; const m = String(s).replace(/\./g, "").match(/\d+/); return m ? parseInt(m[0]) : null; };
  const out = new Map();
  for (let pagina = 1; pagina <= 30; pagina++) {
    let html = null;
    for (let t = 0; t < 3 && html === null; t++) {
      const r = await fetch(BASE + (pagina > 1 ? `&o=${pagina}` : ""));
      if (r.status === 429 || r.status === 403) { await new Promise((res) => setTimeout(res, 4000 * (t + 1))); continue; }
      html = await r.text();
    }
    if (!html) break;
    const ads = anuncios(html);
    if (!ads.length) break;
    for (const a of ads) {
      if (!a.listId || out.has(String(a.listId))) continue;
      const quartos = num(prop(a, "rooms")); if (!quartos || quartos < 2) continue;
      const loc = a.locationDetails || {}; if (loc.uf && loc.uf !== "DF") continue;
      out.set(String(a.listId), {
        id: String(a.listId), titulo: (a.subject || "").slice(0, 80), preco: num(a.priceValue || a.price),
        condominio: num(prop(a, "condominio")), bairro: (loc.neighbourhood || "").slice(0, 60), cidade: loc.municipality || null,
        quartos, banheiros: num(prop(a, "bathrooms")), vagas: num(prop(a, "garage_spaces")), area: num(prop(a, "size")),
        fotos: (a.images || []).slice(0, 12).map((i) => ((i.originalWebp || i.original || "").match(/images\/\d+\/(\d+)\.(webp|jpg)/) || []).slice(1).join(".")).filter(Boolean),
        url: (a.url || "").replace(/^https:\/\/df\.olx\.com\.br\//, ""),
        publicado: a.date || null, profissional: !!a.professionalAd,
        texto: [a.subject, prop(a, "re_features"), prop(a, "re_complex_features"), prop(a, "real_estate_type")].filter(Boolean).join(" ").slice(0, 400),
      });
    }
    await new Promise((res) => setTimeout(res, 800));
  }
  return [...out.values()];
}

async function coletarDfImoveis(conhecidosLista) {
  const conhecidos = new Set(conhecidosLista || []);
  const KW = /(piscina|aceita (?:pets?|animais)|pets? permitid|animais permitid|pet friendly|mobiliad[ao]|churrasqueira)/gi;
  const out = new Map(); const parser = new DOMParser();
  for (const lista of ["/aluguel/df/todos/casa", "/aluguel/df/todos/casa-condominio"]) {
    for (let pagina = 1; pagina <= 60; pagina++) {
      const r = await fetch(`${lista}?pagina=${pagina}`); if (!r.ok) break;
      const doc = parser.parseFromString(await r.text(), "text/html");
      const ld = {};
      for (const s of doc.querySelectorAll('script[type="application/ld+json"]')) {
        try { const d = JSON.parse(s.textContent); if (d && d["@type"] === "ItemList") for (const el of d.itemListElement || []) { const it = el.item || {}; if (it.identifier) ld[String(it.identifier)] = it; } } catch (e) {}
      }
      const cards = doc.querySelectorAll('article[itemtype*="RealEstateListing"]'); if (!cards.length) break;
      for (const art of cards) {
        const a = art.querySelector('a[href*="/imovel/"]'); if (!a) continue;
        const href = a.getAttribute("href").split("?")[0]; const m = href.match(/-(\d+)$/); if (!m) continue;
        const id = m[1]; if (out.has(id)) continue;
        const it = ld[id] || {}; const texto = (art.textContent || "").replace(/\s+/g, " ").trim();
        const q = it.numberOfBedrooms ?? (texto.match(/(\d+)\s*Quartos?/i) || [])[1]; const quartos = q ? parseInt(q) : null;
        if (!quartos || quartos < 2) continue;
        const h2 = art.querySelector("h2[itemprop=name]"); const img = art.querySelector("img[src*='img.dfimoveis']"); const anun = art.querySelector(".imovel-anunciante img");
        const mv = texto.match(/(\d+)\s*Vagas?/i);
        const fotos = (it.image || []).concat(img ? [img.src] : []);
        out.set(id, {
          id, titulo: (it.name || (h2 ? h2.textContent.trim() : "")).slice(0, 80), preco: it.offers ? Number(it.offers.price) : null,
          street: ((it.address || {}).streetAddress || "").slice(0, 80), h2: (h2 ? h2.textContent.trim() : "").slice(0, 80),
          quartos, area: it.floorSize ? Number(it.floorSize.value) : null, vagas: mv ? parseInt(mv[1]) : null,
          fotos, url: href, lat: (it.geo || {}).latitude || null, lng: (it.geo || {}).longitude || null,
          publicado: it.datePosted || null, anunciante: (anun ? anun.getAttribute("alt") : "").slice(0, 40),
          kw: [...new Set((((it.name || "") + " " + (it.description || "") + " " + texto).match(KW) || []).map((s) => s.toLowerCase()))].join(" "),
        });
      }
      if (cards.length < 30) break;
    }
  }
  // Fotos completas só dos anúncios novos (1 por vez, respeitando o limite do site)
  const t0 = Date.now();
  for (const it of out.values()) {
    if (conhecidos.has(it.id)) continue;
    if (Date.now() - t0 > 8 * 60 * 1000) break;
    let html = null;
    for (let t = 0; t < 4 && html === null; t++) {
      try {
        const r = await fetch(it.url);
        if (r.status === 429) { await new Promise((res) => setTimeout(res, 3000 * (t + 1))); continue; }
        html = await r.text();
      } catch (e) { break; }
    }
    if (html) {
      const re = new RegExp("https://img\\.dfimoveis\\.com\\.br/fotos/" + it.id + "/([a-f0-9]+)\\.(webp|jpe?g|png)", "g");
      const seen = new Set(); const fotos = [];
      for (const m of html.matchAll(re)) { if (!seen.has(m[1])) { seen.add(m[1]); fotos.push(m[1] + (m[2] === "webp" ? "" : "." + m[2])); } if (fotos.length >= 12) break; }
      if (fotos.length) it.fotos = fotos;
      const t = html.replace(/<script[\s\S]*?<\/script>/g, " ").replace(/<[^>]+>/g, " ");
      it.kw = [...new Set(((it.kw || "").split(" ").filter(Boolean)).concat((t.match(KW) || []).map((s) => s.toLowerCase())))].join(" ");
    }
    await new Promise((res) => setTimeout(res, 700));
  }
  // Compacta: fotos viram só o hash
  return [...out.values()].map((o) => ({
    ...o,
    fotos: (o.fotos || []).map((u) => { const m = String(u).match(/\/fotos\/\d+\/([a-f0-9]+)\.(webp|jpe?g|png)/); return m ? m[1] + (m[2] === "webp" ? "" : "." + m[2]) : u; }),
  }));
}
