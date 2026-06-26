"""
coletar_views_split.py — Le o split de Views por tipo de publico (seguidores /
nao-seguidores) de cada Reel, abrindo a pagina de insights logado (Playwright
headless + sessao salva em ig_state.json). E "a mesma tela" que o Rodrigo olha.

Funcao principal: split_de_reels(shortcodes) -> {shortcode: {...}}
Uso direto p/ teste: python coletar_views_split.py DZ8GFuxp55t [outro...]
"""
import re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

PASTA = Path(__file__).parent
STATE = PASTA / "ig_state.json"
ALFA = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'

def shortcode_de_link(link):
    m = re.search(r"/(?:reel|reels|p)/([A-Za-z0-9_-]+)", link or "")
    return m.group(1) if m else None

def pk_de_shortcode(sc):
    n = 0
    for c in sc:
        n = n * 64 + ALFA.index(c)
    return str(n)

def _num(s):
    return float(s.replace(".", "").replace(",", ".")) if "," in s else float(s)

def _parse(texto):
    """Extrai seg%, nao% e visualizacoes do texto renderizado da pagina."""
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    seg = nao = views = None
    for i, l in enumerate(linhas):
        prox = linhas[i + 1] if i + 1 < len(linhas) else ""
        if l.lower() == "seguidores" and "%" in prox:
            seg = _num(prox.replace("%", "").strip())
        elif l.lower() == "não seguidores" and "%" in prox:
            nao = _num(prox.replace("%", "").strip())
    # Visualizacoes: primeiro numero puro apos a(s) palavra(s) "Visualizações"
    for i, l in enumerate(linhas):
        if l.lower() == "visualizações":
            for j in range(i + 1, min(i + 4, len(linhas))):
                t = linhas[j].replace(".", "").replace(" ", "")
                if t.isdigit():
                    views = int(t); break
            if views is not None:
                break
    return seg, nao, views

def split_de_reels(shortcodes, headless=True):
    out = {}
    if not STATE.exists():
        raise SystemExit("ERRO: ig_state.json (sessao do Instagram) nao encontrado.")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(storage_state=str(STATE), locale="pt-BR")
        page = ctx.new_page()
        for sc in shortcodes:
            pk = pk_de_shortcode(sc)
            rec = {"shortcode": sc, "pk": pk, "seg_pct": None, "nao_pct": None,
                   "views": None, "erro": None}
            try:
                page.goto(f"https://www.instagram.com/insights/media/{pk}/", timeout=45000)
                seg = nao = None
                for _ in range(20):  # ate ~20s p/ o painel renderizar
                    time.sleep(1)
                    txt = page.inner_text("body")
                    if "accounts/login" in page.url:
                        rec["erro"] = "sessao_deslogada"; break
                    seg, nao, views = _parse(txt)
                    if seg is not None and nao is not None:
                        rec.update(seg_pct=seg, nao_pct=nao, views=views); break
                if rec["seg_pct"] is None and not rec["erro"]:
                    rec["erro"] = "nao_achou_split"
            except Exception as e:
                rec["erro"] = repr(e)[:120]
            out[sc] = rec
            time.sleep(2)  # gentil com o IG
        browser.close()
    return out

if __name__ == "__main__":
    scs = sys.argv[1:] or ["DZ8GFuxp55t"]
    res = split_de_reels(scs, headless=True)
    for sc, r in res.items():
        if r["erro"]:
            print(f"{sc}: ERRO -> {r['erro']}")
        else:
            vs = r["views"]; seg = r["seg_pct"]; nao = r["nao_pct"]
            abs_seg = round(vs * seg / 100) if vs and seg is not None else None
            abs_nao = round(vs * nao / 100) if vs and nao is not None else None
            print(f"{sc}: views={vs} | Seguidores {seg}% (~{abs_seg}) | "
                  f"Nao-seguidores {nao}% (~{abs_nao})")
