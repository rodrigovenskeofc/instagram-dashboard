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
F (Data do Reel) · G (Dia da semana) · H (Link) · I (Head/legenda) · J (Views) · K (Likes) ·
L (Coments) · M (Shares) · N (Saved) · O (Alcance).

- **B (Distribuição):** manual — o robô não mexe.
- **P / Q (Views/Alcance Seguidores e Não-Seguidores):** ficam **em branco** de propósito.
  A API do Instagram não entrega mais esse dado real (só estimativa, que não usamos).
  Veja abaixo como religar se um dia voltar a valer a pena.

---

## Como mexer

### ▶️ Rodar na hora (sem esperar as 07:30)
- **Pelo GitHub (mais fácil):** abra
  **https://github.com/rodrigovenskeofc/instagram-dashboard/actions** → no menu esquerdo
  **"Atualizar Planilha Trafego"** → **"Run workflow"**. Em ~1 min atualiza a planilha.
- **Pelo VPS:** `ssh -p 22022 root@143.95.213.127` e rode
  `cd /root/automacoes/planilha && python3 atualizar_planilha.py --daily`

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
  Lá ficam: `atualizar_planilha.py`, `.env` (token) e `gdrive_sa.json` (chave Google), com
  permissão `600`. Log em `/root/automacoes/planilha/log.txt`. O token se renova sozinho a cada
  execução (regravado no `.env` do VPS).
- **Reserva manual (GitHub Actions):** mesmo script no repo, lê os secrets
  `INSTAGRAM_ACCESS_TOKEN` e `GDRIVE_SA`. Útil pra "Run workflow" manual se o VPS estiver fora.
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
