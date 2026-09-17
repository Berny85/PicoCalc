# ==============================================================================
# Vollständiges Backup vom NUC (Debian) auf lokalen Windows-Rechner ziehen
# Sichert: PicoCalc (DB + Storage + .env), Bambuddy und PicoAccounting
# ==============================================================================

param (
    [string]$NUC_IP = "192.168.50.8",
    [string]$SSH_USER = "berny",
    [string]$BASE_BACKUP_DIR = "$env:USERPROFILE\Documents\PicoCalc-Backups"
)

$DATE = Get-Date -Format "yyyy-MM-dd_HH-mm"
$DEST_DIR = "$BASE_BACKUP_DIR\$DATE"

Write-Host "========================================" -ForegroundColor Green
Write-Host "PicoCalc, Bambuddy & Accounting Backup  " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Ziel-IP:  $NUC_IP (User: $SSH_USER)" -ForegroundColor Yellow
Write-Host "Ziel-Ordner: $DEST_DIR" -ForegroundColor Yellow
Write-Host ""

# Backup-Verzeichnis erstellen
New-Item -ItemType Directory -Force -Path $DEST_DIR | Out-Null

# 1. PicoCalc Datenbank
Write-Host "[1/5] Sichere PicoCalc Datenbank (PostgreSQL)..." -ForegroundColor Yellow
ssh ${SSH_USER}@$NUC_IP "docker exec picocalc-db pg_dump -U printuser -Fc printcalc > /tmp/backup_db_$DATE.dump"
if ($LASTEXITCODE -eq 0) {
    scp ${SSH_USER}@${NUC_IP}:/tmp/backup_db_$DATE.dump "$DEST_DIR\picocalc_db.dump"
    ssh ${SSH_USER}@$NUC_IP "rm -f /tmp/backup_db_$DATE.dump"
    Write-Host "      [OK] Datenbank gesichert" -ForegroundColor Green
} else {
    Write-Host "      [FEHLER] Fehler beim Datenbank-Dump!" -ForegroundColor Red
}

# 2. PicoCalc Storage (SVGs, Bilder)
Write-Host "[2/5] Sichere PicoCalc Storage (SVG-Dateien, Bilder)..." -ForegroundColor Yellow
ssh ${SSH_USER}@$NUC_IP "tar -czf /tmp/picocalc_storage_$DATE.tar.gz -C /srv/containers/picocalc storage 2>/dev/null"
if ($LASTEXITCODE -eq 0) {
    scp ${SSH_USER}@${NUC_IP}:/tmp/picocalc_storage_$DATE.tar.gz "$DEST_DIR\picocalc_storage.tar.gz"
    ssh ${SSH_USER}@$NUC_IP "rm -f /tmp/picocalc_storage_$DATE.tar.gz"
    Write-Host "      [OK] Storage (SVGs/Bilder) gesichert" -ForegroundColor Green
} else {
    Write-Host "      [WARNUNG] Kein Storage-Ordner gefunden oder Fehler beim Packen" -ForegroundColor Yellow
}

# 3. PicoCalc .env Konfiguration
Write-Host "[3/5] Sichere PicoCalc .env Konfiguration..." -ForegroundColor Yellow
scp ${SSH_USER}@${NUC_IP}:/srv/containers/picocalc/.env "$DEST_DIR\picocalc.env" 2>$null
if (Test-Path "$DEST_DIR\picocalc.env") {
    Write-Host "      [OK] .env gesichert" -ForegroundColor Green
} else {
    Write-Host "      [INFO] Keine .env vorhanden" -ForegroundColor Gray
}

# 4. Bambuddy Daten (Druckhistorie, Filament-Profile)
Write-Host "[4/5] Sichere Bambuddy Daten..." -ForegroundColor Yellow
ssh ${SSH_USER}@$NUC_IP "tar -czf /tmp/bambuddy_$DATE.tar.gz -C /srv/containers/bambuddy data 2>/dev/null"
if ($LASTEXITCODE -eq 0) {
    scp ${SSH_USER}@${NUC_IP}:/tmp/bambuddy_$DATE.tar.gz "$DEST_DIR\bambuddy.tar.gz"
    ssh ${SSH_USER}@$NUC_IP "rm -f /tmp/bambuddy_$DATE.tar.gz"
    Write-Host "      [OK] Bambuddy Daten gesichert" -ForegroundColor Green
} else {
    Write-Host "      [WARNUNG] Bambuddy-Ordner unter /srv/containers/bambuddy nicht gefunden!" -ForegroundColor Yellow
}

# 5. PicoAccounting Daten (SQLite DB, Belege)
Write-Host "[5/5] Sichere PicoAccounting Daten..." -ForegroundColor Yellow
ssh ${SSH_USER}@$NUC_IP "tar -czf /tmp/picoaccounting_$DATE.tar.gz -C /srv/containers/pico-accounting data 2>/dev/null"
if ($LASTEXITCODE -eq 0) {
    scp ${SSH_USER}@${NUC_IP}:/tmp/picoaccounting_$DATE.tar.gz "$DEST_DIR\picoaccounting.tar.gz"
    ssh ${SSH_USER}@$NUC_IP "rm -f /tmp/picoaccounting_$DATE.tar.gz"
    Write-Host "      [OK] PicoAccounting Daten gesichert" -ForegroundColor Green
} else {
    Write-Host "      [WARNUNG] PicoAccounting-Ordner unter /srv/containers/pico-accounting nicht gefunden!" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Voll-Backup abgeschlossen!" -ForegroundColor Green
Write-Host "Gespeichert unter: $DEST_DIR" -ForegroundColor Cyan
Get-ChildItem -Path $DEST_DIR | Format-Table Name, Length, LastWriteTime
Write-Host "========================================" -ForegroundColor Green
