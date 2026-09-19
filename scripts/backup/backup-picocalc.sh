#!/bin/bash
# =============================================================================
# PicoCalc - Backup auf den OMV (NFS-Share)
# =============================================================================
# Sichert die PostgreSQL-Datenbank (pg_dump, Custom-Format), das Storage-Verzeichnis (SVG-Konverter)
# und optional die .env. Die Sicherung wird geprüft (Dump lesbar, Archiv lesbar), bevor sie gilt.
#
# Aufbewahrung: täglich KEEP_DAILY Stände, dazu sonntags KEEP_WEEKLY Wochenstände.
#
# Konfiguration: Umgebungsvariablen oder /etc/picocalc-backup.env (siehe picocalc-backup.env.example).
# Aufruf (als root, damit docker erreichbar ist):   bash backup-picocalc.sh
# Einrichtung und Wiederherstellung: siehe README.md in diesem Ordner.
# =============================================================================

set -euo pipefail

CONFIG_FILE="${CONFIG_FILE:-/etc/picocalc-backup.env}"
# shellcheck disable=SC1090
[[ -f "$CONFIG_FILE" ]] && source "$CONFIG_FILE"

DB_CONTAINER="${DB_CONTAINER:-picocalc-db}"
DB_USER="${DB_USER:-printuser}"
DB_NAME="${DB_NAME:-printcalc}"
STORAGE_DIR="${STORAGE_DIR:-/srv/containers/picocalc/storage}"
ENV_FILE="${ENV_FILE:-/srv/containers/picocalc/.env}"       # leer lassen, um die .env nicht zu sichern
MOUNT_POINT="${MOUNT_POINT:-/mnt/omv-backup}"               # hier wird der NFS-Share eingebunden
BACKUP_DIR="${BACKUP_DIR:-$MOUNT_POINT/picocalc}"
REQUIRE_MOUNT="${REQUIRE_MOUNT:-1}"                          # 1 = nur sichern, wenn MOUNT_POINT wirklich eingebunden ist
KEEP_DAILY="${KEEP_DAILY:-14}"
KEEP_WEEKLY="${KEEP_WEEKLY:-8}"
STAMP="${BACKUP_STAMP:-$(date +%Y-%m-%d_%H%M)}"              # BACKUP_STAMP nur für Tests
WEEKDAY="${BACKUP_WEEKDAY:-$(date +%u)}"                     # 7 = Sonntag

log()  { echo "[$(date '+%F %T')] $*"; }
fail() { echo "[$(date '+%F %T')] FEHLER: $*" >&2; exit 1; }

TMP_FILES=()
cleanup() { for f in "${TMP_FILES[@]:-}"; do [[ -n "$f" ]] && rm -f -- "$f"; done; }
trap cleanup EXIT

# --- Nur ein Backup gleichzeitig ---------------------------------------------
if command -v flock >/dev/null 2>&1; then
    exec 9>"${LOCK_FILE:-/tmp/picocalc-backup.lock}"
    flock -n 9 || fail "Es läuft bereits ein Backup."
fi

# --- Ziel prüfen: nie versehentlich auf die lokale Platte schreiben ----------
if [[ "$REQUIRE_MOUNT" == "1" ]]; then
    if ! mountpoint -q "$MOUNT_POINT"; then
        # fstab mit x-systemd.automount bindet beim ersten Zugriff ein; ansonsten ein Mount versuchen
        ls "$MOUNT_POINT" >/dev/null 2>&1 || true
        mountpoint -q "$MOUNT_POINT" || mount "$MOUNT_POINT" 2>/dev/null || true
    fi
    mountpoint -q "$MOUNT_POINT" || fail "$MOUNT_POINT ist nicht eingebunden (OMV nicht erreichbar?). Es wurde nichts gesichert."
fi
mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"
touch "$BACKUP_DIR/.schreibtest" 2>/dev/null || fail "$BACKUP_DIR ist nicht beschreibbar (NFS-Rechte prüfen)."
rm -f "$BACKUP_DIR/.schreibtest"

DAILY="$BACKUP_DIR/daily"
WEEKLY="$BACKUP_DIR/weekly"

# --- 1. Datenbank ------------------------------------------------------------
DB_FILE="$DAILY/picocalc_db_${STAMP}.dump"
log "Datenbank $DB_NAME aus $DB_CONTAINER sichern -> $DB_FILE"
TMP_FILES+=("$DB_FILE.part")
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$DB_FILE.part"
[[ -s "$DB_FILE.part" ]] || fail "Der Datenbank-Dump ist leer."
# Prüfung: pg_restore muss das Inhaltsverzeichnis des Dumps lesen können. Die Ausgabe wird erst komplett
# gesammelt: "| grep -q" würde die Pipe beim ersten Treffer schließen, pg_restore bekäme SIGPIPE und
# scheiterte unter pipefail (je nach Timing) trotz gültigem Dump.
DUMP_LIST=$(docker exec -i "$DB_CONTAINER" pg_restore --list < "$DB_FILE.part") \
    || fail "pg_restore kann den Datenbank-Dump nicht lesen."
grep -q "TABLE public" <<<"$DUMP_LIST" || fail "Der Datenbank-Dump enthält keine Tabellen."
mv -- "$DB_FILE.part" "$DB_FILE"
log "  OK ($(du -h "$DB_FILE" | cut -f1))"

# --- 2. Storage (SVG-Konverter) ----------------------------------------------
STORAGE_FILE=""
if [[ -d "$STORAGE_DIR" ]]; then
    STORAGE_FILE="$DAILY/picocalc_storage_${STAMP}.tar.gz"
    log "Storage $STORAGE_DIR sichern -> $STORAGE_FILE"
    TMP_FILES+=("$STORAGE_FILE.part")
    tar -czf "$STORAGE_FILE.part" -C "$(dirname "$STORAGE_DIR")" "$(basename "$STORAGE_DIR")"
    tar -tzf "$STORAGE_FILE.part" >/dev/null || fail "Das Storage-Archiv ist nicht lesbar."
    mv -- "$STORAGE_FILE.part" "$STORAGE_FILE"
    log "  OK ($(du -h "$STORAGE_FILE" | cut -f1))"
else
    log "Kein Storage-Verzeichnis unter $STORAGE_DIR - übersprungen."
fi

# --- 3. .env (enthält Passwörter -> nur für den Besitzer lesbar) --------------
ENV_COPY=""
if [[ -n "$ENV_FILE" && -f "$ENV_FILE" ]]; then
    ENV_COPY="$DAILY/picocalc_env_${STAMP}"
    ( umask 077; cp -- "$ENV_FILE" "$ENV_COPY" )
    chmod 600 -- "$ENV_COPY"
    log ".env gesichert -> $ENV_COPY"
fi

# --- 4. Wochenstand (sonntags) ------------------------------------------------
if [[ "$WEEKDAY" == "7" ]]; then
    for f in "$DB_FILE" "$STORAGE_FILE" "$ENV_COPY"; do
        if [[ -n "$f" && -f "$f" ]]; then cp -p -- "$f" "$WEEKLY/"; fi
    done
    log "Wochenstand abgelegt in $WEEKLY"
fi

# --- 5. Alte Stände entfernen -------------------------------------------------
prune() {   # prune <Ordner> <Muster> <behalten>
    local dir="$1" pattern="$2" keep="$3"
    # Der Zeitstempel im Dateinamen sortiert chronologisch: neueste zuerst, alles ab Platz keep+1 entfernen
    # (ls schlägt fehl, wenn nichts passt - z.B. beim ersten Lauf; das ist kein Fehler)
    # shellcheck disable=SC2012
    { ls -1 "$dir"/$pattern 2>/dev/null || true; } | sort -r | tail -n +"$((keep + 1))" | while read -r old; do
        rm -f -- "$old"
        log "Entfernt (Aufbewahrung): $old"
    done
}
for pattern in "picocalc_db_*.dump" "picocalc_storage_*.tar.gz" "picocalc_env_*"; do
    prune "$DAILY" "$pattern" "$KEEP_DAILY"
    prune "$WEEKLY" "$pattern" "$KEEP_WEEKLY"
done

count() { { ls -1 "$1"/picocalc_db_*.dump 2>/dev/null || true; } | wc -l; }
log "Backup abgeschlossen: $(count "$DAILY") tägliche und $(count "$WEEKLY") wöchentliche Datenbank-Stände."
