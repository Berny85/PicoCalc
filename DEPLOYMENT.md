# PicoCalc – Deployment und Betrieb

Stand: Der Server ist ein **Intel NUC mit Debian** (Docker Engine). Die frühere Unraid-Umgebung (Portainer,
Watchtower, GitHub Actions, Docker Hub) gibt es nicht mehr; die zugehörigen Skripte sind entfernt und in der
Git-Historie nachlesbar.

## Überblick

| | Entwicklung | Produktion |
|---|---|---|
| Rechner | Windows 11, Docker Desktop | Intel NUC, Debian, IP `192.168.50.8`, Benutzer `berny` |
| App | http://localhost:5000 | http://192.168.50.8:5000 |
| Projektordner | dieses Repo | `/srv/containers/picocalc` (Git-Clone) |
| Compose-Datei | `docker-compose.yaml` | **`docker-compose.prod.yml`** |
| Container | `picocalc-web-1`, `picocalc-db-1`, `picocalc-pgadmin-1` | `picocalc-app`, `picocalc-db`, `dozzle` |
| Daten | Docker-Volume | `./db_data` (PostgreSQL), `./storage` (SVG-Konverter), `.env` (`DB_PASSWORD`, `SECRET_KEY`) |
| Weitere Dienste | – | Bambuddy `:8000`, PicoAccounting `:8500`, Dozzle (Logs) `:8080` |
| Backup-Ziel | – | OMV `192.168.50.202` (NFS), siehe unten |

> **Zwei Compose-Dateien, immer die richtige benutzen.** Im Projektordner liegen `docker-compose.yaml` (Entwicklung) und
> `docker-compose.prod.yml` (Produktion). Ein einfaches `docker compose ...` würde die Entwicklungs-Datei nehmen (bind-gemountetes
> `./app`, Auto-Reload, eigene leere Datenbank). `deploy.sh` benutzt deshalb immer `-f docker-compose.prod.yml`. Für den
> Handbetrieb auf dem NUC einmalig in der `.env` eintragen: `COMPOSE_FILE=docker-compose.prod.yml`

## Entwicklung

```bash
docker compose up -d            # starten
docker compose logs -f web      # Logs
docker compose down             # stoppen (Daten bleiben)
docker compose down -v          # stoppen und Datenbank löschen (frischer Start)
```

Das Schema legt die App beim Start selbst an (Alembic, siehe unten). Tests: siehe `README.md`.

## Deployment auf den NUC

Auf dem NUC, im Projektordner:

```bash
ssh berny@192.168.50.8
cd /srv/containers/picocalc
bash deploy.sh
```

`deploy.sh` (1) holt den Code per `git pull origin main`, (2) stoppt die Container (Daten bleiben), (3) baut und startet neu,
(4) wartet auf Datenbank und App, zeigt die Schema-Revision und (5) den Container-Status. Antwortet die App nicht, zeigt es die
Log-Zeilen und beendet sich mit Fehler. Migrationen laufen beim Start der App automatisch.

Alternativ vom Windows-Rechner: `.\deploy-to-nuc.ps1` (optionaler Commit, `git push`, dann per SSH `bash deploy.sh` auf dem NUC).

**Einmalige Vorbereitung auf dem NUC** (der Projektordner gehört `root`, deshalb verweigert Git als `berny` die Arbeit):

```bash
git config --global --add safe.directory /srv/containers/picocalc
git config core.fileMode false      # Dateirechte (666/777) nicht als Änderungen werten
echo 'COMPOSE_FILE=docker-compose.prod.yml' >> .env
```

## Einmalig: Umstellung auf das neue Datenbankschema (Rezept-Modell)

Die Produktivdatenbank hat noch das **alte Schema** (vor 2026-09-18). Es lässt sich nicht migrieren, weil sich das
Datenmodell grundlegend geändert hat (Produkte bestehen jetzt aus Material-, Maschinen-, Arbeits- und Verpackungszeilen,
Materialpreise haben eine Historie, Kosten liegen in eigenen Tabellen, Typen und Marken sind Tabellen).

Auf dem NUC läuft noch die Compose-Datei vom Umzug (`docker-compose.yml`, lokal angelegt, nicht im Repo). Die neuen Dateien
(`docker-compose.prod.yml`, `deploy.sh`, `reset-prod.sh`) kommen erst mit `git pull`. Reihenfolge:

1. **Auf dem Windows-Rechner:** Änderungen committen und pushen; `.\backup-to-local.ps1` ausführen.
2. **Auf dem NUC, Git vorbereiten** (einmalig, siehe oben), dann den lokalen Stand prüfen:
   ```bash
   cd /srv/containers/picocalc
   git status --short
   ```
   Erwartet sind nur `docker-compose.yml` (neu, `??`) und ggf. eine gelöschte `docker-compose.yaml` (` D`). Die laufende Datei
   sichern und den Zustand herstellen, den `git pull` erwartet:
   ```bash
   cp docker-compose.yml ~/docker-compose.picocalc-nuc.bak
   git checkout -- docker-compose.yaml 2>/dev/null || true
   mv docker-compose.yml docker-compose.yml.alt        # verhindert, dass Compose zwei Dateien findet
   ```
   Zeigt `git status` weitere geänderte Dateien, erst ansehen (`git diff --stat`) und klären. **Nicht** `git clean` oder
   `git stash -u` verwenden: `db_data/` enthält die Datenbank.
3. `git pull origin main` – holt Skripte und Compose-Datei. Die laufenden Container bleiben unberührt (der Code steckt im Image).
4. **Leeren, App bleibt aus:** `bash reset-prod.sh --ohne-start`
   Sichert die DB (Dump im Home-Verzeichnis), stoppt `picocalc-app`, löscht das Schema.
5. **Neue Version starten:** `bash deploy.sh` – die App legt das Schema selbst an (Revision `0001`, Standard-Stammdaten).
6. **Stammdaten neu erfassen:** `/settings` (Strompreis, Stundensatz, Marge, Kategorien, Maschinentypen), `/materials`,
   `/machines`, danach die Produkte.

Der komplette Ablauf (alte DB → `deploy.sh` scheitert mit Hinweis → `reset-prod.sh --ohne-start` → `deploy.sh` → Revision `0001`)
wurde mit den echten Containernamen in einer Testumgebung durchgespielt.

**Variante B** (erst deployen, dann leeren): `bash deploy.sh` bricht gegen die alte DB mit dem Hinweis auf `reset-prod.sh` ab
(die App findet die alte Alembic-Revision nicht); danach `bash reset-prod.sh` (ohne Option) leert die DB und startet die App wieder.

> Die alte App-Version darf nach dem Leeren **nicht** mehr starten: Sie würde das alte Schema sofort wieder anlegen.
> Alte Datenbank-Dumps (auch `picocalc_dump.sql`) passen nur zum alten Schema und dürfen nicht in die neue Datenbank
> zurückgespielt werden.
## Backup und Wiederherstellung

**Automatisch auf den OMV (NFS):** Ein täglicher `systemd`-Timer sichert Datenbank, Storage und `.env` auf den OMV, prüft die
Sicherung und hält 14 Tagesstände plus 8 Wochenstände vor. Einrichtung, Wiederherstellung und Restore-Test:
[`scripts/backup/README.md`](scripts/backup/README.md).

**Manuelles Voll-Backup auf den lokalen Rechner:**

```powershell
.\backup-to-local.ps1     # Ziel: %USERPROFILE%\Documents\PicoCalc-Backups\<Datum>
```

Gesichert werden: PicoCalc-Datenbank (`pg_dump -Fc` aus `picocalc-db`), `storage/` (SVG-Konverter-Dateien),
`.env`, sowie die Daten von Bambuddy und PicoAccounting.

**Datenbank wiederherstellen** (Dump aus demselben Schema-Stand, App vorher stoppen):

```bash
docker stop picocalc-app
docker cp picocalc_db.dump picocalc-db:/tmp/restore.dump
docker exec picocalc-db pg_restore -U printuser -d printcalc --clean --if-exists --no-owner /tmp/restore.dump
docker start picocalc-app
```

> Auf dem Debian-Server lief bisher **kein** automatisches Backup (der frühere `offen/docker-volume-backup`-Dienst gehörte zur Unraid-Compose). Das OMV-Backup ersetzt ihn.
## Datenbank-Migrationen (Alembic)

- Migrationen liegen in `app/alembic/versions/`, die Baseline ist Revision `0001`.
- Neue Migration erzeugen (Entwicklung): `./migrate.sh create "Beschreibung"` bzw. `.\migrate.ps1 -Command create -Message "..."`
- Auf dem Server laufen Migrationen automatisch beim Start der App.
- Ein Test (`test_migration_matches_models`) schlägt an, wenn Models und Migrationen auseinanderlaufen.

## Fehlersuche

```bash
# Auf dem NUC
docker logs picocalc-app                      # App-Logs (auch Dozzle: http://192.168.50.8:8080)
docker logs picocalc-db                       # Datenbank-Logs
docker exec picocalc-db pg_isready -U printuser
docker exec picocalc-app env | grep DATABASE  # Verbindungsdaten der App
```

| Symptom | Ursache / Lösung |
|---|---|
| App startet ständig neu, Log: `Can't locate revision identified by ...` | Alte Datenbank mit fremdem Schema → einmalige Umstellung durchführen (siehe oben, `reset-prod.sh`) |
| App startet nicht, Log: `Database not ready yet` | Datenbank-Container läuft nicht oder ist noch nicht bereit → `docker ps`, `docker logs picocalc-db` |
| `relation ... already exists` beim Start | Datenbank enthält Tabellen ohne Alembic-Revision (z. B. Rückspielen eines alten Dumps) → `reset-prod.sh` |

## Sicherheit

- Die App hat **keine Anmeldung** und ist nur für das lokale Netz gedacht – nicht ins Internet freigeben.
- Datenbankpasswort und `SECRET_KEY` stehen in der `.env` auf dem Server, nicht im Repo.
- Die Dev-Compose enthält Standardzugänge (Datenbank `printuser/printpass`, pgAdmin `admin@admin.com/admin`); sie ist nur für den lokalen Rechner gedacht.
