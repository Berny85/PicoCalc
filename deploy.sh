#!/bin/bash
# Build Script für den NUC
# Dieses Script wird auf dem NUC ausgeführt

set -e

echo "========================================"
echo "PicoCalc Deployment Script"
echo "========================================"

# Ins Projektverzeichnis wechseln
cd /mnt/user/appdata/picocalc

echo "[1/4] Aktualisiere Code aus GitHub..."
git pull origin main

echo "[2/4] Stoppe alte Container..."
docker-compose -f docker-compose.prod.yml down

echo "[3/4] Baue und starte neue Container..."
docker-compose -f docker-compose.prod.yml up --build -d

echo "[4/4] Prüfe Status..."
docker-compose -f docker-compose.prod.yml ps

echo ""
echo "========================================"
echo "Deployment abgeschlossen!"
echo "App erreichbar unter: http://NUC-IP:5000"
echo "========================================"
