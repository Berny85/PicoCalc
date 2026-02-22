#!/bin/bash
# Build Script für den NUC
# Dieses Script wird auf dem NUC ausgeführt

set -e

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Hilfsfunktion für Logging
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ✗${NC} $1"
}

echo "========================================"
echo "PicoCalc Deployment Script"
echo "========================================"

# Ins Projektverzeichnis wechseln
cd /mnt/user/appdata/picocalc

log "[1/5] Aktualisiere Code aus GitHub..."
git pull origin main
success "Code aktualisiert"

log "[2/5] Stoppe alte Container..."
docker compose -f docker-compose.prod.yml down
success "Container gestoppt"

log "[3/5] Baue und starte neue Container..."
docker compose -f docker-compose.prod.yml up --build -d
success "Container gestartet"

log "[4/5] Warte auf Datenbank..."

# Warte auf PostgreSQL (max 60 Sekunden)
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker compose -f docker-compose.prod.yml exec -T db pg_isready -U printuser > /dev/null 2>&1; then
        success "Datenbank ist bereit"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    error "Datenbank ist nicht bereit nach 60 Sekunden!"
    docker compose -f docker-compose.prod.yml logs db --tail 20
    exit 1
fi

# Zusätzliche Wartezeit für vollständigen Start
sleep 3

log "[4.5/5] Führe Datenbank-Migrationen aus..."

# Führe Migrationen aus
if docker compose -f docker-compose.prod.yml exec -T web alembic upgrade head; then
    success "Migrationen erfolgreich ausgeführt"
else
    error "Migration fehlgeschlagen!"
    warning "Versuche Datenbank-Status zu prüfen..."
    
    # Zeige aktuellen Alembic-Status
    docker compose -f docker-compose.prod.yml exec -T web alembic current || true
    docker compose -f docker-compose.prod.yml exec -T web alembic history --verbose || true
    
    exit 1
fi

# Prüfe ob der Web-Container gesund ist
log "Prüfe Web-Container Status..."
sleep 2

if curl -sf http://localhost:5000/health > /dev/null 2>&1 || curl -sf http://localhost:5000/ > /dev/null 2>&1; then
    success "Web-Container läuft und antwortet"
else
    warning "Web-Container Healthcheck nicht erreichbar (App läuft trotzdem möglicherweise)"
fi

log "[5/5] Prüfe Container-Status..."
docker compose -f docker-compose.prod.yml ps

echo ""
echo "========================================"
success "Deployment abgeschlossen!"
echo "App erreichbar unter: http://NUC-IP:5000"
echo "========================================"
