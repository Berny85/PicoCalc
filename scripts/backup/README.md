# PicoCalc-Backup auf den OMV (NFS)

Ein täglicher Timer auf dem NUC sichert Datenbank, Storage (SVG-Konverter) und `.env` auf einen NFS-Share des OMV.

| Datei | Zweck |
|---|---|
| `backup-picocalc.sh` | Erstellt und prüft das Backup, räumt alte Stände auf |
| `picocalc-backup.env.example` | Konfigurationsvorlage (Pfade, Aufbewahrung) |
| `picocalc-backup.service` / `.timer` | systemd: läuft täglich um 02:30 (holt verpasste Läufe nach) |

**Was passiert bei jedem Lauf:** Der Share muss wirklich eingebunden sein (sonst bricht das Skript ab, statt auf die lokale
Platte zu schreiben). Dann wird die Datenbank per `pg_dump` gesichert und **geprüft** (`pg_restore --list`), das Storage-Verzeichnis
als `.tar.gz` gepackt und geprüft, die `.env` mit Rechten `600` kopiert, sonntags zusätzlich ein Wochenstand abgelegt und alles
über `KEEP_DAILY` (14) bzw. `KEEP_WEEKLY` (8) hinaus entfernt. Bei jedem Fehler endet der Lauf mit Fehlerstatus, `systemd`
zeigt ihn als `failed`.

Ablage auf dem OMV: `picocalc/daily/` und `picocalc/weekly/`.

## Einrichtung

### 1. OMV (192.168.50.202): NFS-Share anlegen
Der NUC bindet dort schon `192.168.50.202:/export/accounting` ein. Für PicoCalc bekommt ein **eigener Share** dasselbe Muster:
1. *Speicher → Freigegebene Ordner*: Ordner anlegen, Name `picocalc-backup`.
2. *Dienste → NFS → Freigaben → Hinzufügen*: den Ordner auswählen, **Client** `192.168.50.8` (der NUC), Rechte **Lesen/Schreiben**,
   *Extra-Optionen* wie beim Share `accounting` (bei dem das Schreiben vom NUC aus bereits funktioniert). Als `root` schreibt
   der NUC standardmäßig nicht auf einen NFS-Share: entweder `no_root_squash` in den Extra-Optionen (im reinen Heimnetz
   vertretbar) oder die Rechte des Ordners für den NFS-Benutzer passend setzen. *Speichern*, *Änderungen übernehmen*.
3. Der Exportpfad folgt dem Muster des vorhandenen Shares: `/export/picocalc-backup` (im OMV unter *NFS → Freigaben* prüfen).

### 2. NUC: Share einbinden
`nfs-common` ist wegen des `accounting`-Mounts schon installiert. Mountpunkt anlegen und in `/etc/fstab` eintragen (gleiche Optionen
wie die vorhandene Zeile):
```bash
sudo mkdir -p /mnt/omv-backup
echo '192.168.50.202:/export/picocalc-backup /mnt/omv-backup nfs defaults,_netdev,nofail 0 0' | sudo tee -a /etc/fstab
sudo systemctl daemon-reload
sudo mount /mnt/omv-backup
mountpoint /mnt/omv-backup && sudo touch /mnt/omv-backup/test && sudo rm /mnt/omv-backup/test && echo "Schreiben OK"
```
`nofail` verhindert, dass der NUC nicht bootet, wenn der OMV aus ist. Ist der Share beim Backup nicht eingebunden, versucht das
Skript ihn einzubinden und bricht sonst ab. Klappt das Schreiben nicht: Rechte/Optionen im OMV prüfen (Schritt 1.2).

### 3. Konfiguration (optional)
Die Vorgaben passen zum Aufbau auf dem NUC (`picocalc-db`, `/srv/containers/picocalc`, `/mnt/omv-backup`). Nur bei Abweichung:
```bash
sudo cp /srv/containers/picocalc/scripts/backup/picocalc-backup.env.example /etc/picocalc-backup.env
sudoedit /etc/picocalc-backup.env
```
Soll die `.env` (enthält Passwörter) nicht auf den OMV: `ENV_FILE=` leer lassen.

### 4. Testlauf von Hand
```bash
sudo bash /srv/containers/picocalc/scripts/backup/backup-picocalc.sh
ls -lh /mnt/omv-backup/picocalc/daily
```

### 5. Timer aktivieren
```bash
sudo cp /srv/containers/picocalc/scripts/backup/picocalc-backup.service /etc/systemd/system/
sudo cp /srv/containers/picocalc/scripts/backup/picocalc-backup.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now picocalc-backup.timer
systemctl list-timers picocalc-backup.timer        # nächster Lauf
```
Einen Lauf sofort auslösen und das Ergebnis lesen:
```bash
sudo systemctl start picocalc-backup.service
systemctl status picocalc-backup.service
journalctl -u picocalc-backup.service -n 30 --no-pager
```
Liegt der Mountpunkt woanders als `/mnt/omv-backup`, in der `.service` die Zeile `RequiresMountsFor=` anpassen.

## Wiederherstellung

**Immer zuerst in eine Wegwerf-Datenbank einspielen** (so testest du die Sicherung, ohne etwas zu gefährden). Das solltest
du nach der Einrichtung einmal machen:
```bash
DUMP=/mnt/omv-backup/picocalc/daily/picocalc_db_<Datum>.dump
docker exec picocalc-db psql -U printuser -d postgres -c "CREATE DATABASE printcalc_restoretest;"
docker cp "$DUMP" picocalc-db:/tmp/restore.dump
docker exec picocalc-db pg_restore -U printuser -d printcalc_restoretest --no-owner /tmp/restore.dump
docker exec picocalc-db psql -U printuser -d printcalc_restoretest -c "SELECT version_num FROM alembic_version;" -c "SELECT count(*) FROM materials;"
docker exec picocalc-db psql -U printuser -d postgres -c "DROP DATABASE printcalc_restoretest;"
```
**Echte Wiederherstellung** (ersetzt die Live-Datenbank; App vorher stoppen):
```bash
docker stop picocalc-app
docker cp "$DUMP" picocalc-db:/tmp/restore.dump
docker exec picocalc-db pg_restore -U printuser -d printcalc --clean --if-exists --no-owner /tmp/restore.dump
docker start picocalc-app
```
Der Dump muss zum Schema-Stand der laufenden App-Version passen (Alembic-Revision prüfen).

Storage zurückspielen: `sudo tar -xzf /mnt/omv-backup/picocalc/daily/picocalc_storage_<Datum>.tar.gz -C /srv/containers/picocalc/`

## Hinweis
Ein Backup auf dem OMV schützt vor Fehlern und einem defekten NUC, nicht vor Ausfall des OMV selbst oder Brand/Diebstahl
(beide stehen vermutlich im selben Raum). Wer das will, sichert den `picocalc`-Ordner des OMV zusätzlich extern
(z. B. auf eine USB-Platte oder in die Cloud).
