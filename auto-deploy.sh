#!/bin/bash
# Auto-Deployment Script für PicoCalc
# Prüft alle 5 Minuten auf neue Commits und deployed automatisch

cd /mnt/user/appdata/picocalc

# Git fetch ausführen (ohne Merge)
git fetch origin main

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "[$(date)] Neue Version gefunden, deploye..."
    
    # Code aktualisieren
    git pull origin main
    
    # Container neu bauen und starten
    docker compose -f docker-compose.prod.yml up --build -d
    
    # Warte auf Datenbank (max 60 Sekunden)
    echo "[$(date)] Warte auf Datenbank..."
    for i in {1..30}; do
        if docker compose -f docker-compose.prod.yml exec -T db pg_isready -U printuser > /dev/null 2>&1; then
            echo "[$(date)] Datenbank bereit"
            break
        fi
        sleep 2
    done
    
    # Kurze zusätzliche Wartezeit
    sleep 3
    
    # Migrationen ausführen
    echo "[$(date)] Führe Datenbank-Migrationen aus..."
    if docker compose -f docker-compose.prod.yml exec -T web alembic upgrade head; then
        echo "[$(date)] Migrationen erfolgreich"
    else
        echo "[$(date)] FEHLER: Migrationen fehlgeschlagen!"
        echo "[$(date)] Aktueller Status:"
        docker compose -f docker-compose.prod.yml exec -T web alembic current 2>/dev/null || echo "Konnte Status nicht abrufen"
    fi
    
    echo "[$(date)] Deployment abgeschlossen"
else
    echo "[$(date)] Keine Änderungen"
fi
