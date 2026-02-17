# Produkt Kalkulator - Deployment Dokumentation

## System-Architektur

```
┌─────────────────────────────────────────────────────────────┐
│                      GITHUB (Public)                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Repository: print-calculator                         │  │
│  │  └── .github/workflows/deploy.yml (CI/CD)            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ GitHub Actions
                              │ Build & Push Image
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              WINDOWS 11 (Entwicklungs-System)               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Dev App    │    │   Dev DB     │    │  Local Git   │  │
│  │   :5000      │    │   :5432      │    │   Repo       │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                              │
│  Domain: printcalc-dev.local                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Push to GitHub
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              INTEL NUC 11 (Produktiv-System)                │
│                    Unraid OS + Portainer                    │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Prod App   │    │   Prod DB    │    │   Portainer  │  │
│  │   :5000      │    │   :5432      │    │   :9000      │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Backup     │    │  Watchtower  │    │  Monitoring  │  │
│  │  (3x/Tag)    │    │  (Auto-Update)│   │  Dashboard   │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                              │
│  Domain: printcalc.local (mDNS)                              │
└─────────────────────────────────────────────────────────────┘
```

## Inhaltsverzeichnis

1. [Voraussetzungen](#voraussetzungen)
2. [GitHub Repository Setup](#github-repository-setup)
3. [Lokale Entwicklungsumgebung](#lokale-entwicklungsumgebung)
4. [Unraid Setup auf NUC11](#unraid-setup-auf-nuc11)
5. [Datenbank & Backup-Strategie](#datenbank--backup-strategie)
6. [Automatisches Deployment](#automatisches-deployment)
7. [Monitoring Dashboard](#monitoring-dashboard)
8. [Troubleshooting](#troubleshooting)

---

## Voraussetzungen

### Hardware
- **Windows 11 Rechner**: Docker Desktop installiert
- **Intel NUC 11**: Mindestens 8GB RAM, 128GB Storage
- **Netzwerk**: Beide Geräte im gleichen LAN

### Software
- Docker Desktop (Win11)
- Git
- Unraid Lizenz (Basic: ~60-70€)
- GitHub Account

### Netzwerk-Konfiguration
- Statische IPs empfohlen:
  - Win11: `192.168.1.100` (Beispiel)
  - NUC11: `192.168.1.101` (Beispiel)

---

## GitHub Repository Setup

### 1. Repository erstellen

1. Auf GitHub ein neues Repository erstellen: `print-calculator`
2. Public einstellen (keine sensiblen Daten im Code)
3. README.md initialisieren

### 2. Repository Secrets konfigurieren

Unter Settings → Secrets → Actions:

| Secret Name | Value | Beschreibung |
|------------|-------|--------------|
| `DOCKER_USERNAME` | Dein Docker Hub Username | Für Image-Push |
| `DOCKER_PASSWORD` | Docker Hub Access Token | Nicht das Passwort! |

**Docker Hub Access Token erstellen:**
1. Auf Docker Hub einloggen
2. Account Settings → Security
3. "New Access Token" erstellen
4. Token kopieren und in GitHub Secret einfügen

### 3. Projektstruktur

```
print-calculator/
├── .github/
│   └── workflows/
│       └── deploy.yml          # CI/CD Pipeline
├── app/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   └── templates/
├── docker-compose.yml          # Dev Konfiguration
├── docker-compose.prod.yml     # Prod Konfiguration
├── migrations/                 # Alembic Migrationen
├── backup/
│   ├── backup-script.sh
│   └── restore-script.sh
└── README.md
```

---

## Lokale Entwicklungsumgebung

### 1. Repository klonen

```bash
git clone https://github.com/DEIN_USERNAME/print-calculator.git
cd print-calculator
```

### 2. Docker Compose für Entwicklung

**docker-compose.yml**:

```yaml
version: '3.8'

services:
  web:
    build: ./app
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql://printuser:printpass@db:5432/printcalc
      - SECRET_KEY=dev-secret-key
    depends_on:
      - db
    volumes:
      - ./app:/app
    command: uvicorn main:app --host 0.0.0.0 --port 5000 --reload

  db:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=printcalc
      - POSTGRES_USER=printuser
      - POSTGRES_PASSWORD=printpass
    ports:
      - "5432:5432"

  pgadmin:
    image: dpage/pgadmin4:latest
    ports:
      - "5050:80"
    environment:
      - PGADMIN_DEFAULT_EMAIL=admin@admin.com
      - PGADMIN_DEFAULT_PASSWORD=admin

volumes:
  postgres_data:
```

### 3. Lokale Domain einrichten (Optional)

**Windows:** `C:\Windows\System32\drivers\etc\hosts` bearbeiten:

```
127.0.0.1   printcalc-dev.local
```

**ODER** mDNS verwenden (avahi/bonjour):
- Windows 10/11 hat mDNS nativ
- Zugriff via: `http://printcalc-dev.local:5000`

### 4. Entwicklungs-Workflow

```bash
# Container starten
docker-compose up -d

# Entwickeln...
# Code ändern in app/

# Änderungen commiten
git add .
git commit -m "Feature XY implementiert"
git push origin main
```

---

## Unraid Setup auf NUC11

### 1. Unraid Installation

1. **USB-Stick erstellen:**
   - Unraid USB Creator Tool herunterladen
   - USB-Stick (mindestens 4GB) vorbereiten
   - Unraid auf Stick installieren

2. **NUC11 konfigurieren:**
   - USB-Stick anschließen
   - Im BIOS Boot von USB aktivieren
   - Unraid startet automatisch

3. **Erstkonfiguration:**
   - Web-Interface öffnen: `http://NUC-IP`
   - Root-Passwort setzen
   - Lizenz (Basic) kaufen und eintragen
   - Array starten

### 2. Wesentliche Einstellungen

**Settings → Network:**
- Static IP: `192.168.1.101` (anpassen an dein Netzwerk)
- DNS: Router-IP oder `8.8.8.8`

**Settings → Dateisystem:**
- Cache Pool erstellen (für Docker - schneller)
- Shares erstellen:
  - `appdata` (für Container-Daten)
  - `backups` (für DB-Backups)
  - `domains` (für VM-Daten, falls später)

### 3. Docker aktivieren

**Settings → Docker:**
- Docker Service: Enabled
- Docker Hub: Einloggen
- Default appdata path: `/mnt/user/appdata/`

### 4. Portainer installieren

1. **Apps** (Community Applications Plugin)
2. Nach "Portainer" suchen
3. "Add Container"
4. Konfiguration:
   - Name: `portainer`
   - Repository: `portainer/portainer-ce:latest`
   - Port: `9000:9000`
   - Volume: `/var/run/docker.sock:/var/run/docker.sock`
   - Volume: `/mnt/user/appdata/portainer:/data`
5. **Apply**

Zugriff: `http://NUC-IP:9000`
Erstkonfiguration: Admin-Passwort setzen

### 5. Watchtower installieren (Auto-Updates)

**In Portainer:**

1. **Stacks** → **Add Stack**
2. Name: `watchtower`
3. Stack-Datei:

```yaml
version: '3.8'

services:
  watchtower:
    image: containrrr/watchtower
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - WATCHTOWER_POLL_INTERVAL=300  # Alle 5 Minuten prüfen
      - WATCHTOWER_CLEANUP=true       # Alte Images löschen
      - WATCHTOWER_INCLUDE_STOPPED=true
      - WATCHTOWER_REVIVE_STOPPED=false
      - WATCHTOWER_NOTIFICATIONS=email
      - WATCHTOWER_NOTIFICATION_EMAIL_FROM=watchtower@local
      - WATCHTOWER_NOTIFICATION_EMAIL_TO=admin@local
      - WATCHTOWER_NOTIFICATION_EMAIL_SERVER=mail.local
    command: --interval 300 --cleanup
    restart: unless-stopped
```

### 6. Lokale Domain (mDNS)

Unraid hat avahi (mDNS) integriert. Automatisch verfügbar als:
- `http://tower.local` (Standard)
- Oder: `http://printcalc.local` (wenn wir es so nennen)

**Für custom Domain:**
In Portainer Stack für den App-Container Hostname setzen:
```yaml
services:
  web:
    hostname: printcalc
    # ... restliche Konfiguration
```

Zugriff dann: `http://printcalc.local:5000`

---

## Datenbank & Backup-Strategie

### 1. PostgreSQL Container mit WAL-Archiving

**In Portainer neuen Stack erstellen:**

Name: `print-calculator`

```yaml
version: '3.8'

services:
  db:
    image: postgres:16-alpine
    container_name: printcalc-db
    volumes:
      - /mnt/user/appdata/print-calculator/db:/var/lib/postgresql/data
      - /mnt/user/backups/print-calculator/wal:/var/lib/postgresql/wal
      - /mnt/user/appdata/print-calculator/postgresql.conf:/etc/postgresql/postgresql.conf
    environment:
      - POSTGRES_DB=printcalc
      - POSTGRES_USER=printuser
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - PGDATA=/var/lib/postgresql/data/pgdata
    ports:
      - "5432:5432"
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U printuser -d printcalc"]
      interval: 10s
      timeout: 5s
      retries: 5

  web:
    image: DEIN_DOCKERHUB_USERNAME/print-calculator:latest
    container_name: printcalc-app
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgresql://printuser:${DB_PASSWORD}@db:5432/printcalc
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - db
    restart: unless-stopped
    labels:
      - "com.centurylinklabs.watchtower.enable=true"

  backup:
    image: offen/docker-volume-backup:latest
    container_name: printcalc-backup
    volumes:
      - /mnt/user/backups/print-calculator:/backup
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /etc/localtime:/etc/localtime:ro
    environment:
      - BACKUP_CRON_EXPRESSION=0 6,12,18 * * *
      - BACKUP_RETENTION_DAYS=14
      - BACKUP_FILENAME=backup-%Y-%m-%dT%H-%M-%S.tar.gz
      - BACKUP_ARCHIVE=/backup
      - BACKUP_STOP_CONTAINER_LABEL=printcalc-db
      - BACKUP_STOP_CONTAINER_TIMEOUT=120
      - BACKUP_PRUNING_PREFIX=backup-
      - AWS_S3_BUCKET_NAME=
      - BACKUP_NOTIFICATION_URL=
    restart: unless-stopped
    depends_on:
      - db

volumes:
  postgres_data:
  backup_data:
```

**Wichtig:** In Portainer unter **Environment Variables** setzen:
- `DB_PASSWORD`: Ein sicheres Passwort
- `SECRET_KEY`: Ein zufälliger String (z.B. mit `openssl rand -hex 32`)

### 2. PostgreSQL Konfiguration für WAL

**Datei erstellen:** `/mnt/user/appdata/print-calculator/postgresql.conf`

```conf
# PostgreSQL Konfiguration für WAL-Archiving

# Basis-Einstellungen
listen_addresses = '*'
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 768MB
maintenance_work_mem = 64MB
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 4MB
min_wal_size = 1GB
max_wal_size = 4GB

# WAL Archiving für Point-in-Time Recovery
wal_level = replica
archive_mode = on
archive_command = 'cp %p /var/lib/postgresql/wal/%f'
archive_timeout = 3600
max_wal_senders = 3
wal_keep_size = 256MB

# Logging
log_destination = 'stderr'
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_rotation_age = 1d
log_rotation_size = 100MB
log_min_duration_statement = 1000
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on
```

### 3. Backup-Details

**Automatische Backups (3x täglich):**
- 06:00 Uhr
- 12:00 Uhr  
- 18:00 Uhr

**Aufbewahrung:** 14 Tage (automatische Löschung)

**Speicherort:** `/mnt/user/backups/print-calculator/`

**Backup-Typen:**
1. **Base Backups**: Vollständige Datenbank-Kopien
2. **WAL-Archive**: Transaktionslogs für Point-in-Time Recovery

### 4. Manuelles Backup (für deinen Rechner)

**PowerShell Script:** `backup-to-local.ps1`

```powershell
# Backup vom NUC auf lokalen Rechner ziehen
$NUC_IP = "192.168.1.101"
$BACKUP_DIR = "$env:USERPROFILE\Documents\PrintCalc-Backups"
$DATE = Get-Date -Format "yyyy-MM-dd_HH-mm"

# Backup-Verzeichnis erstellen
New-Item -ItemType Directory -Force -Path $BACKUP_DIR

# Backup erstellen auf NUC
Write-Host "Erstelle Backup auf NUC..."
ssh root@$NUC_IP "docker exec printcalc-db pg_dump -U printuser -Fc printcalc > /tmp/backup_$DATE.dump"

# Backup herunterladen
Write-Host "Lade Backup herunter..."
scp root@${NUC_IP}:/tmp/backup_$DATE.dump "$BACKUP_DIR\backup_$DATE.dump"

# Aufräumen auf NUC
ssh root@$NUC_IP "rm /tmp/backup_$DATE.dump"

Write-Host "Backup gespeichert unter: $BACKUP_DIR\backup_$DATE.dump"
Write-Host "Fertig!"
```

**Voraussetzung:** SSH-Key Setup zwischen Win11 und NUC

### 5. Restore (Wiederherstellung)

**Einfacher Restore (letztes Backup):**

```bash
# Auf dem NUC ausführen
# 1. Container stoppen
docker stop printcalc-app

# 2. Datenbank leeren
docker exec printcalc-db dropdb -U printuser printcalc
docker exec printcalc-db createdb -U printuser printcalc

# 3. Backup einspielen
docker exec -i printcalc-db pg_restore -U printuser -d printcalc < /mnt/user/backups/print-calculator/latest/backup.dump

# 4. Container starten
docker start printcalc-app
```

**Point-in-Time Recovery (zu bestimmtem Zeitpunkt):**

```bash
# 1. PostgreSQL im Recovery-Modus starten
# 2. WAL-Archive anwenden bis zum gewünschten Zeitpunkt
# 3. Datenbank starten

# Detaillierte Anleitung siehe: /backup/restore-pit.sh
```

---

## Automatisches Deployment

### 1. GitHub Actions Workflow

**.github/workflows/deploy.yml:**

```yaml
name: Build and Deploy

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

env:
  REGISTRY: docker.io
  IMAGE_NAME: ${{ secrets.DOCKER_USERNAME }}/print-calculator

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
    - name: Checkout repository
      uses: actions/checkout@v3

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2

    - name: Log in to Docker Hub
      uses: docker/login-action@v2
      with:
        username: ${{ secrets.DOCKER_USERNAME }}
        password: ${{ secrets.DOCKER_PASSWORD }}

    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v4
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
        tags: |
          type=ref,event=branch
          type=sha,prefix={{branch}}-
          type=raw,value=latest,enable={{is_default_branch}}

    - name: Build and push Docker image
      uses: docker/build-push-action@v4
      with:
        context: ./app
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

    - name: Trigger Portainer Webhook
      if: github.ref == 'refs/heads/main'
      run: |
        curl -X POST ${{ secrets.PORTAINER_WEBHOOK_URL }}
```

### 2. Portainer Webhook einrichten

1. In Portainer: **Stacks** → **print-calculator**
2. **Pull and redeploy** Option aktivieren
3. **Webhook** URL kopieren
4. In GitHub Secrets hinzufügen:
   - Name: `PORTAINER_WEBHOOK_URL`
   - Value: Die kopierte URL (z.B. `http://192.168.1.101:9000/api/stacks/webhook/xyz`)

### 3. Deployment-Workflow

```
1. Du entwickelst lokal
        ↓
2. Testest mit docker-compose up
        ↓
3. git add . && git commit -m "Feature X"
        ↓
4. git push origin main
        ↓
5. GitHub Actions baut Image
        ↓
6. Push zu Docker Hub
        ↓
7. Webhook triggered
        ↓
8. Portainer pullt neues Image
        ↓
9. Watchtower oder Portainer startet neuen Container
        ↓
10. Migrationen werden automatisch ausgeführt
        ↓
11. App ist aktualisiert!
```

### 4. Datenbank-Migrationen

**Alembic Setup:**

**app/alembic.ini:**
```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = postgresql://printuser:printpass@db:5432/printcalc
```

**app/migrations/env.py:** (automatisch generiert)

**Entrypoint im Dockerfile:**

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Migration ausführen beim Start
CMD alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 5000
```

**Migration erstellen (bei DB-Änderungen):**

```bash
# Lokal ausführen
alembic revision --autogenerate -m "Neue Tabelle X"

# Commiten
git add migrations/
git commit -m "DB: Migration für Tabelle X"
git push
```

---

## Monitoring Dashboard

### 1. Simples Dashboard mit Dozzle

**In Portainer Stack hinzufügen:**

```yaml
  dozzle:
    image: amir20/dozzle:latest
    container_name: dozzle
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    ports:
      - "8080:8080"
    environment:
      - DOZZLE_BASE=/
      - DOZZLE_LEVEL=info
    restart: unless-stopped
```

Zugriff: `http://NUC-IP:8080`

Features:
- Live Docker Logs
- Container-Status
- Einfache Benutzung

### 2. Erweitertes Monitoring mit Netdata (Optional)

```yaml
  netdata:
    image: netdata/netdata:latest
    container_name: netdata
    pid: host
    network_mode: host
    cap_add:
      - SYS_PTRACE
      - SYS_ADMIN
    security_opt:
      - apparmor:unconfined
    volumes:
      - /mnt/user/appdata/netdata/config:/etc/netdata
      - /mnt/user/appdata/netdata/lib:/var/lib/netdata
      - /mnt/user/appdata/netdata/cache:/var/cache/netdata
      - /etc/passwd:/host/etc/passwd:ro
      - /etc/group:/host/etc/group:ro
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /etc/os-release:/host/etc/os-release:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: unless-stopped
```

Zugriff: `http://NUC-IP:19999`

Features:
- System-Ressourcen (CPU, RAM, Disk)
- Docker-Container-Metriken
- PostgreSQL-Statistiken
- Alarme bei Problemen

### 3. Übersicht aller Services

| Service | URL | Beschreibung |
|---------|-----|--------------|
| **App** | `http://printcalc.local:5000` | Hauptanwendung |
| **Portainer** | `http://NUC-IP:9000` | Docker Management |
| **Dozzle** | `http://NUC-IP:8080` | Log-Viewer |
| **Netdata** | `http://NUC-IP:19999` | System-Monitoring |

---

## Troubleshooting

### Problem: Deployment schlägt fehl

**Lösung:**
1. GitHub Actions Logs prüfen
2. Docker Hub Login prüfen
3. Portainer Webhook URL prüfen
4. Container Logs: `docker logs printcalc-app`

### Problem: Datenbank nicht erreichbar

**Lösung:**
```bash
# Auf NUC:
docker ps | grep printcalc-db  # Läuft der Container?
docker logs printcalc-db       # Fehlermeldungen?
docker exec printcalc-db pg_isready -U printuser
```

### Problem: Backup funktioniert nicht

**Lösung:**
1. Backup-Container Logs prüfen: `docker logs printcalc-backup`
2. Berechtigungen prüfen: `ls -la /mnt/user/backups/`
3. Manuelles Test-Backup:
   ```bash
   docker exec printcalc-db pg_dump -U printuser printcalc > /tmp/test.sql
   ```

### Problem: App nicht erreichbar

**Lösung:**
1. Container läuft? `docker ps`
2. Firewall prüfen: `iptables -L | grep 5000`
3. Logs prüfen: `docker logs printcalc-app`
4. Port-Weiterleitung im Router prüfen (falls von außen)

### Problem: Migration schlägt fehl

**Lösung:**
1. Alembic History: `alembic history`
2. Aktueller Stand: `alembic current`
3. Manuelles Upgrade: `alembic upgrade head`
4. Bei Konflikten: `alembic stamp head` (vorsichtig!)

---

## Wartungsaufgaben

### Wöchentlich
- [ ] Logs prüfen (Dozzle)
- [ ] Backup-Status verifizieren
- [ ] Container-Updates prüfen (Watchtower macht das automatisch)

### Monatlich
- [ ] Backup auf externe Festplatte kopieren
- [ ] System-Updates auf Unraid prüfen
- [ ] Docker Images aufräumen: `docker system prune`

### Bei Bedarf
- [ ] Punkt-zu-Punkt Restore testen
- [ ] Migrationen prüfen
- [ ] Performance-Optimierung

---

## Zusammenfassung

Du hast jetzt ein vollständiges System:

✅ **Entwicklung** auf Windows 11 mit Docker Desktop  
✅ **Produktion** auf Intel NUC mit Unraid  
✅ **Automatisches Deployment** via GitHub Actions  
✅ **Datenbank-Backups** 3x täglich mit 14 Tagen Aufbewahrung  
✅ **Point-in-Time Recovery** für Datenbank  
✅ **Monitoring Dashboard** für Überwachung  
✅ **Lokale Domains** ohne Internet-Zugriff  

**Nächste Schritte:**
1. Repository auf GitHub erstellen
2. Unraid auf NUC installieren
3. Docker Hub Account erstellen
4. Secrets in GitHub konfigurieren
5. Ersten Test-Deployment machen

Fragen? Issues im GitHub Repository erstellen!
