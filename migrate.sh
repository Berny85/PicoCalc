#!/bin/bash
#
# Datenbank-Migrationsskript für PicoCalc mit Alembic
#
# Befehle:
#   ./migrate.sh migrate           - Führt alle ausstehenden Migrationen aus (Standard)
#   ./migrate.sh create "Message"  - Erstellt eine neue Migration (--autogenerate)
#   ./migrate.sh downgrade         - Setzt die letzte Migration zurück
#   ./migrate.sh history           - Zeigt die Migrationshistorie an
#   ./migrate.sh current           - Zeigt die aktuelle Migration an
#   ./migrate.sh stamp             - Markiert die Datenbank als aktuell (ohne Migration)

set -e

# Farben für Output
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Prüfe ob Docker läuft
if ! docker-compose ps > /dev/null 2>&1; then
    echo -e "${RED}❌ Fehler: Docker-Container sind nicht gestartet!${NC}"
    echo -e "${YELLOW}Bitte zuerst ausführen: docker-compose up -d${NC}"
    exit 1
fi

COMMAND="${1:-migrate}"
MESSAGE="$2"

echo -e "${CYAN}🔄 PicoCalc Datenbank-Migration${NC}"
echo -e "${CYAN}================================${NC}\n"

case "$COMMAND" in
    migrate)
        echo -e "${YELLOW}⬆️  Führe Migrationen aus...${NC}"
        docker-compose exec -T web alembic upgrade head
        echo -e "\n${GREEN}✅ Migration erfolgreich abgeschlossen!${NC}"
        ;;
    
    create)
        if [ -z "$MESSAGE" ]; then
            echo -e "${RED}❌ Fehler: Bitte eine Nachricht angeben!${NC}"
            echo -e "${YELLOW}Beispiel: ./migrate.sh create 'Added user table'${NC}"
            exit 1
        fi
        echo -e "${YELLOW}📝 Erstelle neue Migration: '$MESSAGE'...${NC}"
        docker-compose exec -T web alembic revision --autogenerate -m "$MESSAGE"
        
        # Kopiere neue Migration in das lokale Verzeichnis
        echo -e "\n${YELLOW}📥 Kopiere neue Migrationsdatei...${NC}"
        docker cp "picocalc-web-1:/app/alembic/versions/." app/alembic/versions/ 2>/dev/null || true
        
        echo -e "\n${GREEN}✅ Migration erstellt! Führe jetzt aus mit: ./migrate.sh${NC}"
        ;;
    
    downgrade)
        echo -e "${YELLOW}⬇️  Setze letzte Migration zurück...${NC}"
        docker-compose exec -T web alembic downgrade -1
        echo -e "\n${GREEN}✅ Downgrade erfolgreich!${NC}"
        ;;
    
    history)
        echo -e "${YELLOW}📜 Migrationshistorie:${NC}"
        docker-compose exec -T web alembic history --verbose
        ;;
    
    current)
        echo -e "${YELLOW}📍 Aktuelle Migration:${NC}"
        docker-compose exec -T web alembic current
        ;;
    
    stamp)
        echo -e "${YELLOW}🔖 Markiere Datenbank als aktuell...${NC}"
        docker-compose exec -T web alembic stamp head
        echo -e "\n${GREEN}✅ Datenbank markiert!${NC}"
        ;;
    
    *)
        echo -e "${RED}❌ Unbekannter Befehl: $COMMAND${NC}"
        echo "Verfügbare Befehle: migrate, create, downgrade, history, current, stamp"
        exit 1
        ;;
esac

echo ""
