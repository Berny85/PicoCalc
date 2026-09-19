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

`deploy.sh` (1) holt den Code per `git pull origin main`, (2) **sichert die Datenbank** (Dump nach `~/picocalc-predeploy/`, die
letzten 10 bleiben; schlägt der Dump fehl, bricht das Deploy ab), (3) stoppt die Container (Daten bleiben), (4) baut und startet neu,
(5) wartet auf Datenbank und App, zeigt die Schema-Revision und (6) den Container-Status. Antwortet die App nicht, zeigt es die
Log-Zeilen und beendet sich mit Fehler. Migrationen laufen beim Start der App automatisch.

Alternativ vom Windows-Rechner: `.\deploy-to-nuc.ps1` (optionaler Commit, `git push`, dann per SSH `bash deploy.sh` auf dem NUC).

**Einmalige Vorbereitung auf dem NUC** (der Projektordner gehört `root`, deshalb verweigert Git als `berny` die Arbeit):

```bash
git config --global --add safe.directory /srv/containers/picocalc
git config core.fileMode false      # Dateirechte (666/777) nicht als Änderungen werten
echo 'COMPOSE_FILE=docker-compose.prod.yml' >> .env
```

## Live-Daten: Regeln ab 2026-09-19

Die Umstellung auf das Rezept-Schema ist abgeschlossen (die Datenbank wurde dabei einmalig neu angelegt, der frühere Ablauf
steht in der Git-Historie). **Seitdem enthält die Produktivdatenbank echte Daten, und die bleiben erhalten:**

- Schema-Änderungen laufen **nur** als Alembic-Migration mit Datenerhalt (siehe „Datenbank-Migrationen“ unten).
- Nie `db_data/` löschen oder verschieben, nie `docker compose down -v`, nie `git clean` oder `git stash -u` im Projektordner des NUC.
- `reset-prod.sh` ist gesperrt (läuft nur mit `PICOCALC_ALLOW_DATA_LOSS=yes`, gedacht für den Notfall einer defekten Datenbank).
- Vor jedem Deploy sichert `deploy.sh` die Datenbank automatisch nach `~/picocalc-predeploy/`; zusätzlich läuft nachts das OMV-Backup.

**Fehlgeschlagene Migration:** Startet die App nach einem Deploy nicht (`docker logs picocalc-app`), sind die Daten unberührt,
weil eine Migration in einer Transaktion läuft und bei einem Fehler zurückgerollt wird. Dann die Migration korrigieren und erneut
deployen. Nur wenn die Daten selbst beschädigt wären, den Dump von vor dem Deploy zurückspielen (siehe unten).

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

Die Dumps von vor jedem Deploy liegen auf dem NUC in `~/picocalc-predeploy/` (`picocalc_<Datum>.dump`, gleiches Format, gleiche
Wiederherstellung). Der Dump muss zum Schema-Stand der laufenden App passen: nach einem Deploy mit Migration erst die App-Version
von damals starten oder den Dump in eine Wegwerf-Datenbank einspielen und die Daten gezielt übernehmen.

## Datenbank-Zugriff von außen (pgAdmin)

Postgres ist auf dem NUC nur an `127.0.0.1:5432` gebunden, vom PC aus geht es per SSH-Tunnel:

- **pgAdmin:** beim Server im Reiter *SSH Tunnel* aktivieren (Host `192.168.50.8`, Port `22`, Benutzer `berny`); unter *Connection*
  Host `localhost`, Port `5432`, Datenbank `printcalc`, Benutzer `printuser`, Passwort = `DB_PASSWORD` aus der `.env`.
- **Von Hand:** `ssh -L 5433:localhost:5432 berny@192.168.50.8` (Fenster offen lassen), pgAdmin dann auf `localhost:5433`.

## Datenbank-Migrationen (Alembic)

- Migrationen liegen in `app/alembic/versions/`, die Baseline ist Revision `0001`, danach `0002` (Produkt-Kategorien entfernt).
- Neue Migration erzeugen (Entwicklung): `./migrate.sh create "Beschreibung"` bzw. `.\migrate.ps1 -Command create -Message "..."`
- Auf dem Server laufen Migrationen automatisch beim Start der App (alle offenen in einer Transaktion: bei einem Fehler wird zurückgerollt).
- Ein Test (`test_migration_matches_models`) schlägt an, wenn Models und Migrationen auseinanderlaufen.

**Regeln, solange Live-Daten existieren (siehe oben):**
- Bereits ausgelieferte Migrationen (`0001`, `0002`, …) nie ändern, immer eine neue anlegen.
- Datenerhalt: neue Spalten `nullable` oder mit `server_default` anlegen; umbenennen/verschieben in Schritten (neu anlegen → Daten mit
  `op.execute(...)` kopieren → erst dann die alte Spalte/Tabelle löschen). Nichts löschen, was Nutzerdaten enthält, ohne sie vorher zu übernehmen.
- Jede Migration, die bestehende Zeilen berührt, bekommt einen Test nach dem Muster `test_migration_0002_...` in `app/tests/test_db.py`:
  auf den Vorgängerstand zurück, Beispieldaten einfügen, auf `head` hoch, Daten prüfen.
- Vor dem Ausrollen die Migration lokal gegen eine Datenbank mit Beispieldaten laufen lassen.

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
| App startet ständig neu, Log: `Can't locate revision identified by ...` | Die Datenbank hat eine Revision, die der Code nicht kennt (z. B. ein älterer Stand wurde deployt) → den passenden, neueren Code deployen (`git pull`), nicht die Datenbank anfassen |
| App startet nicht, Log: `Database not ready yet` | Datenbank-Container läuft nicht oder ist noch nicht bereit → `docker ps`, `docker logs picocalc-db` |
| `relation ... already exists` beim Start | Datenbank enthält Tabellen ohne Alembic-Revision (z. B. ein Dump wurde ohne `alembic_version` zurückgespielt) → nicht löschen: Log lesen, Migration anpassen bzw. `alembic_version` passend setzen |

## Sicherheit

- Die App hat **keine Anmeldung** und ist nur für das lokale Netz gedacht – nicht ins Internet freigeben.
- Datenbankpasswort und `SECRET_KEY` stehen in der `.env` auf dem Server, nicht im Repo.
- Die Dev-Compose enthält Standardzugänge (Datenbank `printuser/printpass`, pgAdmin `admin@admin.com/admin`); sie ist nur für den lokalen Rechner gedacht.
