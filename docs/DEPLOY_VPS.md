# Deploy em VPS Ubuntu 22.04 / 24.04

Este guia mostra como subir o IPTV Organizer Pro em um VPS Linux e mantê-lo em execução 24/7 com systemd.

## 1) Requisitos mínimos

- 1 vCPU
- 1 GB de RAM
- 20 GB de SSD
- Ubuntu 22.04 ou 24.04
- acesso SSH com usuário sudo

## 2) Conectar ao servidor

```bash
ssh usuario@IP_DO_VPS
```

## 3) Atualizar o sistema

```bash
sudo apt update && sudo apt upgrade -y
```

## 4) Instalar dependências básicas

```bash
sudo apt install -y python3 python3-pip python3-venv git ufw curl
```

## 5) Criar usuário não-root (opcional, mas recomendado)

```bash
sudo adduser iptv
sudo usermod -aG sudo iptv
```

## 6) Clonar o repositório

```bash
cd /opt
sudo git clone https://github.com/copa-bhs/servervenuscine.git
sudo chown -R iptv:iptv /opt/servervenuscine
cd /opt/servervenuscine
```

## 7) Criar ambiente virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 8) Configurar .env

Crie um arquivo `.env` na raiz com as credenciais reais do provedor:

```bash
cp .env.example .env
nano .env
```

Preencha com valores reais, por exemplo:

```env
IPTV_URL=https://kixar.xyz/get.php?username=SEU_USUARIO&password=SUA_SENHA&type=m3u_plus&output=ts
IPTV_USERNAME=SEU_USUARIO
IPTV_PASSWORD=SUA_SENHA
IPTV_HOST=http://kixar.xyz:80
USER_AGENT=VLC/3.0.20 LibVLC/3.0.20
CACHE_TTL=3600
PORT=8000
```

> O arquivo `.env` nunca deve ser versionado.

## 9) Testar manualmente

```bash
source .venv/bin/activate
python main.py
```

Ou, para testar com Uvicorn diretamente:

```bash
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 10) Configurar o systemd

Copie o arquivo do serviço e ajuste o diretório do projeto:

```bash
sudo cp iptv.service /etc/systemd/system/
```

Edite se necessário:

```bash
sudo nano /etc/systemd/system/iptv.service
```

Recarregue o daemon:

```bash
sudo systemctl daemon-reload
sudo systemctl enable iptv
sudo systemctl start iptv
```

Verifique o status:

```bash
sudo systemctl status iptv
```

## 11) Configurar firewall

```bash
sudo ufw allow 8000/tcp
sudo ufw enable
```

## 12) Nginx como reverse proxy (opcional)

Se quiser expor a API em porta 80/443 com HTTPS, instale o Nginx:

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

Configure um bloco de servidor com proxy reverso para `http://127.0.0.1:8000`.

## 13) HTTPS com Certbot (opcional)

```bash
sudo certbot --nginx -d seu-dominio.com
```

## 14) Ver logs do serviço

```bash
sudo journalctl -u iptv -f
```

## 15) Atualizar o código no VPS

```bash
cd /opt/servervenuscine
sudo git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart iptv
```

## 16) Checklist Final

- serviço no ar com systemd
- `.env` com credenciais reais preenchidas
- cache local funcionando
- portas liberadas
- logs monitorados
- deploy estável 24/7

Se quiser, a próxima etapa pode ser configurar Nginx + HTTPS e automatizar o deploy com GitHub Actions.
