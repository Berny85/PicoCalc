#!/bin/bash
# Test-Skript für Auto-Deployment
# Zeigt aktuellen Status und führt einen Test-Deploy durch

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/auto-deploy.log"

# Farben
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}PicoCalc Auto-Deploy Status${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Prüfe Auto-Deploy Status
if crontab -l 2>/dev/null | grep -q "auto-deploy.sh"; then
    echo -e "${GREEN}✓ Auto-Deploy ist im Crontab aktiviert${NC}"
    echo ""
    echo "Crontab-Eintrag:"
    crontab -l | grep auto-deploy | sed 's/^/  /'
else
    echo -e "${YELLOW}⚠ Auto-Deploy ist NICHT im Crontab konfiguriert${NC}"
    echo "  Führen Sie ./setup-auto-deploy.sh aus zum Aktivieren"
fi

echo ""
echo -e "${BLUE}----------------------------------------${NC}"
echo "Git-Status:"
echo ""

cd "$SCRIPT_DIR"

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main 2>/dev/null || echo "N/A")

echo "  Lokaler Commit:  ${LOCAL:0:8}"
echo "  Remote Commit:   ${REMOTE:0:8}"

if [ "$LOCAL" != "$REMOTE" ] && [ "$REMOTE" != "N/A" ]; then
    echo -e "  Status: ${YELLOW}⚠ Neue Version verfügbar!${NC}"
else
    echo -e "  Status: ${GREEN}✓ Auf dem neuesten Stand${NC}"
fi

echo ""
echo -e "${BLUE}----------------------------------------${NC}"
echo "Letzte Log-Einträge:"
echo ""

if [ -f "$LOG_FILE" ]; then
    tail -20 "$LOG_FILE" | sed 's/^/  /'
else
    echo -e "  ${YELLOW}(Log-Datei existiert noch nicht)${NC}"
fi

echo ""
echo -e "${BLUE}----------------------------------------${NC}"
echo ""

# Manuelles Deploy anbieten
read -p "Manuelles Deployment jetzt durchführen? (j/n): " answer

if [ "$answer" = "j" ] || [ "$answer" = "ja" ]; then
    echo ""
    echo "Starte Deployment..."
    echo ""
    "$SCRIPT_DIR/auto-deploy.sh"
    echo ""
    echo -e "${GREEN}✓ Deployment-Test abgeschlossen${NC}"
    echo "Siehe $LOG_FILE für Details"
else
    echo "Abbruch"
fi
