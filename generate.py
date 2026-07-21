#!/usr/bin/env python3
"""
Ordem & Liberdade — Gerador de Resumo Diário de Notícias
Layout: jornal digital no estilo BSafe Bitcoin
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
    {"nome": "G1",            "pais": "🇧🇷", "url": "https://g1.globo.com/rss/g1/"},
    {"nome": "Folha",         "pais": "🇧🇷", "url": "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml"},
    {"nome": "UOL Notícias",  "pais": "🇧🇷", "url": "https://rss.uol.com.br/feed/noticias.xml"},
    {"nome": "Gazeta do Povo","pais": "🇧🇷", "url": "https://www.gazetadopovo.com.br/feed/"},
    {"nome": "Mises Brasil",  "pais": "🇧🇷", "url": "https://www.mises.org.br/feed"},
    # ── Internacional ────────────────────────────
    {"nome": "BBC",           "pais": "🌐", "url": "https://feeds.bbci.co.uk/news/rss.xml"},
    {"nome": "The Spectator", "pais": "🌐", "url": "https://www.spectator.co.uk/rss"},
    {"nome": "Fox News",      "pais": "🌐", "url": "https://moxie.foxnews.com/google-publisher/latest.xml"},
    {"nome": "Wall Street Journal","pais": "🌐","url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml"},
    {"nome": "The Times UK",  "pais": "🌐", "url": "https://www.thetimes.co.uk/rss/news"},
]

MAX_NOTICIAS_POR_FONTE = 1
MAX_NOTICIAS_TOTAL     = 8

# ─────────────────────────────────────────────
# PROMPTS
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """Você é um analista político, econômico e cultural que interpreta os acontecimentos
do dia sob uma perspectiva conservadora-libertária — fusão entre o liberalismo econômico clássico
e o conservadorismo de costumes. Fundamentado em: Burke, Kirk, Scruton, Chesterton, Mises, Hayek,
Bastiat, Friedman, Sowell, Rothbard, Roberto Campos.

Diretrizes por tema:
- Econômico: aplique Mises, Hayek, Bastiat, Friedman, Sowell ou Roberto Campos
- Cultural, família, religião, tradição: aplique Burke, Kirk, Scruton ou Chesterton
- Raça, desigualdade, cotas: aplique Sowell
- Mídia e narrativa: ceticismo estrutural (quem financia? quem se beneficia?)

Sowell: julgue políticas pelos resultados, não pelas intenções. Pergunte sempre "e depois?" e "comparado a quê?".
Chesterton: não derrube uma cerca sem entender por que foi erguida.

Ao analisar: cite o pensador mais pertinente, use linguagem clara e culta, seja incisivo mas justo."""

USER_PROMPT_TEMPLATE = """Abaixo estão as principais notícias de hoje ({data}).

Para CADA notícia, forneça análise em PORTUGUÊS (mesmo para fontes internacionais, traduza e analise em PT).

Diretrizes (CONCISO — cada campo máx. 2 frases):
1. titulo: manchete em português, direta e informativa
2. resumo: o que aconteceu, sem interpretação (máx. 2 frases)
3. analise: perspectiva conservadora-libertária, cite um pensador se natural (máx. 2-3 frases)
4. atencao: o que o cidadão vigilante deve monitorar (1 frase, começa com verbo)

Responda em JSON com EXATAMENTE este formato:
{{
  "noticias": [
    {{
      "fonte": "nome da fonte",
      "pais": "🇧🇷 ou 🌐",
      "url": "URL do artigo ou string vazia",
      "pensador": "pensador mais pertinente ou null",
      "tags": ["tag1", "tag2"],
      "titulo": "manchete em português",
      "resumo": "resumo factual em 2 frases",
      "analise": "análise conservadora-libertária em 2-3 frases citando o pensador",
      "atencao": "ponto de atenção em 1 frase"
    }}
  ],
  "editorial": "parágrafo editorial em português (3-4 frases, tom ensaístico, perspectiva conservadora-libertária sobre o conjunto das notícias do dia)"
}}

NOTÍCIAS DE HOJE:
{noticias}"""


# ─────────────────────────────────────────────
# FUNÇÕES DE COLETA
# ─────────────────────────────────────────────

def buscar_ticker() -> dict:
    """Busca preço do Bitcoin, câmbio USD/BRL e outros indicadores."""
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
                resumo = re.sub(r"<[^>]+>", "", resumo).strip()[:500]
                noticias.append({
                    "titulo": entry.get("title", "Sem título"),
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

    bloco = ""
    for i, n in enumerate(noticias, 1):
        bloco += f"\n---\n{i}. [{n['pais']} {n['fonte']}] {n['titulo']}\n{n['resumo_original']}\n"

    prompt = USER_PROMPT_TEMPLATE.format(data=data_str, noticias=bloco)

    print("\nEnviando para o Claude...")
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    resposta = message.content[0].text

    import re
    for attempt in [resposta, re.sub(r"```(?:json)?\s*", "", resposta).strip()]:
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            pass

    start = resposta.find("{")
    if start != -1:
        depth = 0
        for i, c in enumerate(resposta[start:], start):
            depth += (c == "{") - (c == "}")
            if depth == 0:
                try:
                    return json.loads(resposta[start:i+1])
                except json.JSONDecodeError:
                    break

    raise ValueError(f"Resposta do Claude não continha JSON válido:\n{resposta[:500]}")


# ─────────────────────────────────────────────
# FUNÇÕES DE HTML
# ─────────────────────────────────────────────

def _fmt_btc(valor) -> str:
    return f"R$ {valor:,.0f}".replace(",", ".")


def _ticker_html(ticker: dict) -> str:
    """Ticker bar com BTC e indicadores."""
    if not ticker.get("btc_brl"):
        return '<div class="ticker"><div class="ticker-item"><span class="label">BSafe Bitcoin</span> <a href="https://bsafebitcoin.org" target="_blank" style="color:#e5a810">bsafebitcoin.org ↗</a></div></div>'

    btc_brl = _fmt_btc(ticker["btc_brl"])
    btc_usd = f"$ {ticker['btc_usd']:,.0f}".replace(",", ".")
    usd_brl = f"{ticker['usd_brl']:.2f}".replace(".", ",") if ticker.get("usd_brl") else "—"

    return f"""<div class="ticker">
  <div class="ticker-item"><span class="label">BTC/BRL</span> {btc_brl} <span class="tick-sep">·</span> <span class="muted">{btc_usd}</span></div>
  <div class="ticker-item"><span class="label">USD/BRL</span> {usd_brl}</div>
  <div class="ticker-item"><span class="label">BSafe Bitcoin</span> <a href="https://bsafebitcoin.org" target="_blank">bsafebitcoin.org ↗</a></div>
</div>"""


def _sidebar_item(noticia: dict) -> str:
    """Item compacto para o sidebar do hero."""
    tags_str = " · ".join(noticia.get("tags", [])[:2])
    tag_label = f"{noticia.get('fonte', '')} · {tags_str}" if tags_str else noticia.get("fonte", "")
    url = noticia.get("url", "") or "#"
    return f"""  <a class="sidebar-article" href="{url}" target="_blank" rel="noopener">
    <div class="s-tag">{tag_label.upper()}</div>
    <h4>{noticia.get('titulo', '')}</h4>
    <div class="s-meta">{noticia.get('pais', '')} {noticia.get('fonte', '')}</div>
  </a>"""


def _article_card(noticia: dict) -> str:
    """Card compacto para o grid de 3 colunas."""
    tags_html = "".join(f'<span class="a-tag-chip">{t}</span>' for t in noticia.get("tags", [])[:2])
    pensador = noticia.get("pensador")
    pensador_html = f'<div class="a-pensador">✍️ {pensador}</div>' if pensador else ""
    url = noticia.get("url", "") or "#"
    analise = noticia.get("analise", "")
    atencao = noticia.get("atencao", "")
    analise_html = f"""  <div class="a-analise">
    <div class="a-analise-label">⚖️ ANÁLISE — ORDEM &amp; LIBERDADE</div>
    <p>{analise}</p>
  </div>""" if analise else ""
    atencao_html = f'  <div class="a-atencao">👁 {atencao}</div>' if atencao else ""

    return f"""<a class="article-card" href="{url}" target="_blank" rel="noopener">
  <div class="a-fonte">{noticia.get('pais','')}&nbsp;{noticia.get('fonte','').upper()}</div>
  {tags_html}
  <h3>{noticia.get('titulo', '')}</h3>
  <p class="a-resumo">{noticia.get('resumo', '')}</p>
{analise_html}
{atencao_html}
{pensador_html}
</a>"""


def gerar_html(analise: dict, data_str: str, data_formatada: str, ticker: dict | None = None) -> str:
    """Gera o HTML no novo layout de jornal digital."""

    noticias    = analise.get("noticias", [])
    editorial   = analise.get("editorial", "")
    ticker      = ticker or {}

    noticias_br   = [n for n in noticias if n.get("pais") == "🇧🇷"]
    noticias_intl = [n for n in noticias if n.get("pais") == "🌐"]

    # Sidebar: até 4 primeiras notícias
    sidebar_items = "".join(_sidebar_item(n) for n in noticias[:4])

    # Grids
    grid_br   = "".join(_article_card(n) for n in noticias_br)
    grid_intl = "".join(_article_card(n) for n in noticias_intl)

    # Ticker
    ticker_html = _ticker_html(ticker)

    # BTC price badge no navbar
    nav_btc = ""
    if ticker.get("btc_brl"):
        nav_btc = f'<span class="nav-btc">₿ {_fmt_btc(ticker["btc_brl"])}</span>'

    # Seções condicionais
    secao_br = f"""<div class="section-header">
  <div class="accent-line"></div>
  <h2>🇧🇷 Brasil</h2>
  <div class="sh-line"></div>
</div>
<div class="articles-grid">
{grid_br}
</div>""" if noticias_br else ""

    secao_intl = f"""<div class="section-header">
  <div class="accent-line"></div>
  <h2>🌐 Internacional</h2>
  <div class="sh-line"></div>
</div>
<div class="articles-grid">
{grid_intl}
</div>""" if noticias_intl else ""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ordem &amp; Liberdade — {data_formatada}</title>
  <meta name="description" content="Digest diário de notícias interpretadas sob a ótica conservadora-libertária. Fundamentado em Mises, Hayek, Burke e Sowell.">
  <meta property="og:title" content="Ordem &amp; Liberdade — {data_formatada}">
  <meta property="og:description" content="Digest conservador-libertário do dia.">
  <style>
    :root {{
      --ouro:      #e5a810;
      --ouro-esc:  #b8860b;
      --ouro-clr:  #f0c040;
      --bg:        #0f0f0f;
      --surface:   #141414;
      --surface-1: #1a1a1a;
      --surface-2: #222;
      --texto:     #e0e0e0;
      --texto-sec: #aaa;
      --texto-fra: #666;
      --borda:     #222;
      --borda-f:   #333;
      --verde:     #4caf82;
      --fonte-ser: 'Georgia', 'Times New Roman', serif;
      --fonte-san: Arial, 'Helvetica Neue', sans-serif;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: var(--fonte-san);
      background: var(--bg);
      color: var(--texto);
      line-height: 1.6;
    }}
    a {{ color: inherit; text-decoration: none; }}

    /* ── NAV ── */
    .nav {{
      background: var(--bg);
      padding: 0 2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 56px;
      border-bottom: 2px solid var(--ouro);
      position: sticky;
      top: 0;
      z-index: 100;
    }}
    .nav-logo {{
      display: flex;
      flex-direction: column;
      line-height: 1.1;
      gap: 2px;
    }}
    .nav-logo .title {{
      font-family: var(--fonte-ser);
      font-size: 19px;
      font-weight: 700;
      color: #fff;
      letter-spacing: -0.3px;
    }}
    .nav-logo .title span {{ color: var(--ouro); }}
    .nav-logo .subtitle {{
      font-size: 9px;
      color: var(--ouro);
      letter-spacing: 2px;
      text-transform: uppercase;
    }}
    .nav-links {{
      display: flex;
      gap: 24px;
      list-style: none;
    }}
    .nav-links a {{
      color: var(--texto-sec);
      font-size: 13px;
      letter-spacing: 0.3px;
      transition: color 0.2s;
    }}
    .nav-links a:hover, .nav-links a.active {{ color: var(--ouro); }}
    .nav-right {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .nav-btc {{
      font-size: 12px;
      color: var(--ouro);
      font-weight: 600;
      border: 1px solid var(--ouro-esc);
      padding: 4px 10px;
      border-radius: 4px;
      font-family: var(--fonte-san);
      letter-spacing: 0.3px;
    }}
    .nav-date {{
      font-size: 11px;
      color: var(--texto-fra);
      letter-spacing: 0.5px;
    }}

    /* ── TICKER ── */
    .ticker {{
      background: var(--surface-1);
      padding: 7px 2rem;
      display: flex;
      gap: 0;
      overflow-x: auto;
      scrollbar-width: none;
      border-bottom: 0.5px solid var(--borda-f);
    }}
    .ticker::-webkit-scrollbar {{ display: none; }}
    .ticker-item {{
      font-size: 12px;
      color: var(--texto-sec);
      white-space: nowrap;
      display: flex;
      gap: 6px;
      align-items: center;
      padding: 0 18px;
      border-right: 0.5px solid var(--borda-f);
    }}
    .ticker-item:first-child {{ padding-left: 0; }}
    .ticker-item:last-child {{ border-right: none; }}
    .ticker-item .label {{ color: var(--ouro); font-weight: 600; font-size: 11px; letter-spacing: 0.5px; }}
    .ticker-item .muted {{ color: var(--texto-fra); }}
    .ticker-item .tick-sep {{ color: var(--borda-f); }}
    .ticker-item a {{ color: var(--ouro); opacity: 0.75; transition: opacity 0.2s; }}
    .ticker-item a:hover {{ opacity: 1; }}

    /* ── HERO ── */
    .hero {{
      display: grid;
      grid-template-columns: 1fr 320px;
      border-bottom: 0.5px solid var(--borda-f);
      min-height: 380px;
    }}
    .hero-main {{
      position: relative;
      background: var(--surface-1);
      overflow: hidden;
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
      padding: 2.5rem 2.5rem 2rem;
    }}
    .hero-chart {{
      position: absolute;
      inset: 0;
      z-index: 0;
    }}
    .hero-overlay {{
      position: absolute;
      inset: 0;
      z-index: 1;
      background: linear-gradient(to top, rgba(10,8,0,0.95) 40%, rgba(10,8,0,0.6) 75%, rgba(10,8,0,0.3) 100%);
    }}
    .hero-content {{
      position: relative;
      z-index: 2;
    }}
    .hero-tag {{
      display: inline-block;
      background: var(--ouro);
      color: #0f0f0f;
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 2.5px;
      text-transform: uppercase;
      padding: 3px 9px;
      border-radius: 2px;
      margin-bottom: 14px;
    }}
    .hero-title {{
      font-family: var(--fonte-ser);
      font-size: 26px;
      font-weight: 700;
      color: #fff;
      line-height: 1.35;
      margin-bottom: 14px;
      max-width: 680px;
    }}
    .hero-editorial {{
      font-family: var(--fonte-ser);
      font-style: italic;
      font-size: 0.95rem;
      color: #c8bc96;
      line-height: 1.75;
      max-width: 640px;
      text-align: justify;
    }}
    .hero-meta {{
      margin-top: 1.2rem;
      font-size: 11px;
      color: rgba(255,255,255,0.45);
      letter-spacing: 0.5px;
    }}

    .hero-sidebar {{
      border-left: 0.5px solid var(--borda-f);
      display: flex;
      flex-direction: column;
      background: var(--surface);
    }}
    .sidebar-title {{
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 2.5px;
      text-transform: uppercase;
      color: var(--texto-fra);
      padding: 14px 16px 10px;
      border-bottom: 0.5px solid var(--borda-f);
    }}
    .sidebar-article {{
      display: block;
      padding: 14px 16px;
      border-bottom: 0.5px solid var(--borda);
      cursor: pointer;
      transition: background 0.2s;
    }}
    .sidebar-article:hover {{ background: var(--surface-1); }}
    .sidebar-article .s-tag {{
      font-size: 9px;
      color: var(--ouro);
      letter-spacing: 1.5px;
      text-transform: uppercase;
      margin-bottom: 5px;
      font-weight: 600;
    }}
    .sidebar-article h4 {{
      font-family: var(--fonte-ser);
      font-size: 13.5px;
      font-weight: 600;
      color: var(--texto);
      line-height: 1.4;
      margin-bottom: 4px;
    }}
    .sidebar-article .s-meta {{
      font-size: 10px;
      color: var(--texto-fra);
    }}

    /* ── SECTION HEADER ── */
    .section-header {{
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 1.4rem 2rem 1rem;
      border-bottom: 0.5px solid var(--borda-f);
    }}
    .section-header .accent-line {{
      width: 36px;
      height: 2px;
      background: var(--ouro);
      border-radius: 1px;
      flex-shrink: 0;
    }}
    .section-header h2 {{
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 2.5px;
      text-transform: uppercase;
      color: var(--texto);
      white-space: nowrap;
    }}
    .section-header .sh-line {{
      flex: 1;
      height: 0.5px;
      background: var(--borda-f);
    }}

    /* ── ARTICLES GRID ── */
    .articles-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      border-bottom: 0.5px solid var(--borda-f);
    }}
    .article-card {{
      display: block;
      padding: 1.5rem;
      border-right: 0.5px solid var(--borda-f);
      cursor: pointer;
      transition: background 0.2s;
      text-decoration: none;
    }}
    .article-card:last-child {{ border-right: none; }}
    .article-card:hover {{ background: var(--surface-1); }}
    .a-fonte {{
      font-size: 9px;
      color: var(--ouro);
      letter-spacing: 1.5px;
      text-transform: uppercase;
      font-weight: 700;
      margin-bottom: 6px;
    }}
    .a-tag-chip {{
      display: inline-block;
      font-size: 9px;
      padding: 2px 6px;
      background: var(--surface-2);
      border: 0.5px solid var(--borda-f);
      border-radius: 3px;
      color: var(--texto-fra);
      margin: 0 3px 6px 0;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .article-card h3 {{
      font-family: var(--fonte-ser);
      font-size: 16px;
      font-weight: 700;
      color: var(--texto);
      line-height: 1.4;
      margin-bottom: 10px;
    }}
    .a-resumo {{
      font-size: 13px;
      color: var(--texto-sec);
      line-height: 1.65;
      margin-bottom: 12px;
    }}
    .a-analise {{
      background: #0d0900;
      border: 0.5px solid var(--borda-f);
      border-top: 1.5px solid var(--ouro-esc);
      border-radius: 4px;
      padding: 10px 12px;
      margin-bottom: 10px;
    }}
    .a-analise-label {{
      font-size: 8.5px;
      color: var(--ouro);
      letter-spacing: 1.5px;
      text-transform: uppercase;
      font-weight: 700;
      margin-bottom: 5px;
    }}
    .a-analise p {{
      font-size: 12.5px;
      color: #c8bc96;
      line-height: 1.6;
      font-family: var(--fonte-ser);
    }}
    .a-atencao {{
      font-size: 12px;
      color: var(--ouro);
      font-weight: 500;
      line-height: 1.5;
      margin-bottom: 8px;
    }}
    .a-pensador {{
      display: inline-block;
      font-size: 10px;
      padding: 2px 8px;
      background: #1a1400;
      border: 0.5px solid var(--ouro-esc);
      border-radius: 3px;
      color: var(--ouro-clr);
      font-style: italic;
      font-family: var(--fonte-ser);
    }}

    /* ── BSAFE BANNER ── */
    .btc-banner {{
      background: var(--surface);
      border-top: 0.5px solid var(--borda-f);
      border-bottom: 0.5px solid var(--borda-f);
      padding: 1.1rem 2rem;
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .btc-banner .btc-icon {{
      font-size: 26px;
      color: var(--ouro);
      flex-shrink: 0;
    }}
    .btc-banner .btc-text {{ flex: 1; }}
    .btc-banner .btc-text h4 {{
      font-size: 14px;
      font-weight: 600;
      color: #fff;
      margin-bottom: 3px;
    }}
    .btc-banner .btc-text p {{
      font-size: 12px;
      color: var(--texto-fra);
    }}
    .btc-banner .btc-cta {{
      font-size: 12px;
      color: var(--ouro);
      border: 1px solid var(--ouro-esc);
      padding: 7px 16px;
      border-radius: 4px;
      cursor: pointer;
      white-space: nowrap;
      transition: background 0.2s, color 0.2s;
      font-weight: 500;
    }}
    .btc-banner .btc-cta:hover {{ background: var(--ouro); color: #0f0f0f; }}

    /* ── FOOTER ── */
    .footer {{
      background: var(--bg);
      padding: 2rem;
      display: grid;
      grid-template-columns: 1.4fr 1fr 1fr;
      gap: 2.5rem;
      border-top: 2px solid var(--ouro);
    }}
    .footer-col h5 {{
      font-size: 9px;
      letter-spacing: 2.5px;
      text-transform: uppercase;
      color: var(--ouro);
      margin-bottom: 14px;
      font-weight: 700;
    }}
    .footer-logo {{
      font-family: var(--fonte-ser);
      font-size: 20px;
      font-weight: 700;
      color: #fff;
      margin-bottom: 8px;
    }}
    .footer-logo span {{ color: var(--ouro); }}
    .footer-col p, .footer-col a {{
      font-size: 12px;
      color: var(--texto-fra);
      line-height: 1.85;
      display: block;
    }}
    .footer-col a:hover {{ color: var(--texto-sec); }}
    .footer-bottom {{
      background: var(--bg);
      padding: 12px 2rem;
      border-top: 0.5px solid var(--borda);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .footer-bottom span {{
      font-size: 10.5px;
      color: #3a3a3a;
      letter-spacing: 0.3px;
    }}

    /* ── RESPONSIVE ── */
    @media (max-width: 900px) {{
      .hero {{ grid-template-columns: 1fr; }}
      .hero-sidebar {{ display: none; }}
      .articles-grid {{ grid-template-columns: 1fr; }}
      .article-card {{ border-right: none; border-bottom: 0.5px solid var(--borda-f); }}
      .nav-links {{ display: none; }}
      .footer {{ grid-template-columns: 1fr; gap: 1.5rem; }}
    }}
  </style>
</head>
<body>

<!-- NAV -->
<nav class="nav">
  <div class="nav-logo">
    <span class="title">Ordem <span>&amp;</span> Liberdade</span>
    <span class="subtitle">BSafe Bitcoin · Est. 2026</span>
  </div>
  <ul class="nav-links">
    <li><a href="index.html" class="active">Digest do Dia</a></li>
    <li><a href="analisar.html">Analisar Notícia</a></li>
    <li><a href="https://bsafebitcoin.org" target="_blank">BSafe Bitcoin ↗</a></li>
  </ul>
  <div class="nav-right">
    {nav_btc}
    <span class="nav-date">{data_formatada}</span>
  </div>
</nav>

<!-- TICKER -->
{ticker_html}

<!-- HERO -->
<div class="hero">
  <div class="hero-main">
    <svg class="hero-chart" viewBox="0 0 700 380" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <rect width="700" height="380" fill="#0d0900"/>
      <polyline points="0,320 70,300 140,310 210,260 280,210 350,230 420,170 490,110 560,85 630,60 700,35"
        fill="none" stroke="#e5a810" stroke-width="1.5" opacity="0.5"/>
      <polygon points="0,320 70,300 140,310 210,260 280,210 350,230 420,170 490,110 560,85 630,60 700,35 700,380 0,380"
        fill="#e5a810" opacity="0.04"/>
    </svg>
    <div class="hero-overlay"></div>
    <div class="hero-content">
      <span class="hero-tag">Editorial do Dia</span>
      <h2 class="hero-title">Ordem &amp; Liberdade — {data_formatada}</h2>
      <p class="hero-editorial">{editorial}</p>
      <p class="hero-meta">Burke · Mises · Hayek · Sowell · Roberto Campos</p>
    </div>
  </div>

  <div class="hero-sidebar">
    <div class="sidebar-title">Destaques de Hoje</div>
{sidebar_items}
  </div>
</div>

<!-- SEÇÃO BRASIL -->
{secao_br}

<!-- BANNER BSAFE -->
<div class="btc-banner">
  <span class="btc-icon">₿</span>
  <div class="btc-text">
    <h4>BSafe Bitcoin — Sua segurança, sua soberania</h4>
    <p>Aprenda a guardar Bitcoin com segurança. Custódia própria, sem depender de terceiros.</p>
  </div>
  <a href="https://bsafebitcoin.org" target="_blank" class="btc-cta">Conhecer →</a>
</div>

<!-- SEÇÃO INTERNACIONAL -->
{secao_intl}

<!-- FOOTER -->
<footer class="footer">
  <div class="footer-col">
    <div class="footer-logo">Ordem <span>&amp;</span> Liberdade</div>
    <p>Jornalismo independente sobre Bitcoin, economia e liberdade individual. Sem anunciantes, sem agenda oculta.</p>
  </div>
  <div class="footer-col">
    <h5>Editorias</h5>
    <a href="#">Brasil</a>
    <a href="#">Internacional</a>
    <a href="analisar.html">Analisar Notícia</a>
    <a href="https://mises.org.br" target="_blank">Mises Brasil ↗</a>
    <a href="https://www.gazetadopovo.com.br" target="_blank">Gazeta do Povo ↗</a>
  </div>
  <div class="footer-col">
    <h5>BSafe Bitcoin</h5>
    <a href="https://bsafebitcoin.org" target="_blank">bsafebitcoin.org</a>
    <a href="mailto:bsafe@bsafebitcoin.org">bsafe@bsafebitcoin.org</a>
    <a href="https://bsafebitcoin.org" target="_blank">Apoie com Bitcoin</a>
  </div>
</footer>
<div class="footer-bottom">
  <span>© 2026 Ordem &amp; Liberdade · BSafe Bitcoin</span>
  <span>Atualizado em {data_formatada}</span>
</div>

</body>
</html>"""


# ─────────────────────────────────────────────
# SALVAR
# ─────────────────────────────────────────────

def salvar_arquivo(html: str, data_str: str, output_dir: Path):
    """Salva o HTML e atualiza o index.html."""
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
