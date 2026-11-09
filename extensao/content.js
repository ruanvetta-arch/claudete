// Ponte entre a página da claudete e a extensão.
// Página -> extensão: window.postMessage({claudete:'coletar', forcar})
// Extensão -> página: window.postMessage({claudeteColetor: {fase, msg}})
document.documentElement.dataset.claudeteColetor = "1";

function paraPagina(m) {
  window.postMessage({ claudeteColetor: m }, location.origin);
}

window.addEventListener("message", (e) => {
  if (e.source !== window || !e.data || e.data.claudete !== "coletar") return;
  chrome.runtime.sendMessage({ tipo: "coletar", forcar: !!e.data.forcar }, (resp) => {
    if (chrome.runtime.lastError) return;
    if (resp) paraPagina(resp);
  });
});

chrome.runtime.onMessage.addListener((m) => {
  if (m && m.claudeteColetor) paraPagina(m.claudeteColetor);
});

paraPagina({ fase: "presente" });
