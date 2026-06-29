# Automação da Planilha de Tráfego (Reels do Instagram)

Atualiza sozinha, **todo dia às 07:30 (horário de Brasília)**, a planilha de tráfego
no Google Drive com as métricas dos Reels de **@recorrenciadehonorarios**.

Roda no **VPS** (sempre ligado) — **não depende do seu PC**. **Usa apenas a API oficial do
Instagram** (Graph API). Nada de navegador/automação de login.

- **Planilha:** `4) MÉTRICAS REELS DISTRIBUIÇÃO DE CONTEÚDO.xlsx`
  → https://docs.google.com/spreadsheets/d/1OspNVc8Sd-JvE1NHXM-l3-NWayG7dKfx/edit
  (aba **`2026 Reels Org`**, dados a partir da linha 60)
- **Script:** [`atualizar_planilha.py`](atualizar_planilha.py)
- **Agendador:** cron no VPS `143.95.213.127` → `/root/automacoes/planilha/` (`30 7 * * *`).

---

## A regra
Todo dia o robô registra os Reels postados em **HOJE − 3 dias**, na próxima linha vazia.
- Vários Reels no mesmo dia → várias linhas. Nenhum → nenhuma linha.
- Se falhar/pular um dia, **recupera no dia seguinte** (preenche o que faltou a partir do último
  Reel já registrado, sem repetir). Nunca volta ao passado anterior ao que já está lá.

### Colunas preenchidas
A (Nr, automático) · C (Seguidores) · D (Dif Seguidores) · E (Atualização = dia da coleta) ·
F (Data do Reel) · G (Dia da semana) · H (Link) · I (Head/legenda) · **J (Views)** · K (Likes) ·
L (Coments) · M (Shares) · N (Saved) · O (Alcance).

- **B (Distribuição):** manual — o robô não mexe.
- **J (Views):** métrica `views` da API = **Visualizações só do Instagram** (não inclui Facebook).
- **P, Q, R, S:** **não são mais usadas.** Eram o split seguidor/não-seguidor e Views-IG lidos da
  tela de insights via navegador logado — **descontinuado** porque a automação de login fazia o
  Instagram **travar a conta**. A API oficial não fornece esse split. Ficam em branco.

---

## Como mexer (tudo no VPS)
Acesse: `ssh -p 22022 root@143.95.213.127` e vá em `cd /root/automacoes/planilha`

- **Rodar na hora:** `python3 atualizar_planilha.py --daily`
- **Ver o agendamento:** `crontab -l` · **Pausar:** `crontab -e` e comente a linha do
  `atualizar_planilha.py` (põe `#`); religar = tira o `#`.
- **Mudar o horário:** `crontab -e`, ajuste o início `30 7` (= 07:30 BRT). Formato `minuto hora * * *`.
- **Mudar a regra dos 3 dias:** em `atualizar_planilha.py`, a constante `DELAY_DIAS = 3`.
- **Refazer um intervalo:** `python3 atualizar_planilha.py --range 2026-06-16 2026-06-23 --start-row 60`
- **Ver o log:** `tail -30 log.txt`

---

## Bastidores (referência)
- **Onde roda:** VPS, via cron, 07:30 BRT. Arquivos: `atualizar_planilha.py`, `.env` (token IG,
  chmod 600), `gdrive_sa.json` (chave Google, chmod 600). Log em `log.txt`.
- **Token do Instagram:** renova-se sozinho a cada execução (regravado no `.env`). É um token de
  API (independe da senha da conta).
- **Grava no mesmo arquivo/link** do Drive (Drive API `files.update`, conta de serviço
  `planilha-writer@meta-map-500519-n1.iam.gserviceaccount.com`). Nunca cria cópia. Deduplica por link.
- **GitHub Actions (`planilha.yml`): DESATIVADO.** O cron do GitHub não dispara de forma confiável
  neste repo; o VPS é o executor. (O código aqui é só versionamento/backup.)
- **Tarefa local do Windows e leitura por navegador (Playwright/`ig_state.json`/.bat de login):
  REMOVIDAS** — a leitura logada travava a conta. Não reativar.

## Se algo der errado
- No VPS: `tail -30 /root/automacoes/planilha/log.txt`.
- Token vencido: renova sozinho; se ficar >60 dias parado, gerar novo token IG e regravar no
  `.env` do VPS.
- Planilha movida/renomeada no Drive muda o `fileId` → avisar o dev.
