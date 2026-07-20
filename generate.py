
name: Ordem & Liberdade — Geração Diária
 
on:
  schedule:
    # Roda todo dia útil às 7h horário de Brasília (10h UTC)
    - cron: "0 10 * * 1-5"
  workflow_dispatch:  # permite rodar manualmente pelo GitHub
 
permissions:
  contents: write
  pull-requests: write  # necessário para abrir o Pull Request de revisão
 
jobs:
  gerar-digest:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout do repositório
        uses: actions/checkout@v4
 
      - name: Configurar Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
 
      - name: Instalar dependências
        run: pip install google-generativeai feedparser
 
      - name: Gerar Digest
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python generate.py
 
      - name: Criar branch de rascunho e abrir Pull Request para revisão
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          DATA=$(date +'%Y-%m-%d')
          BRANCH="digest/$DATA"
 
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
 
          # Cria branch do dia e faz push
          git checkout -b "$BRANCH"
          git add docs/
          git diff --staged --quiet || git commit -m "Digest $DATA — aguardando revisão"
          git push origin "$BRANCH"
 
          # Abre Pull Request para você revisar antes de publicar
          gh pr create \
            --title "📰 Digest $DATA — Ordem & Liberdade" \
            --body "O digest de hoje foi gerado automaticamente. Revise o conteúdo e faça o **Merge** para publicar no site. Se quiser editar algo, faça as alterações neste branch antes de aprovar." \
            --base main \
            --head "$BRANCH"
 
