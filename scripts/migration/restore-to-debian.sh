#!/bin/bash
# ==============================================================================
# Wiederherstellungs-Skript für Debian 12 Server
# Stellt PicoCalc, Bambuddy und PicoAccounting auf dem frischen Debian NUC her.
# ==============================================================================

set -e

CONTAINERS_DIR="/opt/containers"
BACKUP_DIR="/root/migration_backup"

echo "======================================================================"
echo "  MIGRATIONS-RESTORE AUF DEBIAN 12                                    "
echo "======================================================================"

if [ "$EUID" -ne 0 ]; then
  echo "[FEHLER] Bitte führe dieses Skript als root oder mit sudo aus!"
  exit 1
fi

if [ ! -d "$BACKUP_DIR" ]; then
  echo "[FEHLER] Backup-Verzeichnis $BACKUP_DIR nicht gefunden!"
  echo "Bitte kopiere den Backup-Ordner zuerst nach $BACKUP_DIR auf den NUC."
  exit 1
fi

mkdir -p "$CONTAINERS_DIR"

# 1. Bambuddy entpacken
if [ -f "$BACKUP_DIR/bambuddy_appdata.tar.gz" ]; then
    echo "[1/4] Entpacke Bambuddy (Profile, Druckhistorie, Logs)..."
    tar -xzf "$BACKUP_DIR/bambuddy_appdata.tar.gz" -C "$CONTAINERS_DIR/"
    # Sicherstellen, dass logs und virtual_printer existieren
    mkdir -p "$CONTAINERS_DIR/bambuddy/logs" "$CONTAINERS_DIR/bambuddy/virtual_printer"
    echo "      [OK] Bambuddy entpackt nach $CONTAINERS_DIR/bambuddy"
fi

# 2. PicoAccounting entpacken
if [ -f "$BACKUP_DIR/picoaccounting_appdata.tar.gz" ]; then
    echo "[2/4] Entpacke PicoAccounting (Code, DB & Belege)..."
    tar -xzf "$BACKUP_DIR/picoaccounting_appdata.tar.gz" -C "$CONTAINERS_DIR/"
    echo "      [OK] PicoAccounting entpackt nach $CONTAINERS_DIR/pico-accounting"
fi

# 3. PicoCalc Dateien & Storage entpacken
if [ -f "$BACKUP_DIR/picocalc_appdata.tar.gz" ]; then
    echo "[3/4] Entpacke PicoCalc (Storage, SVGs, Konfigurationen)..."
    tar -xzf "$BACKUP_DIR/picocalc_appdata.tar.gz" -C "$CONTAINERS_DIR/"
    echo "      [OK] PicoCalc entpackt nach $CONTAINERS_DIR/picocalc"
fi

# 4. Compose-Dateien platzieren
echo "[4/4] Kopiere Docker-Compose Vorlagen..."
[ -f "$BACKUP_DIR/docker-compose.picocalc.yml" ] && cp "$BACKUP_DIR/docker-compose.picocalc.yml" "$CONTAINERS_DIR/picocalc/docker-compose.yml"
[ -f "$BACKUP_DIR/docker-compose.bambuddy.yml" ] && cp "$BACKUP_DIR/docker-compose.bambuddy.yml" "$CONTAINERS_DIR/bambuddy/docker-compose.yml"
[ -f "$BACKUP_DIR/docker-compose.picoaccounting.yml" ] && cp "$BACKUP_DIR/docker-compose.picoaccounting.yml" "$CONTAINERS_DIR/pico-accounting/docker-compose.yml"

echo ""
echo "======================================================================"
echo "  DATEN ERFOLGREICH VORBEREITET!                                      "
echo "======================================================================"
echo ""
echo "Nächste Schritte:"
echo "1. Container starten:"
echo "   containers start"
echo ""
echo "2. PicoCalc PostgreSQL Datenbank wiederherstellen:"
echo "   docker exec -i picocalc-db pg_restore -U printuser -d printcalc --clean --if-exists < $BACKUP_DIR/picocalc_db.dump"
echo ""
echo "3. Überprüfen:"
echo "   containers status"
echo "======================================================================"
