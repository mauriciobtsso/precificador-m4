/**
 * ══════════════════════════════════════════════════════════════
 * CLOUDFLARE WORKER — Cache de Imagens R2 (Plano Gratuito)
 * ══════════════════════════════════════════════════════════════
 *
 * PROBLEMA IDENTIFICADO NO PAGESPEED:
 *   Todas as imagens do Cloudflare R2 retornam Cache-Control: None.
 *   O browser baixa as mesmas imagens em TODA visita, desperdiçando
 *   626 KiB por pageload.
 *
 * O QUE ESTE WORKER FAZ:
 *   Intercepta requisições de imagem e injeta headers de cache
 *   corretos, fazendo o browser (e a CDN do Cloudflare) guardar
 *   as imagens por 1 ano.
 *
 * CUSTO: R$ 0,00 — Workers gratuito inclui 100.000 req/dia.
 *
 * ══════════════════════════════════════════════════════════════
 * COMO INSTALAR (5 passos, ~10 minutos):
 * ══════════════════════════════════════════════════════════════
 *
 * 1. Acesse dash.cloudflare.com → sua conta → "Workers & Pages"
 * 2. Clique "Create" → "Create Worker"
 * 3. Dê o nome "m4-image-cache" e clique "Deploy"
 * 4. Clique "Edit Code", cole TODO este arquivo, clique "Deploy"
 * 5. Vá em "Settings" → "Triggers" → "Add Custom Domain"
 *    e adicione o mesmo domínio do seu bucket R2, ex:
 *    Se suas imagens são: 1202e2896f1...r2.cloudflarestorage.com
 *    adicione uma rota: *r2.cloudflarestorage.com/*
 *
 * ALTERNATIVA MAIS SIMPLES (sem domínio customizado):
 *   Em "Workers & Pages" → seu Worker → "Triggers" → "Routes"
 *   Adicione: *1202e2896f1ad48f3caa5d520ab29ff0.r2.cloudflarestorage.com/*
 *
 * ══════════════════════════════════════════════════════════════
 */

export default {
  async fetch(request, env, ctx) {

    // ── 1. Só processa GET/HEAD ────────────────────────────────
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      return fetch(request);
    }

    const url = new URL(request.url);

    // ── 2. Detecta se é imagem pelo Content-Type ou extensão ──
    const imagemExtensoes = /\.(webp|jpg|jpeg|png|gif|svg|avif|ico)(\?|$)/i;
    const isImagem = imagemExtensoes.test(url.pathname);

    // ── 3. Busca o recurso original no R2 ─────────────────────
    const resposta = await fetch(request);

    // Não modifica se não for imagem ou se houve erro
    if (!isImagem || !resposta.ok) {
      return resposta;
    }

    // ── 4. Clona a resposta e injeta os headers de cache ───────
    const novaResposta = new Response(resposta.body, resposta);

    /**
     * Cache-Control escolhido:
     *
     *   public         → pode ser cacheado por CDN e browser
     *   max-age=31536000 → 1 ano (365 dias × 86400 segundos)
     *   immutable      → informa que o arquivo NUNCA muda
     *                    (correto para imagens de produto com
     *                     URLs que contêm hash, ex: 79f3f86.webp)
     *
     * Se suas imagens podem mudar mantendo a mesma URL, troque
     * immutable por stale-while-revalidate=86400
     */
    novaResposta.headers.set(
      'Cache-Control',
      'public, max-age=31536000, immutable'
    );

    // Cloudflare CDN também vai cachear por 1 ano
    novaResposta.headers.set(
      'CDN-Cache-Control',
      'public, max-age=31536000'
    );

    // Indica ao browser a data de expiração absoluta
    const expira = new Date(Date.now() + 365 * 24 * 60 * 60 * 1000);
    novaResposta.headers.set('Expires', expira.toUTCString());

    // Varia por Accept para futura compatibilidade com AVIF/WebP
    novaResposta.headers.set('Vary', 'Accept');

    return novaResposta;
  }
};