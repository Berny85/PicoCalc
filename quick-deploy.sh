#!/bin/bash
# Quick Deploy Script für den NUC
# Nutzt bestehendes Image ohne neu zu bauen (schneller)

set -e

cd /mnt/user/appdata/picocalc

echo "Aktualisiere Code..."
git pull origin main

if docker-compose version > /dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
elif docker compose version > /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

echo "Starte Container neu..."
$COMPOSE_CMD -f docker-compose.prod.yml up -d

echo "Fertig!"
