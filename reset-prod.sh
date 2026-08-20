#!/bin/bash
# =============================================================================
# PicoCalc - Produktiv-System Reset Script
# Für Intel NUC mit Unraid OS
# =============================================================================
# 
# WARNUNG: Dieses Script löscht ALLE Datenbank-Daten!
# Nur verwenden wenn ein frischer Start nötig ist (z.B. nach Schema-Änderungen)
#
# Backup vorher erstellen:
#   ./backup/backup-script.sh
#
# =============================================================================

set -e  # Beenden bei Fehler

echo "=========================================="
echo "  PicoCalc - PRODUKTION RESET"
echo "=========================================="
echo ""
echo "WARNUNG: Alle Daten werden gelöscht!"
echo ""

# Bestätigung einholen
read -p "Möchtest du wirklich fortfahren? (j/N): " confirm
if [[ $confirm != "j" && $confirm != "J" ]]; then
    echo "Abbruch."
    exit 0
fi

echo ""
echo "Schritt 1/5: Container stoppen..."
cd /mnt/user/appdata/picocalc
docker compose -f docker-compose.prod.yml down

echo ""
echo "Schritt 2/5: Datenbank-Daten löschen..."
rm -rf /mnt/user/appdata/picocalc/db/*
echo "  ✓ /mnt/user/appdata/picocalc/db gelöscht"

echo ""
echo "Schritt 3/5: pgAdmin-Daten löschen..."
rm -rf /mnt/user/appdata/picocalc/pgadmin/*
echo "  ✓ /mnt/user/appdata/picocalc/pgadmin gelöscht"

echo ""
echo "Schritt 4/5: Docker-Images neu bauen..."
docker compose -f docker-compose.prod.yml build --no-cache

echo ""
echo "Schritt 5/5: Container starten..."
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "=========================================="
echo "  Reset abgeschlossen!"
echo "=========================================="
echo ""
echo "Warte auf Datenbank-Initialisierung..."
sleep 10

# Prüfe Status
if docker ps | grep -q picocalc-app; then
    echo "✓ Container laufen"
    echo ""
    echo "Logs prüfen:"
    echo "  docker logs -f picocalc-app"
    echo ""
    echo "Webseite: http://192.168.50.8:5000"
else
    echo "✗ Fehler - Container laufen nicht!"
    echo "Logs:"
    docker logs picocalc-app | tail -20
fi
