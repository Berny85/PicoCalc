#!/bin/bash
# =============================================================================
# PicoCalc - Deployment auf dem Debian-NUC (wird AUF dem NUC ausgeführt)
# =============================================================================
#   ssh berny@192.168.50.8
#   cd /srv/containers/picocalc && bash deploy.sh
#
# Ablauf: Code aus GitHub holen -> Container stoppen -> neu bauen und starten -> auf Datenbank und
# App warten -> Status zeigen. Die App legt/aktualisiert das Datenbankschema beim Start selbst (Alembic).
# Daten (./db_data, ./storage) bleiben erhalten.
# =============================================================================

set -euo pipefail

# Projektordner = Ordner dieses Skripts (unabhängig davon, von wo aus es gestartet wird)
cd "$(dirname "$(readlink -f "$0")")"

COMPOSE_FILE="docker-compose.prod.yml"
DC="docker compose -f $COMPOSE_FILE"

BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()     { echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"; }
success() { echo -e "${GREEN}[$(date '+%H:%M:%S')] ✓${NC} $1"; }
warning() { echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠${NC} $1"; }
error()   { echo -e "${RED}[$(date '+%H:%M:%S')] ✗${NC} $1"; }

echo "========================================"
echo "PicoCalc Deployment ($(pwd))"
echo "========================================"

[ -f "$COMPOSE_FILE" ] || { error "$COMPOSE_FILE nicht gefunden - liegt das Skript im Projektordner?"; exit 1; }
[ -f .env ] || { error ".env fehlt (DB_PASSWORD wird benötigt)"; exit 1; }

log "[1/5] Aktualisiere Code aus GitHub..."
if ! git pull origin main; then
    error "git pull ist fehlgeschlagen."
    warning "Bei 'dubiose Besitzverhältnisse' einmalig:  git config --global --add safe.directory $(pwd)"
    warning "Bei lokalen Änderungen:  git status --short  ansehen und klären."
    exit 1
fi
success "Code aktualisiert ($(git log --oneline -1))"

log "[2/5] Stoppe alte Container (Daten bleiben erhalten)..."
$DC down
success "Container gestoppt"

log "[3/5] Baue und starte neue Container..."
$DC up --build -d
success "Container gestartet"

log "[4/5] Warte auf Datenbank und App (max. 90 Sekunden)..."
for i in $(seq 1 45); do
    if $DC exec -T db pg_isready -U printuser -d printcalc >/dev/null 2>&1; then
        break
    fi
    sleep 2
done
$DC exec -T db pg_isready -U printuser -d printcalc >/dev/null 2>&1 \
    && success "Datenbank ist bereit" \
    || { error "Datenbank ist nicht bereit"; $DC logs db --tail 20; exit 1; }

APP_OK=0
for i in $(seq 1 45); do
    if curl -sf -o /dev/null http://localhost:5000/; then APP_OK=1; break; fi
    sleep 2
done
if [ "$APP_OK" = "1" ]; then
    success "App antwortet auf Port 5000"
else
    error "App antwortet nicht. Letzte Log-Zeilen:"
    $DC logs web --tail 25
    warning "Typische Ursache nach dem Schema-Umbau: alte Datenbank -> ./reset-prod.sh (siehe DEPLOYMENT.md)"
    exit 1
fi

echo -n "Schema-Revision: "
$DC exec -T db psql -U printuser -d printcalc -At -c "SELECT version_num FROM alembic_version;" || true

log "[5/5] Container-Status:"
$DC ps

echo ""
echo "========================================"
success "Deployment abgeschlossen!  http://192.168.50.8:5000"
echo "========================================"
