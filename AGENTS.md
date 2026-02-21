# PicoCalc - Agent Documentation

> **Language Note**: Dieses Projekt verwendet Deutsch als Primärsprache für Code-Kommentare, Dokumentation und UI-Texte.

## Project Overview

**PicoCalc** ist ein webbasierter Produktpreis-Kalkulator für kleine Fertigungsunternehmen. Er berechnet Produktionskosten für verschiedene Produkttypen wie 3D-Druck, Sticker-Produktion, Die-Cut-Sticker, Papierprodukte und Laser-Gravur.

- **Repository**: https://github.com/Berny85/PicoCalc.git
- **Production URL**: http://192.168.50.8:5000
- **Primary Language**: German (Code, Kommentare, Dokumentation, UI)

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11 + FastAPI 0.109.0 |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0.25 |
| Frontend | Jinja2 Templates + HTMX 1.9.10 |
| Styling | Vanilla CSS (in Templates, Purple/Blue Theme) |
| Deployment | Docker + Docker Compose |
| Infrastructure | Intel NUC mit Unraid OS |
| CI/CD | GitHub Actions + Docker Hub |

## Project Structure

```
PicoCalc/
├── app/                          # Hauptanwendung
│   ├── main.py                   # FastAPI App mit allen Routes (~1590 Zeilen)
│   ├── models.py                 # SQLAlchemy Datenbank-Modelle (~422 Zeilen)
│   ├── database.py               # Datenbank-Konfiguration
│   ├── requirements.txt          # Python-Abhängigkeiten
│   ├── Dockerfile                # Container-Image Definition
│   └── templates/                # Jinja2 HTML Templates
│       ├── base.html             # Base Layout mit Navigation
│       ├── index.html            # Dashboard
│       ├── materials/            # Material-Verwaltung UI
│       ├── machines/             # Maschinen-Verwaltung UI
│       ├── products/             # Produkt-Formulare und Details
│       ├── feedback/             # Feedback-Formular und Liste
│       ├── ideas/                # Kanban-Style Ideen-Board
│       ├── tools/                # PNG-zu-SVG Converter
│       └── partials/             # HTMX Partial Templates
├── backup/                       # Backup-Skripte
│   ├── backup-script.sh          # Automatisiertes Backup
│   └── restore-script.sh         # Datenbank-Wiederherstellung
├── .github/workflows/            # CI/CD Konfiguration
│   └── deploy.yml                # GitHub Actions Workflow
├── docker-compose.yaml           # Entwicklungs-Konfiguration
├── docker-compose.prod.yml       # Produktions-Konfiguration
├── postgresql.conf               # PostgreSQL WAL Konfiguration
├── deploy.sh                     # NUC Deployment Script (Bash)
├── deploy-to-nuc.ps1             # Windows Deployment Script
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
| backup | picocalc-backup | - | Automatisierte Volume-Backups |
| dozzle | dozzle | 8080 | Docker Log-Viewer |
| pgadmin | picocalc-pgadmin | 5050 | PostgreSQL Management UI |

## Database Models

### Machine (`models.py`)
Repräsentiert Produktionsgeräte (3D-Drucker, Cutter, etc.):
- `name`, `machine_type` (3d_printer, cutter_plotter, other)
- `depreciation_euro` - Geräte-Abschreibungskosten
- `lifespan_hours` - Erwartete Lebensdauer
- `power_kw` - Stromverbrauch
- Methoden: `calculate_cost_per_hour()`, `calculate_cost_per_unit()`

### MaterialType (`models.py`)
Konfigurierbare Material-Kategorien:
- `key` - Interner Identifier (z.B. 'filament', 'sticker_sheet')
- `name` - Anzeigename
- `sort_order` - Für Dropdown-Reihenfolge
- `is_active` - Aktiv/Inaktiv Flag

### Material (`models.py`)
Repräsentiert Rohmaterialien (Filamente, Stickerbögen, Papier):
- `name`, `material_type` (verweist auf MaterialType.key)
- `brand`, `color`, `unit` (kg, sheet, m, piece)
- `price_per_unit`

### Product (`models.py`)
Zentrale Entity mit typ-spezifischen Feldern:
- **Gemeinsam**: `name`, `product_type`, `category`, `labor_hours`, `labor_rate_per_hour`
- **3D-Druck**: `filament_material_id`, `filament_weight_g`, `print_time_hours`, `machine_id`
- **Sticker/Papier**: `sheet_material_id`, `sheet_count`, `units_per_sheet`, `cut_time_hours`
- **Laser**: `laser_material_id`, `laser_design_name`, `laser1_*`, `laser2_*`, `laser3_*`
- Methode: `calculate_costs()` - Gibt Kostenaufschlüsselung und Verkaufspreis-Vorschläge zurück

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
- `conversion_mode`, `color_mode`
- `description`, `tags`

### ProductImage (`models.py`)
Produktbilder:
- `product_id` - Verknüpfung zu Product
- `file_path`, `mime_type`
- `is_primary` - Hauptbild Flag
- `converted_file_id` - Optionale Verknüpfung zu SVG-Bibliothek

## Product Types & Categories

### Product Types (intern)
- `3d_print` - 3D-gedruckte Objekte
- `sticker_sheet` - Stickerbögen
- `diecut_sticker` - Die-Cut Sticker
- `paper` - Papierprodukte
- `laser_engraving` - Laser-gravierte Artikel

### Categories (User-facing)
Dekoration, Technik, Ersatzteile, Spielzeug, Werkzeuge, Sticker, Papierprodukte, Sonstiges

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
- Retention: 14 Tage

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

### Product Images
- Bilder können zu Produkten hochgeladen werden
- Unterstützt PNG, JPG, WEBP
- SVGs aus der Bibliothek können mit Produkten verknüpft werden
- Hauptbild-Funktionalität für primäre Produktfotos

### Kanban-Style Ideas Board
- Ideen können in Status "todo", "in_progress", "done" verschoben werden
- Drag & Drop Funktionalität
- Schnelles Notieren von Verbesserungsideen

## Common Tasks

### Adding a New Product Type
1. Typ zu `PRODUCT_TYPES` in `main.py` hinzufügen
2. Typ-spezifische Felder zu `Product` Modell in `models.py` hinzufügen
3. Formular-Template erstellen: `templates/products/form_{type}.html`
4. Routes für Create/Edit in `main.py` hinzufügen
5. Berechnungslogik zu `calculate_costs()` in models erweitern

### Adding Database Fields
1. Spalte zu Modell in `models.py` hinzufügen
2. Formular-Templates aktualisieren
3. Route Handler in `main.py` aktualisieren
4. Da kein Migrationssystem existiert, manuelles DB-Update oder Neuerstellung erforderlich

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

2. **No ORM Migrations**: Das Projekt verwendet `Base.metadata.create_all()` beim Start. Schema-Änderungen erfordern:
   - Modell-Updates
   - Manuelle DB-Migration oder Neuerstellung (nutze `reset-prod.sh` auf NUC mit Vorsicht)

3. **Cost Calculation Logic**: Die zentrale Business-Logik ist in `models.py`:
   - `Machine.calculate_cost_per_hour()` - Inkludiert Abschreibung + Strom
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

10. **Time Conversion**: Die Funktion `minutes_to_hours()` konvertiert Minuten zu Stunden. Formularfelder für Zeit verwenden typischerweise Minuten (User-freundlicher), werden aber als Stunden gespeichert.
