"""
build.py — Gera data.json (e acumula follower_history.json) para o Dashboard
de Performance do Instagram @recorrenciadehonorarios.

Roda no GitHub Actions todo dia às 11:00 UTC (08:00 BRT). Não precisa de servidor:
o resultado é um arquivo estático servido pelo GitHub Pages.

Melhorias sobre o plano original:
- Insights vêm na MESMA chamada da mídia (expansão de campo) → sem N+1.
- Usa `views` (substitui video_view_count, descontinuado) e `total_interactions`.
- Médias incluem o zero (só descartam None) → não inflam os números.
- Eng. rate real = total_interactions / reach.
- Fuso BRT explícito no carimbo e na data do histórico.
- Retry com backoff; mantém o último data.json bom se a API falhar.
- Renova o token a cada execução e (se GH_PAT estiver configurado) regrava
  o secret no GitHub → automação realmente sem manutenção.
"""
import os
import sys
import csv
import json
import time
import base64
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone

import requests

try:
    from zoneinfo import ZoneInfo
    BRT = ZoneInfo("America/Sao_Paulo")
except Exception:  # fallback se tzdata ausente
    BRT = timezone(timedelta(hours=-3))

# ─── CONFIG ──────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).resolve().parent
DATA_FILE    = SCRIPT_DIR / "data.json"
HISTORY_FILE = SCRIPT_DIR / "follower_history.json"
CSV_FILE     = SCRIPT_DIR / "historico_metricas.csv"   # 1 linha por dia, p/ Excel/Sheets
DB_FILE      = SCRIPT_DIR / "historico.db"             # banco SQLite — histórico detalhado p/ gráficos
TOKEN_FILE   = SCRIPT_DIR / "token.txt"                # persistência local do token (VPS)


def _load_token() -> str:
    """Token vem do env (GitHub Actions) ou de token.txt (VPS)."""
    t = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    if t:
        return t
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    return ""


TOKEN       = _load_token()
API_VERSION = os.getenv("META_API_VERSION", "").strip()       # vazio = última versão
BASE_URL    = "https://graph.instagram.com" + (f"/{API_VERSION}" if API_VERSION else "")

DAYS         = 30
HISTORY_KEEP = 35

# Métricas válidas para Reels E Carrosséis na mesma chamada (testado na conta).
# `impressions` foi descontinuado a nível de mídia → não pedir (quebraria a chamada).
INSIGHT_METRICS = "views,reach,total_interactions,saved,shares"

STOPWORDS = {
    "para", "como", "isso", "esse", "essa", "aqui", "voce", "você", "mais",
    "muito", "muitos", "porque", "quando", "sobre", "seu", "sua", "dos", "das",
    "que", "com", "uma", "por", "não", "nao", "ele", "ela", "mas", "tem",
}


# ─── HTTP COM RETRY ──────────────────────────────────────────────────────────
def ig_get(url_or_endpoint: str, params: dict = None, retries: int = 3) -> dict:
    """GET autenticado na Instagram Graph API, com retry e backoff."""
    if url_or_endpoint.startswith("http"):
        url = url_or_endpoint            # paginação já traz URL completa
        p = dict(params or {})
    else:
        url = f"{BASE_URL}/{url_or_endpoint}"
        p = dict(params or {})
        p["access_token"] = TOKEN

    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=p, timeout=30)
            if r.status_code == 200:
                return r.json()
            # 4xx que não seja rate-limit não adianta repetir
            if r.status_code < 500 and r.status_code != 429:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            last_err = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except requests.RequestException as e:
            last_err = e
        time.sleep(2 ** attempt)         # 1s, 2s, 4s
    raise last_err


# ─── COLETA ──────────────────────────────────────────────────────────────────
def fetch_profile() -> dict:
    return ig_get("me", {
        "fields": "id,username,followers_count,follows_count,media_count,profile_picture_url"
    })


def parse_insights(item: dict) -> dict:
    """Extrai as métricas de insights que vieram embutidas na mídia."""
    out = {}
    block = (item.get("insights") or {}).get("data") or []
    for metric in block:
        vals = metric.get("values") or [{}]
        out[metric.get("name")] = vals[0].get("value")
    return out


def fetch_media_30d() -> list:
    """Mídia dos últimos 30 dias COM insights na mesma chamada (sem N+1)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS)
    fields = (
        "id,caption,media_type,media_product_type,timestamp,"
        "like_count,comments_count,permalink,thumbnail_url,media_url,"
        f"insights.metric({INSIGHT_METRICS})"
    )
    items, params = [], {"fields": fields, "limit": 50}
    url = "me/media"

    while True:
        data = ig_get(url, params)
        for item in data.get("data", []):
            ts = item.get("timestamp", "")
            try:
                when = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z")
            except ValueError:
                when = None
            if when and when < cutoff:
                return items          # API vem do mais novo p/ mais antigo
            items.append(item)
        nxt = (data.get("paging") or {}).get("next")
        if not nxt:
            return items
        url, params = nxt, None       # a URL de next já tem token + fields


# ─── AGREGAÇÃO ───────────────────────────────────────────────────────────────
def avg(items: list, key: str) -> float:
    """Média que descarta apenas None (mantém o zero — não infla)."""
    vals = [i[key] for i in items if i.get(key) is not None]
    return round(sum(vals) / len(vals), 1) if vals else 0


def eng_rate(item: dict) -> float:
    """Eng. rate = (curtidas + comentários + salvamentos + compartilhamentos) / alcance × 100."""
    reach = item.get("reach")
    if not reach:
        return 0
    inter = ((item.get("like_count") or 0) + (item.get("comments_count") or 0)
             + (item.get("saved") or 0) + (item.get("shares") or 0))
    return round(inter / reach * 100, 1)


def keywords(caption: str, n: int = 3) -> list:
    if not caption:
        return ["sem legenda"]
    tags = [h[1:] for h in caption.split() if h.startswith("#")][:n]
    if tags:
        return tags
    words = []
    for w in caption.split():
        w = w.strip(".,;:!?()\"'—…").lower()
        if len(w) > 4 and w not in STOPWORDS and not w.startswith("@"):
            words.append(w)
        if len(words) >= n:
            break
    return words or ["—"]


def thumb_of(item: dict) -> str:
    if item.get("media_type") == "VIDEO":
        return item.get("thumbnail_url") or item.get("media_url") or ""
    return item.get("media_url") or ""


def trim(item: dict) -> dict:
    return {
        "media_type": item.get("media_type"),
        "thumb": thumb_of(item),
        "permalink": item.get("permalink"),
        "views": item.get("views") or 0,
        "like_count": item.get("like_count") or 0,
        "comments_count": item.get("comments_count") or 0,
        "saved": item.get("saved"),
        "shares": item.get("shares"),
        "reach": item.get("reach"),
        "eng_rate": item.get("eng_rate"),
        "keywords": keywords(item.get("caption") or ""),
    }


def section(items: list) -> dict:
    return {
        "count": len(items),
        "avg_views": avg(items, "views"),
        "avg_reach": avg(items, "reach"),
        "avg_impressions": None,                 # descontinuado pela Meta
        "avg_likes": avg(items, "like_count"),
        "avg_comments": avg(items, "comments_count"),
        "avg_saves": avg(items, "saved"),
        "avg_shares": avg(items, "shares"),
        "avg_eng_rate": avg(items, "eng_rate"),
    }


def build_data() -> dict:
    profile = fetch_profile()
    media = fetch_media_30d()

    reels, carousels, posts = [], [], []
    for it in media:
        ins = parse_insights(it)
        it["views"]  = ins.get("views")
        it["reach"]  = ins.get("reach")
        it["saved"]  = ins.get("saved")
        it["shares"] = ins.get("shares")
        it["total_interactions"] = ins.get("total_interactions")
        it["eng_rate"] = eng_rate(it)

        kind = it.get("media_product_type")
        if kind == "REELS" or it.get("media_type") == "VIDEO":
            reels.append(it)
        elif it.get("media_type") == "CAROUSEL_ALBUM":
            carousels.append(it)
        else:
            posts.append(it)

    all_media = reels + carousels + posts

    # histórico de seguidores (acumulado no repo)
    history = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            history = []
    today = datetime.now(BRT).strftime("%Y-%m-%d")
    followers = profile.get("followers_count", 0)
    if not history or history[-1].get("date") != today:
        history.append({"date": today, "count": followers})
    else:
        history[-1]["count"] = followers          # atualiza o do dia
    history = history[-HISTORY_KEEP:]
    write_json(HISTORY_FILE, history)

    top5 = lambda lst: [trim(i) for i in sorted(lst, key=lambda x: x.get("views") or 0, reverse=True)[:5]]

    result = {
        "profile": profile,
        "updated_at": datetime.now(BRT).strftime("%d/%m/%Y às %H:%M"),
        "account_stats": {
            "followers": followers,
            "total_posts_30d": len(all_media),
            "avg_likes": avg(all_media, "like_count"),
            "avg_comments": avg(all_media, "comments_count"),
            "avg_saves": avg(all_media, "saved"),
            "avg_shares": avg(all_media, "shares"),
            "avg_reach": avg(all_media, "reach"),
            "avg_impressions": None,
        },
        "reels_stats": section(reels),
        "carousels_stats": section(carousels),
        "posts_count": len(posts),
        "top5_reels": top5(reels),
        "top5_carousels": top5(carousels),
        "follower_history": history,
    }

    # histórico detalhado no banco SQLite (não derruba o build se falhar)
    try:
        save_db(result, all_media)
    except Exception as e:
        print(f"  (aviso) falha ao salvar no banco SQLite: {e}")

    return result


# ─── TOKEN: RENOVAÇÃO AUTOMÁTICA ─────────────────────────────────────────────
def refresh_token():
    """Estende o token por +60 dias e, se houver GH_PAT, regrava o secret."""
    try:
        resp = ig_get("refresh_access_token", {
            "grant_type": "ig_refresh_token", "access_token": TOKEN
        })
    except Exception as e:
        print(f"  (aviso) não foi possível renovar o token agora: {e}")
        return
    new_token = resp.get("access_token")
    if not new_token or new_token == TOKEN:
        print("  Token já está fresco (nada a fazer).")
        return
    print(f"  Token renovado (expira em ~{resp.get('expires_in', 0)//86400} dias).")
    # VPS: persiste no arquivo local. GitHub Actions: persiste no secret (via GH_PAT).
    if not os.getenv("INSTAGRAM_ACCESS_TOKEN"):
        try:
            TOKEN_FILE.write_text(new_token, encoding="utf-8")
            print("  Token salvo em token.txt.")
        except Exception as e:
            print(f"  (aviso) falha ao salvar token.txt: {e}")
    if os.getenv("GH_PAT"):
        update_github_secret("INSTAGRAM_ACCESS_TOKEN", new_token)


def update_github_secret(name: str, value: str):
    """Regrava um secret do repositório via API (precisa de GH_PAT + GH_REPO)."""
    pat, repo = os.getenv("GH_PAT", "").strip(), os.getenv("GH_REPO", "").strip()
    if not pat or not repo:
        print("  (info) GH_PAT/GH_REPO ausentes — atualize o token manualmente "
              "no painel de Secrets antes de ~55 dias.")
        return
    try:
        from nacl import encoding, public
    except ImportError:
        print("  (aviso) PyNaCl ausente — não foi possível regravar o secret.")
        return
    h = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}
    pk = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=h, timeout=30).json()
    sealed = public.SealedBox(public.PublicKey(pk["key"].encode(), encoding.Base64Encoder()))
    enc = base64.b64encode(sealed.encrypt(value.encode())).decode()
    r = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{name}",
        headers=h, json={"encrypted_value": enc, "key_id": pk["key_id"]}, timeout=30)
    print("  Secret atualizado no GitHub." if r.status_code in (201, 204)
          else f"  (aviso) falha ao gravar secret: HTTP {r.status_code}")


# ─── HISTÓRICO EM CSV (para Excel / Google Sheets) ───────────────────────────
CSV_HEADER = [
    "data", "seguidores", "seguindo", "total_publicacoes", "posts_30d",
    "reels_qtd", "carrosseis_qtd", "posts_qtd",
    "reels_views_med", "reels_alcance_med", "reels_eng_med",
    "reels_curtidas_med", "reels_comentarios_med", "reels_salvos_med", "reels_compart_med",
    "carrosseis_views_med", "carrosseis_alcance_med", "carrosseis_eng_med",
    "carrosseis_curtidas_med", "carrosseis_comentarios_med", "carrosseis_salvos_med", "carrosseis_compart_med",
    "geral_curtidas_med", "geral_comentarios_med", "geral_salvos_med", "geral_compart_med", "geral_alcance_med",
    "top_reel_views", "top_reel_link", "top_carrossel_views", "top_carrossel_link",
]


def append_csv(data: dict):
    """Anexa (ou atualiza) a linha do dia no histórico em CSV — idempotente."""
    r, c, a = data["reels_stats"], data["carousels_stats"], data["account_stats"]
    p = data["profile"]
    tr = data["top5_reels"][0] if data["top5_reels"] else {}
    tc = data["top5_carousels"][0] if data["top5_carousels"] else {}
    today = datetime.now(BRT).strftime("%Y-%m-%d")
    row = [today, p.get("followers_count", 0), p.get("follows_count", 0),
           p.get("media_count", 0), a["total_posts_30d"],
           r["count"], c["count"], data["posts_count"],
           r["avg_views"], r["avg_reach"], r["avg_eng_rate"],
           r["avg_likes"], r["avg_comments"], r["avg_saves"], r["avg_shares"],
           c["avg_views"], c["avg_reach"], c["avg_eng_rate"],
           c["avg_likes"], c["avg_comments"], c["avg_saves"], c["avg_shares"],
           a["avg_likes"], a["avg_comments"], a["avg_saves"], a["avg_shares"], a["avg_reach"],
           tr.get("views", 0), tr.get("permalink", ""),
           tc.get("views", 0), tc.get("permalink", "")]

    rows = []
    if CSV_FILE.exists():
        with CSV_FILE.open(encoding="utf-8", newline="") as f:
            rows = [r for r in csv.reader(f) if r]
    if not rows:
        rows = [CSV_HEADER]
    row = [str(x) for x in row]
    if len(rows) > 1 and rows[-1][0] == today:
        rows[-1] = row                      # já rodou hoje → atualiza a linha
    else:
        rows.append(row)
    with CSV_FILE.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)


# ─── HISTÓRICO EM BANCO SQLITE (para gráficos e comparativos futuros) ─────────
def save_db(data: dict, all_media: list):
    """Grava o snapshot do dia no SQLite — idempotente (REPLACE por data/post).

    Duas tabelas:
      • daily_snapshot  — 1 linha por dia, todas as métricas macro (base p/ gráficos)
      • media_snapshot  — métricas de cada post, capturadas dia a dia (análise profunda)
    """
    p = data["profile"]
    a = data["account_stats"]
    r = data["reels_stats"]
    c = data["carousels_stats"]
    today = datetime.now(BRT).strftime("%Y-%m-%d")
    now   = datetime.now(BRT).strftime("%Y-%m-%d %H:%M:%S")

    con = sqlite3.connect(DB_FILE)
    try:
        cur = con.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS daily_snapshot (
            date TEXT PRIMARY KEY, captured_at TEXT,
            followers INTEGER, follows INTEGER, media_count INTEGER,
            posts_30d INTEGER, reels_count INTEGER, carrosseis_count INTEGER, posts_count INTEGER,
            acct_avg_likes REAL, acct_avg_comments REAL, acct_avg_saves REAL,
            acct_avg_shares REAL, acct_avg_reach REAL,
            reels_avg_views REAL, reels_avg_reach REAL, reels_avg_eng REAL, reels_avg_likes REAL,
            reels_avg_comments REAL, reels_avg_saves REAL, reels_avg_shares REAL,
            carrs_avg_views REAL, carrs_avg_reach REAL, carrs_avg_eng REAL, carrs_avg_likes REAL,
            carrs_avg_comments REAL, carrs_avg_saves REAL, carrs_avg_shares REAL
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS media_snapshot (
            date TEXT, media_id TEXT, media_type TEXT, product_type TEXT,
            posted_at TEXT, permalink TEXT, caption TEXT,
            views INTEGER, reach INTEGER, likes INTEGER, comments INTEGER,
            saved INTEGER, shares INTEGER, total_interactions INTEGER, eng_rate REAL,
            PRIMARY KEY (date, media_id)
        )""")

        cur.execute(
            "INSERT OR REPLACE INTO daily_snapshot VALUES "
            "(?,?, ?,?,?, ?,?,?,?, ?,?,?,?,?, ?,?,?,?,?,?,?, ?,?,?,?,?,?,?)",
            (today, now,
             p.get("followers_count"), p.get("follows_count"), p.get("media_count"),
             a["total_posts_30d"], r["count"], c["count"], data["posts_count"],
             a["avg_likes"], a["avg_comments"], a["avg_saves"], a["avg_shares"], a["avg_reach"],
             r["avg_views"], r["avg_reach"], r["avg_eng_rate"], r["avg_likes"],
             r["avg_comments"], r["avg_saves"], r["avg_shares"],
             c["avg_views"], c["avg_reach"], c["avg_eng_rate"], c["avg_likes"],
             c["avg_comments"], c["avg_saves"], c["avg_shares"]))

        for it in all_media:
            cap = (it.get("caption") or "").replace("\n", " ").strip()[:300]
            cur.execute(
                "INSERT OR REPLACE INTO media_snapshot VALUES (?,?,?,?, ?,?,?, ?,?,?,?,?,?,?,?)",
                (today, it.get("id"), it.get("media_type"), it.get("media_product_type"),
                 it.get("timestamp"), it.get("permalink"), cap,
                 it.get("views"), it.get("reach"), it.get("like_count"), it.get("comments_count"),
                 it.get("saved"), it.get("shares"), it.get("total_interactions"), it.get("eng_rate")))
        con.commit()
    finally:
        con.close()


# ─── IO ──────────────────────────────────────────────────────────────────────
def write_json(path: Path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)                    # escrita atômica


def main():
    if not TOKEN:
        print("ERRO: INSTAGRAM_ACCESS_TOKEN não definido.")
        sys.exit(1)
    print("→ Buscando dados do Instagram...")
    try:
        data = build_data()
        write_json(DATA_FILE, data)
        append_csv(data)
        a = data["account_stats"]
        print(f"✓ data.json gerado: {a['followers']} seguidores, "
              f"{a['total_posts_30d']} posts/30d "
              f"({data['reels_stats']['count']} reels, "
              f"{data['carousels_stats']['count']} carrosséis).")
    except Exception as e:
        print(f"✗ Falha ao gerar dados: {e}")
        if DATA_FILE.exists():
            print("  Mantendo o data.json anterior (último bom).")
            # não derruba o build: histórico/preview seguem com o dado antigo
            sys.exit(0)
        sys.exit(1)
    print("→ Renovando token...")
    refresh_token()
    print("Pronto.")


if __name__ == "__main__":
    main()
