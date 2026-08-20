#!/bin/bash
# Auto-Deployment Script für PicoCalc
# Prüft auf neue Commits und deployed automatisch
# Verwendung: ./auto-deploy.sh oder via cron: */5 * * * * /mnt/user/appdata/picocalc/auto-deploy.sh >> /mnt/user/appdata/picocalc/auto-deploy.log 2>&1

# Konfiguration
PROJECT_DIR="/mnt/user/appdata/picocalc"
LOG_FILE="$PROJECT_DIR/auto-deploy.log"
COMPOSE_FILE="docker-compose.prod.yml"

# In Projektverzeichnis wechseln
cd "$PROJECT_DIR" || exit 1

# Logging-Funktion
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Git fetch ausführen (ohne Merge)
git fetch origin main 2>&1 | tee -a "$LOG_FILE"

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    log "========================================"
    log "Neue Version gefunden!"
    log "Lokal:  $LOCAL"
    log "Remote: $REMOTE"
    log "========================================"
    
    # Code aktualisieren
    log "Pulling latest code..."
    git pull origin main 2>&1 | tee -a "$LOG_FILE"
    
    # Container neu bauen und starten
    log "Baue und starte Container..."
    docker compose -f "$COMPOSE_FILE" up --build -d 2>&1 | tee -a "$LOG_FILE"
    
    # Warte auf Datenbank (max 60 Sekunden)
    log "Warte auf Datenbank..."
    DB_READY=0
    for i in {1..30}; do
        if docker compose -f "$COMPOSE_FILE" exec -T db pg_isready -U printuser > /dev/null 2>&1; then
            log "✓ Datenbank bereit"
            DB_READY=1
            break
        fi
        sleep 2
    done
    
    if [ $DB_READY -eq 0 ]; then
        log "✗ FEHLER: Datenbank nicht bereit nach 60 Sekunden!"
    fi
    
    # Kurze zusätzliche Wartezeit
    sleep 3
    
    # Migrationen ausführen
    log "Führe Datenbank-Migrationen aus..."
    if docker compose -f "$COMPOSE_FILE" exec -T web alembic upgrade head 2>&1 | tee -a "$LOG_FILE"; then
        log "✓ Migrationen erfolgreich"
    else
        log "✗ FEHLER: Migrationen fehlgeschlagen!"
        log "Aktueller Status:"
        docker compose -f "$COMPOSE_FILE" exec -T web alembic current 2>&1 | tee -a "$LOG_FILE" || log "Konnte Status nicht abrufen"
    fi
    
    log "========================================"
    log "Deployment abgeschlossen"
    log "========================================"
else
    log "Keine Änderungen (beide auf $LOCAL)"
fi

# Alte Logs rotieren (nur letzte 1000 Zeilen behalten)
if [ -f "$LOG_FILE" ]; then
    tail -n 1000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi
