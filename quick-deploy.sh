#!/bin/bash
# Quick Deploy Script für den NUC
# Nutzt bestehendes Image ohne neu zu bauen (schneller)

set -e

cd /mnt/user/appdata/picocalc

echo "Aktualisiere Code..."
git pull origin main

echo "Starte Container neu..."
docker compose -f docker-compose.prod.yml up -d

echo "Fertig!"
