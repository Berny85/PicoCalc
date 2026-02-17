#!/bin/bash
# PostgreSQL Restore Script für Unraid
# Erlaubt Wiederherstellung aus Base Backup

set -e

CONTAINER_NAME="picocalc-db"
APP_CONTAINER="picocalc-app"
BACKUP_DIR="/mnt/user/backups/picocalc"
DB_NAME="printcalc"
DB_USER="printuser"

# Funktion: Verwendung anzeigen
usage() {
    echo "Verwendung: $0 [latest|YYYYmmDD_HHMMSS]"
    echo ""
    echo "Beispiele:"
    echo "  $0 latest          # Letztes Backup wiederherstellen"
    echo "  $0 20250115_120000 # Bestimmtes Backup wiederherstellen"
    exit 1
}

# Parameter prüfen
if [ $# -eq 0 ]; then
    usage
fi

BACKUP_NAME="$1"

# Backup-Datei bestimmen
if [ "$BACKUP_NAME" = "latest" ]; then
    BACKUP_FILE=$(ls -t "$BACKUP_DIR"/base_*.dump.gz 2>/dev/null | head -1)
    if [ -z "$BACKUP_FILE" ]; then
        echo "FEHLER: Kein Backup gefunden!"
        exit 1
    fi
else
    BACKUP_FILE="$BACKUP_DIR/base_$BACKUP_NAME.dump.gz"
    if [ ! -f "$BACKUP_FILE" ]; then
        echo "FEHLER: Backup nicht gefunden: $BACKUP_FILE"
        exit 1
    fi
fi

echo "======================================"
echo "PostgreSQL Restore"
echo "======================================"
echo "Backup-Datei: $BACKUP_FILE"
echo ""

# Sicherheitsabfrage
read -p "ACHTUNG: Alle aktuellen Daten werden überschrieben! Fortfahren? (ja/NEIN): " CONFIRM
if [ "$CONFIRM" != "ja" ]; then
    echo "Abgebrochen."
    exit 0
fi

# App stoppen
echo "[1/5] Stoppe App-Container..."
docker stop "$APP_CONTAINER" 2>/dev/null || true

# Backup dekomprimieren
echo "[2/5] Dekomprimiere Backup..."
gunzip -c "$BACKUP_FILE" > /tmp/restore.dump

# Datenbank löschen und neu erstellen
echo "[3/5] Lösche und erstelle Datenbank neu..."
docker exec "$CONTAINER_NAME" dropdb -U "$DB_USER" --if-exists "$DB_NAME"
docker exec "$CONTAINER_NAME" createdb -U "$DB_USER" "$DB_NAME"

# Backup einspielen
echo "[4/5] Spiele Backup ein..."
docker exec -i "$CONTAINER_NAME" pg_restore -U "$DB_USER" -d "$DB_NAME" < /tmp/restore.dump

# Aufräumen
echo "[5/5] Aufräumen..."
rm -f /tmp/restore.dump

# App starten
echo "Starte App-Container..."
docker start "$APP_CONTAINER"

echo ""
echo "======================================"
echo "Restore erfolgreich abgeschlossen!"
echo "======================================"
