# ==============================================================================
# Vollständiges Migrations-Backup vor NUC-Neuinstallation (Unraid -> Debian)
# Sichert in einem Rutsch: PicoCalc (DB + Storage + Config), Bambuddy, 
# PicoAccounting & Docker-Configs/Templates
# ==============================================================================

param (
    [string]$NucIp = "192.168.50.8",
    [string]$TargetDir = "$PSScriptRoot\..\Backups\NUC_Unraid_Migration_$(Get-Date -Format 'yyyy-MM-dd_HH-mm')"
)

$ErrorActionPreference = "Continue"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  NUC MIGRATIONS-BACKUP: UNRAID -> DEBIAN                             " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "Ziel-IP:     $NucIp" -ForegroundColor Yellow
Write-Host "Ziel-Ordner: $TargetDir" -ForegroundColor Yellow
Write-Host ""

# Zielverzeichnis erstellen
if (-not (Test-Path $TargetDir)) {
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
}

Write-Host "Prüfe Erreichbarkeit des NUC..." -ForegroundColor Gray
$pingTest = Test-Connection -ComputerName $NucIp -Count 1 -Quiet
if (-not $pingTest) {
    Write-Host "[FEHLER] NUC unter $NucIp ist per Ping nicht erreichbar!" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] NUC antwortet auf Ping." -ForegroundColor Green
Write-Host ""

# ------------------------------------------------------------------------------
# 1. Erstelle das Backup direkt auf dem NUC in einem einzigen Skript-Lauf
# (Spart ständiges erneutes Eingeben des SSH-Passworts!)
# ------------------------------------------------------------------------------
Write-Host "[1/3] Erstelle komprimiertes Gesamt-Backup direkt auf dem NUC..." -ForegroundColor Yellow
Write-Host "      (Bitte bei Abfrage das Unraid root-Passwort eingeben)" -ForegroundColor Gray
Write-Host ""

$remoteCommands = @'
set -e
WORK_DIR="/tmp/nuc_migration_backup"
rm -rf $WORK_DIR
mkdir -p $WORK_DIR/picocalc $WORK_DIR/picoaccounting $WORK_DIR/bambuddy $WORK_DIR/docker_metadata

echo "--- 1. Docker Status & Templates ---"
docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" > $WORK_DIR/docker_metadata/docker_ps.txt || true
docker inspect $(docker ps -aq 2>/dev/null) > $WORK_DIR/docker_metadata/docker_inspect_all.json 2>/dev/null || true
if [ -d "/boot/config/plugins/dockerMan/templates-user" ]; then
    cp -r /boot/config/plugins/dockerMan/templates-user $WORK_DIR/docker_metadata/
fi

echo "--- 2. PicoCalc sichern ---"
# PostgreSQL Dump
if docker ps --format '{{.Names}}' | grep -q "^picocalc-db$"; then
    echo "Dumping picocalc-db..."
    docker exec picocalc-db pg_dump -U printuser -Fc printcalc > $WORK_DIR/picocalc/picocalc_db.dump || echo "Dump Warning"
fi
# Storage (SVGs/Bilder)
if [ -d "/mnt/user/appdata/picocalc/storage" ]; then
    cp -r /mnt/user/appdata/picocalc/storage $WORK_DIR/picocalc/
fi
# Configs
[ -f "/mnt/user/appdata/picocalc/.env" ] && cp /mnt/user/appdata/picocalc/.env $WORK_DIR/picocalc/
[ -f "/mnt/user/appdata/picocalc/postgresql.conf" ] && cp /mnt/user/appdata/picocalc/postgresql.conf $WORK_DIR/picocalc/

echo "--- 3. PicoAccounting sichern ---"
if [ -d "/mnt/user/appdata/pico-accounting" ]; then
    cp -r /mnt/user/appdata/pico-accounting/* $WORK_DIR/picoaccounting/ 2>/dev/null || true
elif [ -d "/mnt/user/appdata/picoaccounting" ]; then
    cp -r /mnt/user/appdata/picoaccounting/* $WORK_DIR/picoaccounting/ 2>/dev/null || true
fi

echo "--- 4. Bambuddy sichern ---"
if [ -d "/mnt/user/appdata/bambuddy" ]; then
    cp -r /mnt/user/appdata/bambuddy $WORK_DIR/bambuddy/data 2>/dev/null || true
fi

echo "--- 5. Appdata Übersicht ---"
ls -laR /mnt/user/appdata > $WORK_DIR/docker_metadata/all_appdata_tree.txt 2>/dev/null || true

echo "--- 6. Archiv erstellen ---"
cd /tmp
tar -czf /tmp/nuc_full_backup.tar.gz -C $WORK_DIR .
rm -rf $WORK_DIR
echo "FERTIG_AUF_NUC"
'@

ssh root@$NucIp "$remoteCommands"

# ------------------------------------------------------------------------------
# 2. Archiv auf Windows PC herunterladen
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "[2/3] Lade Archiv vom NUC auf den lokalen PC herunter..." -ForegroundColor Yellow
$archiveDest = "$TargetDir\nuc_full_backup.tar.gz"
scp root@${NucIp}:/tmp/nuc_full_backup.tar.gz "$archiveDest"

if ($LASTEXITCODE -eq 0 -and (Test-Path $archiveDest)) {
    $fileSizeMB = [math]::Round(((Get-Item $archiveDest).Length / 1MB), 2)
    Write-Host "      [OK] Archiv erfolgreich empfangen ($fileSizeMB MB)" -ForegroundColor Green
    
    # Auf NUC aufräumen
    ssh root@$NucIp "rm -f /tmp/nuc_full_backup.tar.gz" | Out-Null
} else {
    Write-Host "      [FEHLER] Download des Backup-Archivs fehlgeschlagen!" -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------------------------
# 3. Archiv lokal entpacken zur direkten Kontrolle
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "[3/3] Entpacke Archiv lokal zur Verifikation..." -ForegroundColor Yellow
tar -xzf "$archiveDest" -C "$TargetDir"

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "  MIGRATIONS-BACKUP ERFOLGREICH ABGESCHLOSSEN!                         " -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "Gespeichert in: $TargetDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "Gefundene Dateien und Ordner:" -ForegroundColor Yellow
Get-ChildItem -Path $TargetDir -Recurse | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize

Write-Host "WICHTIG:" -ForegroundColor Red
Write-Host "1. Prüfe, ob 'picocalc_db.dump' existiert und nicht 0 Bytes groß ist." -ForegroundColor White
Write-Host "2. Prüfe die Ordner 'picoaccounting' und 'bambuddy'." -ForegroundColor White
Write-Host "Erst danach darf der NUC plattgemacht werden!" -ForegroundColor Yellow
Write-Host ""
