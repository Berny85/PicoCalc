# PicoCalc - Agent Documentation

> **Language Note**: Dieses Projekt verwendet Deutsch als Primärsprache für Code-Kommentare, Dokumentation und UI-Texte.

## Project Overview

**Picobellu Design** (ehemals PicoCalc) ist ein webbasierter Produktpreis-Kalkulator für kleine Fertigungsunternehmen (3D-Druck, Sticker, Handarbeit). Ein Produkt ist ein Rezept für eine Charge (Materialien, Maschinenzeiten, Arbeitszeit, Ausbeute). Der Kalkulator zeigt Herstellkosten, Selbstkosten (EK), Richtwert-VK (Herstellkosten × Marge + Verpackung) und Gewinn an.

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
| Infrastructure | Intel NUC mit Debian Server (Docker Engine) |
| Deployment-Weg | `bash deploy.sh` auf dem NUC (git pull, `docker compose -f docker-compose.prod.yml up --build`, Health-Checks); `deploy-to-nuc.ps1` ruft es per SSH auf |
| Migrationen | Alembic | 1.13.1 |
| SVG Konvertierung | vtracer | 0.6.11 |
| Bildverarbeitung | Pillow | 10.2.0 |

## Project Structure

```
PicoCalc/
├── app/                          # Hauptanwendung
│   ├── main.py                   # App-Start: Datenbank vorbereiten, Router einbinden (klein halten)
│   ├── routers/                  # Routen nach Bereich: dashboard, materials, machines, products,
│   │                             #   events, feedback, tools (SVG-Converter), settings
│   ├── product_service.py        # Produktformular parsen/anwenden, Kalkulator-Kontext, Live-Vorschau (preview_costs)
│   ├── common.py                 # Gemeinsame Helfer: Config-Werte, Formular-Parser (parse_money), Stammdaten, JSON-Darstellung
│   ├── core.py                   # Jinja-Templates und Filter (z.B. `price`)
│   ├── models.py                 # SQLAlchemy Datenbank-Modelle
│   ├── calc.py                   # Produktkalkulation (reine Funktionen, Decimal, ohne DB)
│   ├── units.py                  # Material-Einheiten und Umrechnungsfaktoren
│   ├── seed.py                   # Standard-Stammdaten für eine frische Datenbank
│   ├── database.py               # Datenbank-Konfiguration, Sessions, upgrade_database()
│   ├── alembic/                  # Datenbank-Migrationen (Alembic), läuft beim App-Start
│   │   └── versions/             # Migrations-Skripte (Baseline 0001, dann 0002)
│   ├── alembic.ini               # Alembic Hauptkonfiguration
│   ├── tests/                    # pytest: test_calc.py (ohne DB), test_db.py + test_routes.py (*_test-Datenbank)
│   ├── run_tests.sh              # pyflakes + pytest im Container
│   ├── requirements.txt          # Python-Abhängigkeiten
│   ├── requirements-dev.txt      # + pytest, pyflakes
│   ├── Dockerfile                # Container-Image Definition
│   ├── assets/                   # Statische Dateien (unter /static): Logo, js/table-tools.js, css/table-tools.css
│   └── templates/                # Jinja2 HTML Templates
│       ├── base.html             # Base Layout mit Navigation und CSS
│       ├── index.html            # Dashboard
│       ├── materials/            # Material-Verwaltung UI
│       ├── machines/             # Maschinen-Verwaltung UI
│       ├── products/             # Produkt-Formulare und Details
│       ├── feedback_ideas/       # Feedback & Ideen Verwaltung
│       └── tools/                # SVG Converter + Bibliothek
├── scripts/backup/               # OMV-Backup: backup-picocalc.sh, systemd-Timer, Einrichtung (README dort)
├── scripts/migration/            # Einmal-Skripte vom Umzug Unraid -> Debian (löschbar, siehe README dort)
├── docker-compose.yaml           # Entwicklungs-Konfiguration
├── docker-compose.prod.yml       # Produktion (Debian-NUC): db, web, dozzle; Daten in ./db_data und ./storage
├── migrate.ps1 / migrate.sh      # Alembic-Hilfsskripte (Entwicklung)
├── deploy.sh                     # Deployment, wird AUF dem NUC ausgeführt (bash deploy.sh)
├── deploy-to-nuc.ps1             # Deployment auf den Debian-NUC (PowerShell)
├── backup-to-local.ps1           # Voll-Backup vom NUC auf den lokalen Rechner
├── reset-prod.sh                 # GESPERRT: löscht die DB (Live-Daten!); läuft nur mit PICOCALC_ALLOW_DATA_LOSS=yes
├── README.md                     # Projekt-Übersicht (Deutsch)
└── DEPLOYMENT.md                 # Deployment, Backup, Umstellung, Fehlersuche (Deutsch)
```

> Archiv: Der frühere Projektstand (`old_project/`) liegt außerhalb des Repos unter `C:\OpenCode\_archiv\PicoCalc-old_project`.

## Architecture

### Development Environment (Windows 11)
- **Docker Desktop** für Containerisierung
- **Local URL**: http://localhost:5000
- **App Name**: Picobellu Design
- **Database**: PostgreSQL auf Port 5432
- **pgAdmin**: http://localhost:5050
- **Hot reload**: Code als Volume gemountet, Auto-Reload aktiviert

### Production Environment (Intel NUC mit Debian Server)
- **IP**: 192.168.50.8
- **PicoCalc App**: http://192.168.50.8:5000
- **Dozzle**: http://192.168.50.8:8080 (Log-Viewer)
- **Bambuddy**: http://192.168.50.8:8000
- **PicoAccounting**: http://192.168.50.8:8500

### Production (Debian-NUC)
- Projektordner auf dem Server: `/srv/containers/picocalc` (Git-Clone), Container `picocalc-app` und `picocalc-db`
- Compose: immer `docker-compose.prod.yml` (`-f`, `deploy.sh` tut das; oder `COMPOSE_FILE=docker-compose.prod.yml` in der `.env` auf dem Server). Ein einfaches `docker compose` würde die Dev-Datei `docker-compose.yaml` nehmen.
- Git auf dem NUC: Ordner gehört `root`, deshalb einmalig `git config --global --add safe.directory /srv/containers/picocalc`
- Automatisches Backup: `scripts/backup/` (täglicher Timer, Ziel NFS-Share auf dem OMV `192.168.50.202`); vorbereitet, die Einrichtung auf dem NUC steht in der dortigen README

## Database Models

Das Schema wird ausschließlich über Alembic verwaltet (siehe unten). Ein Produkt ist ein **Rezept für eine
Charge**: Materialien, Maschinennutzung und Arbeitsschritte ergeben die Chargenkosten, geteilt durch die Ausbeute
(`yield_qty`) die Herstellkosten pro Stück; Verpackungsmaterial kommt pro verkauftem Stück obendrauf.

**Designregel: lieber mehr schmale Tabellen als wenige breite.** Was nur zu einer Abrechnungsart gehört, was sich wiederholen
kann oder was eine Historie hat, bekommt eine eigene Tabelle (19 Tabellen insgesamt). Verweise immer per Fremdschlüssel.

### Stammdaten
- **MachineType** – Maschinentypen (`name`, `default_billing_mode`). Nur ein Etikett; schlägt beim Anlegen einer Maschine die Abrechnungsart vor.
- **MaterialType** – Materialkategorien (`key`, `name`, `sort_order`, `is_active`), Verwaltung unter `/material-types`.
- **Brand** – Marken/Hersteller (`name`, eindeutig); Materialien verweisen per `brand_id`.
- **Config** – Key-Value-Store nur für einzelne Werte (`electricity_price_kwh`, `labor_rate_per_hour`, `margin_multiplier`, `company_name`).

### Maschinen: `machines` + zwei 1:1-Kostentabellen
- **Machine**: `name`, `machine_type_id`, `billing_mode` (`'time'` = Minuten × Stundensatz, `'sheet'` = Bögen × Bogenpreis), `description`
- **MachineTimeCost** (`machine_id` = PK): `depreciation_euro`, `lifespan_hours` (> 0), `power_w` (Watt, **nicht** kW). Pflicht bei `time`; bei `sheet` optional (nur Herleitung des Bogenpreises)
- **MachineSheetCost** (`machine_id` = PK): `cost_per_sheet`. Pflicht bei `sheet`
- Zugriff über `machine.depreciation_euro`, `.lifespan_hours`, `.power_w`, `.cost_per_sheet` (Properties, Standard: 0 / 1 / 0 / `None`); Schreiben über `set_time_costs(...)` und `set_sheet_cost(...)`
- Methoden: `cost_per_hour(electricity_price)`, `cost_per_sheet_value()`, `to_input(value)`

### Materialien: `materials` + `material_prices`
- **Material**: `name`, `material_type_id`, `brand_id`, `color`, `unit` (Schlüssel aus `units.MATERIAL_UNITS`: `kg`, `sheet`, `piece`, `pack`, `m`, `m2`), `description`
- **MaterialPrice** (`material_id`, `price` `Numeric(12,4)`, `valid_from`): **Preis-Historie**, der neueste Eintrag gilt. `material.price_per_unit` ist der aktuelle Preis (schreibgeschützte `column_property`, auch sortierbar). Preis ändern nur über `material.set_price(...)`: bleibt der Preis gleich, entsteht kein neuer Eintrag. Produkte rechnen immer mit dem aktuellen Preis.
- Die Menge im Produkt wird in der **Eingabe-Einheit** erfasst (bei `kg` in Gramm). Der Umrechnungsfaktor steht in `units.py`, nirgends sonst.

### Produkte: `products` + vier Zeilentabellen
- **Product**: `name`, `notes`, `yield_qty` (Ausbeute, ≥ 1), `shipping_cost` (nur Richtwert), `selling_price` (manueller VK, sonst Richtwert), `is_for_market`
- **ProductMaterial** (`material_id`, `amount` in Eingabe-Einheit **pro Charge**)
- **ProductMachine** (`machine_id`, `value` in Minuten bzw. Bögen **pro Charge**)
- **ProductLabor** – Arbeitsschritte (`description`, `minutes`, `hourly_rate`) **pro Charge**, jeder mit eigenem Stundensatz. `product.labor_minutes` = Summe
- **ProductPackaging** (`material_id`, `amount` **pro verkauftem Stück**) – Verpackung als Material, ohne Marge durchgereicht, rechnet mit dem aktuellen Materialpreis
- Der Produkttyp wird nicht gespeichert: `type_label` ergibt sich aus den Typen der verwendeten Maschinen (ohne Maschine: Handarbeit).
- Methoden: `calculate(settings)` → `calc.ProductCosts` (Decimal), `calculate_costs(settings)` → Dict für Templates (auf Cent gerundet)
- Materialien und Maschinen, die in Produkten (auch als Verpackung) verwendet werden, lassen sich nicht löschen.

### Kalkulation (`calc.py`)
Reine Funktionen ohne Datenbankzugriff, durchgehend `Decimal`, gerundet wird erst für die Anzeige:
1. Chargenkosten = Material + Maschinen + Arbeitsschritte
2. Herstellkosten pro Stück = Chargenkosten ÷ Ausbeute
3. Selbstkosten (EK) = Herstellkosten + Verpackung (Summe der Verpackungszeilen, pro Stück, nicht durch die Ausbeute geteilt)
4. Richtwert-VK = Herstellkosten × Marge + Verpackung; VK = manueller `selling_price` oder Richtwert

**Es gibt nur eine Rechnung.** Die Live-Vorschau im Formular (`form_universal.html`) rechnet nichts selbst, sondern
fragt den Server: `POST /api/calculate` (`product_service.preview_costs` → `calc.calculate_product`). Ebenso holen das
Maschinenformular und der Maschinen-Dialog Stundensatz und Bogen-Herleitung von `GET /api/machine-rate`. Änderungen an
der Berechnung passieren deshalb nur in `calc.py`; `tests/test_routes.py::test_live_preview_matches_the_saved_product`
stellt sicher, dass Vorschau und gespeichertes Produkt identisch bleiben.

### MarketEvent / EventItem / EventTodo (`models.py`)
Markt-/Flohmarkt-Vorproduktion. `MarketEvent.calculate_totals()` rechnet den Materialbedarf in **ganzen Chargen**
(Soll-Menge ÷ Ausbeute, aufgerundet) und liefert Filament (g), Bögen, weitere Materialien, Maschinen- und Arbeitszeit.

### FeedbackIdea, ConvertedFile
Feedback/Ideen-System und gespeicherte PNG→SVG-Konvertierungen (unverändert).

> **Entfernt**: Komponenten (`ProductComponent`; Kleinteile sind jetzt Materialien mit Einheit „Stück“), Laser-/Sticker-/3D-Druck-Spezialfelder am Produkt,
> Seiten-basierte Kosten am Inkjet-Drucker (`lifespan_pages`, `depreciation_per_page`) sowie die alten Formulare
> `/products/3d-print`, `/products/sticker` und `/products/classic-new`.

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

### Deployment und Betrieb (Debian-NUC, vom Dev-PC aus)
```powershell
.\deploy-to-nuc.ps1     # committen (optional), pushen, auf dem NUC `bash deploy.sh` ausführen
.\backup-to-local.ps1   # Voll-Backup vom NUC herunterladen
```
Auf dem NUC (`/srv/containers/picocalc`): `bash deploy.sh`, `docker logs picocalc-app`, `docker logs picocalc-db`. Kein Reset der Live-Datenbank (siehe Migrationen).
Ablauf, Wiederherstellung und die einmalige Schema-Umstellung: siehe `DEPLOYMENT.md`.

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
1. Änderungen nach GitHub pushen (kein CI, kein Docker Hub, kein Portainer mehr)
2. Auf dem NUC in `/srv/containers/picocalc`: `bash deploy.sh` (per SSH oder über `deploy-to-nuc.ps1`)
3. Die App migriert die Datenbank beim Start selbst (Alembic)

## Key Configuration Files

### Environment Variables
Production nutzt (aus der `.env` auf dem Server):
- `DB_PASSWORD` - PostgreSQL Passwort
- `SECRET_KEY` - wird von der App derzeit nicht verwendet
- `FILE_STORAGE_PATH` - Pfad für Dateispeicher (`/app/storage`)

### Database Connection
Development: `postgresql://printuser:printpass@db:5432/printcalc`
Production: `postgresql://printuser:${DB_PASSWORD}@db:5432/printcalc`

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
- Verweise zwischen Tabellen immer per Fremdschlüssel (`*_id`), nie über Namen oder Strings
- Boolean-Flags als `Boolean` (Ausnahmen mit Integer 0/1: `EventTodo.is_done`, `MaterialType.is_active`)
- Preise/Beträge als `Numeric` mit ausreichend Nachkommastellen (Preise `(12,4)`), Berechnung mit `Decimal`

## Testing

Automatisierte Tests mit pytest (im Container, da lokal kein Python nötig ist):

```bash
# Testdatenbank einmalig anlegen (Name MUSS auf _test enden, sonst überspringen sich die DB-Tests)
docker exec picocalc-db-1 psql -U printuser -d postgres -c "CREATE DATABASE printcalc_test;"

# pyflakes + alle Tests (die Testdatenbank wird dabei jedes Mal neu aufgebaut)
docker compose run --rm --no-deps \
  -e DATABASE_URL=postgresql://printuser:printpass@db:5432/printcalc_test \
  -e FILE_STORAGE_PATH=/tmp/storage web sh run_tests.sh
```

- `tests/test_calc.py` – Kalkulationsformeln inkl. Regressionstests (kg-Preis ohne Rundungsverlust, Ausbeute 1 mit mehreren Bögen)
- `tests/test_db.py` – Migration entspricht den Models (`alembic check`), Genauigkeit der Spalten, Löschschutz, Event-Bedarf
- `tests/test_routes.py` – die gesamte Weboberfläche über den `TestClient` (CRUD aller Bereiche, Validierung, Events, Einstellungen, SVG-Tool, Live-Vorschau = gespeichertes Produkt). Sicherheitsnetz für Umbauten an der Struktur.
- Zusätzlich manuell testen: Formulare im Browser (http://localhost:5000), Live-Vorschau gegen die Detailseite vergleichen

## Security Considerations

1. **Keine sensiblen Daten im Code** - Passwörter in der `.env` auf dem Server (steht in `.gitignore`)
2. **Datenbank** - PostgreSQL im Docker-Netzwerk, Port 5432 ist in Produktion nur an `127.0.0.1` des NUC gebunden (Zugriff von außen per SSH-Tunnel)
3. **Keine Authentifizierung** - Die App hat keine Benutzeranmeldung (nur interner Gebrauch, nicht ins Internet freigeben)
4. **Dev-Standardzugänge** - `docker-compose.yaml` enthält `printuser/printpass` und pgAdmin `admin@admin.com/admin` (nur lokal)

## Backup and Restore

- Manuelles Voll-Backup auf den lokalen Rechner: `.\backup-to-local.ps1` (DB-Dump, Storage, `.env`, Bambuddy, PicoAccounting)
- Datenbank wiederherstellen: `docker exec -i picocalc-db pg_restore -U printuser -d printcalc --clean --if-exists < picocalc_db.dump` – nur mit einem Dump aus dem **aktuellen** Schema-Stand
- Automatisches Backup auf dem Debian-Server: aus dem Repo nicht ersichtlich, bitte auf dem Server prüfen
- Details: `DEPLOYMENT.md`

## Special Features

### Preiskalkulation
Details und Formeln siehe „Kalkulation (`calc.py`)“ oben.
- **Produktverpackung**: 1:1 Durchreichung pro Stück ohne Marge (z.B. Schutzhülle, Kartonversteifung)
- **Verkaufspreis (VK)**: Entweder manuell gesetzter VK (`selling_price`) oder automatisch Richtwert-VK
- **Einstellungen**: Strompreis (€/kWh), Standard-Stundensatz, Marge und Firmendaten unter `/settings`; dort auch die Maschinentypen (eine pro Zeile, `| Bogen` schlägt Abrechnung pro Bogen vor). Typen, die noch von Maschinen verwendet werden, bleiben erhalten. Produkte haben keine Kategorie (entfernt mit Migration `0002`).

### Produkt-Formular (`form_universal.html`)
- Ein Formular für alle Produkte (Neu und Bearbeiten), Rezept- und Ausbeuteprinzip, Live-Kalkulation rechts
- Materialien und Maschinen können direkt im Formular per Dialog angelegt werden (`POST /api/materials`, `POST /api/machines`); das Ergebnis erscheint sofort in allen Dropdowns
- Materialmengen werden in der Eingabe-Einheit erfasst (Gramm bei kg-Preis), Stückmaterial wird mit `1` vorbelegt
- Materialien und Maschinen, die in Produkten verwendet werden, lassen sich nicht löschen (Hinweis statt Fehler)

### Listen: Sortieren und Filtern in den Spaltenköpfen
- Die Listen (Produkte, Materialien, Materialtypen, Maschinen, Feedback) haben **kein** eigenes Such-/Filterformular. Die Router liefern alle Zeilen (sortiert nach Name), Sortieren und Filtern passiert im Browser (`assets/js/table-tools.js`, `css/table-tools.css`, in `base.html` eingebunden).
- Neue Tabelle: `<table class="data-table">` und im `<th>` `data-col="text"` (Werteliste + Suchfeld) `data-col="number"` (von/bis) oder `data-col="date"` (von/bis mit Datumsauswahl, Sortierwert als ISO-Datum in `data-sort`); `data-list="off"` bei langen Texten; Spalten ohne `data-col` (z. B. Aktionen) bleiben unberührt.
- Zellen: `data-sort="…"` liefert den Sortierwert (Zahlen mit Punkt, Datum als ISO-String, leer = kein Wert, landet immer am Ende), `data-value="…"` den Filterwert. Checkboxen zählen als Ja/Nein. Die Tabelle sendet `dt:filtered`, wenn sich die sichtbaren Zeilen ändern.
- Nicht betroffen: die Kartenlisten (Events, gespeicherte SVG-Konvertierungen) haben weiterhin ihre eigene Suche.

## Database Migrations (Alembic)

Das Schema wird **nur** über Alembic verändert. Die App führt beim Start automatisch `alembic upgrade head` aus
(`database.upgrade_database()`), legt danach fehlende Stammdaten an (`seed.py`) – es gibt kein `create_all` mehr.
Alembic liegt in `app/alembic/` (eine einzige Kopie, im Container unter `/app/alembic`).

### Neue Migration erstellen
1. Model in `models.py` ändern
2. `./migrate.sh create "Beschreibung"` (bzw. `.\migrate.ps1 -Command create -Message "..."`) – die Datei landet in `app/alembic/versions/`
3. Migration prüfen und committen; `tests/test_db.py::test_migration_matches_models` schlägt an, wenn Models und Migrationen auseinanderlaufen

### Befehle

```bash
./migrate.sh migrate     # ausstehende Migrationen ausführen (passiert beim Start ohnehin)
./migrate.sh create "…"  # neue Migration (--autogenerate)
./migrate.sh downgrade   # letzte Migration zurücksetzen
./migrate.sh history     # Historie
./migrate.sh current     # aktuelle Revision
```

### Wichtig
- Baseline ist Revision `0001` (Neuaufbau am 2026-09-18), `0002` entfernt die Produkt-Kategorien. Die früheren Migrationen einer Vorgängerversion wurden entfernt.
- **⚠️ Live-Daten (seit 2026-09-19): Die Produktivdatenbank enthält echte Daten und wird nie mehr geleert.** Schema-Änderungen nur als Migration **mit Datenerhalt**:
  - ausgelieferte Migrationen (`0001`, `0002`, …) nie ändern, immer eine neue anlegen;
  - neue Spalten `nullable` oder mit `server_default`; Umbauten in Schritten (neu anlegen → Daten per `op.execute` kopieren → erst dann alte Spalte/Tabelle löschen); nichts mit Nutzerdaten löschen, ohne es vorher zu übernehmen;
  - jede Migration, die bestehende Zeilen berührt, bekommt einen Test nach dem Muster `test_migration_0002_removes_categories_and_keeps_products` (Vorgängerstand, Daten einfügen, `head`, prüfen);
  - `reset-prod.sh` ist gesperrt (nur mit `PICOCALC_ALLOW_DATA_LOSS=yes`), niemals `db_data/` löschen oder `docker compose down -v` auf dem NUC ausführen; `deploy.sh` sichert vor jedem Deploy per Dump nach `~/picocalc-predeploy/`.
- Die `env.py` liest `DATABASE_URL` aus den Umgebungsvariablen

## Common Tasks

### Adding a Database Field
1. Spalte zu Modell in `models.py` hinzufügen (Genauigkeit der `Numeric`-Spalte bewusst wählen: Preise `(12,4)`)
2. Migration erzeugen (siehe oben)
3. Formular-Parser (`parse_*_form` in `routers/*.py` bzw. `product_service.py`) und Formular-Template aktualisieren
4. Falls die Berechnung betroffen ist: `calc.py` (und ggf. `preview_costs`) sowie die Tests anpassen – die Formulare rechnen nicht selbst

### Adding a Material Unit
Eintrag in `units.MATERIAL_UNITS` (Label, Eingabe-Einheit, Faktor). Formulare und Kalkulation lesen die Liste von dort.

### Updating Dependencies
1. `app/requirements.txt` bearbeiten
2. Container rebuild: `docker-compose up --build -d`
3. Gründlich testen
4. Änderungen committen

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

### Production: kein Reset mehr
Die Produktivdatenbank enthält seit 2026-09-19 echte Daten (siehe „Wichtig“ bei den Migrationen). `reset-prod.sh` ist gesperrt und nur
für den Notfall einer defekten Datenbank gedacht (`PICOCALC_ALLOW_DATA_LOSS=yes`). Bei `Can't locate revision identified by '...'` läuft
ein älterer Code-Stand gegen eine neuere Datenbank → den aktuellen Code deployen. Bei `relation "..." already exists` fehlt die Alembic-Revision
→ Log lesen und die Migration bzw. `alembic_version` anpassen, nichts löschen.

## Important Notes for AI Agents

1. **German Language**: Alle User-facing Texte sind auf Deutsch. Neue UI-Texte, Kommentare und Dokumentation sollten auf Deutsch verfasst werden.

2. **Database Migrations with Alembic**: Das Projekt verwendet **Alembic** für Migrationen:
   - Migrationen laufen beim App-Start automatisch (`upgrade_database()`), es gibt kein `create_all`
   - Neue Migration erstellen: `migrate.sh create "Description"`
   - Siehe Abschnitt "Database Migrations (Alembic)"

3. **Cost Calculation Logic**: Die zentrale Business-Logik ist in `calc.py` (reine Funktionen, `Decimal`, mit Tests):
   - `machine_cost_per_hour()` - Abschreibung + Strom (Strompreis aus `Config`, Fallback 0.22 €/kWh, Leistung in **Watt**)
   - `material_cost()` - Menge in Eingabe-Einheit ÷ Faktor × Preis (Faktor aus `units.py`)
   - `calculate_product()` - Chargenkosten ÷ Ausbeute, Verpackung 1:1, Richtwert-VK = Herstellkosten × Marge + Verpackung, optionaler manueller VK (`selling_price`)
   - `Product.calculate_costs()` in `models.py` baut die Eingaben aus der Datenbank und ruft `calc.py`. Die Formulare rechnen nicht selbst, sie rufen `/api/calculate` bzw. `/api/machine-rate` (siehe oben).

4. **Konfigurierbare Einstellungen**: Strompreis (€/kWh), Standard-Stundensatz, Marge und Firmendaten werden in der Tabelle `config` gespeichert und über `/settings` gepflegt (Fallback: `STROM_PREIS_KWH = 0.22`).

5. **Template Inheritance**: Alle Templates erben von `base.html` welches HTMX und gemeinsames Styling inkludiert

6. **Development vs Production**:
   - Dev: Code als Volume gemountet, Auto-Reload aktiviert
   - Prod: Code in Image gebacken, keine Volume Mounts für App-Code

7. **File Organization**: `main.py` startet nur die App. Routen liegen in `routers/<bereich>.py` (je ein `APIRouter`, in `main.py` eingebunden), Formular-/Kalkulationslogik in `product_service.py`, gemeinsame Helfer in `common.py`. Neue Bereiche = neuer Router + Eintrag in `main.py`. Route-Reihenfolge innerhalb eines Routers beachten (`/products/new` vor `/products/{product_id}`).

8. **Dependencies**: Siehe `app/requirements.txt` für exakte Versionen:
   - FastAPI 0.109.0
   - SQLAlchemy 2.0.25
   - PostgreSQL driver: psycopg2-binary 2.9.9
   - Alembic 1.13.1 (für Datenbank-Migrationen)

9. **Decimal Parsing**: `common.parse_money()` (Formularfelder, liefert `Decimal`, Fehler → HTTP 400 mit deutscher Meldung) und `calc.dec()` akzeptieren Komma oder Punkt als Dezimaltrenner. `common.parse_decimal()` (float) wird nur noch für Config-Werte und die Event-VK-Felder benutzt.

10. **Time Storage**: Arbeitszeit wird als `labor_minutes` (Numeric) in Minuten gespeichert, nicht als Stunden. Berechnung: `labor_hours = labor_minutes / 60`

11. **Multi-Machine / Multi-Material**: Ein Produkt hat beliebig viele Material- und Maschinenzeilen (`ProductMaterial`, `ProductMachine`), jede mit eigener Menge pro Charge. Es gibt keine "primäre" Maschine oder Komponenten mehr.

12. **Machine Billing**: Wie eine Maschine abrechnet steht an der Maschine (`billing_mode`), nicht am Typ:
    - `time` - Eingabe in Minuten, Kosten = Minuten ÷ 60 × Stundensatz (Strom + Abschreibung)
    - `sheet` - Eingabe in Bögen/Durchläufen, Kosten = Bögen × `cost_per_sheet`
    - Der Maschinentyp (`MachineType`) ist nur ein Etikett mit Vorschlag für die Abrechnungsart. Keine Logik über Typ-Strings!

13. **Storage Paths**:
    - Development: `/app/storage` (Docker Volume)
    - Production: `/srv/containers/picocalc/storage` (Debian Server)

14. **Sticker & 3D-Druck**: Es gibt keine getrennten Workflows mehr. Ein Sticker-Bogen ist ein Produkt mit Bogen-Material, einer Bogen-Maschine (Plotter/Drucker) und Ausbeute = Anzahl Sticker pro Charge (z.B. 9 DieCut-Sticker auf einem Bogen).

15. **Listen-Sortierung und Suche**:
    - Alle Listen haben einheitliche Suche und Sortierung
    - Default-Sortierung ist alphabetisch nach Name (außer Feedback → Datum)
    - Sortierfelder pro Liste: Name, Typ, Preis, Datum etc.
    - Suche filtert in relevanten Feldern (Name, Beschreibung, Marke etc.)

16. **SVG Converter**:
    - `GET /tools/png-to-svg` - Upload-Formular mit Konvertierungs-Optionen
    - Unterstützt PNG, JPG, WEBP, BMP → SVG via `vtracer`
    - Optionen: Kurven-Modus (spline/pixel), Farbmodus (color/binary), Rauschfilter, Farbgenauigkeit
    - Bibliothek: `GET /tools/converted-files` - Gespeicherte Konvertierungen mit Vorschau/Download
    - Code: `routers/tools.py`, Dateien im Verzeichnis `FILE_STORAGE_PATH`

17. **Feedback & Ideen**:
    - `GET /feedback-ideas` - Liste mit Tabs (Offen / Erledigt / Alle)
    - Nur `description` als Eingabe (kein Typ/Titel mehr)
    - Status-Toggle, Bearbeiten, Löschen

18. **Navigation Structure**: Die Header-Navigation umfasst:
    - Dashboard (📊)
    - Flohmärkte & Events (🎪)
    - Produkte (🛠️)
    - Materialien (🧻)
    - Maschinen (⚙️)
    - SVG Converter (🎨)
    - Feedback (💬)

19. **Rezept-Workflow**: Ein Produkt besteht aus beliebig vielen Materialzeilen (Menge pro Charge), Maschinenzeilen (Minuten bzw. Bögen pro Charge), Arbeitszeit und der Ausbeute. Kleinteile (z.B. Metallringe) sind normale Materialien mit Einheit „Stück“. Die Berechnung steht oben unter „Kalkulation (`calc.py`)“.

20. **Archiv**: Der frühere Projektstand (mit eigenem `.git`) liegt außerhalb des Repos unter `C:\OpenCode\_archiv\PicoCalc-old_project` und wird nicht mehr benötigt, bleibt aber als Nachschlagewerk erhalten.

21. **Flohmarkt & Event-Vorproduktion**:
    - `GET /events` - Liste aller Märkte/Events (aktiv / abgeschlossen)
    - `GET /events/{id}` - Dashboard für ein Event mit Vorproduktions-Liste (Soll/Ist, Live `+1`/`-1` Buttons)
    - Ressourcen- & Wertkalkulation (gesamtes Filament in g, Bögen, Druckstunden, Stand-VK, Vorproduktions-EK)
    - Orga- & Pack-Checkliste (Aufgaben, Standard-Packliste importieren, abhaken)
    - `GET /events/{id}/print` - DIN-A4 Druckansicht

22. **Commit & Push Policy**:
    - **WICHTIG**: Git `commit` und `push` werden **ausschließlich nach ausdrücklicher Aufforderung** durch den Benutzer ausgeführt.
    - Codeänderungen werden lokal umgesetzt und getestet, aber niemals eigenmächtig committet oder gepusht.


