# ⚖️ Ordem & Liberdade

Resumo diário de notícias interpretadas sob a ótica conservadora-libertária, gerado automaticamente via Claude (Anthropic).

Fundamentado em: Burke · Kirk · Scruton · Mises · Hayek · Bastiat · Friedman · Rothbard · Roberto Campos

---

## Como funciona

1. Todo dia útil às 7h (Brasília), o GitHub Actions executa `generate.py`
2. O script coleta as principais notícias de G1, Folha, Estadão, Gazeta do Povo, Mises Brasil, Reuters e AP
3. O Claude analisa cada notícia sob a ótica libertária (livre mercado, Estado mínimo, liberdade individual)
4. O resultado é publicado como página estática no GitHub Pages

---

## Setup (10 minutos)

### 1. Criar o repositório no GitHub

- Acesse [github.com](https://github.com) e clique em **New repository**
- Nome sugerido: `libertario-digest`
- Marque como **Public** (necessário para GitHub Pages gratuito)
- Clique em **Create repository**

### 2. Fazer upload dos arquivos

Faça upload de todos os arquivos deste projeto para o repositório:
- `generate.py`
- `.github/workflows/daily.yml`
- `docs/` (pasta onde os HTMLs serão salvos — crie uma vazia ou com um `index.html` inicial)

Se preferir via terminal:
```bash
git clone https://github.com/SEU_USUARIO/libertario-digest
cd libertario-digest
# copie os arquivos aqui
git add .
git commit -m "Setup inicial"
git push
```

### 3. Adicionar a chave da API do Claude

- No seu repositório GitHub, vá em **Settings → Secrets and variables → Actions**
- Clique em **New repository secret**
- Nome: `ANTHROPIC_API_KEY`
- Valor: sua chave da API (obtenha em [console.anthropic.com](https://console.anthropic.com))
- Clique em **Add secret**

### 4. Ativar o GitHub Pages

- Vá em **Settings → Pages**
- Em **Source**, selecione **Deploy from a branch**
- Branch: `main`, pasta: `/docs`
- Clique em **Save**

Após alguns minutos, seu site estará disponível em:
`https://SEU_USUARIO.github.io/libertario-digest`

### 5. Testar manualmente

Para gerar o primeiro digest sem esperar o agendamento:
- Vá em **Actions → Libertário Digest — Geração Diária**
- Clique em **Run workflow**

---

## Rodar localmente

```bash
pip install anthropic feedparser
export ANTHROPIC_API_KEY="sua-chave-aqui"
python generate.py
```

O HTML será gerado na pasta `docs/`.

---

## Personalização

No arquivo `generate.py` você pode:

- **Adicionar/remover fontes RSS** — edite a lista `RSS_FEEDS`
- **Ajustar o número de notícias** — variáveis `MAX_NOTICIAS_POR_FONTE` e `MAX_NOTICIAS_TOTAL`
- **Mudar o modelo do Claude** — parâmetro `model` na chamada da API
- **Refinar o prompt** — edite `SYSTEM_PROMPT` para enfatizar temas específicos

---

## Princípios editoriais

**Liberdade econômica**
- Propriedade privada e livre mercado (Mises, Hayek, Bastiat, Friedman)
- Estado mínimo e ceticismo fiscal (Rothbard, Roberto Campos)
- Análise das consequências não intencionais de cada política pública

**Conservadorismo de costumes**
- Valorização da ordem, da tradição e das instituições (Burke, Kirk)
- Defesa da família, da comunidade e da subsidiariedade (Scruton)
- Ceticismo à engenharia social e ao progressismo ideológico

**Brasil**
- Ceticismo à mídia financiada por verbas governamentais
- Crítica ao patrimonialismo e ao clientelismo estrutural

---

## Custo estimado

Com 15 notícias por dia usando `claude-opus-4-8`:
- ~3.000 tokens de entrada + ~1.500 de saída por execução
- Custo aproximado: **US$ 0,05–0,10 por dia**
- ~US$ 1,50–3,00 por mês

Para reduzir custo, substitua o modelo por `claude-haiku-4-5-20251001` em `generate.py`.
