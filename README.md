# Monitoring und Incident Platform
**Modul 169 – Matteo und Jan | Berufsfachschule Uster 2026**

Eine Docker-basierte Monitoring- und Incident-Plattform mit eigenem Ticketsystem, Uptime-Monitoring und öffentlichem Zugriff via Cloudflare Tunnel.

---

## Container

| Container | Image | Eigenes Dockerfile |
|---|---|---|
| `uptime-kuma` | louislam/uptime-kuma:1 | Nein |
| `postgres` | postgres:16-alpine | Nein |
| `incident-app` | python:3.12-slim | **Ja** |
| `heartbeat-service` | alpine:3.19 | **Ja** |
| `nginx` | nginx:1.25-alpine | **Ja** |
| `cloudflared` | cloudflare/cloudflared | Nein |
| `cloudflared-kuma` | cloudflare/cloudflared | Nein |

---

## Voraussetzungen

- Docker und Docker Compose
- Linux (getestet auf Debian 12)
- offene Ports am besten 80

---

## Starten

```bash
# 1. Repository klonen
git clone https://github.com/DeJan-LE/monitoring-platform.git
cd monitoring-platform

# 2. .env anpassen
cp template.env .env
nano .env

# 3. Alle Container starten
docker compose up -d

# 4. Cloudflare URLs holen
docker compose logs cloudflared | grep trycloudflare.com
docker compose logs cloudflared-kuma | grep trycloudflare.com
```

---

## Erreichbarkeit

| Service | URL | lokale möglichkeit |
|---|---|---|
| Ticketsystem | Cloudflare URL aus logs cloudflared | HTTP://IP-adressevonVM:80
| Uptime Kuma | Cloudflare URL aus logs cloudflared-kuma | HTTP://IP-adressevonVM:3001

---

## .env Konfiguration

```env
# Datenbank
POSTGRES_DB=monitoring
POSTGRES_USER=monitor
POSTGRES_PASSWORD=changeme123

# Flask
SECRET_KEY=supergeheim123

# IT-Zugangscode (für Registrierung als IT-User)
IT_CODE=it_for_users26

# Mail (Gmail App-Passwort)
MAIL_USER=deine@gmail.com
MAIL_PASS=xxxx xxxx xxxx xxxx
MAIL_FROM=Incident System <deine@gmail.com>

# App URL (für Links in Mails)
APP_URL=http://localhost

# Heartbeat (Push-Key aus Uptime Kuma)
KUMA_HEARTBEAT_URL=http://uptime-kuma:3001/api/push/DEIN_KEY
HEARTBEAT_INTERVAL=60
```

---

## Nützliche Befehle

```bash
docker compose ps                          # Status aller Container
docker compose logs -f                     # Live-Logs
docker compose down                        # Stoppen (Volumes bleiben)
docker compose down -v                     # Stoppen + Volumes löschen
docker compose up -d --build incident-app  # Nur incident-app neu bauen
docker compose restart heartbeat-service   # Heartbeat neu starten
```

---

## Docker Hub

Die eigenen Images sind auf Docker Hub publiziert:

- `jaaannnnnn/incident-app`
- `jaaannnnnn/heartbeat-service`
- `jaaannnnnn/monitoring-platform-nginx`

---

## Projektstruktur

```
monitoring-platform/
├── docker-compose.yml
├── .env
├── heartbeat-service/
│   ├── Dockerfile
│   └── heartbeat.sh
├── nginx/
│   ├── Dockerfile
│   └── nginx.conf
├── incident-app/
│   ├── Dockerfile
│   ├── app.py
│   ├── requirements.txt
│   └── templates/
└── postgres/
    └── init.sql
```
