#!/bin/bash
# PostgreSQL Backup Script für Unraid
# Wird automatisch 3x täglich ausgeführt

set -e

CONTAINER_NAME="picocalc-db"
BACKUP_DIR="/mnt/user/backups/print-calculator"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="printcalc"
DB_USER="printuser"

# Backup-Verzeichnis erstellen
mkdir -p "$BACKUP_DIR"

# Base Backup erstellen
echo "[$(date)] Erstelle Base Backup..."
docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$BACKUP_DIR/base_$DATE.dump"

# Backup komprimieren
echo "[$(date)] Komprimiere Backup..."
gzip -f "$BACKUP_DIR/base_$DATE.dump"

# Alte Backups löschen (älter als 14 Tage)
echo "[$(date)] Lösche alte Backups..."
find "$BACKUP_DIR" -name "base_*.dump.gz" -mtime +14 -delete

# WAL-Archive bereinigen (älter als 14 Tage)
echo "[$(date)] Bereinige WAL-Archive..."
find "/mnt/user/backups/print-calculator/wal" -type f -mtime +14 -delete

echo "[$(date)] Backup abgeschlossen: base_$DATE.dump.gz"
echo "[$(date)] Backup-Größe: $(du -h "$BACKUP_DIR/base_$DATE.dump.gz" | cut -f1)"
