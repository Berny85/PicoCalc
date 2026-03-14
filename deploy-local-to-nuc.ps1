# Lokales Deployment zu NUC (OHNE GitHub!)
# Dieses Script kopiert nur die geänderten Dateien direkt auf den NUC

$NUC_IP = "192.168.50.8"
$NUC_PATH = "/mnt/user/appdata/picocalc"

Write-Host "========================================" -ForegroundColor Green
Write-Host "PicoCalc Lokales Deployment (Test → NUC)" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "⚠️  WICHTIG: Dieses Script:" -ForegroundColor Yellow
Write-Host "   • Pusht NICHT zu GitHub" -ForegroundColor Yellow
Write-Host "   • Löscht KEINE Datenbank-Daten" -ForegroundColor Yellow
Write-Host "   • Führt nur Migrationen aus" -ForegroundColor Yellow
Write-Host ""

$confirm = Read-Host "Möchten Sie fortfahren? (j/n)"
if ($confirm -ne "j" -and $confirm -ne "ja") {
    Write-Host "Abbruch." -ForegroundColor Red
    exit 1
}

# 1. Backup der Datenbank auf dem NUC erstellen
Write-Host ""
Write-Host "[1/5] Erstelle Backup auf NUC..." -ForegroundColor Yellow
$backupFile = "backup_pre_deploy_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"
ssh root@$NUC_IP "docker exec picocalc-db pg_dump -U printuser printcalc > /tmp/$backupFile"
if ($LASTEXITCODE -eq 0) {
    Write-Host "      Backup erstellt: /tmp/$backupFile" -ForegroundColor Green
} else {
    Write-Host "      ⚠️ Backup konnte nicht erstellt werden!" -ForegroundColor Red
    $continue = Read-Host "Trotzdem fortfahren? (j/n)"
    if ($continue -ne "j") { exit 1 }
}

# 2. Code auf NUC kopieren
Write-Host ""
Write-Host "[2/5] Kopiere Code auf NUC..." -ForegroundColor Yellow

# Wichtige Verzeichnisse kopieren
$dirsToCopy = @(
    "app",
    "alembic"
)

foreach ($dir in $dirsToCopy) {
    Write-Host "      Kopiere $dir..." -ForegroundColor Gray
    scp -r "./$dir" "root@${NUC_IP}:$NUC_PATH/"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Fehler beim Kopieren von $dir" -ForegroundColor Red
        exit 1
    }
}

# Wichtige Dateien kopieren
$filesToCopy = @(
    "alembic.ini",
    "docker-compose.prod.yml"
)

foreach ($file in $filesToCopy) {
    Write-Host "      Kopiere $file..." -ForegroundColor Gray
    scp "./$file" "root@${NUC_IP}:$NUC_PATH/"
}

Write-Host "      Code erfolgreich kopiert" -ForegroundColor Green

# 3. Container neustarten
Write-Host ""
Write-Host "[3/5] Starte Container neu..." -ForegroundColor Yellow
ssh root@$NUC_IP "cd $NUC_PATH && docker compose -f docker-compose.prod.yml up -d --build"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Fehler beim Neustarten der Container!" -ForegroundColor Red
    exit 1
}
Write-Host "      Container neu gestartet" -ForegroundColor Green

# 4. Migrationen ausführen
Write-Host ""
Write-Host "[4/5] Führe Datenbank-Migrationen aus..." -ForegroundColor Yellow
Start-Sleep -Seconds 5  # Warten bis Container bereit
ssh root@$NUC_IP "cd $NUC_PATH && docker compose -f docker-compose.prod.yml exec -T web alembic upgrade head"
if ($LASTEXITCODE -eq 0) {
    Write-Host "      Migrationen erfolgreich" -ForegroundColor Green
} else {
    Write-Host "      ⚠️ Migrationen möglicherweise fehlgeschlagen" -ForegroundColor Yellow
    Write-Host "         Prüfen Sie die Logs: docker logs picocalc-app" -ForegroundColor Yellow
}

# 5. Status prüfen
Write-Host ""
Write-Host "[5/5] Prüfe Container-Status..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

$services = ssh root@$NUC_IP "docker compose -f $NUC_PATH/docker-compose.prod.yml ps --format json 2>/dev/null | grep -c 'running'"
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Deployment abgeschlossen!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Services:" -ForegroundColor Yellow
Write-Host "  PicoCalc App: http://$NUC_IP`:5000" -ForegroundColor Cyan
Write-Host "  Portainer:    http://$NUC_IP`:9000" -ForegroundColor Cyan
Write-Host "  pgAdmin:      http://$NUC_IP`:5050" -ForegroundColor Cyan
Write-Host ""
Write-Host "Backup auf NUC: /tmp/$backupFile" -ForegroundColor Gray
Write-Host ""

# Container-Status anzeigen
ssh root@$NUC_IP "docker compose -f $NUC_PATH/docker-compose.prod.yml ps"
