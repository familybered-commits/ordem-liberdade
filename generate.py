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
    {"nome": "G1",             "pais": "🇧🇷", "url": "https://g1.globo.com/rss/g1/"},
    {"nome": "Folha",          "pais": "🇧🇷", "url": "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml"},
    {"nome": "UOL Notícias",   "pais": "🇧🇷", "url": "https://rss.uol.com.br/feed/noticias.xml"},
    {"nome": "Gazeta do Povo", "pais": "🇧🇷", "url": "https://www.gazetadopovo.com.br/feed/"},
    {"nome": "Mises Brasil",   "pais": "🇧🇷", "url": "https://www.mises.org.br/feed"},
    # ── Internacional (🇬🇧 UK + 🇺🇸 US) ────────────
    {"nome": "BBC",              "pais": "🌐", "url": "https://feeds.bbci.co.uk/news/rss.xml"},
    {"nome": "The Times UK",     "pais": "🌐", "url": "https://www.thetimes.co.uk/rss/news"},
    {"nome": "The Spectator",    "pais": "🌐", "url": "https://www.spectator.co.uk/rss"},
    {"nome": "Fox News",         "pais": "🌐", "url": "https://moxie.foxnews.com/google-publisher/latest.xml"},
    {"nome": "Wall Street Journal", "pais": "🌐", "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml"},
]

MAX_NOTICIAS_POR_FONTE = 1   # 1 por fonte × 10 fontes = até 10 notícias
MAX_NOTICIAS_TOTAL = 6       # teto geral (3 Brasil + 3 internacional)


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

3. CONSEQUÊNCIAS NÃO INTENCIONAIS (Bastiat, Hayek, Friedman)
   - Toda intervenção cria distorções que exigem novas intervenções — ciclo vicioso.
   - Milton Friedman: "Não existe almoço grátis." Alguém sempre paga a conta.

═══ CONSERVADORISMO DE COSTUMES ═══

4. ORDEM, TRADIÇÃO E INSTITUIÇÕES (Edmund Burke, Russell Kirk)
   - A sociedade é um contrato entre os mortos, os vivos e os que ainda nascerão (Burke).
   - Mudanças abruptas destroem o conhecimento acumulado em instituições e costumes.
   - Russell Kirk: a ordem moral é o fundamento de toda liberdade política duradoura.
   - Reformas sem ancoragem na tradição tendem ao caos e ao autoritarismo.

5. FAMÍLIA, COMUNIDADE E SUBSIDIARIEDADE (Roger Scruton, T.S. Eliot)
   - A família é a célula básica da sociedade — sua erosão enfraquece toda a ordem social.
   - Roger Scruton: o amor ao lugar, à pátria e à herança cultural não é reacionarismo — é sabedoria.
   - Problemas locais devem ser resolvidos localmente, não por burocracia central.

6. CETICISMO À ENGENHARIA SOCIAL (Scruton, Kirk, Olavo de Carvalho)
   - Projetos de transformação radical da sociedade historicamente produzem tirania.
   - A cultura, a religião e os costumes são repositórios de sabedoria que o racionalismo abstrato ignora.
   - Olavo de Carvalho: a inversão de valores na cultura precede e prepara a invasão política.

═══ BRASIL ESPECIFICAMENTE ═══

7. CONTEXTO BRASILEIRO (Roberto Campos, Gustavo Franco)
   - O Estado brasileiro é historicamente predatório, ineficiente e capturado por corporações e sindicatos.
   - A mídia mainstream brasileira é, em grande parte, financiada por verbas publicitárias governamentais.
   - O clientelismo e o patrimonialismo são vícios estruturais que transcendem partidos.

═══ DIRETRIZES DE ANÁLISE ═══

Ao analisar cada notícia:
- Classifique o tema predominante: econômico, cultural/moral, político-institucional ou midiático
- Cite o pensador mais pertinente quando houver encaixe natural (não force citações)
- Para temas econômicos: aplique Mises/Hayek/Bastiat/Friedman/Roberto Campos
- Para temas culturais, família, educação, religião: aplique Burke/Kirk/Scruton
- Para temas de mídia e narrativa: aplique ceticismo estrutural (quem financia? quem se beneficia?)
- Use linguagem clara, culta e acessível — como um ensaísta, não um burocrata
- Seja incisivo e direto, mas justo — critique ideias e fatos, não pessoas
- Mantenha o tom de quem leu muito, pensa com clareza e não se intimida com o consenso midiático"""


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
                    "fonte": feed_info["nome"],
                    "pais": feed_info.get("pais", "🌐"),
                    "url": entry.get("link", ""),
                    "resumo_original": resumo,
                })
            print(f"  ✓ {feed_info['pais']} {feed_info['nome']}: {len(entradas)} notícias")
        except Exception as e:
            print(f"  ✗ {feed_info['nome']}: erro — {e}")

    return noticias[:MAX_NOTICIAS_TOTAL]


def analisar_com_claude(noticias: list[dict], data_str: str) -> dict:
    """Envia as notícias para o Claude e retorna a análise libertária."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Variável de ambiente ANTHROPIC_API_KEY não definida.")

    client = anthropic.Anthropic(api_key=api_key)

    # Monta o bloco de notícias para o prompt
    bloco_noticias = ""
    for i, n in enumerate(noticias, 1):
        bloco_noticias += f"""
---
{i}. [{n['fonte']}] {n['titulo']}
{n['resumo_original']}
"""

    prompt = USER_PROMPT_TEMPLATE.format(data=data_str, noticias=bloco_noticias)

    print("\nEnviando para o Claude...")
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    resposta_texto = message.content[0].text

    # Extrai JSON da resposta (pode vir com markdown ```json ... ```)
    import re

    # Tenta parsear direto
    try:
        return json.loads(resposta_texto)
    except json.JSONDecodeError:
        pass

    # Remove blocos markdown ```json ... ```
    cleaned = re.sub(r"```(?:json)?\s*", "", resposta_texto).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Extrai o primeiro objeto JSON completo
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

    raise ValueError(f"Resposta do Claude não continha JSON válido:\n{resposta_texto[:500]}")


def _card_pt(noticia: dict) -> str:
    """Card para notícia brasileira — sempre em português, sem toggle."""
    tags_html = "".join(f'<span class="tag">{t}</span>' for t in noticia.get("tags", []))
    pensador = noticia.get("pensador")
    pensador_html = f'<span class="pensador">✍️ {pensador}</span>' if pensador else ""
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
                <h3>📋 Resumo</h3>
                <p>{noticia.get('resumo', '')}</p>
            </div>
            <div class="secao analise">
                <h3>⚖️ Análise — Ordem &amp; Liberdade</h3>
                <p>{noticia.get('analise', '')}</p>
            </div>
            <div class="secao atencao">
                <h3>👁️ Ponto de Atenção</h3>
                <p>{noticia.get('atencao', '')}</p>
            </div>
        </article>"""


def _card_en(noticia: dict, idx: int) -> str:
    """Card para notícia internacional — EN por padrão, traduz para PT no toggle."""
    tags_html = "".join(f'<span class="tag">{t}</span>' for t in noticia.get("tags", []))
    pensador = noticia.get("pensador")
    pensador_html = f'<span class="pensador">✍️ {pensador}</span>' if pensador else ""
    share_url = noticia.get('url', '') or ''
    return f"""
        <article class="card card-en" data-intl="{idx}">
            <div class="card-header">
                <span class="pais">🌐</span>
                <span class="fonte">{noticia.get('fonte', '')}</span>
                {tags_html}
                {pensador_html}
                <button class="share-btn" onclick="compartilhar('{share_url}', this)" title="Share">
                    ↗ Share
                </button>
            </div>
            <h2 class="card-titulo intl-titulo">{noticia.get('titulo', '')}</h2>
            <div class="secao">
                <h3 class="intl-lbl-resumo">📋 Summary</h3>
                <p class="intl-resumo">{noticia.get('resumo', '')}</p>
            </div>
            <div class="secao analise">
                <h3 class="intl-lbl-analise">⚖️ Analysis — Order &amp; Liberty</h3>
                <p class="intl-analise">{noticia.get('analise', '')}</p>
            </div>
            <div class="secao atencao">
                <h3 class="intl-lbl-atencao">👁️ Watch Point</h3>
                <p class="intl-atencao">{noticia.get('atencao', '')}</p>
            </div>
        </article>"""


def gerar_html(analise: dict, data_str: str, data_formatada: str) -> str:
    """Gera o HTML com notícias BR em PT e internacionais em EN."""

    noticias = analise.get("noticias", [])
    editorial_pt = analise.get("editorial_pt", "")
    editorial_en = analise.get("editorial_en", "")

    # Coleta notícias internacionais com índice para o JS
    intl = [(i, n) for i, n in enumerate(noticias) if n.get("pais") == "🌐"]

    # Serializa conteúdo bilíngue das internacionais + editorials para JS
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

    # Gera seções separadas
    cards_br = "".join(_card_pt(n) for n in noticias if n.get("pais") == "🇧🇷")
    cards_en = "".join(_card_en(n, i) for i, n in intl)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ordem &amp; Liberdade / Order &amp; Liberty — {data_formatada}</title>
    <style>
        :root {{
            --ouro: #c9a227;
            --ouro-escuro: #9b7c1a;
            --bg: #0f0f0f;
            --surface: #1a1a1a;
            --surface2: #242424;
            --texto: #e8e8e8;
            --texto-fraco: #888;
            --borda: #2e2e2e;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Georgia', serif;
            background: var(--bg);
            color: var(--texto);
            line-height: 1.7;
            min-height: 100vh;
        }}
        header {{
            background: var(--surface);
            border-bottom: 2px solid var(--ouro);
            padding: 2rem 1rem 1.5rem;
            text-align: center;
        }}
        .logo {{
            font-size: 0.85rem;
            letter-spacing: 0.05em;
            color: var(--ouro);
            font-style: italic;
            font-family: 'Georgia', serif;
            margin-bottom: 0.5rem;
            opacity: 0.85;
        }}
        header h1 {{
            font-size: 2.2rem;
            color: #fff;
            font-weight: 700;
        }}
        header h1 span {{ color: var(--ouro); }}
        .data {{
            color: var(--texto-fraco);
            font-size: 0.9rem;
            margin-top: 0.4rem;
            font-family: 'Arial', sans-serif;
        }}
        /* ── Toggle de idioma ── */
        .lang-toggle {{
            display: inline-flex;
            margin-top: 1rem;
            border: 1px solid var(--ouro-escuro);
            border-radius: 30px;
            overflow: hidden;
        }}
        .lang-toggle button {{
            background: transparent;
            border: none;
            padding: 0.35rem 1.1rem;
            font-size: 0.8rem;
            letter-spacing: 0.1em;
            cursor: pointer;
            color: var(--texto-fraco);
            font-family: 'Arial', sans-serif;
            transition: background 0.2s, color 0.2s;
        }}
        .lang-toggle button.active {{
            background: var(--ouro);
            color: #000;
            font-weight: 700;
        }}
        /* ── Layout ── */
        .container {{
            max-width: 860px;
            margin: 0 auto;
            padding: 2rem 1rem;
        }}
        .editorial {{
            background: linear-gradient(135deg, #1e1a0e, #1a1a1a);
            border-left: 4px solid var(--ouro);
            border-radius: 8px;
            padding: 1.5rem 1.8rem;
            margin-bottom: 2.5rem;
            font-style: italic;
            font-size: 1.05rem;
            color: #d4c89a;
            text-align: justify;
            hyphens: auto;
        }}
        .editorial-label {{
            font-size: 0.75rem;
            letter-spacing: 0.2em;
            text-transform: uppercase;
            color: var(--ouro);
            font-style: normal;
            margin-bottom: 0.6rem;
            display: block;
            font-family: 'Arial', sans-serif;
        }}
        .card {{
            background: var(--surface);
            border: 1px solid var(--borda);
            border-radius: 10px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            transition: border-color 0.2s;
        }}
        .card:hover {{ border-color: var(--ouro-escuro); }}
        .card-header {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.7rem;
            flex-wrap: wrap;
        }}
        .pais {{ font-size: 1rem; }}
        .fonte {{
            font-size: 0.75rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--ouro);
            font-family: 'Arial', sans-serif;
            font-weight: 700;
        }}
        .tag {{
            font-size: 0.7rem;
            padding: 0.15rem 0.5rem;
            background: var(--surface2);
            border-radius: 20px;
            color: var(--texto-fraco);
            font-family: 'Arial', sans-serif;
        }}
        .pensador {{
            font-size: 0.72rem;
            padding: 0.15rem 0.6rem;
            background: #1e1a0e;
            border: 1px solid var(--ouro-escuro);
            border-radius: 20px;
            color: var(--ouro);
            font-family: 'Georgia', serif;
            font-style: italic;
        }}
        .card-titulo {{
            font-size: 1.2rem;
            color: #fff;
            margin-bottom: 1.2rem;
            line-height: 1.4;
        }}
        .secao {{ margin-bottom: 1rem; }}
        .secao:last-child {{ margin-bottom: 0; }}
        .secao h3 {{
            font-size: 0.8rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--texto-fraco);
            margin-bottom: 0.4rem;
            font-family: 'Arial', sans-serif;
        }}
        .secao p {{
            font-size: 0.97rem;
            color: var(--texto);
            text-align: justify;
            hyphens: auto;
        }}
        .secao.analise {{ background: var(--surface2); border-radius: 6px; padding: 1rem; }}
        .secao.analise h3 {{ color: var(--ouro); }}
        .secao.analise p {{ color: #d4c89a; text-align: justify; hyphens: auto; }}
        .secao.atencao p {{ color: #f0a500; font-weight: bold; font-size: 0.93rem; text-align: justify; }}
        /* ── Separador de seções ── */
        .section-title {{
            font-size: 0.75rem;
            letter-spacing: 0.25em;
            text-transform: uppercase;
            color: var(--texto-fraco);
            font-family: 'Arial', sans-serif;
            margin: 2.5rem 0 1rem;
            display: flex;
            align-items: center;
            gap: 0.8rem;
        }}
        .section-title::after {{
            content: '';
            flex: 1;
            height: 1px;
            background: var(--borda);
        }}
        /* ── Share button ── */
        .share-btn {{
            margin-left: auto;
            background: transparent;
            border: 1px solid var(--ouro-escuro);
            color: var(--ouro);
            font-size: 0.72rem;
            padding: 0.2rem 0.7rem;
            border-radius: 20px;
            cursor: pointer;
            font-family: 'Arial', sans-serif;
            transition: background 0.2s, color 0.2s;
        }}
        .share-btn:hover {{ background: var(--ouro); color: #000; }}
        .share-btn.copied {{ background: #2a4a2a; border-color: #4caf50; color: #4caf50; }}
        footer {{
            text-align: center;
            padding: 2rem 1rem;
            color: var(--texto-fraco);
            font-size: 0.8rem;
            border-top: 1px solid var(--borda);
            font-family: 'Arial', sans-serif;
        }}
        footer a {{ color: var(--ouro); text-decoration: none; }}
    </style>
</head>
<body>
    <header>
        <p class="logo">⚖️ <span id="logo-txt">O preço da liberdade é a eterna vigilância</span></p>
        <h1 id="site-title">Ordem <span>&amp; Liberdade</span></h1>
        <p class="data">{data_formatada}</p>
        <div class="lang-toggle">
            <button id="btn-pt" class="active" onclick="setLang('pt')">🇧🇷 PT</button>
            <button id="btn-en" onclick="setLang('en')">🇺🇸 EN</button>
        </div>
    </header>

    <div class="container">
        <div class="editorial">
            <span class="editorial-label" id="editorial-label">Editorial do dia</span>
            <span id="editorial-text">{editorial_pt}</span>
        </div>

        <div class="section-title">🇧🇷 Brasil</div>
        {cards_br}

        <div class="section-title">🌐 Internacional · International</div>
        {cards_en}
    </div>

    <footer>
        <p>Burke · Kirk · Scruton · Mises · Hayek · Bastiat · Friedman · Roberto Campos</p>
        <p style="margin-top:0.4rem">🇧🇷 G1 · Folha · Estadão · Gazeta do Povo · Mises Brasil &nbsp;|&nbsp; 🌐 Reuters · AP · BBC · The Guardian · NYT</p>
        <p style="margin-top:0.8rem; color:#555">Atualizado em {data_formatada} · <a href="https://mises.org.br" target="_blank">Mises Brasil</a> · <a href="https://iea.org.br" target="_blank">IEA</a> · <a href="https://www.gazetadopovo.com.br" target="_blank">Gazeta do Povo</a></p>
    </footer>

    <script>
        const DADOS = {dados_js};

        function setLang(lang) {{
            const isPt = lang === 'pt';
            document.getElementById('btn-pt').classList.toggle('active', isPt);
            document.getElementById('btn-en').classList.toggle('active', !isPt);

            // Título e logo
            document.getElementById('site-title').innerHTML = isPt
                ? 'Ordem <span style="color:var(--ouro)">&amp; Liberdade</span>'
                : 'Order <span style="color:var(--ouro)">&amp; Liberty</span>';
            document.getElementById('logo-txt').textContent = isPt
                ? 'O preço da liberdade é a eterna vigilância'
                : 'The price of liberty is eternal vigilance';

            // Editorial
            document.getElementById('editorial-label').textContent = isPt ? 'Editorial do dia' : "Today's editorial";
            document.getElementById('editorial-text').textContent = DADOS.editorial[isPt ? 'pt' : 'en'];

            // Cards internacionais: traduz para PT ou volta ao EN
            document.querySelectorAll('.card-en[data-intl]').forEach(card => {{
                const idx = card.getAttribute('data-intl');
                const d = DADOS.intl[idx];
                if (!d) return;
                const v = d[isPt ? 'pt' : 'en'];
                card.querySelector('.intl-titulo').textContent  = v.titulo  || '';
                card.querySelector('.intl-resumo').textContent  = v.resumo  || '';
                card.querySelector('.intl-analise').textContent = v.analise || '';
                card.querySelector('.intl-atencao').textContent = v.atencao || '';
                // Labels das seções
                card.querySelector('.intl-lbl-resumo').textContent  = isPt ? '📋 Resumo'  : '📋 Summary';
                card.querySelector('.intl-lbl-analise').textContent = isPt
                    ? '⚖️ Análise — Ordem & Liberdade' : '⚖️ Analysis — Order & Liberty';
                card.querySelector('.intl-lbl-atencao').textContent = isPt ? '👁️ Ponto de Atenção' : '👁️ Watch Point';
            }});

            document.documentElement.lang = isPt ? 'pt-BR' : 'en';
        }}

        function compartilhar(url, btn) {{
            const texto = btn.closest('.card').querySelector('.card-titulo').textContent;
            const link = url || window.location.href;
            if (navigator.share) {{
                navigator.share({{ title: texto, text: texto + ' — Order & Liberty', url: link }});
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

    # Arquivo do dia
    arquivo_dia = output_dir / f"{data_str}.html"
    arquivo_dia.write_text(html, encoding="utf-8")
    print(f"\n✓ Salvo: {arquivo_dia}")

    # Copia para index.html (página principal do GitHub Pages)
    index = output_dir / "index.html"
    index.write_text(html, encoding="utf-8")
    print(f"✓ index.html atualizado")

    return arquivo_dia


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    hoje = datetime.date.today()
    data_str = hoje.strftime("%Y-%m-%d")
    data_formatada = hoje.strftime("%d de %B de %Y").replace(
        "January","janeiro").replace("February","fevereiro").replace(
        "March","março").replace("April","abril").replace(
        "May","maio").replace("June","junho").replace(
        "July","julho").replace("August","agosto").replace(
        "September","setembro").replace("October","outubro").replace(
        "November","novembro").replace("December","dezembro")

    print(f"=== Ordem & Liberdade — {data_formatada} ===\n")
    print("Buscando notícias...")
    noticias = buscar_noticias()
    print(f"\nTotal: {len(noticias)} notícias coletadas")

    print("\nAnalisando com Claude...")
    analise = analisar_com_claude(noticias, data_formatada)
    print(f"✓ {len(analise.get('noticias', []))} notícias analisadas")

    html = gerar_html(analise, data_str, data_formatada)

    output_dir = Path(__file__).parent / "docs"
    salvar_arquivo(html, data_str, output_dir)

    print("\n✅ Digest gerado com sucesso!")


if __name__ == "__main__":
    main()
