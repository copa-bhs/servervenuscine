# Checklist final de deploy em VPS

## 1) Preparação do servidor

- [ ] Conectar ao VPS via SSH
- [ ] Atualizar sistema (`apt update && apt upgrade -y`)
- [ ] Instalar dependências mínimas:
  - [ ] `python3`, `python3-venv`, `python3-pip`, `git`, `curl`, `nginx`, `certbot`, `python3-certbot-nginx`
- [ ] Criar usuário para a aplicação, se necessário
- [ ] Configurar `ufw` e liberar portas:
  - [ ] `22/tcp` (SSH)
  - [ ] `80/tcp` (HTTP)
  - [ ] `443/tcp` (HTTPS)

## 2) Clonar e preparar o projeto

- [ ] `git clone https://github.com/copa-bhs/servervenuscine.git`
- [ ] `cd servervenuscine`
- [ ] `python3 -m venv .venv`
- [ ] `source .venv/bin/activate`
- [ ] `pip install -r requirements.txt`
- [ ] Copiar `.env.example` para `.env` e preencher valores reais
- [ ] Validar import do app: `python -c "import main; print('ok')"`
- [ ] Testar startup local: `uvicorn main:app --host 0.0.0.0 --port 8000`

## 3) Serviço systemd

- [ ] Criar o arquivo do serviço com base em `iptv.service`
- [ ] Ajustar `WorkingDirectory`, `ExecStart`, `User` e `EnvironmentFile`
- [ ] Habilitar o serviço:
  - [ ] `sudo systemctl daemon-reload`
  - [ ] `sudo systemctl enable iptv.service`
  - [ ] `sudo systemctl start iptv.service`
- [ ] Verificar status:
  - [ ] `sudo systemctl status iptv.service`
  - [ ] `sudo journalctl -u iptv.service -f`
- [ ] Confirmar que o app responde em `http://IP_DO_VPS:8000/status`

## 4) Nginx como proxy reverso

- [ ] Criar arquivo do site em `/etc/nginx/sites-available/iptv`
- [ ] Configurar upstream para `127.0.0.1:8000`
- [ ] Habilitar site:
  - [ ] `sudo ln -s /etc/nginx/sites-available/iptv /etc/nginx/sites-enabled/`
- [ ] Validar nginx: `sudo nginx -t`
- [ ] Reiniciar nginx: `sudo systemctl restart nginx`
- [ ] Confirmar domínio ou IP público acessando a API pelo proxy

## 5) HTTPS (Certbot)

- [ ] Registrar domínio e apontar DNS para o VPS
- [ ] Executar:
  - [ ] `sudo certbot --nginx -d seu-dominio.com`
- [ ] Verificar a renovação automática do certificado
- [ ] Validar acesso em HTTPS e redirecionamento HTTP→HTTPS

## 6) Monitoramento e manutenção

- [ ] Verificar logs diários (`journalctl` e `/var/log/nginx`)
- [ ] Validar `/status` e endpoints chave
- [ ] Ajustar `CACHE_TTL` e `PORT` se necessário
- [ ] Fazer backup do `.env`
- [ ] Configurar alertas simples de uptime e falha do serviço

## 7) Checklist de pronto para produção

- [ ] Serviço rodando em background com `systemd`
- [ ] Nginx conectado ao app em `127.0.0.1:8000`
- [ ] HTTPS ativo
- [ ] `.env` preenchido corretamente
- [ ] Logs funcionando
- [ ] Porta 80/443 liberadas no firewall
- [ ] Repositório GitHub conectado e push configurado
- [ ] Branch principal `main` com histórico de commits
