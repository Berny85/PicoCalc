#!/bin/bash
# Auto-Deployment Script für PicoCalc
# Prüft alle 5 Minuten auf neue Commits und deployed automatisch

set -e

LOG_FILE="/mnt/user/appdata/picocalc/auto-deploy.log"
LOCK_FILE="/tmp/picocalc-auto-deploy.lock"
DEPLOY_SCRIPT="/mnt/user/appdata/picocalc/deploy.sh"

# Logging mit Zeitstempel
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Prüfe ob bereits ein Deployment läuft
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        log "INFO: Deployment läuft bereits (PID: $PID)"
        exit 0
    else
        log "WARN: Lock-File existiert, aber Prozess nicht aktiv - entferne Lock"
        rm -f "$LOCK_FILE"
    fi
fi

# Erstelle Lock-File
echo $$ > "$LOCK_FILE"

# Cleanup bei Beendigung
cleanup() {
    rm -f "$LOCK_FILE"
}
trap cleanup EXIT

# Ins Projektverzeichnis wechseln
cd /mnt/user/appdata/picocalc

# Git fetch ausführen (ohne Merge)
git fetch origin main > /dev/null 2>&1

# Prüfe ob lokaler HEAD hinter dem Remote ist
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    # Keine Änderungen - stilles Beenden
    exit 0
fi

# Neue Änderungen gefunden!
log "============================================"
log "NEUE COMMITS ERKANNT"
log "Lokal:  ${LOCAL:0:8}"
log "Remote: ${REMOTE:0:8}"
log "============================================"

# Prüfe ob deploy.sh existiert und ausführbar ist
if [ ! -f "$DEPLOY_SCRIPT" ]; then
    log "FEHLER: deploy.sh nicht gefunden: $DEPLOY_SCRIPT"
    exit 1
fi

if [ ! -x "$DEPLOY_SCRIPT" ]; then
    log "INFO: deploy.sh ist nicht ausführbar - setze Berechtigungen"
    chmod +x "$DEPLOY_SCRIPT"
fi

# Führe Deployment durch
log "Starte Deployment..."
if "$DEPLOY_SCRIPT" >> "$LOG_FILE" 2>&1; then
    log "✓ Deployment erfolgreich abgeschlossen"
else
    log "✗ DEPLOYMENT FEHLGESCHLAGEN! (Exit-Code: $?)"
    log "Prüfe die Logs für Details"
fi

log "============================================"
