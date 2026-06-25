# Dashboard de Performance — Instagram @recorrenciadehonorarios

Dashboard estático (tema escuro, otimizado para TV) com as métricas dos últimos
30 dias. **Atualiza sozinho todo dia às 08:00 BRT** via GitHub Actions e é servido
de graça pelo GitHub Pages — sem servidor, sem hibernação, sem custo.

```
index.html               → o dashboard (consome ./data.json)
build.py                 → gera data.json a partir da Meta Graph API
data.json                → dados do dashboard (gerado/atualizado pelo Actions)
follower_history.json    → histórico diário de seguidores (acumula no repo)
historico_metricas.csv   → 1 linha por dia (Excel/Google Sheets) — histórico completo
requirements.txt         → dependências Python
.github/workflows/update.yml → agenda 08:00 BRT + commit/push
```

## Como funciona
1. Às **11:00 UTC (08:00 BRT)** o GitHub Actions roda `build.py`.
2. `build.py` busca perfil + mídia **com insights na mesma chamada** (alcance, views,
   salvamentos, compartilhamentos, engajamento), grava `data.json` e atualiza o
   `follower_history.json`.
3. O Actions faz commit dos dados; o **GitHub Pages** publica o `index.html` atualizado.
4. O dashboard recarrega o `data.json` sozinho a cada 30 min (bom para deixar na TV).

> **Insights já funcionam** com o token "Instagram Login for Business" — não precisa
> de App Review nem da permissão antiga `instagram_manage_insights`.

## Deploy (uma vez, ~10 min)

**1. Criar o repositório**
```bash
cd "dashboard_web"
git init && git add . && git commit -m "dashboard inicial"
gh repo create instagram-dashboard --private --source=. --push
# (ou crie o repo no site do GitHub e dê git push)
```

**2. Adicionar os Secrets** (repo → Settings → Secrets and variables → Actions → New):
| Secret | Valor |
| --- | --- |
| `INSTAGRAM_ACCESS_TOKEN` | o token IGAA do `.env` (na pasta INSTAGRAM (CLaude)) |
| `INSTAGRAM_BUSINESS_ID` | `26890120633982173` |
| `GH_PAT` | *(opcional)* token fino com permissão **Secrets: write** — só para o token se renovar sozinho |

**3. Ligar o GitHub Pages**
Settings → Pages → Source: **Deploy from a branch** → Branch: `main` / `/ (root)` → Save.
A URL pública será algo como `https://SEU_USUARIO.github.io/instagram-dashboard/`.

**4. Rodar a primeira vez**
Aba **Actions** → "Atualizar Dashboard Instagram" → **Run workflow**.
Em ~1 min o `data.json` é gerado e o Pages publica.

## Renovação do token
- O token IGAA dura **60 dias**. O `build.py` tenta **renová-lo a cada execução**.
- Com o `GH_PAT` configurado, ele **regrava o secret sozinho** → automação sem manutenção.
- Sem o `GH_PAT`, gere um token novo a cada ~55 dias (script `gerar_token.ps1` na pasta
  INSTAGRAM (CLaude)) e cole em `INSTAGRAM_ACCESS_TOKEN` nos Secrets.

## Preview local
Com o helper incluído: `powershell -File _serve.ps1` e abra `http://localhost:8765/`.
(O `_serve.ps1` e o `_seed.ps1` são só para uso local; ficam fora do deploy via `.gitignore`.)

## Observações sobre métricas
- **Alcance, Views, Salvamentos, Compartilhamentos, Eng. Rate**: disponíveis e exibidos.
- **Impressões / Retenção / Swipe-through**: a API atual (Instagram Login) não expõe
  esses campos a nível de mídia — aparecem como "—". `views` substitui "impressões".
- Médias são **por post** (não totais) e incluem o zero (não inflam o número).
