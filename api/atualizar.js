// Vercel Serverless Function: dispara a coleta no GitHub Actions ("Atualizar agora").
// Precisa da variável de ambiente GITHUB_TOKEN (token fine-grained com permissão Actions: write no repo).
module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") {
    res.status(405).json({ ok: false, mensagem: "Use POST." });
    return;
  }
  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.GITHUB_REPO || "ruanvetta-arch/claudete";
  if (!token) {
    res.status(500).json({ ok: false, mensagem: "A busca manual ainda não foi ativada. As casas são atualizadas sozinhas todo dia às 7h e às 13h." });
    return;
  }
  try {
    // Evita disparos repetidos: se já há uma coleta rodando, só avisa
    const runs = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/coletar.yml/runs?status=in_progress&per_page=1`, {
      headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json", "User-Agent": "claudete" },
    }).then((r) => r.json()).catch(() => ({}));
    if (runs && runs.total_count > 0) {
      res.status(200).json({ ok: true, mensagem: "Já tem uma atualização em andamento." });
      return;
    }
    const r = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/coletar.yml/dispatches`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json", "User-Agent": "claudete", "Content-Type": "application/json" },
      body: JSON.stringify({ ref: "main" }),
    });
    if (r.status === 204) {
      res.status(200).json({ ok: true, mensagem: "Atualização iniciada." });
    } else {
      const txt = await r.text();
      res.status(502).json({ ok: false, mensagem: `GitHub respondeu ${r.status}: ${txt.slice(0, 120)}` });
    }
  } catch (e) {
    res.status(500).json({ ok: false, mensagem: String(e).slice(0, 160) });
  }
};
