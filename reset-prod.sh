#!/bin/bash
# =============================================================================
# PicoCalc - Datenbank auf dem Server zurücksetzen (Debian NUC)
# =============================================================================
#
# WARNUNG: Löscht ALLE Daten der PicoCalc-Datenbank (Produkte, Materialien, Maschinen, Events ...).
#
# Wann? Einmalig nach der Umstellung auf das neue Rezept-Schema (Alembic ab Baseline 0001): Die alte
# Datenbank hat ein anderes Schema und kann nicht migriert werden. Nach dem Reset legt die neue App
# das Schema beim Start selbst an (alembic upgrade head + Standard-Stammdaten).
#
# Zwei Reihenfolgen:
#
#   A) Erst leeren, dann deployen (empfohlen, wenn du mit ./deploy.sh deployest)
#        ./reset-prod.sh --ohne-start      # sichert, stoppt die alte App, leert die DB, lässt die App AUS
#        git pull && ./deploy.sh           # startet die neue Version gegen die leere DB
#
#   B) Erst deployen, dann leeren
#        ./deploy.sh                       # die neue App startet gegen die alte DB nicht (unbekannte
#                                          # alembic-Revision) - das ist erwartet
#        ./reset-prod.sh                   # leert die DB und startet die (neue) App wieder
#
# Nie die App mit der ALTEN Version starten lassen, nachdem die DB geleert wurde: Sie würde das alte
# Schema sofort wieder anlegen.
#
# Der Dump landet im Home-Verzeichnis. Er passt nur zum ALTEN Schema und kann nicht in die neue
# Datenbank zurückgespielt werden.
#
# Andere Containernamen:  APP_CONTAINER=... DB_CONTAINER=... ./reset-prod.sh [--ohne-start]
# =============================================================================

set -euo pipefail

START_APP=1
case "${1:-}" in
    "") ;;
    --ohne-start) START_APP=0 ;;
    *) echo "Unbekannte Option: $1 (erlaubt: --ohne-start)"; exit 2 ;;
esac

APP_CONTAINER="${APP_CONTAINER:-picocalc-app}"
DB_CONTAINER="${DB_CONTAINER:-picocalc-db}"
DB_USER="${DB_USER:-printuser}"
DB_NAME="${DB_NAME:-printcalc}"
DUMP_FILE="$HOME/picocalc_vor_reset_$(date +%Y-%m-%d_%H-%M).dump"

echo "=========================================="
echo "  PicoCalc - DATENBANK-RESET"
echo "=========================================="
echo "App-Container: $APP_CONTAINER"
echo "DB-Container:  $DB_CONTAINER (Datenbank $DB_NAME)"
if [[ "$START_APP" == "1" ]]; then
    echo "Modus:         leeren und die App danach wieder starten (die NEUE Version muss bereits deployt sein)"
else
    echo "Modus:         leeren, App bleibt AUS (danach ./deploy.sh mit der neuen Version)"
fi
echo ""
echo "WARNUNG: Alle Daten der Datenbank werden gelöscht!"
read -r -p "Wirklich fortfahren? (j/N): " confirm
if [[ "$confirm" != "j" && "$confirm" != "J" ]]; then
    echo "Abbruch."
    exit 0
fi

echo ""
echo "Schritt 1/4: Sicherung erstellen -> $DUMP_FILE"
docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$DUMP_FILE"
echo "  OK ($(du -h "$DUMP_FILE" | cut -f1))"

echo ""
echo "Schritt 2/4: App stoppen ($APP_CONTAINER)"
docker stop "$APP_CONTAINER" >/dev/null 2>&1 || echo "  (Container läuft nicht oder existiert nicht - weiter)"

echo ""
echo "Schritt 3/4: Schema in $DB_NAME löschen und neu anlegen"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 \
    -c "DROP SCHEMA public CASCADE;" -c "CREATE SCHEMA public;"

if [[ "$START_APP" == "0" ]]; then
    echo ""
    echo "=========================================="
    echo "  Datenbank geleert - die App ist AUS"
    echo "=========================================="
    echo "Nächster Schritt (neue Version bauen und starten, sie legt das Schema an):"
    echo "   git pull origin main && ./deploy.sh"
    echo "Danach in der App unter /settings, /materials und /machines die Stammdaten neu erfassen."
    exit 0
fi

echo ""
echo "Schritt 4/4: App starten (legt das Schema per Alembic neu an)"
docker start "$APP_CONTAINER"

echo ""
echo "Warte auf den Start der App ..."
for i in $(seq 1 30); do
    if docker logs --tail 20 "$APP_CONTAINER" 2>&1 | grep -q "Application startup complete"; then
        break
    fi
    sleep 2
done

echo ""
echo "=========================================="
echo "  Reset abgeschlossen"
echo "=========================================="
docker logs --since 1m --tail 8 "$APP_CONTAINER" 2>&1
echo ""

REVISION="$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -At \
    -c 'SELECT version_num FROM alembic_version;' 2>/dev/null || true)"
HEAD_REVISION="$(docker exec "$APP_CONTAINER" alembic heads 2>/dev/null | awk 'NR==1 {print $1}' || true)"
if [[ -n "$HEAD_REVISION" && "$REVISION" == "$HEAD_REVISION" ]]; then
    echo "OK: Schema-Revision $REVISION (aktuell) - die neue Version läuft."
    echo "Jetzt in der App unter /settings, /materials und /machines die Stammdaten neu erfassen."
else
    echo "WARNUNG: Schema-Revision '${REVISION:-nichts}' passt nicht zur App (erwartet: '${HEAD_REVISION:-unbekannt}')."
    echo "Läuft noch die alte App-Version? Erst die neue Version deployen, dann dieses Skript erneut starten."
    exit 1
fi
