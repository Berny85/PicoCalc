#!/bin/bash
# Deploy-Script: Nur Pull von GitHub + Deployment
# KEIN Push! Nutzung wenn Code schon auf GitHub ist
# 
# Verwendung: ./deploy-pull-only.sh
# Optionen:
#   ./deploy-pull-only.sh --logs    # Nach Deploy Logs anzeigen
#   ./deploy-pull-only.sh --skip-build  # Nur Pull + Restart

set -e

# Konfiguration
PROJECT_DIR="/mnt/user/appdata/picocalc"
LOG_FILE="deploy-pull.log"
COMPOSE_FILE="docker-compose.prod.yml"

# Optionen parsen
SHOW_LOGS=0
SKIP_BUILD=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --logs)
            SHOW_LOGS=1
            shift
            ;;
        --skip-build)
            SKIP_BUILD=1
            shift
            ;;
        --help)
            echo "Verwendung: $0 [OPTIONEN]"
            echo ""
            echo "Optionen:"
            echo "  --logs         Nach Deploy Logs anzeigen"
            echo "  --skip-build   Kein Rebuild, nur Pull + Restart"
            echo "  --help         Diese Hilfe anzeigen"
            exit 0
            ;;
        *)
            echo "Unbekannte Option: $1"
            echo "Verwenden Sie --help für Hilfe"
            exit 1
            ;;
    esac
done

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_section() {
    echo -e "${BLUE}========================================${NC}"
    echo "$1"
    echo -e "${BLUE}========================================${NC}"
}

# In Projektverzeichnis wechseln
cd "$PROJECT_DIR" || {
    log "${RED}Fehler: Kann nicht in $PROJECT_DIR wechseln${NC}"
    exit 1
}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}PicoCalc Deploy (Pull Only)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

log "Starte Deploy in: $PROJECT_DIR"
log ""

# [1/4] Git Status prüfen
log_section "[1/4] GIT STATUS"
log ""

log "Lokaler Commit: $(git rev-parse --short HEAD)"
log "Remote Commit:  $(git rev-parse origin/main 2>/dev/null | cut -c1-7 || echo 'N/A')"
log ""

# [2/4] Code von GitHub ziehen
log_section "[2/4] PULL VON GITHUB"
log ""

log "Führe git fetch aus..."
git fetch origin main 2>&1 | tee -a "$LOG_FILE"

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    log "${GREEN}✓ Bereits auf dem neuesten Stand${NC}"
    log ""
    log "Keine Änderungen zum Deployen."
    exit 0
fi

log "Neue Version verfügbar:"
log "  Alt: $LOCAL"
log "  Neu: $REMOTE"
log ""

log "Ziehe neue Version..."
git reset --hard origin/main 2>&1 | tee -a "$LOG_FILE"
log "${GREEN}✓ Code aktualisiert${NC}"
log ""

# [3/4] Container
log_section "[3/4] CONTAINER"
log ""

if [ $SKIP_BUILD -eq 0 ]; then
    log "Stoppe alte Container..."
    docker compose -f "$COMPOSE_FILE" down 2>&1 | tee -a "$LOG_FILE"
    log "${GREEN}✓ Container gestoppt${NC}"
    log ""
    
    log "Starte Container (mit Build)..."
    docker compose -f "$COMPOSE_FILE" up --build -d 2>&1 | tee -a "$LOG_FILE"
else
    log "Skip-Build: Nur Restart..."
    docker compose -f "$COMPOSE_FILE" restart 2>&1 | tee -a "$LOG_FILE"
fi

log "${GREEN}✓ Container gestartet${NC}"
log ""

# [4/4] Datenbank
log_section "[4/4] DATENBANK"
log ""

log "Warte auf Datenbank..."
for i in {1..30}; do
    if docker compose -f "$COMPOSE_FILE" exec -T db pg_isready -U printuser > /dev/null 2>&1; then
        log "${GREEN}✓ Datenbank bereit${NC}"
        break
    fi
    sleep 2
done

sleep 3

log "Führe Migrationen aus..."
if docker compose -f "$COMPOSE_FILE" exec -T web alembic upgrade head 2>&1 | tee -a "$LOG_FILE"; then
    log "${GREEN}✓ Migrationen erfolgreich${NC}"
else
    log "${YELLOW}⚠ Migrationen fehlgeschlagen (oder keine vorhanden)${NC}"
fi

log ""

# Abschluss
log_section "DEPLOY ABGESCHLOSSEN"
log ""
log "Log-Datei: $PROJECT_DIR/$LOG_FILE"
log "App:       http://$(hostname -I | awk '{print $1}'):5000"
log ""

# Container Status
log "Container-Status:"
docker compose -f "$COMPOSE_FILE" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>&1 | tee -a "$LOG_FILE"

log ""

# Logs anzeigen
if [ $SHOW_LOGS -eq 1 ]; then
    log "Verfolge Logs (Strg+C zum Beenden)..."
    echo ""
    docker compose -f "$COMPOSE_FILE" logs -f web
else
    read -p "Container-Logs anzeigen? (j/n): " answer
    if [ "$answer" = "j" ]; then
        echo ""
        docker compose -f "$COMPOSE_FILE" logs --tail 30 web
    fi
fi
