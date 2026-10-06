# IPTV Organizer Pro

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Servidor FastAPI para organizar, cachear e expor conteúdo IPTV (filmes, séries e canais) a partir de um provedor Xtream Codes, com paginação, cache em disco e rotas de metadados por ID.

## Features principais

- Acesso a conteúdo IPTV via M3U + API Xtream
- Cache local com TTL de 1 hora para a lista e 24 horas para metadados por ID
- Paginação em filmes, séries, canais e busca
- Download paralelo com Range requests para acelerar a atualização do cache
- Parser robusto do M3U com limpeza de títulos e extração do ID do provedor
- API leve para clientes e apps frontends
- Compatibilidade com Termux/Android ARM64 e VPS Linux
- Auto-refresh em background para manter o índice atualizado sem downtime

## Estrutura do projeto

```text
Server/
├── main.py
├── config.py
├── parser.py
├── downloader.py
├── info.py
├── requirements.txt
├── .gitignore
├── .env.example
├── Procfile
├── iptv.service
├── README.md
├── LICENSE
├── docs/
│   └── DEPLOY_VPS.md
├── .vscode/
│   └── settings.json
└── cache/
    ├── playlist.m3u
    ├── meta.json
    ├── index.json
    └── info/
```

## Requisitos

- Python 3.11+
- pip
- Git
- FastAPI + Uvicorn
- httpx
- aiofiles

> Não use `uvicorn[standard]` em ambientes ARM/Termux por incompatibilidades de build.

## Como rodar localmente

### 1) Clone o projeto

```bash
git clone https://github.com/copa-bhs/servervenuscine.git
cd servervenuscine
```

### 2) Crie um ambiente virtual

```bash
python -m venv .venv
source .venv/bin/activate
```

No Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3) Instale as dependências

```bash
pip install -r requirements.txt
```

### 4) Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` com os valores reais do seu provedor IPTV.

### 5) Rode o projeto

```bash
python main.py
```

Ou em modo de desenvolvimento:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Variáveis de ambiente

Arquivo `.env` (nunca versionado):

```env
IPTV_URL=https://kixar.xyz/get.php?username=SEU_USUARIO&password=SUA_SENHA&type=m3u_plus&output=ts
IPTV_USERNAME=SEU_USUARIO
IPTV_PASSWORD=SUA_SENHA
IPTV_HOST=http://kixar.xyz:80
USER_AGENT=VLC/3.0.20 LibVLC/3.0.20
CACHE_TTL=3600
PORT=8000
```

## Endpoints principais

### Base

```text
GET /
```

### Status do cache

```text
GET /status
```

### Forçar refresh

```text
POST /refresh
```

### Filmes

```text
GET /filmes?page=1&size=30
GET /filmes?categoria=Filmes&page=1&size=30
```

### Séries

```text
GET /series?page=1&size=30
GET /series?categoria=Series&page=1&size=30
```

### Canais

```text
GET /canais?page=1&size=50
```

### Busca

```text
GET /buscar?q=acao&tipo=filme&page=1&size=30
GET /buscar?q=the&tipo=serie&page=1&size=20
```

### Categorias

```text
GET /categorias
```

### Metadados por ID

```text
GET /info/filme/2127
GET /info/serie/4521
```

## Deploy em VPS

O guia completo está em [docs/DEPLOY_VPS.md](docs/DEPLOY_VPS.md).

Resumo:

1. Atualizar o sistema
2. Instalar Python, Python venv, git, ufw
3. Clonar o repositório
4. Criar virtualenv e instalar dependências
5. Configurar `.env`
6. Testar manualmente
7. Instalar o serviço systemd com `iptv.service`
8. Garantir firewall e logs

## Deploy em Railway / Render

Use o arquivo [Procfile](Procfile):

```text
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

No Railway ou Render, defina a variável `PORT` automaticamente e mantenha o projeto como um serviço web Python.

## Licença

Este projeto está licenciado sob a licença MIT. Consulte [LICENSE](LICENSE).

---

Desenvolvido para servir conteúdo IPTV de forma organizada, resiliente e com cache em runtime.

