# Automação da Planilha de Tráfego (Reels do Instagram)

Atualiza sozinha, **todo dia às 07:30 (horário de Brasília)**, a planilha de tráfego
no Google Drive com as métricas dos Reels de **@recorrenciadehonorarios**.

Roda na **nuvem (GitHub Actions)** — **não depende do seu PC estar ligado**.

- **Planilha:** `4) MÉTRICAS REELS DISTRIBUIÇÃO DE CONTEÚDO.xlsx`
  → https://docs.google.com/spreadsheets/d/1OspNVc8Sd-JvE1NHXM-l3-NWayG7dKfx/edit
  (aba **`2026 Reels Org`**, dados a partir da linha 60)
- **Script:** [`atualizar_planilha.py`](atualizar_planilha.py)
- **Agendador:** [`.github/workflows/planilha.yml`](.github/workflows/planilha.yml)

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
1. Abra **https://github.com/rodrigovenskeofc/instagram-dashboard/actions**
2. No menu esquerdo, clique em **"Atualizar Planilha Trafego"**.
3. Botão **"Run workflow"** → **Run workflow**. Em ~1 min ele roda e atualiza a planilha.

### ⏸️ Pausar (desligar)
- Mesma tela do Actions → workflow **"Atualizar Planilha Trafego"** → botão **"•••"** (canto
  superior direito) → **"Disable workflow"**. Para religar, **"Enable workflow"**.

### 🕢 Mudar o horário
- Edite [`.github/workflows/planilha.yml`](.github/workflows/planilha.yml), linha do `cron`.
- O horário é em **UTC**. Brasília = UTC−3, então **some 3 horas**:
  - 07:30 BRT = `30 10 * * *`  ·  08:00 BRT = `0 11 * * *`  ·  06:00 BRT = `0 9 * * *`
- Formato: `minuto hora * * *`.

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

- **Onde roda:** GitHub Actions (servidores do GitHub), não no seu PC.
- **Credenciais (secrets do repo, nunca no código):**
  - `INSTAGRAM_ACCESS_TOKEN` — token do Instagram (renovado sozinho, todo dia, pelo job do dashboard).
  - `GDRIVE_SA` — chave da conta de serviço Google `planilha-writer@meta-map-500519-n1.iam.gserviceaccount.com`,
    que tem permissão de escrita na planilha (compartilhada como "qualquer um com link pode editar").
- **Mantém o mesmo arquivo e link:** baixa a versão atual do Drive, preenche e regrava no
  mesmo `fileId` (via Drive API). Nunca cria cópia.
- **Reserva local:** existe uma tarefa equivalente no Agendador do Windows
  (`PlanilhaTrafegoInstagram`), mas está **desativada** para não competir com a nuvem.
  Arquivos locais: `atualizar_planilha.py`, `run_diario.bat`, `.env`, `gdrive_sa.json`
  na pasta `C:\Users\Rodrigo\Documents\INSTAGRAM (CLaude)`.

## Se algo der errado
- Veja o resultado de cada execução em **Actions → "Atualizar Planilha Trafego"** (verde = ok,
  vermelho = erro; clique no run para ver o log).
- Causas comuns: token vencido (o dashboard renova sozinho; se o dashboard estiver desligado,
  reative-o) ou a planilha ter sido movida/renomeada no Drive (o `fileId` muda → avisar o dev).
