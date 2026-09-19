# PicoCalc (Picobellu Design)

Webbasierter Produktpreis-Kalkulator für kleine Fertigungsbetriebe (3D-Druck, Sticker, Handarbeit).
Ein Produkt ist ein **Rezept für eine Charge**: Materialien, Maschinenzeiten und Arbeitszeit ergeben die
Chargenkosten, geteilt durch die Ausbeute die Herstellkosten pro Stück. Dazu kommen Materialverwaltung,
Maschinenverwaltung mit Strom- und Abschreibungskosten, Flohmarkt-Vorproduktion (Events, Materialbedarf, Packliste)
und ein PNG→SVG-Konverter.

**Stack:** Python 3.11, FastAPI, SQLAlchemy 2, PostgreSQL 16, Jinja2, Alembic – läuft in Docker.

## Lokal entwickeln (Windows, Docker Desktop)

```bash
docker compose up -d        # App unter http://localhost:5000, pgAdmin unter http://localhost:5050
docker compose logs -f web  # Logs
```

Der Code ist als Volume eingebunden (Auto-Reload). Das Datenbankschema wird beim Start automatisch per Alembic
angelegt bzw. aktualisiert.

## Tests

```bash
docker exec picocalc-db-1 psql -U printuser -d postgres -c "CREATE DATABASE printcalc_test;"   # einmalig
docker compose run --rm --no-deps \
  -e DATABASE_URL=postgresql://printuser:printpass@db:5432/printcalc_test \
  -e FILE_STORAGE_PATH=/tmp/storage web sh run_tests.sh
```

## Deployment und Betrieb (Debian-NUC)

```powershell
.\deploy-to-nuc.ps1     # committen (optional), pushen, auf dem NUC pullen und neu bauen
.\backup-to-local.ps1   # Datenbank-Dump und Dateien vom NUC auf den lokalen Rechner sichern
```

Einzelheiten, Wiederherstellung und die Regeln für die Live-Datenbank (Migrationen immer mit Datenerhalt) stehen in
[DEPLOYMENT.md](DEPLOYMENT.md). Architektur, Datenmodell und Konventionen für die Weiterentwicklung stehen in
[AGENTS.md](AGENTS.md).

## Wichtige Dateien

| Pfad | Zweck |
|------|-------|
| `app/` | Anwendung (Router, Modelle, Kalkulation, Templates, Tests, Alembic-Migrationen) |
| `docker-compose.yaml` | Entwicklungsumgebung |
| `deploy-to-nuc.ps1`, `backup-to-local.ps1` | Deployment und Backup für den Debian-NUC |
| `migrate.sh`, `migrate.ps1` | Alembic-Hilfsskripte für die Entwicklung |
| `reset-prod.sh` | gesperrt (löscht die Datenbank); nur mit `PICOCALC_ALLOW_DATA_LOSS=yes` für den Notfall |
| `scripts/backup/` | Automatisches Backup auf den OMV (NFS, systemd-Timer) |
| `scripts/migration/` | Einmal-Skripte vom Umzug Unraid → Debian |
