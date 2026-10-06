import asyncio
import json
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from config import (
    IPTV_URL, USER_AGENT, CACHE_TTL,
    M3U_FILE, META_FILE, INDEX_FILE,
    DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE,
)
from downloader import parallel_download
from parser import parse_m3u, build_index
from info import fetch_movie_info, fetch_series_info

app = FastAPI(title="IPTV Organizer Pro", version="2.0.0")

# índice em memória (carregado no startup, resposta instantânea)
_INDEX: dict = {}


# ==========================================================
# CACHE / ÍNDICE
# ==========================================================
def cache_valid() -> bool:
    if not M3U_FILE.exists() or not META_FILE.exists():
        return False
    try:
        meta = json.loads(META_FILE.read_text())
        return (time.time() - meta["timestamp"]) < CACHE_TTL
    except Exception:
        return False


def load_index_from_disk() -> bool:
    global _INDEX
    if INDEX_FILE.exists():
        try:
            _INDEX = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            return True
        except Exception:
            return False
    return False


def rebuild_index_from_m3u():
    """Reprocessa o M3U local e salva o índice."""
    global _INDEX
    content = M3U_FILE.read_text(encoding="utf-8", errors="ignore")
    raw = parse_m3u(content)
    _INDEX = build_index(raw)
    INDEX_FILE.write_text(
        json.dumps(_INDEX, ensure_ascii=False),
        encoding="utf-8",
    )


def _cleanup_temp_files(*paths: Path):
    for path in paths:
        if not path:
            continue
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass


async def auto_refresh_loop():
    """Atualiza o índice em background sem interromper as rotas."""
    global _INDEX

    while True:
        temp_m3u = M3U_FILE.with_name(f"{M3U_FILE.name}.new")
        temp_index = INDEX_FILE.with_name(f"{INDEX_FILE.name}.new")
        temp_meta = META_FILE.with_name(f"{META_FILE.name}.new")
        started_at = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[•] [{started_at}] Auto-refresh iniciado...")

        try:
            old_stats = _INDEX.get("stats", {})

            _cleanup_temp_files(temp_m3u, temp_index, temp_meta)

            print("[•] Baixando lista IPTV em paralelo (refresh background)...")
            t0 = time.time()
            result = await parallel_download(IPTV_URL, temp_m3u)
            dt = time.time() - t0
            print(f"[✓] Download refresh: {result} em {dt:.2f}s")

            print("[•] Processando M3U em índice temporário...")
            t1 = time.time()
            content = temp_m3u.read_text(encoding="utf-8", errors="ignore")
            raw_items = parse_m3u(content)
            new_index = build_index(raw_items)
            temp_index.write_text(json.dumps(new_index, ensure_ascii=False), encoding="utf-8")
            temp_meta.write_text(json.dumps({"timestamp": time.time()}), encoding="utf-8")

            # troca atômica em disco e depois troca a referência global
            temp_m3u.replace(M3U_FILE)
            temp_index.replace(INDEX_FILE)
            temp_meta.replace(META_FILE)

            _INDEX = new_index
            finished_at = time.strftime("%Y-%m-%d %H:%M:%S")
            new_stats = new_index.get("stats", {})
            print(f"[✓] [{finished_at}] Auto-refresh concluído em {time.time() - t1:.2f}s")
            print(f"[✓] Stats: {new_stats}")

            if old_stats and new_stats:
                delta = {
                    "filmes": new_stats.get("total_filmes", 0) - old_stats.get("total_filmes", 0),
                    "series": new_stats.get("total_series", 0) - old_stats.get("total_series", 0),
                    "episodios": new_stats.get("total_episodios", 0) - old_stats.get("total_episodios", 0),
                    "canais": new_stats.get("total_canais", 0) - old_stats.get("total_canais", 0),
                }
                print(f"[✓] Diferença de conteúdo: {delta}")

        except Exception as exc:
            _cleanup_temp_files(temp_m3u, temp_index, temp_meta)
            print(f"[!] Auto-refresh falhou: {exc}")

        await asyncio.sleep(CACHE_TTL)


async def fetch_and_rebuild(force: bool = False):
    """Baixa em paralelo e reconstrói o índice."""
    if not force and cache_valid() and load_index_from_disk():
        print("[✓] Cache válido — usando índice em disco.")
        return

    print("[•] Baixando lista IPTV em paralelo...")
    t0 = time.time()
    result = await parallel_download(IPTV_URL, M3U_FILE)
    dt = time.time() - t0
    print(f"[✓] Download: {result} em {dt:.2f}s")

    META_FILE.write_text(json.dumps({"timestamp": time.time()}))

    print("[•] Processando M3U...")
    t1 = time.time()
    rebuild_index_from_m3u()
    print(f"[✓] Índice pronto em {time.time()-t1:.2f}s")
    print(f"[✓] Stats: {_INDEX['stats']}")


# ==========================================================
# PAGINAÇÃO
# ==========================================================
def paginate(items: list, page: int, size: int) -> dict:
    total = len(items)
    total_pages = (total + size - 1) // size if size else 0
    start = (page - 1) * size
    end = start + size
    return {
        "page": page,
        "page_size": size,
        "total_items": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
        "items": items[start:end],
    }


# ==========================================================
# STARTUP
# ==========================================================
@app.on_event("startup")
async def startup():
    print("[•] Startup: verificando cache...")
    try:
        await fetch_and_rebuild(force=False)
    except Exception as e:
        print(f"[!] Startup falhou: {e}")

    print("[✓] Auto-refresh em background ativo.")
    asyncio.create_task(auto_refresh_loop())


# ==========================================================
# ROTAS BÁSICAS
# ==========================================================
@app.get("/")
def root():
    return {
        "service": "IPTV Organizer Pro",
        "endpoints": {
            "POST /refresh": "Força atualização do cache e índice",
            "GET  /status": "Estado do cache e estatísticas",
            "GET  /filmes?page=1&size=30": "Filmes paginados",
            "GET  /series?page=1&size=30": "Séries paginadas (resumo)",
            "GET  /canais?page=1&size=50": "Canais de TV paginados",
            "GET  /buscar?q=texto&tipo=filme|serie|canal": "Busca paginada",
            "GET  /categorias": "Lista de categorias disponíveis",
            "GET  /info/filme/{id}": "Metadados completos do filme",
            "GET  /info/serie/{id}": "Metadados completos da série + episódios",
        },
    }


@app.get("/status")
async def status():
    meta = {}
    if META_FILE.exists():
        try:
            meta = json.loads(META_FILE.read_text())
        except Exception:
            meta = {}
    idade = time.time() - meta.get("timestamp", 0) if meta else 0
    return {
        "cached": bool(meta),
        "age_seconds": int(idade),
        "ttl_seconds": CACHE_TTL,
        "expires_in": max(0, int(CACHE_TTL - idade)),
        "valid": idade < CACHE_TTL,
        "stats": _INDEX.get("stats", {}),
    }


@app.post("/refresh")
async def refresh():
    await fetch_and_rebuild(force=True)
    return {"ok": True, "stats": _INDEX.get("stats", {})}


# ==========================================================
# FILMES
# ==========================================================
@app.get("/filmes")
def listar_filmes(
    page: int = Query(1, ge=1),
    size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    categoria: str | None = None,
):
    if not _INDEX:
        raise HTTPException(503, "Índice ainda não carregado. Chame /refresh.")
    filmes = _INDEX.get("filmes", [])
    if categoria:
        filmes = [f for f in filmes if f["categoria"].lower() == categoria.lower()]
    return paginate(filmes, page, size)


# ==========================================================
# SÉRIES
# ==========================================================
@app.get("/series")
def listar_series(
    page: int = Query(1, ge=1),
    size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    categoria: str | None = None,
):
    if not _INDEX:
        raise HTTPException(503, "Índice ainda não carregado. Chame /refresh.")
    series = _INDEX.get("series", [])
    if categoria:
        series = [s for s in series if s["categoria"].lower() == categoria.lower()]

    # resumo (sem episódios, que são pesados)
    resumo = [{k: v for k, v in s.items() if k != "episodios"} for s in series]
    return paginate(resumo, page, size)


# ==========================================================
# CANAIS
# ==========================================================
@app.get("/canais")
def listar_canais(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
    categoria: str | None = None,
):
    if not _INDEX:
        raise HTTPException(503, "Índice ainda não carregado. Chame /refresh.")
    canais = _INDEX.get("canais", [])
    if categoria:
        canais = [c for c in canais if c["categoria"].lower() == categoria.lower()]
    return paginate(canais, page, size)


# ==========================================================
# BUSCA
# ==========================================================
@app.get("/buscar")
def buscar(
    q: str = Query(..., min_length=1),
    tipo: str | None = None,          # filme | serie | canal
    page: int = Query(1, ge=1),
    size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
):
    if not _INDEX:
        raise HTTPException(503, "Índice ainda não carregado. Chame /refresh.")
    q_low = q.lower()
    resultados = []

    if tipo in (None, "filme"):
        resultados += [
            f for f in _INDEX.get("filmes", [])
            if q_low in (f.get("titulo") or "").lower()
        ]
    if tipo in (None, "serie"):
        for s in _INDEX.get("series", []):
            if q_low in (s.get("titulo") or "").lower():
                resultados.append({k: v for k, v in s.items() if k != "episodios"})
    if tipo in (None, "canal"):
        resultados += [
            c for c in _INDEX.get("canais", [])
            if q_low in (c.get("titulo") or "").lower()
        ]

    return paginate(resultados, page, size)


# ==========================================================
# CATEGORIAS
# ==========================================================
@app.get("/categorias")
def categorias():
    cats = {"filmes": set(), "series": set(), "canais": set()}
    for f in _INDEX.get("filmes", []):
        cats["filmes"].add(f["categoria"])
    for s in _INDEX.get("series", []):
        cats["series"].add(s["categoria"])
    for c in _INDEX.get("canais", []):
        cats["canais"].add(c["categoria"])
    return {k: sorted(v) for k, v in cats.items()}


# ==========================================================
# INFORMAÇÕES VIA ID DO PROVEDOR
# ==========================================================
@app.get("/info/filme/{filme_id}")
async def info_filme(filme_id: str, force: bool = False):
    """
    Metadados completos de um filme via ID do provedor.
    Retorna: banner, capa, sinopse, ano, score, trailer,
    duração, qualidade, gênero, elenco, url_stream, etc.
    Cache de 24h por ID.
    """
    try:
        return await fetch_movie_info(filme_id, force=force)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, "Provedor recusou a requisição")
    except httpx.RequestError as e:
        raise HTTPException(502, f"Falha ao contatar o provedor: {e}")


@app.get("/info/serie/{serie_id}")
async def info_serie(serie_id: str, force: bool = False):
    """
    Metadados completos de uma série via ID do provedor.
    Retorna: banner, capa, sinopse, ano, score, trailer,
    temporadas e lista de episódios com URL de cada um.
    Cache de 24h por ID.
    """
    try:
        return await fetch_series_info(serie_id, force=force)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, "Provedor recusou a requisição")
    except httpx.RequestError as e:
        raise HTTPException(502, f"Falha ao contatar o provedor: {e}")


# ==========================================================
# START
# ==========================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)