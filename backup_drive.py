"""
backup_drive.py — Envia o historico.db (banco do dashboard) para o Google Drive.

Usa a MESMA técnica da planilha: files().update num arquivo PRÉ-EXISTENTE
(criado e compartilhado por você com a conta de serviço) — assim não esbarra
na cota de armazenamento das contas de serviço.

Config:
  • _backup_drive_id.txt  → ID do arquivo de destino no Drive (uma linha)
  • reaproveita a conta de serviço da planilha (gdrive_sa.json)

Roda no VPS, encadeado após o build.py (ver cron).
"""
import sys
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

HERE    = Path(__file__).resolve().parent
DB      = HERE / "historico.db"
ID_FILE = HERE / "_backup_drive_id.txt"
SA      = "/root/automacoes/planilha/gdrive_sa.json"   # conta de serviço da planilha


def main():
    if not ID_FILE.exists() or not ID_FILE.read_text(encoding="utf-8").strip():
        print("backup: _backup_drive_id.txt ausente/vazio — configure o ID do Drive.")
        return
    if not DB.exists():
        print("backup: historico.db não encontrado.")
        return

    file_id = ID_FILE.read_text(encoding="utf-8").strip()
    creds = service_account.Credentials.from_service_account_file(
        SA, scopes=["https://www.googleapis.com/auth/drive"])
    svc = build("drive", "v3", credentials=creds)
    media = MediaFileUpload(str(DB), mimetype="application/x-sqlite3", resumable=True)
    svc.files().update(fileId=file_id, media_body=media, supportsAllDrives=True).execute()
    print(f"backup: historico.db enviado ao Drive ({DB.stat().st_size} bytes).")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"backup: falha ao enviar ao Drive: {e}")
        sys.exit(0)   # nunca derruba a automação principal
