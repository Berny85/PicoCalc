#!/bin/bash
# Setup-Skript für Auto-Deployment auf dem NUC
# Erstellt systemd-Service oder crontab-Eintrag

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="picocalc"

# Farben
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}PicoCalc Auto-Deploy Setup${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Prüfe ob wir auf Unraid sind (kein systemd)
if [ -f "/boot/config/go" ]; then
    echo -e "${YELLOW}Unraid erkannt - verwende Crontab${NC}"
    
    # Prüfe ob Eintrag bereits existiert
    CRON_CMD="*/5 * * * * $SCRIPT_DIR/auto-deploy.sh >> $SCRIPT_DIR/auto-deploy.log 2>&1"
    
    if crontab -l 2>/dev/null | grep -q "auto-deploy.sh"; then
        echo "Auto-Deploy ist bereits im Crontab konfiguriert."
        echo ""
        echo "Möchten Sie:"
        echo "  1) Auto-Deploy deaktivieren"
        echo "  2) Auto-Deploy neu konfigurieren"
        echo "  3) Nichts tun"
        read -p "Auswahl (1-3): " choice
        
        case $choice in
            1)
                crontab -l | grep -v "auto-deploy.sh" | crontab -
                echo -e "${GREEN}Auto-Deploy deaktiviert${NC}"
                ;;
            2)
                crontab -l | grep -v "auto-deploy.sh" | crontab -
                (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
                echo -e "${GREEN}Auto-Deploy neu konfiguriert${NC}"
                ;;
            *)
                echo "Keine Änderungen vorgenommen"
                ;;
        esac
    else
        echo "Füge Crontab-Eintrag hinzu..."
        (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
        echo -e "${GREEN}✓ Auto-Deploy aktiviert${NC}"
        echo ""
        echo "Prüft alle 5 Minuten auf neue Commits."
        echo "Log-Datei: $SCRIPT_DIR/auto-deploy.log"
    fi
    
    echo ""
    echo "Aktueller Crontab:"
    crontab -l | grep auto-deploy || echo "(nicht vorhanden)"
    
else
    echo "Standard Linux erkannt - verwende systemd"
    
    # Systemd Service erstellen
    SERVICE_FILE="/etc/systemd/system/${PROJECT_NAME}-autodeploy.service"
    TIMER_FILE="/etc/systemd/system/${PROJECT_NAME}-autodeploy.timer"
    
    # Service
    sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=PicoCalc Auto-Deployment
After=network.target

[Service]
Type=oneshot
User=$(whoami)
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/auto-deploy.sh
StandardOutput=append:$SCRIPT_DIR/auto-deploy.log
StandardError=append:$SCRIPT_DIR/auto-deploy.log

[Install]
WantedBy=multi-user.target
EOF

    # Timer (alle 5 Minuten)
    sudo tee "$TIMER_FILE" > /dev/null << EOF
[Unit]
Description=PicoCalc Auto-Deployment Timer
Requires=${PROJECT_NAME}-autodeploy.service

[Timer]
OnCalendar=*:0/5
Persistent=true

[Install]
WantedBy=timers.target
EOF

    # Systemd neu laden und aktivieren
    sudo systemctl daemon-reload
    sudo systemctl enable ${PROJECT_NAME}-autodeploy.timer
    sudo systemctl start ${PROJECT_NAME}-autodeploy.timer
    
    echo -e "${GREEN}✓ Auto-Deploy Service aktiviert${NC}"
    echo ""
    echo "Status prüfen mit:"
    echo "  sudo systemctl status ${PROJECT_NAME}-autodeploy.timer"
    echo "  sudo systemctl status ${PROJECT_NAME}-autodeploy.service"
    echo "  tail -f $SCRIPT_DIR/auto-deploy.log"
fi

echo ""
echo -e "${GREEN}Setup abgeschlossen!${NC}"
