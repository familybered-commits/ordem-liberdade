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
import html as htmllib
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIGURAÇÃO DE FONTES RSS
# 3 nacionais + 3 internacionais → 1 manchete por fonte
# ─────────────────────────────────────────────
RSS_FEEDS = [
    # ── Brasil ──────────────────────────────────
    {"nome": "G1 / Globo",      "pais": "🇧🇷", "url": "https://g1.globo.com/rss/g1/"},
    {"nome": "Folha",           "pais": "🇧🇷", "url": "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml"},
    {"nome": "Gazeta do Povo",  "pais": "🇧🇷", "url": "https://www.gazetadopovo.com.br/feed/"},
    # ── Internacional ────────────────────────────
    {"nome": "New York Times", "pais": "🌐", "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"},
    {"nome": "The Guardian",   "pais": "🌐", "url": "https://www.theguardian.com/world/rss"},
    {"nome": "BBC News",       "pais": "🌐", "url": "https://feeds.bbci.co.uk/news/rss.xml"},
]

MAX_NOTICIAS_POR_FONTE = 1
MAX_NOTICIAS_TOTAL     = 6

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

USER_PROMPT_TEMPLATE = """Abaixo estão as principais manchetes de hoje ({data}).

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
  "editorial": "parágrafo editorial em português (3-4 frases, tom ensaístico, perspectiva conservadora-libertária sobre o conjunto das manchetes do dia)"
}}

MANCHETES DE HOJE:
{noticias}"""


# ─────────────────────────────────────────────
# FUNÇÕES DE COLETA
# ─────────────────────────────────────────────

def buscar_ticker() -> dict:
    """Busca preço do Bitcoin em USD."""
    import urllib.request
    ticker = {"btc_usd": None}
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        req = urllib.request.Request(url, headers={"User-Agent": "OrdemLiberdade/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
            ticker["btc_usd"] = data["bitcoin"]["usd"]
        print(f" ✓ Ticker: BTC $ {ticker['btc_usd']:,.0f}")
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
            print(f" ✓ {feed_info['pais']} {feed_info['nome']}: {len(entradas)} manchete(s)")
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

def _fmt_btc_usd(valor) -> str:
    return f"$ {valor:,.0f}"


def _ticker_html(ticker: dict) -> str:
    """Ticker bar com BTC/USD."""
    if not ticker.get("btc_usd"):
        return '<div class="ticker"><div class="ticker-item"><span class="label">BSafe Bitcoin</span> <a href="https://bsafebitcoin.org" target="_blank" style="color:#e5a810">bsafebitcoin.org ↗</a></div></div>'

    btc_usd = _fmt_btc_usd(ticker["btc_usd"])

    return f"""<div class="ticker">
  <div class="ticker-item"><span class="label">BTC/USD</span> {btc_usd}</div>
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
    """Card para o grid de 3 colunas com compartilhamento individual."""
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

    # Escape seguro para data attributes
    titulo_esc  = htmllib.escape(noticia.get("titulo", ""), quote=True)
    resumo_esc  = htmllib.escape(noticia.get("resumo", ""), quote=True)
    analise_esc = htmllib.escape(analise, quote=True)
    url_esc     = htmllib.escape(url, quote=True)

    return f"""<div class="article-card">
  <a href="{url_esc}" target="_blank" rel="noopener" style="text-decoration:none;color:inherit;display:block;">
  <div class="a-fonte">{noticia.get('pais','')}&nbsp;{noticia.get('fonte','').upper()}</div>
  {tags_html}
  <h3>{noticia.get('titulo', '')}</h3>
  <p class="a-resumo">{noticia.get('resumo', '')}</p>
{analise_html}
{atencao_html}
{pensador_html}
  </a>
  <button class="share-btn"
    data-titulo="{titulo_esc}"
    data-resumo="{resumo_esc}"
    data-analise="{analise_esc}"
    data-url="{url_esc}"
    onclick="compartilharArtigo(event, this)">↗ Compartilhar</button>
</div>"""


def dia_util_anterior(data: datetime.date) -> datetime.date:
    """Retorna o dia útil anterior (pula fins de semana)."""
    d = data - datetime.timedelta(days=1)
    while d.weekday() >= 5:  # 5=Sáb, 6=Dom
        d -= datetime.timedelta(days=1)
    return d


def formatar_data_pt(data: datetime.date) -> str:
    return data.strftime("%d de %B de %Y").replace(
        "January","janeiro").replace("February","fevereiro").replace(
        "March","março").replace("April","abril").replace(
        "May","maio").replace("June","junho").replace(
        "July","julho").replace("August","agosto").replace(
        "September","setembro").replace("October","outubro").replace(
        "November","novembro").replace("December","dezembro")


def gerar_html(analise: dict, data_str: str, data_formatada: str,
               ticker: dict | None = None,
               data_anterior: str | None = None,
               data_proxima: str | None = None) -> str:
    """Gera o HTML no layout de jornal digital."""

    noticias    = analise.get("noticias", [])
    editorial   = analise.get("editorial", "")
    ticker      = ticker or {}

    # ── Navegação entre dias ──
    nav_anterior = ""
    nav_proxima  = ""
    if data_anterior:
        nav_anterior = f'<a class="pag-nav-link prev" href="{data_anterior}.html">← Dia anterior</a>'
    if data_proxima:
        nav_proxima = f'<a class="pag-nav-link next" href="{data_proxima}.html">Próximo →</a>'
    pag_nav_html = f"""<div class="pag-nav">
  <div class="pag-nav-inner">
    {nav_anterior}
    <a class="pag-nav-link arquivo" href="arquivo.html">📅 Arquivo</a>
    {nav_proxima}
  </div>
</div>""" if (data_anterior or data_proxima) else \
    '<div class="pag-nav"><div class="pag-nav-inner"><a class="pag-nav-link arquivo" href="arquivo.html">📅 Arquivo de Edições</a></div></div>'

    noticias_br   = [n for n in noticias if n.get("pais") == "🇧🇷"]
    noticias_intl = [n for n in noticias if n.get("pais") == "🌐"]

    # Sidebar: até 6 manchetes
    sidebar_items = "".join(_sidebar_item(n) for n in noticias[:6])

    # Grids
    grid_br   = "".join(_article_card(n) for n in noticias_br)
    grid_intl = "".join(_article_card(n) for n in noticias_intl)

    # Ticker e nav badge
    ticker_html = _ticker_html(ticker)
    nav_btc = ""
    if ticker.get("btc_usd"):
        nav_btc = f'<span class="nav-btc">₿ {_fmt_btc_usd(ticker["btc_usd"])}</span>'

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

    /* ── NAV (mais alto e com fontes maiores) ── */
    .nav {{
      background: var(--bg);
      padding: 0 2.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 100px;
      border-bottom: 3px solid var(--ouro);
      position: sticky;
      top: 0;
      z-index: 100;
    }}
    .nav-logo {{
      display: flex;
      flex-direction: column;
      line-height: 1.15;
      gap: 5px;
    }}
    .nav-logo .title {{
      font-family: var(--fonte-ser);
      font-size: 34px;
      font-weight: 700;
      color: #fff;
      letter-spacing: -0.5px;
    }}
    .nav-logo .title span {{ color: var(--ouro); }}
    .nav-logo .subtitle {{
      font-size: 13px;
      color: var(--ouro);
      letter-spacing: 3px;
      text-transform: uppercase;
    }}
    .nav-links {{
      display: flex;
      gap: 36px;
      list-style: none;
    }}
    .nav-links a {{
      color: var(--texto-sec);
      font-size: 16px;
      letter-spacing: 0.3px;
      transition: color 0.2s;
    }}
    .nav-links a:hover, .nav-links a.active {{ color: var(--ouro); }}
    .nav-right {{
      display: flex;
      align-items: center;
      gap: 14px;
    }}
    .nav-btc {{
      font-size: 15px;
      color: var(--ouro);
      font-weight: 600;
      border: 1px solid var(--ouro-esc);
      padding: 7px 16px;
      border-radius: 4px;
      font-family: var(--fonte-san);
      letter-spacing: 0.3px;
    }}
    .nav-date {{
      font-size: 14px;
      color: var(--texto-fra);
      letter-spacing: 0.5px;
    }}
    .menu-toggle {{
      display: none;
      background: none;
      border: none;
      color: var(--texto-sec);
      font-size: 26px;
      cursor: pointer;
      padding: 4px 8px;
      line-height: 1;
    }}

    /* ── TICKER ── */
    .ticker {{
      background: var(--surface-1);
      padding: 8px 2.5rem;
      display: flex;
      gap: 0;
      overflow-x: auto;
      scrollbar-width: none;
      border-bottom: 0.5px solid var(--borda-f);
    }}
    .ticker::-webkit-scrollbar {{ display: none; }}
    .ticker-item {{
      font-size: 13px;
      color: var(--texto-sec);
      white-space: nowrap;
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 0 22px;
      border-right: 0.5px solid var(--borda-f);
    }}
    .ticker-item:first-child {{ padding-left: 0; }}
    .ticker-item:last-child {{ border-right: none; }}
    .ticker-item .label {{ color: var(--ouro); font-weight: 600; font-size: 12px; letter-spacing: 0.5px; }}
    .ticker-item a {{ color: var(--ouro); opacity: 0.75; transition: opacity 0.2s; }}
    .ticker-item a:hover {{ opacity: 1; }}

    /* ── HERO (sidebar mais larga) ── */
    .hero {{
      display: grid;
      grid-template-columns: 1fr 480px;
      border-bottom: 0.5px solid var(--borda-f);
      min-height: 500px;
    }}
    .hero-main {{
      position: relative;
      background: var(--surface-1);
      overflow: hidden;
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
      padding: 3rem 3rem 2.5rem;
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
      background: linear-gradient(to top, rgba(10,8,0,0.97) 40%, rgba(10,8,0,0.65) 75%, rgba(10,8,0,0.3) 100%);
    }}
    .hero-content {{
      position: relative;
      z-index: 2;
    }}
    .hero-tag {{
      display: inline-block;
      background: var(--ouro);
      color: #0f0f0f;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 2.5px;
      text-transform: uppercase;
      padding: 5px 13px;
      border-radius: 2px;
      margin-bottom: 18px;
    }}
    .hero-title {{
      font-family: var(--fonte-ser);
      font-size: 44px;
      font-weight: 700;
      color: #fff;
      line-height: 1.25;
      margin-bottom: 18px;
      max-width: 700px;
    }}
    .hero-editorial {{
      font-family: var(--fonte-ser);
      font-style: italic;
      font-size: 1.2rem;
      color: #c8bc96;
      line-height: 1.8;
      max-width: 660px;
      text-align: justify;
    }}
    .hero-meta {{
      margin-top: 1.4rem;
      font-size: 13px;
      color: rgba(255,255,255,0.45);
      letter-spacing: 0.5px;
    }}

    /* ── SIDEBAR (mais larga) ── */
    .hero-sidebar {{
      border-left: 0.5px solid var(--borda-f);
      display: flex;
      flex-direction: column;
      background: var(--surface);
    }}
    .sidebar-title {{
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 2.5px;
      text-transform: uppercase;
      color: var(--texto-fra);
      padding: 18px 22px 14px;
      border-bottom: 0.5px solid var(--borda-f);
    }}
    .sidebar-article {{
      display: block;
      padding: 18px 22px;
      border-bottom: 0.5px solid var(--borda);
      cursor: pointer;
      transition: background 0.2s;
    }}
    .sidebar-article:hover {{ background: var(--surface-1); }}
    .sidebar-article .s-tag {{
      font-size: 10px;
      color: var(--ouro);
      letter-spacing: 1.5px;
      text-transform: uppercase;
      margin-bottom: 7px;
      font-weight: 600;
    }}
    .sidebar-article h4 {{
      font-family: var(--fonte-ser);
      font-size: 16px;
      font-weight: 600;
      color: var(--texto);
      line-height: 1.4;
      margin-bottom: 6px;
    }}
    .sidebar-article .s-meta {{
      font-size: 12px;
      color: var(--texto-fra);
    }}

    /* ── SECTION HEADER ── */
    .section-header {{
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 1.4rem 2.5rem 1rem;
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
      font-size: 12px;
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

    /* ── ARTICLES GRID — 3 colunas fixas ── */
    .articles-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      border-bottom: 0.5px solid var(--borda-f);
    }}
    .article-card {{
      display: block;
      padding: 1.8rem;
      border-right: 0.5px solid var(--borda-f);
      transition: background 0.2s;
      position: relative;
    }}
    .article-card:nth-child(3n) {{ border-right: none; }}
    .article-card:hover {{ background: var(--surface-1); }}
    .a-fonte {{
      font-size: 10px;
      color: var(--ouro);
      letter-spacing: 1.5px;
      text-transform: uppercase;
      font-weight: 700;
      margin-bottom: 7px;
    }}
    .a-tag-chip {{
      display: inline-block;
      font-size: 10px;
      padding: 2px 7px;
      background: var(--surface-2);
      border: 0.5px solid var(--borda-f);
      border-radius: 3px;
      color: var(--texto-fra);
      margin: 0 3px 7px 0;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .article-card h3 {{
      font-family: var(--fonte-ser);
      font-size: 19px;
      font-weight: 700;
      color: var(--texto);
      line-height: 1.4;
      margin-bottom: 12px;
    }}
    .a-resumo {{
      font-size: 15px;
      color: var(--texto-sec);
      line-height: 1.7;
      margin-bottom: 14px;
    }}
    .a-analise {{
      background: #0d0900;
      border: 0.5px solid var(--borda-f);
      border-top: 1.5px solid var(--ouro-esc);
      border-radius: 4px;
      padding: 12px 14px;
      margin-bottom: 12px;
    }}
    .a-analise-label {{
      font-size: 10px;
      color: var(--ouro);
      letter-spacing: 1.5px;
      text-transform: uppercase;
      font-weight: 700;
      margin-bottom: 6px;
    }}
    .a-analise p {{
      font-size: 14px;
      color: #c8bc96;
      line-height: 1.65;
      font-family: var(--fonte-ser);
    }}
    .a-atencao {{
      font-size: 13.5px;
      color: var(--ouro);
      font-weight: 500;
      line-height: 1.5;
      margin-bottom: 10px;
    }}
    .a-pensador {{
      display: inline-block;
      font-size: 11px;
      padding: 3px 9px;
      background: #1a1400;
      border: 0.5px solid var(--ouro-esc);
      border-radius: 3px;
      color: var(--ouro-clr);
      font-style: italic;
      font-family: var(--fonte-ser);
    }}

    /* ── NAVEGAÇÃO ENTRE DIAS ── */
    .pag-nav {{
      background: var(--surface-1);
      border-top: 0.5px solid var(--borda-f);
      border-bottom: 0.5px solid var(--borda-f);
      padding: 14px 2.5rem;
    }}
    .pag-nav-inner {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 40px;
    }}
    .pag-nav-link {{
      font-size: 14px;
      color: var(--texto-sec);
      letter-spacing: 0.3px;
      padding: 8px 20px;
      border: 0.5px solid var(--borda-f);
      border-radius: 4px;
      transition: color 0.2s, border-color 0.2s, background 0.2s;
      background: transparent;
    }}
    .pag-nav-link:hover {{
      color: var(--ouro);
      border-color: var(--ouro-esc);
      background: #1a1400;
    }}
    .pag-nav-link.arquivo {{
      color: var(--ouro);
      border-color: var(--ouro-esc);
      font-weight: 600;
    }}
    .pag-nav-link.prev::before {{ content: ''; }}
    .pag-nav-link.next::after  {{ content: ''; }}

    /* ── SHARE BUTTON ── */
    .share-btn {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      margin-top: 14px;
      font-size: 12px;
      color: var(--texto-fra);
      background: var(--surface-2);
      border: 0.5px solid var(--borda-f);
      border-radius: 4px;
      padding: 7px 14px;
      cursor: pointer;
      transition: color 0.2s, border-color 0.2s, background 0.2s;
      font-family: var(--fonte-san);
      letter-spacing: 0.3px;
    }}
    .share-btn:hover {{
      color: var(--ouro);
      border-color: var(--ouro-esc);
      background: #1a1400;
    }}
    .share-btn.copiado {{
      color: var(--verde);
      border-color: var(--verde);
    }}

    /* ── BSAFE BANNER ── */
    .btc-banner {{
      background: var(--surface);
      border-top: 0.5px solid var(--borda-f);
      border-bottom: 0.5px solid var(--borda-f);
      padding: 1.2rem 2.5rem;
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .btc-banner .btc-icon {{
      font-size: 28px;
      color: var(--ouro);
      flex-shrink: 0;
    }}
    .btc-banner .btc-text {{ flex: 1; }}
    .btc-banner .btc-text h4 {{
      font-size: 15px;
      font-weight: 600;
      color: #fff;
      margin-bottom: 3px;
    }}
    .btc-banner .btc-text p {{
      font-size: 13px;
      color: var(--texto-fra);
    }}
    .btc-banner .btc-cta {{
      font-size: 13px;
      color: var(--ouro);
      border: 1px solid var(--ouro-esc);
      padding: 8px 18px;
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
      padding: 2.5rem;
      display: grid;
      grid-template-columns: 1.4fr 1fr 1fr;
      gap: 2.5rem;
      border-top: 2px solid var(--ouro);
    }}
    .footer-col h5 {{
      font-size: 10px;
      letter-spacing: 2.5px;
      text-transform: uppercase;
      color: var(--ouro);
      margin-bottom: 14px;
      font-weight: 700;
    }}
    .footer-logo {{
      font-family: var(--fonte-ser);
      font-size: 22px;
      font-weight: 700;
      color: #fff;
      margin-bottom: 8px;
    }}
    .footer-logo span {{ color: var(--ouro); }}
    .footer-col p, .footer-col a {{
      font-size: 13px;
      color: var(--texto-fra);
      line-height: 1.85;
      display: block;
    }}
    .footer-col a:hover {{ color: var(--texto-sec); }}
    .footer-bottom {{
      background: var(--bg);
      padding: 14px 2.5rem;
      border-top: 0.5px solid var(--borda);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .footer-bottom span {{
      font-size: 11px;
      color: #3a3a3a;
      letter-spacing: 0.3px;
    }}

    /* ── RESPONSIVE ── */
    @media (max-width: 1100px) {{
      .hero {{ grid-template-columns: 1fr 360px; }}
    }}
    @media (max-width: 900px) {{
      .hero {{ grid-template-columns: 1fr; min-height: auto; }}
      .hero-main {{ padding: 2rem 1.5rem 2rem; }}
      .hero-title {{ font-size: 30px; }}
      .hero-editorial {{ font-size: 1rem; }}
      .hero-sidebar {{ display: none; }}
      .articles-grid {{ grid-template-columns: 1fr; }}
      .article-card {{ border-right: none; border-bottom: 0.5px solid var(--borda-f); }}
      .nav-links {{ display: none; }}
      .nav-links.open {{
        display: flex;
        flex-direction: column;
        position: absolute;
        top: 100px;
        left: 0;
        right: 0;
        background: var(--surface);
        border-bottom: 2px solid var(--ouro);
        padding: 1rem 2rem;
        gap: 16px;
        z-index: 99;
      }}
      .nav-links.open a {{ font-size: 18px; padding: 4px 0; }}
      .menu-toggle {{ display: block; }}
      .footer {{ grid-template-columns: 1fr; gap: 1.5rem; }}
      .ticker {{ padding: 6px 1rem; }}
      .section-header {{ padding: 1rem 1rem 0.8rem; }}
      .btc-banner {{ flex-wrap: wrap; padding: 1rem; gap: 12px; }}
    }}
    @media (max-width: 600px) {{
      .nav {{ padding: 0 1rem; height: 76px; }}
      .nav-logo .title {{ font-size: 26px; }}
      .nav-logo .subtitle {{ font-size: 11px; }}
      .nav-btc {{ display: none; }}
      .nav-date {{ display: none; }}
      .hero-main {{ padding: 1.5rem 1rem 1.5rem; }}
      .hero-title {{ font-size: 26px; }}
      .hero-editorial {{ font-size: 0.95rem; }}
      .article-card {{ padding: 1.2rem 1rem; }}
      .article-card h3 {{ font-size: 17px; }}
      .a-resumo {{ font-size: 14px; }}
      .footer {{ padding: 1.5rem 1rem; }}
      .footer-bottom {{ padding: 10px 1rem; flex-direction: column; gap: 4px; text-align: center; }}
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
  <ul class="nav-links" id="nav-links">
    <li><a href="index.html" class="active">Digest do Dia</a></li>
    <li><a href="arquivo.html">Arquivo</a></li>
    <li><a href="analisar.html">Analisar Notícia</a></li>
    <li><a href="https://bsafebitcoin.org" target="_blank">BSafe Bitcoin ↗</a></li>
  </ul>
  <div class="nav-right">
    {nav_btc}
    <span class="nav-date">{data_formatada}</span>
    <button class="menu-toggle" id="menu-toggle" aria-label="Menu">☰</button>
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

<!-- NAVEGAÇÃO ENTRE DIAS -->
{pag_nav_html}

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

<script>
  // Menu hamburger
  const toggle = document.getElementById('menu-toggle');
  const navLinks = document.getElementById('nav-links');
  if (toggle && navLinks) {{
    toggle.addEventListener('click', () => {{
      navLinks.classList.toggle('open');
      toggle.textContent = navLinks.classList.contains('open') ? '✕' : '☰';
    }});
    document.addEventListener('click', (e) => {{
      if (!toggle.contains(e.target) && !navLinks.contains(e.target)) {{
        navLinks.classList.remove('open');
        toggle.textContent = '☰';
      }}
    }});
  }}

  // Compartilhamento individual: título + resumo + análise
  function compartilharArtigo(e, btn) {{
    e.preventDefault();
    e.stopPropagation();

    const titulo  = btn.dataset.titulo;
    const resumo  = btn.dataset.resumo;
    const analise = btn.dataset.analise;
    const url     = btn.dataset.url;

    const texto = titulo
      + '\\n\\n' + resumo
      + '\\n\\n⚖️ Ordem & Liberdade: ' + analise
      + (url ? '\\n\\n🔗 ' + url : '');

    function feedback(ok) {{
      btn.classList.add(ok ? 'copiado' : '');
      const orig = btn.textContent;
      btn.textContent = ok ? '✓ Copiado!' : '✗ Erro';
      setTimeout(() => {{
        btn.textContent = orig;
        btn.classList.remove('copiado');
      }}, 2200);
    }}

    if (navigator.share) {{
      navigator.share({{ title: titulo, text: texto, url: url || undefined }})
        .catch(() => {{}}); // user dismissed — silencioso
    }} else {{
      navigator.clipboard.writeText(texto)
        .then(() => feedback(true))
        .catch(() => feedback(false));
    }}
  }}
</script>

</body>
</html>"""


# ─────────────────────────────────────────────
# SALVAR
# ─────────────────────────────────────────────

def gerar_arquivo_html(output_dir: Path) -> None:
    """Gera/atualiza arquivo.html com a lista de todos os digests publicados."""
    import re
    pattern = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")
    dias = []
    for f in output_dir.iterdir():
        m = pattern.match(f.name)
        if m:
            dias.append(m.group(1))
    dias.sort(reverse=True)

    if not dias:
        return

    items_html = ""
    for d in dias:
        try:
            data_obj = datetime.date.fromisoformat(d)
            label = formatar_data_pt(data_obj)
        except ValueError:
            label = d
        items_html += f'    <li><a class="arq-link" href="{d}.html">📰 {label}</a></li>\n'

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Arquivo — Ordem &amp; Liberdade</title>
  <style>
    :root {{
      --ouro: #e5a810; --ouro-esc: #b8860b;
      --bg: #0f0f0f; --surface: #141414; --surface-1: #1a1a1a;
      --texto: #e0e0e0; --texto-sec: #aaa; --texto-fra: #666;
      --borda-f: #333;
      --fonte-ser: 'Georgia','Times New Roman',serif;
      --fonte-san: Arial,'Helvetica Neue',sans-serif;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: var(--fonte-san); background: var(--bg); color: var(--texto); }}
    .nav {{
      background: var(--bg); padding: 0 2.5rem;
      display: flex; align-items: center; justify-content: space-between;
      height: 100px; border-bottom: 3px solid var(--ouro);
      position: sticky; top: 0; z-index: 100;
    }}
    .nav-logo .title {{
      font-family: var(--fonte-ser); font-size: 34px; font-weight: 700; color: #fff;
    }}
    .nav-logo .title span {{ color: var(--ouro); }}
    .nav-logo .subtitle {{
      font-size: 13px; color: var(--ouro); letter-spacing: 3px; text-transform: uppercase;
    }}
    .nav-back {{
      font-size: 15px; color: var(--texto-sec); border: 0.5px solid var(--borda-f);
      padding: 8px 20px; border-radius: 4px; transition: color 0.2s, border-color 0.2s;
    }}
    .nav-back:hover {{ color: var(--ouro); border-color: var(--ouro-esc); }}
    .container {{
      max-width: 800px; margin: 0 auto; padding: 3rem 2rem;
    }}
    h1 {{
      font-family: var(--fonte-ser); font-size: 32px; color: #fff;
      margin-bottom: 8px;
    }}
    .subtitle-page {{
      font-size: 14px; color: var(--texto-fra); margin-bottom: 2.5rem;
    }}
    ul {{ list-style: none; }}
    li {{ border-bottom: 0.5px solid var(--borda-f); }}
    .arq-link {{
      display: block; padding: 18px 0;
      font-family: var(--fonte-ser); font-size: 18px;
      color: var(--texto-sec); transition: color 0.2s, padding-left 0.2s;
    }}
    .arq-link:hover {{ color: var(--ouro); padding-left: 10px; }}
    .footer-bottom {{
      text-align: center; padding: 2rem; font-size: 11px; color: #3a3a3a;
      border-top: 0.5px solid var(--borda-f); margin-top: 3rem;
    }}
  </style>
</head>
<body>
<nav class="nav">
  <div class="nav-logo">
    <div class="title">Ordem <span>&amp;</span> Liberdade</div>
    <div class="subtitle">BSafe Bitcoin · Est. 2026</div>
  </div>
  <a class="nav-back" href="index.html">← Edição de Hoje</a>
</nav>
<div class="container">
  <h1>📅 Arquivo de Edições</h1>
  <p class="subtitle-page">{len(dias)} edição{'ões' if len(dias) != 1 else ''} publicada{'s' if len(dias) != 1 else ''}</p>
  <ul>
{items_html}  </ul>
</div>
<div class="footer-bottom">© 2026 Ordem &amp; Liberdade · BSafe Bitcoin</div>
</body>
</html>"""

    (output_dir / "arquivo.html").write_text(html, encoding="utf-8")
    print(f"✓ arquivo.html atualizado ({len(dias)} edições)")


def salvar_arquivo(html: str, data_str: str, output_dir: Path):
    """Salva o HTML, atualiza index.html e regenera arquivo.html."""
    output_dir.mkdir(parents=True, exist_ok=True)

    arquivo_dia = output_dir / f"{data_str}.html"
    arquivo_dia.write_text(html, encoding="utf-8")
    print(f"\n✓ Salvo: {arquivo_dia}")

    index = output_dir / "index.html"
    index.write_text(html, encoding="utf-8")
    print(f"✓ index.html atualizado")

    gerar_arquivo_html(output_dir)

    return arquivo_dia


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    hoje           = datetime.date.today()
    data_str       = hoje.strftime("%Y-%m-%d")
    data_formatada = formatar_data_pt(hoje)

    print(f"=== Ordem & Liberdade — {data_formatada} ===\n")

    output_dir = Path(__file__).parent / "docs"

    # ── Dias anterior e próximo (só mostra link se o arquivo existir) ──
    anterior_obj  = dia_util_anterior(hoje)
    anterior_str  = anterior_obj.strftime("%Y-%m-%d")
    tem_anterior  = (output_dir / f"{anterior_str}.html").exists()

    # Próximo dia útil — só relevante se estivermos regenerando um digest antigo
    proximo_obj   = hoje + datetime.timedelta(days=1)
    while proximo_obj.weekday() >= 5:
        proximo_obj += datetime.timedelta(days=1)
    proximo_str   = proximo_obj.strftime("%Y-%m-%d")
    tem_proximo   = (output_dir / f"{proximo_str}.html").exists()

    print("Buscando cotação do Bitcoin...")
    ticker = buscar_ticker()

    print("\nBuscando manchetes...")
    noticias = buscar_noticias()
    print(f"\nTotal: {len(noticias)} manchetes coletadas")

    print("\nAnalisando com Claude...")
    analise = analisar_com_claude(noticias, data_formatada)
    print(f"✓ {len(analise.get('noticias', []))} manchetes analisadas")

    html = gerar_html(
        analise, data_str, data_formatada, ticker,
        data_anterior=anterior_str if tem_anterior else None,
        data_proxima=proximo_str  if tem_proximo  else None,
    )

    salvar_arquivo(html, data_str, output_dir)

    print("\n✅ Digest gerado com sucesso!")


if __name__ == "__main__":
    main()
