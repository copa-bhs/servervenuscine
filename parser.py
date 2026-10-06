import re
import hashlib
from urllib.parse import urlparse

ATTR_RE = re.compile(r'([a-zA-Z0-9_\-]+)="([^"]*)"')
YEAR_RE = re.compile(r'\b(19\d{2}|20\d{2})\b')
EPISODE_RE = re.compile(r'\s*S(\d+)\s*[E\xd7x]\s*(\d+)', re.I)


# ==========================================================
# PARSER M3U CORRIGIDO (respeita aspas)
# ==========================================================
def _split_name_from_extinf(line: str) -> str:
    """
    Pega o nome do filme/série do #EXTINF.
    O nome é o texto DEPOIS da ÚLTIMA vírgula que NÃO está
    dentro de aspas duplas.
    """
    in_quotes = False
    last_comma = -1

    for i, ch in enumerate(line):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == ',' and not in_quotes:
            last_comma = i

    if last_comma == -1:
        return ""
    return line[last_comma + 1:].strip()


def parse_extinf(line: str) -> dict:
    """Extrai atributos + nome limpo de uma linha #EXTINF."""
    attrs = dict(ATTR_RE.findall(line))

    # nome vem depois da última vírgula fora de aspas
    name = _split_name_from_extinf(line)

    # fallback: se ficou vazio, usa tvg-name
    if not name:
        name = attrs.get("tvg-name", "").strip()

    attrs["name"] = name
    return attrs


def parse_m3u(content: str) -> list:
    items = []
    pending = None
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            pending = parse_extinf(line)
        elif line.startswith("#"):
            continue
        elif pending is not None:
            pending["url"] = line
            items.append(pending)
            pending = None
    return items


# ==========================================================
# CLASSIFICAÇÃO
# ==========================================================
def classify(item: dict) -> str:
    path = urlparse(item.get("url", "")).path
    if "/movie/" in path:
        return "movie"
    if "/series/" in path:
        return "series"
    if "/live/" in path:
        return "live"

    group = (item.get("group-title") or "").lower()
    if any(k in group for k in ("filme", "movie", "vod", "lançamento")):
        return "movie"
    if any(k in group for k in ("serie", "série", "series", "novela", "anime")):
        return "series"
    if any(k in group for k in ("tv", "canal", "channel", "aberto", "fechado")):
        return "live"
    return "live"


# ==========================================================
# LIMPEZA DE NOME
# ==========================================================
def clean_name(name: str) -> str:
    """
    Deixa o título 100% limpo:
      - remove ano entre parênteses
      - remove sufixos de episódio (S01E02)
      - remove hashtags, pipes, hífens soltos
      - remove espaços duplos
    """
    if not name:
        return ""

    t = name

    # remove tags de episódio tipo S01E02 / S01 E02 / S01xE02
    t = EPISODE_RE.sub(" ", t)

    # remove ano entre parênteses: (2024)
    t = re.sub(r'\(\s*(19|20)\d{2}\s*\)', ' ', t)

    # remove hashtags no início/meio (#HD, #4K, #LANÇAMENTO)
    t = re.sub(r'#\S+', ' ', t)

    # remove tags técnicas comuns entre colchetes [HD] [4K] [DUB]
    t = re.sub(r'\[[^\]]*\]', ' ', t)

    # remove prefixos tipo "FILME:", "SERIE -", "|"
    t = re.sub(r'^\s*(filme|série|serie|movie|vod)\s*[:\-–—|]\s*', '', t, flags=re.I)

    # remove pipe solto
    t = t.replace("|", " ")

    # normaliza espaços e limpa pontas soltas
    t = re.sub(r'\s+', ' ', t)
    t = t.strip(" -–—_.,;:")

    return t


# ==========================================================
# ID DO PROVEDOR (extraído da URL Xtream Codes)
# ==========================================================
def extract_provider_id(url: str) -> str | None:
    """
    Extrai o ID numérico da URL:
      http://kixar.xyz:80/movie/VenusCine/sy38hdca/2127.mp4  ->  "2127"
      http://kixar.xyz:80/series/VenusCine/sy38hdca/4521.mkv ->  "4521"
      http://kixar.xyz:80/live/VenusCine/sy38hdca/15.ts      ->  "15"
    """
    if not url:
        return None
    m = re.search(r'/(?:movie|series|live)/[^/]+/[^/]+/(\d+)', url)
    if m:
        return m.group(1)
    # fallback: último número do path
    m = re.search(r'/(\d+)(?:\.[a-z0-9]+)?$', url, re.I)
    return m.group(1) if m else None


def extract_year(text: str):
    if not text:
        return None
    m = YEAR_RE.search(text)
    return int(m.group(1)) if m else None


def stable_id(item: dict) -> str:
    """ID estável interno (não confundir com o id do provedor)."""
    if item.get("tvg-id"):
        return item["tvg-id"]
    raw = f'{item.get("name","")}|{item.get("url","")}'
    return hashlib.md5(raw.encode()).hexdigest()[:16]


# ==========================================================
# BUILDERS
# ==========================================================
def build_movie(item: dict) -> dict:
    raw_name = item.get("name", "")
    titulo = clean_name(raw_name)
    url = item.get("url")

    return {
        "id": extract_provider_id(url) or stable_id(item),
        "titulo": titulo,
        "capa": item.get("tvg-logo") or None,
        "ano": extract_year(raw_name),
        "categoria": item.get("group-title", "Sem categoria"),
        "tipo": "filme",
        "url": url,
    }


def build_series_episode(item: dict) -> dict:
    raw_name = item.get("name", "")
    titulo = clean_name(raw_name)
    url = item.get("url")

    m = EPISODE_RE.search(raw_name)
    season = int(m.group(1)) if m else None
    episode = int(m.group(2)) if m else None

    return {
        "id": extract_provider_id(url) or stable_id(item),
        "titulo": titulo,
        "titulo_episodio": raw_name.strip(),
        "capa": item.get("tvg-logo") or None,
        "ano": extract_year(raw_name),
        "categoria": item.get("group-title", "Sem categoria"),
        "tipo": "serie",
        "temporada": season,
        "episodio": episode,
        "url": url,
    }


def build_channel(item: dict) -> dict:
    raw_name = item.get("name", "")
    url = item.get("url")
    return {
        "id": extract_provider_id(url) or stable_id(item),
        "titulo": clean_name(raw_name) or raw_name.strip(),
        "capa": item.get("tvg-logo") or None,
        "categoria": item.get("group-title", "Sem categoria"),
        "tipo": "canal",
        "tvg_id": item.get("tvg-id"),
        "url": url,
    }


def group_series(episodes: list) -> list:
    """Agrupa episódios por série (usa título limpo)."""
    groups = {}
    for ep in episodes:
        key = ep["titulo"] or ep["titulo_episodio"]

        if key not in groups:
            groups[key] = {
                "id": ep["id"],
                "titulo": key,
                "capa": ep["capa"],
                "ano": ep["ano"],
                "categoria": ep["categoria"],
                "tipo": "serie",
                "total_episodios": 0,
                "temporadas": set(),
                "episodios": [],
            }

        groups[key]["episodios"].append({
            "id": ep["id"],
            "titulo": ep["titulo_episodio"],
            "temporada": ep["temporada"],
            "episodio": ep["episodio"],
            "url": ep["url"],
        })
        groups[key]["total_episodios"] += 1
        if ep["temporada"]:
            groups[key]["temporadas"].add(ep["temporada"])

    result = []
    for g in groups.values():
        g["temporadas"] = sorted(g["temporadas"])
        g["total_temporadas"] = len(g["temporadas"])
        # ordena episódios por temporada + número
        g["episodios"].sort(
            key=lambda e: (e["temporada"] or 0, e["episodio"] or 0)
        )
        result.append(g)
    return result


# ==========================================================
# ÍNDICE
# ==========================================================
def build_index(raw_items: list) -> dict:
    movies, series_eps, channels = [], [], []
    for it in raw_items:
        kind = classify(it)
        if kind == "movie":
            movies.append(build_movie(it))
        elif kind == "series":
            series_eps.append(build_series_episode(it))
        else:
            channels.append(build_channel(it))

    series = group_series(series_eps)

    movies.sort(key=lambda x: (x["titulo"] or "").lower())
    series.sort(key=lambda x: (x["titulo"] or "").lower())
    channels.sort(key=lambda x: (x["titulo"] or "").lower())

    return {
        "filmes": movies,
        "series": series,
        "canais": channels,
        "stats": {
            "total_filmes": len(movies),
            "total_series": len(series),
            "total_episodios": len(series_eps),
            "total_canais": len(channels),
        },
    }