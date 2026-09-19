# Einmal-Skripte: Umzug Unraid → Debian (2026-09-17)

Diese Skripte gehören zum abgeschlossenen Serverumzug und werden im Alltag nicht gebraucht:

- `backup-unraid-migration.ps1` – Migrations-Backup vom alten Unraid-NUC (PicoCalc, Bambuddy, PicoAccounting)
- `restore-to-debian.sh` – Wiederherstellung auf dem frischen Debian-Server

**Achtung:** Der Datenbank-Dump aus diesem Backup enthält das *alte* PicoCalc-Schema (vor dem Rezept-Umbau, Alembic-Baseline `0001`) und lässt sich nicht mehr sinnvoll einspielen – neue Datenbank stattdessen leer starten und die Stammdaten neu erfassen (siehe `DEPLOYMENT.md`).

Sobald der Umzug endgültig verifiziert ist, kann dieser Ordner gelöscht werden (die Skripte bleiben in der Git-Historie).
