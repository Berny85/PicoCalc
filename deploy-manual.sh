#!/bin/bash
# Manuelles Deployment Script für PicoCalc
# Wird auf dem DEV-PC ausgeführt, verbindet sich per SSH mit dem NUC
# Verwendung: ./deploy-manual.sh

set -e

# Konfiguration
NUC_IP="192.168.50.8"
NUC_USER="root"
NUC_PATH="/mnt/user/appdata/picocalc"
LOG_FILE="deploy-manual.log"

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging-Funktion (Console + File)
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "$msg"
    echo "$msg" >> "$LOG_FILE"
}

log_color() {
    local color=$1
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $2"
    echo -e "${color}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

# Header
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}PicoCalc Manuelles Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

log "Starte Deployment zu NUC ($NUC_IP)..."
log ""

# Prüfe Git-Status
log "Prüfe Git-Status..."
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    log_color $RED "✗ Fehler: Kein Git-Repository gefunden!"
    exit 1
fi

# Prüfe auf uncommitted Changes
if [ -n "$(git status --porcelain)" ]; then
    log_color $YELLOW "⚠ Warnung: Ungespeicherte Änderungen vorhanden:"
    git status --short | while read line; do
        log "  $line"
    done
    log ""
    read -p "Möchten Sie trotzdem fortfahren? (j/n): " answer
    if [ "$answer" != "j" ] && [ "$answer" != "ja" ]; then
        log "Abbruch durch Benutzer"
        exit 0
    fi
    log ""
fi

# Zeige aktuellen Commit
LOCAL_COMMIT=$(git rev-parse --short HEAD)
LOCAL_BRANCH=$(git branch --show-current)
log "Aktueller Branch: $LOCAL_BRANCH"
log "Aktueller Commit: $LOCAL_COMMIT"
log ""

# 1. Push zu GitHub
log_color $CYAN "[1/4] Push zu GitHub..."
log ""

if git push origin "$LOCAL_BRANCH" 2>&1 | tee -a "$LOG_FILE"; then
    log ""
    log_color $GREEN "✓ Code erfolgreich gepusht"
else
    log ""
    log_color $RED "✗ Push fehlgeschlagen!"
    exit 1
fi

log ""
log_color $CYAN "[2/4] Verbinde mit NUC ($NUC_IP)..."
log ""

# Prüfe SSH-Verbindung
if ! ssh -o ConnectTimeout=5 "$NUC_USER@$NUC_IP" "echo 'SSH-Verbindung OK'" > /dev/null 2>&1; then
    log_color $RED "✗ SSH-Verbindung zum NUC fehlgeschlagen!"
    log "Bitte prüfen Sie:"
    log "  - Ist der NUC erreichbar? (ping $NUC_IP)"
    log "  - Ist SSH aktiviert?"
    log "  - Ist der SSH-Key eingerichtet?"
    exit 1
fi

log_color $GREEN "✓ SSH-Verbindung erfolgreich"
log ""

# 3. Deployment auf NUC ausführen
log_color $CYAN "[3/4] Starte Deployment auf NUC..."
log ""

# Führe deploy.sh auf dem NUC aus und capture Output
ssh "$NUC_USER@$NUC_IP" "bash $NUC_PATH/deploy.sh" 2>&1 | while read line; do
    echo "$line"
    echo "[NUC] $line" >> "$LOG_FILE"
done

SSH_EXIT_CODE=${PIPESTATUS[0]}

if [ $SSH_EXIT_CODE -ne 0 ]; then
    log ""
    log_color $RED "✗ Deployment auf NUC fehlgeschlagen! (Exit Code: $SSH_EXIT_CODE)"
    exit 1
fi

log ""
log_color $CYAN "[4/4] Prüfe Deployment-Status..."
log ""

# Warte kurz und prüfe Container-Status
sleep 2

CONTAINER_STATUS=$(ssh "$NUC_USER@$NUC_IP" "docker compose -f $NUC_PATH/docker-compose.prod.yml ps --format json" 2>/dev/null || echo "[]")

# Prüfe ob Web-Container läuft
WEB_RUNNING=$(ssh "$NUC_USER@$NUC_IP" "docker compose -f $NUC_PATH/docker-compose.prod.yml ps web --status running -q" 2>/dev/null)
DB_RUNNING=$(ssh "$NUC_USER@$NUC_IP" "docker compose -f $NUC_PATH/docker-compose.prod.yml ps db --status running -q" 2>/dev/null)

if [ -n "$WEB_RUNNING" ] && [ -n "$DB_RUNNING" ]; then
    log_color $GREEN "✓ Alle Container laufen"
    log "  - Web: OK"
    log "  - DB:  OK"
else
    log_color $YELLOW "⚠ Warnung: Nicht alle Container laufen!"
    [ -z "$WEB_RUNNING" ] && log "  - Web: FEHLER"
    [ -z "$DB_RUNNING" ] && log "  - DB:  FEHLER"
fi

log ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Deployment abgeschlossen!${NC}"
echo -e "${GREEN}========================================${NC}"
log ""
log "Log-Datei: $LOG_FILE"
log "NUC URL: http://$NUC_IP:5000"
log ""

# Frage ob Logs angezeigt werden sollen
read -p "Logs anzeigen? (j/n): " show_logs
if [ "$show_logs" = "j" ] || [ "$show_logs" = "ja" ]; then
    echo ""
    echo -e "${CYAN}--- Letzte 30 Zeilen aus $LOG_FILE ---${NC}"
    tail -30 "$LOG_FILE"
fi
