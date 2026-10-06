import os
from pathlib import Path

# Carrega variáveis do arquivo .env quando ele existir.
# Isso permite manter o projeto compatível com o Termux e com deploy em VPS,
# sem exigir dependências extras como python-dotenv.
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"


def load_env_file() -> None:
    """Lê o .env e define valores padrão sem sobrescrever variáveis já existentes."""
    if not ENV_FILE.exists():
        return

    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()

# Credenciais do provedor
IPTV_USERNAME = os.getenv("IPTV_USERNAME", "VenusCine")
IPTV_PASSWORD = os.getenv("IPTV_PASSWORD", "sy38hdca")
IPTV_HOST = os.getenv("IPTV_HOST", "http://kixar.xyz:80").rstrip("/")

# URL M3U do provedor. Mantém compatibilidade para quem já usa valores fixos.
IPTV_URL = os.getenv(
    "IPTV_URL",
    f"{IPTV_HOST}/get.php?username={IPTV_USERNAME}&password={IPTV_PASSWORD}&type=m3u_plus&output=ts",
)

# User-Agent de player IPTV (evita 403)
USER_AGENT = os.getenv("USER_AGENT", "VLC/3.0.20 LibVLC/3.0.20")

# TTL do cache em segundos (1h)
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))

# Porta padrão do servidor
PORT = int(os.getenv("PORT", "8000"))

# Paginação padrão
DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 200

# Download paralelo
DOWNLOAD_CHUNK_SIZE = 1024 * 256       # 256 KB por chunk
DOWNLOAD_WORKERS = 8                    # conexões paralelas
DOWNLOAD_CONNECT_TIMEOUT = 15
DOWNLOAD_READ_TIMEOUT = 60

# Diretórios de cache
BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

M3U_FILE = CACHE_DIR / "playlist.m3u"
META_FILE = CACHE_DIR / "meta.json"
INDEX_FILE = CACHE_DIR / "index.json"      # índice leve de metadados

# Imagens de capa (fallback quando o M3U não traz)
DEFAULT_MOVIE_COVER = "https://via.placeholder.com/300x450?text=Sem+Capa"
DEFAULT_SERIES_COVER = "https://via.placeholder.com/300x450?text=Serie"