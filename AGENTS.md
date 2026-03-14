# PicoCalc - Agent Documentation

> **Language Note**: Dieses Projekt verwendet Deutsch als Primärsprache für Code-Kommentare, Dokumentation und UI-Texte.

## Project Overview

**PicoCalc** ist ein webbasierter Produktpreis-Kalkulator für kleine Fertigungsunternehmen. Er berechnet Produktionskosten für verschiedene Produkttypen wie 3D-Druck, Sticker-Produktion, Die-Cut-Sticker, Papierprodukte und Laser-Gravur.

- **Repository**: https://github.com/Berny85/PicoCalc.git
- **Production URL**: http://192.168.50.8:5000
- **Primary Language**: German (Code, Kommentare, Dokumentation, UI)

## Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Backend | Python | 3.11 |
| Web Framework | FastAPI | 0.109.0 |
| Database | PostgreSQL | 16 (Alpine) |
| ORM | SQLAlchemy | 2.0.25 |
| Frontend | Jinja2 Templates + HTMX | 1.9.10 |
| Styling | Vanilla CSS (Purple/Blue Theme) |
| Deployment | Docker + Docker Compose |
| Infrastructure | Intel NUC mit Unraid OS |
| CI/CD | GitHub Actions + Docker Hub |

## Project Structure

```
PicoCalc/
├── app/                          # Hauptanwendung
│   ├── main.py                   # FastAPI App mit allen Routes (~1597 Zeilen)
│   ├── models.py                 # SQLAlchemy Datenbank-Modelle (~436 Zeilen)
│   ├── database.py               # Datenbank-Konfiguration und Session-Management
│   ├── requirements.txt          # Python-Abhängigkeiten
│   ├── Dockerfile                # Container-Image Definition
│   └── templates/                # Jinja2 HTML Templates
│       ├── base.html             # Base Layout mit Navigation und CSS
│       ├── index.html            # Dashboard
│       ├── materials/            # Material-Verwaltung UI
│       ├── machines/             # Maschinen-Verwaltung UI
│       ├── products/             # Produkt-Formulare und Details
│       ├── feedback/             # Feedback-Formular und Liste
│       ├── ideas/                # Kanban-Style Ideen-Board
│       ├── tools/                # PNG-zu-SVG Converter & Bibliothek
│       └── partials/             # HTMX Partial Templates
├── backup/                       # Backup-Skripte
│   ├── backup-script.sh          # Automatisiertes PostgreSQL Backup
│   └── restore-script.sh         # Datenbank-Wiederherstellung
├── alembic/                      # Datenbank-Migrationen (Alembic)
│   ├── versions/                 # Migrations-Skripte
│   └── env.py                    # Alembic Umgebungs-Konfiguration
├── alembic.ini                   # Alembic Hauptkonfiguration
├── migrate.ps1                   # Windows Migrationsskript
├── migrate.sh                    # Linux/Mac Migrationsskript
├── .github/workflows/            # CI/CD Konfiguration
│   └── deploy.yml                # GitHub Actions Workflow
├── docker-compose.yaml           # Entwicklungs-Konfiguration
├── docker-compose.prod.yml       # Produktions-Konfiguration
├── postgresql.conf               # PostgreSQL WAL Konfiguration
├── deploy.sh                     # NUC Deployment Script (Bash)
├── deploy-to-nuc.ps1             # Windows Deployment Script (PowerShell)
├── backup-to-local.ps1           # Lokales Backup-Download Script
├── quick-deploy.sh               # Schnelles Deployment (ohne Rebuild)
├── reset-prod.sh                 # Produktions-Reset (⚠️ löscht Daten)
├── README.md                     # Projekt-Übersicht (Deutsch)
└── DEPLOYMENT.md                 # Detaillierte Deployment-Doku (Deutsch)
```

## Architecture

### Development Environment (Windows 11)
- **Docker Desktop** für Containerisierung
- **Local URL**: http://localhost:5000
- **Database**: PostgreSQL auf Port 5432
- **pgAdmin**: http://localhost:5050
- **Hot reload**: Code als Volume gemountet, Auto-Reload aktiviert

### Production Environment (Intel NUC mit Unraid)
- **IP**: 192.168.50.8
- **PicoCalc App**: http://192.168.50.8:5000
- **Portainer**: http://192.168.50.8:9000 (Docker Management)
- **Dozzle**: http://192.168.50.8:8080 (Log-Viewer)
- **pgAdmin**: http://192.168.50.8:5050

### Production Services (docker-compose.prod.yml)

| Service | Container Name | Port | Description |
|---------|---------------|------|-------------|
| db | picocalc-db | 5432 | PostgreSQL mit WAL Archiving |
| web | picocalc-app | 5000 | FastAPI Anwendung |
| backup | picocalc-backup | - | Automatisierte Volume-Backups (3x täglich) |
| dozzle | dozzle | 8080 | Docker Log-Viewer |
| pgadmin | picocalc-pgadmin | 5050 | PostgreSQL Management UI |

## Database Models

### Machine (`models.py`)
Repräsentiert Produktionsgeräte (3D-Drucker, Cutter, Tintenstrahl-Drucker):
- `name`, `machine_type` (3d_printer, cutter_plotter, inkjet_printer, other)
- `depreciation_euro` - Geräte-Abschreibungskosten (zeitbasiert)
- `lifespan_hours` - Erwartete Lebensdauer in Stunden
- `power_kw` - Stromverbrauch in kW
- `lifespan_pages` - Für Tintenstrahl-Drucker: Lebensdauer in Seiten
- `depreciation_per_page` - Für Tintenstrahl-Drucker: Abschreibung pro Seite
- **Neu**: `cost_per_sheet` - Für Plotter/Drucker: Kosten pro Bogen (für Sticker-Produktion)
- Methoden: `calculate_cost_per_hour()`, `calculate_cost_per_page()`, `calculate_cost_per_sheet()`, `calculate_cost_per_unit()`

### MaterialType (`models.py`)
Konfigurierbare Material-Kategorien:
- `key` - Interner Identifier (z.B. 'filament', 'sticker_sheet')
- `name` - Anzeigename
- `sort_order` - Für Dropdown-Reihenfolge
- `is_active` - 1 = Aktiv, 0 = Inaktiv

### Material (`models.py`)
Repräsentiert Rohmaterialien (Filamente, Sticker-Sheets, Papier):
- `name`, `material_type` (verweist auf MaterialType.key)
- `brand`, `color`, `unit` (kg, sheet, m, piece)
- `price_per_unit`

### Product (`models.py`)
Zentrale Entity mit typ-spezifischen Feldern:
- **Gemeinsam**: `name`, `product_type`, `category`, `labor_minutes`, `labor_rate_per_hour`, `notes`
  - ⚠️ **Wichtig**: `labor_minutes` (nicht mehr `labor_hours`) - Arbeitszeit in Minuten
  - ⚠️ **Wichtig**: `packaging_cost` und `shipping_cost` entfernt - werden jetzt beim Verkauf erfasst
- **Berechnungsmodus**: `calculation_mode` ("per_unit" oder "per_batch"), `units_per_batch`
- **3D-Druck**: `filament_material_id`, `filament_weight_g`, `print_time_hours`, `machine_id`
- **Sticker/Papier/Schreibwaren**: `sheet_material_id`, `sheet_count` (immer 1), `units_per_sheet`, `additional_machine_ids`
- **Laser**: `laser_material_id`, `laser_design_name`, `laser1_*`, `laser2_*`, `laser3_*` (Layer-Konfiguration)
- Methode: `calculate_costs()` - Gibt Kostenaufschlüsselung und Verkaufspreis-Vorschläge (30%, 50%, 100% Marge) zurück

### Feedback (`models.py`)
User-Feedback und Bug-Reports:
- `page_url`, `page_title` - Kontext wo Feedback gegeben wurde
- `category` - 'bug', 'feature', 'improvement', 'other'
- `message`, `status` - 'new', 'in_progress', 'done', 'rejected'

### Idea (`models.py`)
Kanban-Style Ideen-Board:
- `subject`, `content`
- `status` - 'todo', 'in_progress', 'done'

### ConvertedFile (`models.py`)
Gespeicherte PNG-zu-SVG Konvertierungen:
- `original_filename`, `stored_filename` (UUID)
- `file_path_png`, `file_path_svg`
- `conversion_mode` (spline/pixel), `color_mode` (color/binary)
- `description`, `tags`

### ProductImage (`models.py`)
Produktbilder:
- `product_id` - Verknüpfung zu Product
- `file_path`, `mime_type`
- `is_primary` - 1 = Hauptbild, 0 = Zusatzbild
- `converted_file_id` - Optionale Verknüpfung zu SVG-Bibliothek

### ProductComponent (`models.py`)
Komponenten-System für komplexe Produkte:
- `parent_product_id` - Hauptprodukt
- `component_product_id` - Einzelkomponente
- `quantity` - Anzahl der Komponente
- Wird für Produkte aus mehreren Teilen verwendet (z.B. Sets)

### SalesOrder (`models.py`)
Verkaufsaufträge mit mehreren Positionen:
- `order_number`, `customer_name`
- `packaging_cost`, `shipping_cost` - Werden hier erfasst (nicht mehr beim Produkt)
- `labor_minutes_packaging`, `labor_rate_packaging` - Arbeitszeit für Verpackung
- `status` - 'pending', 'produced', 'shipped', 'cancelled'
- Methode: `calculate_total()` - Gesamtsumme aller Positionen + Verpackung/Versand
- Beziehung: `items` → Liste von SalesOrderItem

### SalesOrderItem (`models.py`)
Einzelpositionen eines Verkaufsauftrags:
- `sales_order_id` - Verknüpfung zum Auftrag
- `product_id` - Verknüpfung zum Produkt
- `quantity` - Anzahl
- `unit_price` - Verkaufspreis pro Einheit
- `production_cost_per_unit` - Selbstkosten (Kopie zum Zeitpunkt des Verkaufs)
- Methode: `calculate_total()`, `calculate_profit()`

## Product Types & Categories

### Product Types (intern)
- `3d_print` - 3D-gedruckte Objekte
- `sticker` - Sticker-Produkte (Sheet & DieCut)
- `stationery` - Schreibwaren (Notizblöcke, Karten, Papierwaren)
- `assembly` - Zusammenbau-Produkte

### Sticker Categories
Für Produkttyp `sticker` gibt es zwei Unterkategorien:
- `StickerSheet` - Ganze Bögen mit mehreren Stickern
- `DieCut` - Einzeln geschnittene Sticker

### Categories (User-facing)
⚠️ **Wichtig**: Kategorie ist in der UI ausgeblendet und wird automatisch auf "Sonstiges" gesetzt.

Historisch: Dekoration, Technik, Ersatzteile, Spielzeug, Werkzeuge, Sticker, Papierprodukte, Sonstiges

## Dependencies (requirements.txt)

```
fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
jinja2==3.1.3
python-multipart==0.0.6
pydantic==2.5.3
pydantic-settings==2.1.0
python-dotenv==1.0.0
alembic==1.13.1
# PNG to SVG Converter
vtracer==0.6.11
pillow==10.2.0
```

## Build and Test Commands

### Development
```bash
# Starte alle Services
docker-compose up -d

# Zeige Logs
docker-compose logs -f web

# Stoppe Services
docker-compose down

# Rebuild nach Abhängigkeits-Änderungen
docker-compose up --build -d

# Reset Database (⚠️ löscht alle Daten)
docker-compose down -v
docker-compose up -d
```

### Production (auf NUC)
```bash
# Vollständiges Deployment mit Rebuild
docker compose -f docker-compose.prod.yml up --build -d

# Schneller Restart (kein Rebuild)
docker compose -f docker-compose.prod.yml up -d

# Container-Status prüfen
docker compose -f docker-compose.prod.yml ps

# Logs anzeigen
docker logs picocalc-app
docker logs picocalc-db
```

### Windows Deployment (vom Dev-PC)
```powershell
# Automatisiertes Deployment via PowerShell
.\deploy-to-nuc.ps1

# Backup vom NUC herunterladen
.\backup-to-local.ps1

# Manuelles Deploy mit Log (nach git push)
.\deploy-manual.ps1
```

### Linux/macOS Deployment (vom Dev-PC)
```bash
# Manuelles Deploy mit Log (nach git push)
./deploy-manual.sh

# Erweitertes Deploy mit Zeitstempel-Logs
./deploy-and-log.sh           # Standard
./deploy-and-log.sh --no-push # Ohne Push
./deploy-and-log.sh --watch   # Mit Log-Verfolgung

# Logs anzeigen
tail -f logs/deploy_latest.log
```

### Auto-Deploy auf dem NUC (Unraid)
```bash
# Einrichten (erstellt Crontab-Eintrag)
./setup-auto-deploy.sh

# Status prüfen
./test-auto-deploy.sh

# Manuelle Ausführung
./auto-deploy.sh

# Logs anzeigen
tail -f auto-deploy.log
```

## Development Workflow

### Local Development
```powershell
# 1. Entwicklungsumgebung starten
docker-compose up -d

# 2. Entwickeln und testen unter http://localhost:5000

# 3. Änderungen zu GitHub pushen
git add .
git commit -m "Beschreibung"
git push origin main
```

### Deployment Flow
1. Push Code zu GitHub
2. GitHub Actions Workflow baut Docker Image und pusht zu Docker Hub
3. Portainer Webhook triggert Auto-Deployment auf NUC
4. NUC pullt neues Image und startet Container neu

## Key Configuration Files

### Environment Variables
Production erfordert diese Environment Variables (gesetzt in Portainer):
- `DB_PASSWORD` - PostgreSQL Passwort
- `SECRET_KEY` - FastAPI Secret Key
- `FILE_STORAGE_PATH` - Pfad für Dateispeicher (/app/storage)

### Database Connection
Development: `postgresql://printuser:printpass@db:5432/printcalc`
Production: `postgresql://printuser:${DB_PASSWORD}@db:5432/printcalc`

### PostgreSQL Configuration
- `postgresql.conf` - WAL Archiving Konfiguration für Point-in-Time Recovery
- Backups laufen 3x täglich (06:00, 12:00, 18:00)
- 14-Tage Retention Policy

## Code Style Guidelines

### Python
- Type Hints wo praktikabel verwenden
- PEP 8 Naming Conventions folgen
- Datenbank-Modelle verwenden deutsche Feldnamen für Business-Konzepte
- Route Handler verwenden deutsche Variablennamen für Form-Daten
- Dekorative Kommentare mit `==== SECTION ====` Format für Übersichtlichkeit

### Template Naming
- Listenansichten: `{resource}/list.html`
- Formular-Ansichten: `{resource}/form.html` oder `form_{type}.html`
- Detail-Ansichten: `{resource}/detail.html`
- HTMX Partials: `partials/{name}.html`

### Database Conventions
- Tabellennamen: plural, lowercase (machines, materials, products)
- Primary Keys: `id` (Integer, auto-increment)
- Timestamps: `created_at`, `updated_at`
- Foreign Keys: `{resource}_id`
- Boolean-Flags als Integer (0/1) für SQLite-Kompatibilität

## Testing

Aktuell hat das Projekt keine automatisierten Tests. Testing erfolgt manuell:

1. Entwicklungsumgebung starten: `docker-compose up -d`
2. http://localhost:5000 aufrufen
3. CRUD-Operationen für alle Entities testen
4. Kostenberechnungen gegen erwartete Werte prüfen
5. Responsive Design in verschiedenen Browsern testen

## Security Considerations

1. **Keine sensiblen Daten im Code** - Passwörter via Environment Variables
2. **Datenbank** - PostgreSQL hinter Docker-Netzwerk, Port 5432 nur auf Host exposed
3. **Secrets Management** - Docker Secrets oder Portainer Environment Variables
4. **Backups** - Automatisierte Backups mit Retention
5. **Keine Authentifizierung** - Aktuelle Version hat keine User-Authentifizierung (nur interner Gebrauch)

## Backup and Restore

### Automated Backups
- Läuft 3x täglich via `docker-volume-backup` Container
- Location: `/mnt/user/backups/picocalc/`
- Format: `backup-YYYY-MM-DDTHH-MM-SS.tar.gz`
- Retention: 14 Tage (automatische Löschung)

### Manual Backup to Local Machine
```powershell
.\backup-to-local.ps1
```

### Restore from Backup (auf NUC)
```bash
# Restore latest backup
./backup/restore-script.sh latest

# Restore specific backup
./backup/restore-script.sh 20250115_120000
```

## Special Features

### PNG to SVG Converter
- Tool unter `/tools/png-to-svg`
- Nutzt vtracer Bibliothek für Vektorisierung
- Konvertierte Dateien können in SVG-Bibliothek gespeichert werden
- Bibliothek verfügbar unter `/tools/converted-files`
- Unterstützte Formate: PNG, JPG, WEBP, BMP

### Product Images
- Bilder können zu Produkten hochgeladen werden
- Unterstützt PNG, JPG, WEBP
- SVGs aus der Bibliothek können mit Produkten verknüpft werden
- Hauptbild-Funktionalität für primäre Produktfotos
- Bilder werden in `FILE_STORAGE_PATH/products/YYYY/MM/` organisiert

### Kanban-Style Ideas Board
- Ideen können in Status "todo", "in_progress", "done" verschoben werden
- Drag & Drop Funktionalität (AJAX Status-Update)
- Schnelles Notieren von Verbesserungsideen

## Database Migrations (Alembic)

PicoCalc verwendet **Alembic** für Datenbank-Migrationen.

### Migrationsskripte

| Plattform | Befehl | Beschreibung |
|-----------|--------|--------------|
| Windows | `.\migrate.ps1` | Führt ausstehende Migrationen aus |
| Windows | `.\migrate.ps1 -Command create -Message "..."` | Erstellt neue Migration |
| Linux/NUC | `./migrate.sh` | Führt ausstehende Migrationen aus |
| Linux/NUC | `./migrate.sh create "..."` | Erstellt neue Migration |

### Verfügbare Befehle

```bash
# Migrationen ausführen (Standard)
./migrate.sh migrate

# Neue Migration erstellen (--autogenerate)
./migrate.sh create "Added labor_minutes column"

# Letzte Migration zurücksetzen
./migrate.sh downgrade

# Migrationshistorie anzeigen
./migrate.sh history

# Aktuelle Migration anzeigen
./migrate.sh current

# Datenbank als aktuell markieren (ohne Migration)
./migrate.sh stamp
```

### Manuelle Alembic-Befehle

```bash
# Innerhalb des Containers
docker-compose exec web alembic revision --autogenerate -m "Description"
docker-compose exec web alembic upgrade head
docker-compose exec web alembic downgrade -1
```

### Wichtige Hinweise

- Migrationen werden automatisch beim Deployment ausgeführt (siehe `deploy.sh`)
- Neue Migrationen müssen ins Git committet werden (`alembic/versions/`)
- Die `env.py` liest `DATABASE_URL` aus den Umgebungsvariablen
- Autogenerate erkennt Schema-Änderungen automatisch

## Common Tasks

### Adding a New Product Type
1. Typ zu `PRODUCT_TYPES` in `main.py` hinzufügen
2. Typ-spezifische Felder zu `Product` Modell in `models.py` hinzufügen
3. Formular-Template erstellen: `templates/products/form_{type}.html`
4. Routes für Create/Edit in `main.py` hinzufügen
5. Berechnungslogik zu `calculate_costs()` in models erweitern

### Adding Database Fields (Mit Alembic Migrationen)
1. Spalte zu Modell in `models.py` hinzufügen
2. Formular-Templates aktualisieren
3. Route Handler in `main.py` aktualisieren
4. Migration erstellen und ausführen:
   ```powershell
   # Windows
   .\migrate.ps1 -Command create -Message "Added new column"
   .\migrate.ps1

   # Linux/Mac/NUC
   ./migrate.sh create "Added new column"
   ./migrate.sh
   ```

### Updating Dependencies
1. `app/requirements.txt` bearbeiten
2. Container rebuild: `docker-compose up --build -d`
3. Gründlich testen
4. Änderungen committen

## CI/CD Pipeline

Der GitHub Actions Workflow (`.github/workflows/deploy.yml`):
1. Triggert bei Push auf `main` Branch
2. Baut Docker Image aus `app/` Verzeichnis
3. Pusht zu Docker Hub (`bernys/picocalc:latest`)
4. Triggert Portainer Webhook für Auto-Deployment

Required GitHub Secrets:
- `DOCKER_USERNAME` - Docker Hub Username
- `DOCKER_PASSWORD` - Docker Hub Access Token
- `PORTAINER_WEBHOOK_URL` - Portainer Stack Webhook URL

## Troubleshooting

### Database Connection Issues
```bash
# Prüfe ob PostgreSQL bereit ist
docker exec picocalc-db pg_isready -U printuser

# Zeige Datenbank-Logs
docker logs picocalc-db
```

### Application Won't Start
```bash
# Prüfe auf Syntax Errors
docker logs picocalc-app

# Verifiziere Environment Variables
docker exec picocalc-app env | grep DATABASE
```

### Reset Development Database
```bash
docker-compose down -v  # Entfernt Volumes
docker-compose up -d    # Erstellt neu
```

### Production Reset (⚠️ Zerstört alle Daten)
```bash
# Nur auf NUC - mit Vorsicht verwenden!
./reset-prod.sh
```

## Important Notes for AI Agents

1. **German Language**: Alle User-facing Texte sind auf Deutsch. Neue UI-Texte, Kommentare und Dokumentation sollten auf Deutsch verfasst werden.

2. **Database Migrations with Alembic**: Das Projekt verwendet **Alembic** für Migrationen:
   - Migrationen werden automatisch beim Deployment ausgeführt
   - Neue Migration erstellen: `migrate.sh create "Description"`
   - Siehe Abschnitt "Database Migrations (Alembic)"

3. **Cost Calculation Logic**: Die zentrale Business-Logik ist in `models.py`:
   - `Machine.calculate_cost_per_hour()` - Inkludiert Abschreibung + Strom
   - `Machine.calculate_cost_per_page()` - Für Tintenstrahl-Drucker
   - `Product.calculate_costs()` - Aggregiert alle Kostenkomponenten
   - Verkaufspreise werden mit 30%, 50%, 100% Margen berechnet

4. **Static Electricity Price**: `STROM_PREIS_KWH = 0.22` (€/kWh) ist hardcoded in models.py

5. **Template Inheritance**: Alle Templates erben von `base.html` welches HTMX und gemeinsames Styling inkludiert

6. **Development vs Production**:
   - Dev: Code als Volume gemountet, Auto-Reload aktiviert
   - Prod: Code in Image gebacken, keine Volume Mounts für App-Code

7. **File Organization**: Die Hauptanwendung ist absichtlich monolithisch (`main.py` enthält alle Routes) für Einfachheit in einem kleinen Projekt.

8. **Dependencies**: Siehe `app/requirements.txt` für exakte Versionen:
   - FastAPI 0.109.0
   - SQLAlchemy 2.0.25
   - PostgreSQL driver: psycopg2-binary 2.9.9
   - vtracer 0.6.11 (für PNG-zu-SVG Konvertierung)

9. **Decimal Parsing**: Die Funktion `parse_decimal()` in `main.py` konvertiert Strings mit Komma oder Punkt als Dezimaltrenner zu float. Wird für alle numerischen Formularfelder verwendet.

10. **Time Storage**: Arbeitszeit wird als `labor_minutes` (Numeric) in Minuten gespeichert, nicht als Stunden. Berechnung: `labor_hours = labor_minutes / 60`

11. **Multi-Machine Support**: Produkte können mehrere Maschinen haben:
    - `machine_id` - Primäre Maschine
    - `additional_machine_ids` - Kommaseparierte IDs (z.B. "2,3") für weitere Maschinen
    - Wird für Sticker-Sheets und Schreibwaren verwendet (Drucker + Plotter)

11. **Machine Types**: Unterstützte Maschinentypen:
    - `3d_printer` - Zeitbasierte Kostenberechnung (Strom + Abschreibung/Stunde)
    - `cutter_plotter` - Bogenbasierte Kostenberechnung (`cost_per_sheet`)
    - `inkjet_printer` - Seitenbasierte Kostenberechnung (`depreciation_per_page`) oder Bogenbasiert (`cost_per_sheet`)
    - `other` - Zeitbasierte Kostenberechnung

12. **Storage Paths**:
    - Development: `/app/storage` (Docker Volume)
    - Production: `/mnt/user/appdata/picocalc/storage` (Unraid Pfad)
    - Temporäre Uploads: `/tmp/picocalc_uploads`

13. **Laser Layer Support**: Laser-Gravur-Produkte unterstützen bis zu 3 Layer mit je:
    - Type (blau, ir, rot)
    - Power (%)
    - Speed (mm/s)
    - Passes (Anzahl Durchläufe)
    - DPI
    - Lines per cm

14. **Sticker/Stationery Workflow**:
    - Produkttyp `sticker` mit Kategorie `StickerSheet` oder `DieCut`
    - `sheet_count` immer = 1 (aus UI entfernt)
    - `units_per_sheet` = Anzahl Sticker/Produkte pro Bogen
    - Mehrere Maschinen möglich (Drucker + Plotter via `additional_machine_ids`)
    - Verpackung/Versand werden im Verkauf erfasst, nicht beim Produkt

15. **Cost Calculation Modes**:
    - `per_unit` - Kosten werden pro Einheit berechnet
    - `per_batch` - Kosten pro Batch werden durch `units_per_batch` geteilt
    - Beispiel: Plotter-Kosten €10 pro Bogen für 20 Sticker = €0.50 pro Sticker
