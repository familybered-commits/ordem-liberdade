#!/usr/bin/env python3
"""
Ordem & Liberdade — Gerador de Resumo Diário de Notícias
Busca as principais notícias do dia e as analisa sob a ótica conservadora-libertária via API do Claude.
"""

import os
import json
import datetime
import feedparser
import anthropic
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIGURAÇÃO DE FONTES RSS
# ─────────────────────────────────────────────
RSS_FEEDS = [
    # ── Brasil ──────────────────────────────────
    {"nome": "G1",           "pais": "🇧🇷", "url": "https://g1.globo.com/rss/g1/"},
    {"nome": "Folha",        "pais": "🇧🇷", "url": "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml"},
    {"nome": "UOL Notícias", "pais": "🇧🇷", "url": "https://rss.uol.com.br/feed/noticias.xml"},
    {"nome": "Gazeta do Povo","pais": "🇧🇷", "url": "https://www.gazetadopovo.com.br/feed/"},
    {"nome": "Mises Brasil",  "pais": "🇧🇷", "url": "https://www.mises.org.br/feed"},
    # ── Internacional ────────────
    {"nome": "BBC",           "pais": "🌐", "url": "https://feeds.bbci.co.uk/news/rss.xml"},
    {"nome": "The Times UK",  "pais": "🌐", "url": "https://www.thetimes.co.uk/rss/news"},
    {"nome": "The Spectator", "pais": "🌐", "url": "https://www.spectator.co.uk/rss"},
    {"nome": "Fox News",      "pais": "🌐", "url": "https://moxie.foxnews.com/google-publisher/latest.xml"},
    {"nome": "Wall Street Journal","pais": "🌐","url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml"},
]

MAX_NOTICIAS_POR_FONTE = 1
MAX_NOTICIAS_TOTAL     = 6

# ─────────────────────────────────────────────
# PROMPT CONSERVADOR-LIBERTÁRIO
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """Você é um analista político, econômico e cultural que interpreta os acontecimentos
do dia sob uma perspectiva conservadora-libertária — fusão entre o liberalismo econômico clássico
e o conservadorismo de costumes. Suas análises são fundamentadas nos seguintes pilares e pensadores:

═══ LIBERDADE ECONÔMICA ═══

1. PROPRIEDADE PRIVADA E LIVRE MERCADO (Mises, Hayek, Bastiat, Friedman)
- O direito à propriedade é sagrado e fundamento de toda liberdade real.
- A cooperação voluntária e o sistema de preços alocam recursos melhor que qualquer planejador.
- Lembre Bastiat: sempre analise o "visto" e o "não-visto" em políticas públicas.
- Segundo Hayek, o conhecimento é disperso — nenhum governo pode centralizar o que milhões sabem.

2. ESTADO MÍNIMO E CETICISMO FISCAL (Mises, Rothbard, Roberto Campos)
- Expansão do Estado gera dependência, corrupção e destruição de capital.
- Tributação excessiva é confisco; inflação é tributação oculta sobre os mais pobres.
- Roberto Campos: "No Brasil, até o passado é incerto" — desconfie de estatísticas oficiais.

3. CONSEQUÊNCIAS NÃO INTENCIONAIS (Bastiat, Hayek, Friedman, Thomas Sowell)
- Toda intervenção cria distorções que exigem novas intervenções — ciclo vicioso.
- Milton Friedman: "Não existe almoço grátis." Alguém sempre paga a conta.
- Thomas Sowell: políticas devem ser julgadas pelos resultados, não pelas intenções.
- Sowell: o pensamento irrestrito ignora trade-offs e custos invisíveis.

═══ CONSERVADORISMO DE COSTUMES ═══

4. ORDEM, TRADIÇÃO E INSTITUIÇÕES (Edmund Burke, Russell Kirk)
- A sociedade é um contrato entre os mortos, os vivos e os que ainda nascerão (Burke).
- Mudanças abruptas destroem o conhecimento acumulado em instituições e costumes.
- Russell Kirk: a ordem moral é o fundamento de toda liberdade política duradoura.

5. FAMÍLIA, COMUNIDADE E SUBSIDIARIEDADE (Roger Scruton, G.K. Chesterton)
- A família é a célula básica da sociedade — sua erosão enfraquece toda a ordem social.
- Roger Scruton: o amor ao lugar, à pátria e à herança cultural não é reacionarismo — é sabedoria.
- G.K. Chesterton: não derrube uma cerca sem antes entender por que ela foi erguida.
- Problemas locais devem ser resolvidos localmente, não por burocracia central.

6. CETICISMO À ENGENHARIA SOCIAL (Scruton, Kirk, Chesterton, Olavo de Carvalho)
- Projetos de transformação radical da sociedade historicamente produzem tirania.
- A cultura, a religião e os costumes são repositórios de sabedoria que o racionalismo abstrato ignora.

═══ RAÇA, DESIGUALDADE E NARRATIVAS PROGRESSISTAS ═══

7. CRÍTICA AO RACIALISMO E AO IGUALITARISMO FORÇADO (Thomas Sowell)
- Sowell demoliu empiricamente a narrativa de que disparidades implicam necessariamente discriminação.
- Políticas de ação afirmativa frequentemente prejudicam os próprios grupos que pretendem ajudar.

═══ BRASIL ESPECIFICAMENTE ═══

8. CONTEXTO BRASILEIRO (Roberto Campos, Gustavo Franco)
- O Estado brasileiro é historicamente predatório, ineficiente e capturado por corporações e sindicatos.
- A mídia mainstream brasileira é, em grande parte, financiada por Verbas publicitárias governamentais.

═══ DIRETRIZES DE ANÁLISE ═══

Ao analisar cada notícia:
- Cite o pensador mais pertinente quando houver encaixe natural (não force citações)
- Para temas econômicos: aplique Mises/Hayek/Bastiat/Friedman/Sowell/Roberto Campos
- Para temas culturais, família, educação, religião: aplique Burke/Kirk/Scruton/Chesterton
- Para temas de raça, desigualdade, cotas: aplique Sowell
- Para temas de mídia e narrativa: ceticismo estrutural (quem financia? quem se beneficia?)
- Use linguagem clara, culta e acessível — como um ensaísta, não um burocrata
- Seja incisivo e direto, mas justo — critique ideias e fatos, não pessoas"""

USER_PROMPT_TEMPLATE = """Below are today's main news stories ({data}). For EACH story, provide analysis in BOTH languages:

- Portuguese (pt): for Brazilian readers
- English (en): for international libertarian/conservative audience

Guidelines per story (be CONCISE — each field max 2 sentences):
1. Factual summary: what happened, no interpretation (2 sentences max)
2. Analysis: conservative-libertarian perspective, cite one thinker if natural (2 sentences max)
3. Watch point: what the vigilant citizen should monitor (1 sentence)

IMPORTANT LANGUAGE RULES:
- Brazilian sources (🇧🇷): generate content in PORTUGUESE only (no English needed)
- International sources (🌐): generate content in BOTH languages — Portuguese (pt) AND English (en)
- editorial_pt: always in Portuguese
- editorial_en: always in English

Respond in JSON with EXACTLY this format:
{{
  "noticias": [
    {{
      "fonte": "source name",
      "pais": "🇧🇷 or 🌐",
      "url": "original article URL or empty string",
      "pensador": "thinker cited or null",
      "tags": ["tag1", "tag2"],
      "titulo": "Portuguese for 🇧🇷 · English for 🌐 (primary language)",
      "resumo": "Portuguese for 🇧🇷 · English for 🌐 (primary language)",
      "analise": "Portuguese for 🇧🇷 · English for 🌐 (primary language)",
      "atencao": "Portuguese for 🇧🇷 · English for 🌐 (primary language)",
      "titulo_pt": "ONLY for 🌐: Portuguese translation of the headline",
      "resumo_pt": "ONLY for 🌐: Portuguese translation of the summary",
      "analise_pt": "ONLY for 🌐: Portuguese translation of the analysis",
      "atencao_pt": "ONLY for 🌐: Portuguese translation of the watch point"
    }}
  ],
  "editorial_pt": "parágrafo editorial em português (3-4 frases, tom ensaístico)",
  "editorial_en": "editorial paragraph in English (3-4 sentences, essayistic tone)"
}}

Note: for 🇧🇷 sources, omit the _pt fields entirely. For 🌐 sources, the main fields (titulo/resumo/analise/atencao) are in English and the _pt fields are the Portuguese versions.

TODAY'S NEWS:
{noticias}"""


# ─────────────────────────────────────────────
# FUNÇÕES
# ─────────────────────────────────────────────

def buscar_ticker() -> dict:
    """Busca preço do Bitcoin e câmbio USD/BRL para o ticker do site."""
    import urllib.request
    ticker = {"btc_brl": None, "btc_usd": None, "usd_brl": None}
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=brl,usd"
        req = urllib.request.Request(url, headers={"User-Agent": "OrdemLiberdade/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
            ticker["btc_brl"] = data["bitcoin"]["brl"]
            ticker["btc_usd"] = data["bitcoin"]["usd"]
        if ticker["btc_brl"] and ticker["btc_usd"]:
            ticker["usd_brl"] = round(ticker["btc_brl"] / ticker["btc_usd"], 2)
        print(f" ✓ Ticker: BTC R$ {ticker['btc_brl']:,.0f} | USD/BRL {ticker['usd_brl']}")
    except Exception as e:
        print(f" ⚠ Ticker indisponível: {e}")
    return ticker


def buscar_noticias() -> list[dict]:
    """Busca notícias das fontes RSS configuradas."""
    import re
    noticias = []
    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            entradas = feed.entries[:MAX_NOTICIAS_POR_FONTE]
            for entry in entradas:
                resumo = getattr(entry, "summary", "") or ""
                resumo = re.sub(r"<[^>]+>", "", resumo).strip()
                resumo = resumo[:500]
                noticias.append({
                    "titulo": entry.get("title", "No title"),
                    "fonte":  feed_info["nome"],
                    "pais":   feed_info.get("pais", "🌐"),
                    "url":    entry.get("link", ""),
                    "resumo_original": resumo,
                })
            print(f" ✓ {feed_info['pais']} {feed_info['nome']}: {len(entradas)} notícias")
        except Exception as e:
            print(f" ✗ {feed_info['nome']}: erro — {e}")
    return noticias[:MAX_NOTICIAS_TOTAL]


def analisar_com_claude(noticias: list[dict], data_str: str) -> dict:
    """Envia as notícias para o Claude e retorna a análise libertária."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Variável de ambiente ANTHROPIC_API_KEY não definida.")

    client = anthropic.Anthropic(api_key=api_key)

    bloco_noticias = ""
    for i, n in enumerate(noticias, 1):
        bloco_noticias += f"\n---\n{i}. [{n['fonte']}] {n['titulo']}\n{n['resumo_original']}\n"

    prompt = USER_PROMPT_TEMPLATE.format(data=data_str, noticias=bloco_noticias)

    print("\nEnviando para o Claude...")
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    resposta_texto = message.content[0].text

    import re
    try:
        return json.loads(resposta_texto)
    except json.JSONDecodeError:
        pass

    cleaned = re.sub(r"```(?json)?\s*", "", resposta_texto).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = resposta_texto.find("{")
    if start != -1:
        depth = 0
        for i, c in enumerate(resposta_texto[start:], start):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            if depth == 0:
                try:
                    return json.loads(resposta_texto[start:i+1])
                except json.JSONDecodeError:
                    break

    raise ValueError(f"Resposta do Claude não continha JSON valido:\n{resposta_texto[:500]}")


def _card_pt(noticia: dict) -> str:
    """Card para notícia brasileira — sempre em português, sem toggle."""
    tags_html    = "".join(f'<span class="tag">{t}</span>' for t in noticia.get("tags", []))
    pensador     = noticia.get("pensador")
    pensador_html = f'<span class="pensador-tag">✍️ {pensador}</span>' if pensador else ""
    return f"""
<article class="card card-br">
  <div class="card-header">
    <span class="pais">🇧🇷</span>
    <span class="fonte">{noticia.get('fonte', '')}</span>
    {tags_html}
    {pensador_html}
  </div>
  <h2 class="card-titulo">{noticia.get('titulo', '')}</h2>
  <div class="secao">
    <h3 class="secao-label">📋 Resumo</h3>
    <p>{noticia.get('resumo', '')}</p>
  </div>
  <div class="secao analise">
    <h3 class="secao-label">⚖️ Análise — Ordem &amp; Liberdade</h3>
    <p>{noticia.get('analise', '')}</p>
  </div>
  <div class="secao atencao">
    <h3 class="secao-label">👁️ Ponto de Atenção</h3>
    <p>{noticia.get('atencao', '')}</p>
  </div>
</article>"""


def _card_en(noticia: dict, idx: int) -> str:
    """Card para notícia internacional — EN por padrão, traduz para PT no toggle."""
    tags_html     = "".join(f'<span class="tag">{t}</span>' for t in noticia.get("tags", []))
    pensador      = noticia.get("pensador")
    pensador_html = f'<span class="pensador-tag">✍️ {pensador}</span>' if pensador else ""
    share_url     = noticia.get('url', '') or ''
    return f"""
<article class="card card-en" data-intl="{idx}">
  <div class="card-header">
    <span class="pais">🌐</span>
    <span class="fonte">{noticia.get('fonte', '')}</span>
    {tags_html}
    {pensador_html}
    <button class="share-btn" onclick="compartilhar('{share_url}', this)" title="Share">↗ Share</button>
  </div>
  <h2 class="card-titulo intl-titulo">{noticia.get('titulo', '')}</h2>
  <div class="secao">
    <h3 class="secao-label intl-lbl-resumo">📋 Summary</h3>
    <p class="intl-resumo">{noticia.get('resumo', '')}</p>
  </div>
  <div class="secao analise">
    <h3 class="secao-label intl-lbl-analise">⚖️ Analysis ─ Order &amp; Liberty</h3>
    <p class="intl-analise">{noticia.get('analise', '')}</p>
  </div>
  <div class="secao atencao">
    <h3 class="secao-label intl-lbl-atencao">👁️ Watch Point</h3>
    <p class="intl-atencao">{noticia.get('atencao', '')}</p>
  </div>
</article>"""


def _ticker_html(ticker: dict) -> str:
    """Gera o HTML do ticker de cotações."""
    if not ticker.get("btc_brl"):
        return ""
    btc_brl_fmt = f"R$ {ticker['btc_brl']:,.0f}".replace(",", ".")
    usd_brl_fmt = f"{ticker['usd_brl']:.2f}".replace(".", ",") if ticker.get("usd_brl") else "— "
    return f"""
<div class="ticker-bar" aria-label="Cotações">
  <div class="tick"><span class="tick-label">BTC</span><span class="tick-val">{btc_brl_fmt}</span></div>
  <div class="tick-sep"></div>
  <div class="tick"><span class="tick-label">USD/BRL</span><span class="tick-val">{usd_brl_fmt}</span></div>
  <div class="tick-sep"></div>
  <div class="tick"><span class="tick-label">BSafe</span><a class="tick-link" href="https://bsafebitcoin.org" target="_blank">bsafebitcoin.org ↗</a></div>
</div>"""


def gerar_html(analise: dict, data_str: str, data_formatada: str, ticker: dict | None = None) -> str:
    """Gera o HTML com notícias BR em PT e internacionais em EN com visual refinado."""

    noticias      = analise.get("noticias", [])
    editorial_pt  = analise.get("editorial_pt", "")
    editorial_en  = analise.get("editorial_en", "")

    intl = [(i, n) for i, n in enumerate(noticias) if n.get("pais") == "🌐"]

    dados_js = json.dumps({
        "editorial": {"pt": editorial_pt, "en": editorial_en},
        "intl": {
            str(i): {
                "en": {
                    "titulo":  n.get("titulo", ""),
                    "resumo":  n.get("resumo", ""),
                    "analise": n.get("analise", ""),
                    "atencao": n.get("atencao", ""),
                },
                "pt": {
                    "titulo":  n.get("titulo_pt", ""),
                    "resumo":  n.get("resumo_pt", ""),
                    "analise": n.get("analise_pt", ""),
                    "atencao": n.get("atencao_pt", ""),
                },
            }
            for i, n in intl
        }
    }, ensure_ascii=False)

    cards_br = "".join(_card_pt(n) for n in noticias if n.get("pais") == "🇧🇷")
    cards_en = "".join(_card_en(n, i) for i, n in intl)
    ticker_html = _ticker_html(ticker or {})

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ordem &amp; Liberdade / Order &amp; Liberty — {data_formatada}</title>
  <meta name="description" content="Digest diário de notícias interpretadas sob a ótica conservadora-libertária. Fundamentado em Mises, Hayek, Burke e Sowell.">
  <meta property="og:title" content="Ordem &amp; Liberdade — {data_formatada}">
  <meta property="og:description" content="Digest conservador-libertário do dia.">
  <style>
    :root {{
      --ouro: #c9a227;
      --ouro-escuro: #9b7c1a;
      --ouro-claro: #e5c563;
      --bg: #0d0d0d;
      --surface: #141414;
      --surface2: #1c1c1c;
      --surface3: #242424;
      --texto: #e0e0e0;
      --texto-fraco: #777;
      --borda: #222;
      --borda-forte: #2e2e2e;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Georgia', serif;
      background: var(--bg);
      color: var(--texto);
      line-height: 1.7;
      min-height: 100vh;
    }}

    /* ── Ticker ── */
    .ticker-bar {{
      background: #0a0a0a;
      border-bottom: 1px solid #1e1a0a;
      padding: 6px 1.5rem;
      display: flex;
      align-items: center;
      gap: 0;
      overflow-x: auto;
      scrollbar-width: none;
    }}
    .ticker-bar::-webkit-scrollbar {{ display: none; }}
    .tick {{
      display: flex;
      align-items: center;
      gap: 7px;
      white-space: nowrap;
      padding: 0 14px;
    }}
    .tick-label {{
      font-family: Arial, sans-serif;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 1px;
      color: var(--ouro);
    }}
    .tick-val {{
      font-family: Arial, sans-serif;
      font-size: 11px;
      color: #aaa;
    }}
    .tick-link {{
      font-family: Arial, sans-serif;
      font-size: 11px;
      color: var(--ouro);
      text-decoration: none;
      opacity: 0.7;
    }}
    .tick-link:hover {{ opacity: 1; }}
    .tick-sep {{
      width: 1px;
      height: 14px;
      background: #2a2a2a;
      flex-shrink: 0;
    }}

    /* ── Header ── */
    header {{
      background: var(--surface);
      border-bottom: 2px solid var(--ouro);
      padding: 2rem 1rem 1.5rem;
      text-align: center;
    }}
    .tagline {{
      font-size: 0.82rem;
      letter-spacing: 0.04em;
      color: var(--ouro);
      font-style: italic;
      font-family: 'Georgia', serif;
      margin-bottom: 0.6rem;
      opacity: 0.8;
    }}
    header h1 {{
      font-size: 2.4rem;
      color: #fff;
      font-weight: 700;
      letter-spacing: -0.5px;
    }}
    header h1 span {{ color: var(--ouro); }}
    .dateline {{
      color: var(--texto-fraco);
      font-size: 0.85rem;
      margin-top: 0.5rem;
      font-family: Arial, sans-serif;
    }}

    /* ── Toggle de idioma ── */
    .lang-toggle {{
      display: inline-flex;
      margin-top: 1rem;
      border: 1px solid #2a2a2a;
      border-radius: 30px;
      overflow: hidden;
    }}
    .lang-toggle button {{
      background: transparent;
      border: none;
      padding: 0.35rem 1.1rem;
      font-size: 0.78rem;
      letter-spacing: 0.08em;
      cursor: pointer;
      color: var(--texto-fraco);
      font-family: Arial, sans-serif;
      transition: background 0.2s, color 0.2s;
    }}
    .lang-toggle button.active {{
      background: var(--ouro);
      color: #000;
      font-weight: 700;
    }}

    /* ── Nav ── */
    .site-nav {{
      margin-top: 1rem;
      display: flex;
      justify-content: center;
      gap: 0.8rem;
      font-family: Arial, sans-serif;
      font-size: 0.78rem;
    }}
    .site-nav a {{
      color: var(--texto-fraco);
      text-decoration: none;
      padding: 0.3rem 0.9rem;
      border-radius: 20px;
      border: 1px solid var(--borda-forte);
      transition: all 0.2s;
    }}
    .site-nav a:hover, site-nav a.active {{
      border-color: var(--ouro);
      color: var(--ouro);
    }}

    /* ── Layout ── */
    .container {{
      max-width: 860px;
      margin: 0 auto;
      padding: 2rem 1rem;
    }}

    /* ── Editorial ── */
    .editorial {{
      border-left: 3px solid var(--ouro);
      background: var(--surface);
      border-radius: 0 8px 8px 0;
      padding: 1.3rem 1.6rem;
      margin-bottom: 2.5rem;
    }}
    .editorial-label {{
      font-size: 0.72rem;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      color: var(--ouro);
      font-style: normal;
      margin-bottom: 0.7rem;
      display: block;
      font-family: Arial, sans-serif;
    }}
    .editorial p {{
      font-style: italic;
      font-size: 1rem;
      color: #c8bc96;
      text-align: justify;
      hyphens: auto;
      line-height: 1.8;
    }}

    /* ── Section header ── */
    .section-header {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin: 2.5rem 0 1.2rem;
    }}
    .section-header .sh-accent {{
      width: 24px;
      height: 2px;
      background: var(--ouro);
      border-radius: 1px;
      flex-shrink: 0;
    }}
    .section-header .sh-label {{
      font-size: 0.72rem;
      letter-spacing: 0.22em;
      text-transform: uppercase;
      color: var(--texto-fraco);
      font-family: Arial, sans-serif;
      white-space: nowrap;
    }}-header .sh-line {{
      flex: 1;
      height: 0.5px;
      background: var(--borda-forte);
    }}

    /* ── Cards ── */
    .card {{
      background: var(--surface);
      border: 0.5px solid var(--borda-forte);
      border-radius: 10px;
      padding: 1.3rem 1.5rem;
      margin-bottom: 1.2rem;
      transition: border-color 0.2s;
    }}
    .card:hover {{ border-color: var(--ouro-escuro); }}

    .card-header {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 0.8rem;
      flex-wrap: wrap;
    }}
    .pais {{ font-size: 1rem; }}
    .fonte {{
      font-size: 0.72rem;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--ouro);
      font-family: Arial, sans-serif;
      font-weight: 700;
    }}
    .tag {{
      font-size: 0.68rem;
      padding: 0.15rem 0.5rem;
      background: var(--surface3);
      border: 0.5px solid var(--borda-forte);
      border-radius: 10px;
      color: var(--texto-fraco);
      font-family: Arial, sans-serif;
    }}
    .pensador-tag {{
      font-size: 0.68rem;
      padding: 0.15rem 0.6rem;
      background: #1a1400;
      border: 0.5px solid var(--ouro-escuro);
      border-radius: 10px;
      color: var(--ouro-claro);
      font-family: 'Georgia', serif;
      font-style: italic;
    }}
    .share-btn {{
      margin-left: auto;
      background: transparent;
      border: 0.5px solid var(--borda-forte);
      color: var(--texto-fraco);
      font-size: 0.68rem;
      padding: 0.2rem 0.7rem;
      border-radius: 10px;
      cursor: pointer;
      font-family: Arial, sans-serif;
      transition: all 0.2s;
    }}
    .share-btn:hover {{ border-color: var(--ouro); color: var(--ouro); }}
    .share-btn.copied {{ border-color: #4caf50; color: #4caf50; }}

    .card-titulo {{
      font-size: 1.15rem;
      color: #f0f0f0;
      margin-bottom: 1.1rem;
      line-height: 1.38;
    }}

    /* ── Seções dentro do card ── */
    .secao {{ margin-bottom: 0.9rem; }}
    .secao:last-child {{ margin-bottom: 0; }}
    .secao-label {{
      font-size: 0.7rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--texto-fraco);
      margin-bottom: 0.4rem;
      font-family: Arial, sans-serif;
      font-weight: normal;
    }}
    .secao p {{
      font-size: 0.95rem;
      color: var(--texto);
      text-align: justify;
      hyphens: auto;
    }}
    .secao.analise {{
      background: #0f0f0f;
      border: 0.5px solid var(--borda-forte);
      border-top: 1.5px solid var(--ouro-escuro);
      border-radius: 6px;
      padding: 0.9rem 1rem;
    }}
    .secao.analise .secao-label {{ color: var(--ouro); }}
    .secao.analise p {{ color: #c8bc96; }}
    .secao.atencao .secao-label {{ color: var(--texto-fraco); }}
    .secao.atencao p {{ color: var(--ouro); font-weight: 500; font-size: 0.9rem; }}

    /* ── BSafe CTA ── */
    .bsafe-cta {{
      border: 0.5px solid var(--ouro-escuro);
      border-radius: 8px;
      padding: 1rem 1.3rem;
      margin: 2rem 0;
      display: flex;
      align-items: center;
      gap: 1rem;
      background: #0d0900;
    }}
    .bsafe-cta .btc-icon {{
      font-size: 1.5rem;
      flex-shrink: 0;
    }}
    .bsafe-cta .bsafe-text {{ flex: 1; }}
    .bsafe-cta .bsafe-text strong {{
      display: block;
      font-size: 0.88rem;
      color: #f0f0f0;
      margin-bottom: 3px;
      font-family: Arial, sans-serif;
    }}
    .bsafe-cta .bsafe-text span {{
      font-size: 0.78rem;
      color: var(--texto-fraco);
      font-family: Arial, sans-serif;
    }}
    .bsafe-cta a {{
      font-size: 0.78rem;
      color: var(--ouro);
      border: 0.5px solid var(--ouro-escuro);
      padding: 0.4rem 0.9rem;
      border-radius: 6px;
      text-decoration: none;
      white-space: nowrap;
      flex-shrink: 0;
      transition: background 0.2s;
    }}
    .bsafe-cta a:hover {{ background: var(--ouro); color: #000; }}

    /* ── Footer ── */
    footer {{
      text-align: center;
      padding: 2rem 1rem;
      color: var(--texto-fraco);
      font-size: 0.76rem;
      border-top: 1px solid var(--borda-forte);
      font-family: Arial, sans-serif;
      line-height: 1.9;
    }}
    footer a {{ color: var(--ouro); text-decoration: none; }}
    footer a:hover {{ opacity: 0.8; }}
  </style>
</head>
<body>

{ticker_html}

<header>
  <p class="tagline" id="tagline">⚖️ O preço da liberdade é a eterna vigilância</p>
  <h1 id="site-title">Ordem <span>&amp; Liberdade</span></h1>
  <p class="dateline">{data_formatada}</p>
  <div class="lang-toggle">
    <button id="btn-pt" class="active" onclick="setLang('pt')">🇧🇷 PT</button>
    <button id="btn-en" onclick="setLang('en')">🇺🇸 EN</button>
  </div>
  <nav class="site-nav">
    <a href="index.html" class="active">📰 Digest do Dia</a>
    <a href="analisar.html">🔍 Analisar Notícia</a>
  </nav>
</header>

<div class="container">

  <div class="editorial">
    <span class="editorial-label" id="editorial-label">Editorial do dia</span>
    <p><span id="editorial-text">{editorial_pt}</span></p>
  </div>

  <div class="section-header">
    <div class="sh-accent"></div>
    <span class="sh-label">🇧🇷 Brasil</span>
    <div class="sh-line"></div>
  </div>

  {cards_br}

  <div class="bsafe-cta">
    <span class="btc-icon">₿</span>
    <div class="bsafe-text">
      <strong>BSafe Bitcoin — Sua segurança, sua soberania</strong>
      <span>Aprenda a guardar Bitcoin com segurança. Custódia própria, sem depender de terceiros.</span>
    </div>
    <a href="https://bsafebitcoin.org" target="_blank">Conhecer →</a>
  </div>

  <div class="section-header">
    <div class="sh-accent"></div>
    <span class="sh-label" id="intl-section-label">🌐 Internacional · International</span>
    <div class="sh-line"></div>
  </div>

  {cards_en}

</div>

<footer>
  <p>Burke · Kirk · Scruton · Chesterton · Mises · Hayek · Bastiat · Friedman · Sowell · Rothbard · Roberto Campos</p>
  <p>🇧🇷 G1 · Folha · Estadão · Gazeta do Povo · Mises Brasil &nbsp;|&nbsp; 🌐 Reuters · AP · BBC · The Guardian · WSJ</p>
  <p style="margin-top: 0.6rem; color: #444;">
    Atualizado em {data_formatada} ·
    <a href="https://mises.org.br" target="_blank">Mises Brasil</a> ·
    <a href="https://iea.org.br" target="_blank">IEA</a> ·
    <a href="https://www.gazetadopovo.com.br" target="_blank">Gazeta do Povo</a> ·
    <a href="https://bsafebitcoin.org" target="_blank">BSafe Bitcoin</a>
  </p>
</footer>

<script>
const DADOS = {dados_js};

function setLang(lang) {{
  const isPt = lang === 'pt';
  document.getElementById('btn-pt').classList.toggle('active', isPt);
  document.getElementById('btn-en').classList.toggle('active', !isPt);

  document.getElementById('site-title').innerHTML = isPt
    ? 'Ordem <span style="color:var(--ouro)">&amp; Liberdade</span>'
    : 'Order <span style="color:var(--ouro)">&amp; Liberty</span>';

  document.getElementById('tagline').textContent = isPt
    ? '⚖️ O preço da liberdade é a eterna vigilância'
    : '⚖️ The price of liberty is eternal vigilance';

  document.getElementById('editorial-label').textContent = isPt ? 'Editorial do dia' : "Today's editorial";
  document.getElementById('editorial-text').textContent  = DADOS.editorial[isPt ? 'pt' : 'en'];

  document.getElementById('intl-section-label').textContent = isPt
    ? '🌐 Internacional · International'
    : '🌐 International · Internacional';

  document.querySelectorAll('.card-en[data-intl]').forEach(card => {{
    const idx = card.getAttribute('data-intl');
    const d   = DADOS.intl[idx];
    if (!d) return;
    const v = d[isPt ? 'pt' : 'en'];
    card.querySelector('.intl-titulo').textContent         = v.titulo  || '';
    card.querySelector('.intl-resumo').textContent         = v.resumo  || '';
    card.querySelector('.intl-analise').textContent        = v.analise || '';
    card.querySelector('.intl-atencao').textContent        = v.atencao || '';
    card.querySelector('.intl-lbl-resumo').textContent     = isPt ? '📋 Resumo'  : '📋 Summary';
    card.querySelector('.intl-lbl-analise').textContent    = isPt
      ? '⚖️ Análise — Ordem & Liberdade' : '⚖️ Analysis — Order & Liberty';
    card.querySelector('.intl-lbl-atencao').textContent    = isPt ? '👁️ Ponto de Atenção' : '👁️ Watch Point';
  }});

  document.documentElement.lang = isPt ? 'pt-BR' : 'en';
}}

function compartilhar(url, btn) {{
  const titulo = btn.closest('.card').querySelector('.card-titulo').textContent;
  const link   = url || window.location.href;
  if (navigator.share) {{
    navigator.share({{ title: titulo, text: titulo + ' — Ordem & Liberdade', url: link }});
  }} else {{
    navigator.clipboard.writeText(link).then(() => {{
      btn.textContent = '✓ Copied!';
      btn.classList.add('copied');
      setTimeout(() => {{ btn.textContent = '↗ Share'; btn.classList.remove('copied'); }}, 2000);
    }});
  }}
}}
</script>
</body>
</html>"""


def salvar_arquivo(html: str, data_str: str, output_dir: Path):
    """Salva o HTML e atualiza o index.html apontando para o arquivo do dia."""
    output_dir.mkdir(parents=True, exist_ok=True)

    arquivo_dia = output_dir / f"{data_str}.html"
    arquivo_dia.write_text(html, encoding="utf-8")
    print(f"\n✓ Salvo: {arquivo_dia}")

    index = output_dir / "index.html"
    index.write_text(html, encoding="utf-8")
    print(f"✓ index.html atualizado")

    return arquivo_dia


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    hoje           = datetime.date.today()
    data_str       = hoje.strftime("%Y-%m-%d")
    data_formatada = hoje.strftime("%d de %B de %Y").replace(
        "January","janeiro").replace("February","fevereiro").replace(
        "March","março").replace("April","abril").replace(
        "May","maio").replace("June","junho").replace(
        "July","julho").replace("August","agosto").replace(
        "September","setembro").replace("October","outubro").replace(
        "November","novembro").replace("December","dezembro")

    print(f"=== Ordem & Liberdade — {data_formatada} ===\n")

    print("Buscando cotações...")
    ticker = buscar_ticker()

    print("\nBuscando notícias...")
    noticias = buscar_noticias()
    print(f"\nTotal: {len(noticias)} notícias coletadas")

    print("\nAnalisando com Claude...")
    analise = analisar_com_claude(noticias, data_formatada)
    print(f"✓ {len(analise.get('noticias', []))} notícias analisadas")

    html = gerar_html(analise, data_str, data_formatada, ticker)

    output_dir = Path(__file__).parent / "docs"
    salvar_arquivo(html, data_str, output_dir)

    print("\n✅ Digest gerado com sucesso!")


if __name__ == "__main__":
    main()
