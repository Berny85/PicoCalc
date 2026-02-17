# PicoCalc

Calculator for product prices.

## Entwicklungs-Workflow

Dieses Projekt verwendet einen einfachen Workflow ohne Docker Hub:

### Lokale Entwicklung (Windows PC)

```bash
# 1. Entwicklungsumgebung starten
docker-compose up -d

# 2. Entwickeln und testen unter http://localhost:5000

# 3. Änderungen zu GitHub pushen
git add .
git commit -m "Beschreibung"
git push origin main
```

### Deployment auf NUC

```powershell
# Automatisch via PowerShell
.\deploy-to-nuc.ps1
```

Oder manuell:
```bash
# Per SSH auf NUC
ssh root@192.168.1.101
cd /mnt/user/appdata/picocalc
git pull origin main
docker-compose -f docker-compose.prod.yml up --build -d
```

## Architektur

- **Entwicklung**: Windows 11 mit Docker Desktop
- **Produktion**: Intel NUC mit Unraid
- **Deployment**: Direkt via Git + SSH (kein Docker Hub nötig)

## Services

| Service | URL | Beschreibung |
|---------|-----|--------------|
| **PicoCalc** | `http://NUC-IP:5000` | Hauptanwendung |
| **Portainer** | `http://NUC-IP:9000` | Docker Management |
| **Dozzle** | `http://NUC-IP:8080` | Log-Viewer |

## Setup NUC (einmalig)

```bash
mkdir -p /mnt/user/appdata/picocalc
cd /mnt/user/appdata/picocalc
git clone https://github.com/berny85/PicoCalc.git .
mkdir -p /mnt/user/backups/picocalc/wal
cp postgresql.conf /mnt/user/appdata/picocalc/
docker-compose -f docker-compose.prod.yml up --build -d
```

Siehe [DEPLOYMENT.md](DEPLOYMENT.md) für vollständige Dokumentation.
