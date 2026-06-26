# Automação da Planilha de Tráfego (Reels do Instagram)

Atualiza sozinha, **todo dia às 07:30 (horário de Brasília)**, a planilha de tráfego
no Google Drive com as métricas dos Reels de **@recorrenciadehonorarios**.

**Quem agenda é o VPS** (servidor sempre ligado) — **não depende do seu PC**.
O cron do GitHub Actions é "best-effort" e neste repositório não dispara, por isso o
agendamento foi movido para o VPS. O GitHub continua como **reserva de disparo manual**.

- **Planilha:** `4) MÉTRICAS REELS DISTRIBUIÇÃO DE CONTEÚDO.xlsx`
  → https://docs.google.com/spreadsheets/d/1OspNVc8Sd-JvE1NHXM-l3-NWayG7dKfx/edit
  (aba **`2026 Reels Org`**, dados a partir da linha 60)
- **Script:** [`atualizar_planilha.py`](atualizar_planilha.py)
- **Agendador real:** cron no VPS `143.95.213.127` →
  `/root/automacoes/planilha/` (cron `30 7 * * *`, fuso America/Sao_Paulo).
- **Reserva manual:** [`.github/workflows/planilha.yml`](.github/workflows/planilha.yml) (só `workflow_dispatch`).

---

## A regra

Todo dia o robô registra os Reels postados em **HOJE − 3 dias**, na próxima linha vazia.

- Roda em 27/06 → registra o Reel de **24/06**; roda em 28/06 → o de **25/06**; e assim por diante.
- **Vários Reels no mesmo dia → várias linhas.** Nenhum Reel no dia → nenhuma linha.
- Se algum dia falhar (ex.: instabilidade do GitHub), **recupera no dia seguinte** —
  preenche tudo que faltou a partir do último Reel já registrado, sem repetir.
- **Nunca volta ao passado** anterior ao que já está na planilha.

### Colunas preenchidas
A (Nr, automático) · C (Seguidores) · D (Dif Seguidores) · E (Atualização = dia da coleta) ·
F (Data do Reel) · G (Dia da semana) · H (Link) · I (Head/legenda) · **J (Views)** · K (Likes) ·
L (Coments) · M (Shares) · N (Saved) · O (Alcance) · **P–S (split de Views por público)**.

- **B (Distribuição):** manual — o robô não mexe.
- **J (Views):** vem das **"Visualizações" reais da tela de insights** (o que você vê no app),
  lidas via navegador logado. ⚠️ A métrica `views` da API do Instagram NÃO corresponde a esse
  número (retorna algo perto do alcance), por isso não a usamos para Views.
- **P, Q, R, S (split de Views):** lidos da mesma tela de insights:
  - **P = Views de Seguidores (%)** · **Q = Views de Seguidores (nº)**
  - **R = Views de Não-Seguidores (%)** · **S = Views de Não-Seguidores (nº)**
  - Q + S = J (Views). Os % são formatados como porcentagem; os nº são absolutos.
- **K, L, M, N, O (curtidas, coments, shares, saved, alcance):** vêm da API (conferidos: batem
  com o app) — mais robustos, não dependem do navegador.

> Renomeie os cabeçalhos da **linha 3** das colunas P–S para: "Views Seguidores %",
> "Views Seguidores nº", "Views Não-Seg %", "Views Não-Seg nº".

---

## Como mexer

### ▶️ Rodar na hora (sem esperar as 07:30)
No VPS: `ssh -p 22022 root@143.95.213.127` e rode
`cd /root/automacoes/planilha && python3 atualizar_planilha.py --daily`
- Para re-ler o split/Views de TODAS as linhas já preenchidas: `... --split-existing`

### ⏸️ Pausar / religar (o agendamento real é o do VPS)
- No VPS: `crontab -e` e comente (coloque `#` na frente) a linha que tem
  `atualizar_planilha.py`. Para religar, tire o `#`.
- Ver o agendamento atual: `crontab -l`.

### 🕢 Mudar o horário
- No VPS: `crontab -e`, na linha do `atualizar_planilha.py`, mude o início `30 7`
  (= 07:30, horário de Brasília — o VPS já está nesse fuso). Formato: `minuto hora * * *`.
  Ex.: `0 8 * * *` = 08:00; `45 6 * * *` = 06:45.

### 📅 Mudar a regra dos "3 dias"
- Edite [`atualizar_planilha.py`](atualizar_planilha.py), a constante no topo:
  ```python
  DELAY_DIAS = 3      # quantos dias depois do post o Reel é registrado
  ```
  Ex.: `2` = registra 2 dias depois; `5` = 5 dias depois.

### 🔓 Religar as colunas P / Q (caso volte o dado real)
- Hoje elas ficam vazias por escolha (sem estimativa). Para voltar a preencher seria preciso
  ajustar a função `preencher_linha` em `atualizar_planilha.py` (há um comentário marcando o
  ponto exato). **Só faça isso se a API voltar a entregar o split real por tipo de público.**

---

## Bastidores (pra referência)

- **Onde roda de verdade:** no **VPS** (`/root/automacoes/planilha/`), via cron, todo dia 07:30.
  Arquivos lá: `atualizar_planilha.py`, `coletar_views_split.py`, `.env` (token),
  `gdrive_sa.json` (chave Google) e `ig_state.json` (sessão logada do Instagram) — os 3 segredos
  com permissão `600`. Usa **Playwright (chromium headless)** pra ler a tela de insights.
  Log em `log.txt`. O token do IG se renova sozinho a cada execução.
- **Sessão do Instagram (`ig_state.json`):** capturada 1x localmente com
  `CAPTURAR_LOGIN_INSTAGRAM.bat` (login feito por você). Se o IG deslogar a sessão (pode acontecer
  por ser outro IP), rode o .bat de novo e copie o `ig_state.json` novo pro VPS:
  `scp -P 22022 ig_state.json root@143.95.213.127:/root/automacoes/planilha/`. Sinal de sessão
  caída no log: `split=---` ou `sessao_deslogada`.
- **GitHub Actions: DESATIVADO.** O workflow `planilha.yml` foi desligado porque os runners do
  GitHub não têm sua sessão logada do IG — sem ela, as Views sairiam erradas (a API não bate com
  o app) e o split ficaria vazio. O VPS é o único executor. (Reativar só faria sentido com uma
  sessão do IG disponível lá, o que não é o caso.)
- **Conta de serviço Google:** `planilha-writer@meta-map-500519-n1.iam.gserviceaccount.com`
  (tem escrita na planilha, que está como "qualquer um com link pode editar").
- **Mantém o mesmo arquivo e link:** baixa a versão atual do Drive, preenche e regrava no
  mesmo `fileId` (via Drive API). Nunca cria cópia. Deduplica por link (não repete Reel).
- **Reserva local (Windows):** tarefa `PlanilhaTrafegoInstagram` no Agendador, **desativada**
  (ficaria competindo com o VPS). Arquivos em `C:\Users\Rodrigo\Documents\INSTAGRAM (CLaude)`.

## Se algo der errado
- **No VPS:** `ssh -p 22022 root@143.95.213.127` → `tail -30 /root/automacoes/planilha/log.txt`
  mostra a última execução.
- **No GitHub:** **Actions → "Atualizar Planilha Trafego"** (verde = ok, vermelho = erro).
- Causas comuns: token vencido (renova sozinho; se ficar >60 dias sem rodar, gerar novo) ou a
  planilha ter sido movida/renomeada no Drive (o `fileId` muda → avisar o dev).
