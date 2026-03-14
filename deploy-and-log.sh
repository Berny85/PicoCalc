#!/bin/bash
# Kombiniertes Deploy-Script mit detailliertem Logging
# Push zu GitHub + Deployment auf NUC mit Zeitstempel-Log
# 
# Verwendung: 
#   ./deploy-and-log.sh              # Standard-Deployment
#   ./deploy-and-log.sh --no-push    # Nur Deploy ohne Push (wenn schon gepusht)
#   ./deploy-and-log.sh --watch      # Deploy und dann Logs verfolgen

set -e

# Konfiguration
NUC_IP="192.168.50.8"
NUC_USER="root"
NUC_PATH="/mnt/user/appdata/picocalc"
LOG_DIR="logs"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
LOG_FILE="$LOG_DIR/deploy_$TIMESTAMP.log"
LATEST_LOG="$LOG_DIR/deploy_latest.log"

# Optionen parsen
NO_PUSH=0
WATCH_LOGS=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-push)
            NO_PUSH=1
            shift
            ;;
        --watch)
            WATCH_LOGS=1
            shift
            ;;
        --help)
            echo "Verwendung: $0 [OPTIONEN]"
            echo ""
            echo "Optionen:"
            echo "  --no-push    Kein Git Push (nur Deploy)"
            echo "  --watch      Nach Deploy Logs verfolgen"
            echo "  --help       Diese Hilfe anzeigen"
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

# Log-Verzeichnis erstellen
mkdir -p "$LOG_DIR"

# Initiale Log-Datei erstellen
echo "PicoCalc Deployment Log" > "$LOG_FILE"
echo "=======================" >> "$LOG_FILE"
echo "Zeitstempel: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Symlink auf latest aktualisieren
ln -sf "$LOG_FILE" "$LATEST_LOG"

# Logging-Funktion
log() {
    local msg="[$(date '+%H:%M:%S')] $1"
    echo -e "$msg" | tee -a "$LOG_FILE"
}

log_section() {
    local color=$1
    local title=$2
    echo -e "${color}" | tee -a "$LOG_FILE"
    echo "========================================" | tee -a "$LOG_FILE"
    echo "$title" | tee -a "$LOG_FILE"
    echo "========================================" | tee -a "$LOG_FILE"
    echo -e "${NC}" | tee -a "$LOG_FILE"
}

# Header
log_section $BLUE "PicoCalc Deployment"
log "Log-Datei: $LOG_FILE"
log ""

# Git-Info
log "Git-Repository: $(git rev-parse --show-toplevel)"
log "Aktueller Branch: $(git branch --show-current)"
log "Letzter Commit: $(git log -1 --pretty=format:'%h - %s (%cr)')"
log ""

# Prüfe auf uncommitted Changes
if [ -n "$(git status --porcelain)" ]; then
    log "${YELLOW}⚠ Warnung: Ungespeicherte Änderungen:${NC}"
    git status --short | tee -a "$LOG_FILE"
    log ""
    read -p "Trotzdem fortfahren? (j/n): " answer
    if [ "$answer" != "j" ]; then
        log "Abbruch."
        exit 0
    fi
fi

# Schritt 1: Git Push
if [ $NO_PUSH -eq 0 ]; then
    log_section $CYAN "[1/3] PUSH ZU GITHUB"
    log ""
    
    if git push origin "$(git branch --show-current)" 2>&1 | tee -a "$LOG_FILE"; then
        log ""
        log "${GREEN}✓ Push erfolgreich${NC}"
    else
        log ""
        log "${RED}✗ Push fehlgeschlagen!${NC}"
        exit 1
    fi
else
    log_section $CYAN "[1/3] PUSH ÜBERSPRUNGEN (--no-push)"
fi

log ""

# Schritt 2: SSH-Verbindung prüfen
log_section $CYAN "[2/3] VERBINDE MIT NUC"
log ""

if ! ssh -o ConnectTimeout=5 "$NUC_USER@$NUC_IP" "echo 'OK'" > /dev/null 2>&1; then
    log "${RED}✗ SSH-Verbindung fehlgeschlagen!${NC}"
    log "Prüfen Sie:"
    log "  - ping $NUC_IP"
    log "  - SSH-Key eingerichtet?"
    exit 1
fi

log "${GREEN}✓ SSH-Verbindung OK${NC}"
log "NUC IP: $NUC_IP"
log "Projektpfad: $NUC_PATH"
log ""

# Schritt 3: Deployment auf NUC
log_section $CYAN "[3/3] DEPLOYMENT AUF NUC"
log ""

log "Starte deploy.sh auf dem NUC..."
log "----------------------------------------"
log ""

# Führe Deploy aus und speichere Output
ssh "$NUC_USER@$NUC_IP" "cd $NUC_PATH && bash deploy.sh" 2>&1 | tee -a "$LOG_FILE"

SSH_EXIT=${PIPESTATUS[0]}

log ""
log "----------------------------------------"

if [ $SSH_EXIT -ne 0 ]; then
    log "${RED}✗ Deployment fehlgeschlagen! (Exit: $SSH_EXIT)${NC}"
    exit 1
fi

log "${GREEN}✓ Deploy-Skript beendet${NC}"
log ""

# Prüfe Container-Status
log "Prüfe Container-Status..."
sleep 2

WEB_STATUS=$(ssh "$NUC_USER@$NUC_IP" "docker compose -f $NUC_PATH/docker-compose.prod.yml ps web --format 'table {{.Status}}' 2>/dev/null | tail -1" || echo "Unbekannt")
DB_STATUS=$(ssh "$NUC_USER@$NUC_IP" "docker compose -f $NUC_PATH/docker-compose.prod.yml ps db --format 'table {{.Status}}' 2>/dev/null | tail -1" || echo "Unbekannt")

log "  Web: $WEB_STATUS"
log "  DB:  $DB_STATUS"

# Zusammenfassung
log ""
log_section $GREEN "DEPLOYMENT ABGESCHLOSSEN"
log ""
log "Log gespeichert in: $LOG_FILE"
log "Symlink: $LATEST_LOG"
log ""
log "URLs:"
log "  App:      http://$NUC_IP:5000"
log "  Portainer: http://$NUC_IP:9000"
log "  Logs:     http://$NUC_IP:8080"
log ""

# Logs anzeigen
if [ $WATCH_LOGS -eq 1 ]; then
    log "Verfolge Container-Logs (Strg+C zum Beenden)..."
    log ""
    ssh "$NUC_USER@$NUC_IP" "docker compose -f $NUC_PATH/docker-compose.prod.yml logs -f web" 2>&1
else
    # Frage ob Logs angezeigt werden sollen
    read -p "Container-Logs anzeigen? (j/n): " show_logs
    if [ "$show_logs" = "j" ]; then
        echo ""
        ssh "$NUC_USER@$NUC_IP" "docker compose -f $NUC_PATH/docker-compose.prod.yml logs --tail 20 web" 2>&1
    fi
fi
