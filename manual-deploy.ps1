# Manuelles Deployment zu NUC (sicher, kontrolliert)
# NACH Crontab-Deaktivierung verwenden!

$NUC_IP = "192.168.50.8"
$NUC_PATH = "/mnt/user/appdata/picocalc"

Write-Host "========================================" -ForegroundColor Green
Write-Host "Manuelles PicoCalc Deployment" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# 1. Prüfe ob Git Changes existieren
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Host "⚠️  Ungespeicherte Änderungen:" -ForegroundColor Yellow
    Write-Host $gitStatus -ForegroundColor Cyan
    Write-Host ""
    
    $commit = Read-Host "Änderungen zu GitHub commiten? (j/n)"
    if ($commit -eq "j" -or $commit -eq "ja") {
        $message = Read-Host "Commit-Nachricht"
        git add .
        git commit -m "$message"
        
        $push = Read-Host "Zu GitHub pushen? (j/n)"
        if ($push -eq "j") {
            git push origin main
        }
    }
}

# 2. Pre-Deployment Check
Write-Host ""
Write-Host "[1/4] Pre-Deployment Check..." -ForegroundColor Yellow

# Teste lokale App
Write-Host "      Teste lokale App..." -ForegroundColor Gray
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5000" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "      ✓ Lokale App läuft (Status: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "      ✗ Lokale App nicht erreichbar!" -ForegroundColor Red
    $continue = Read-Host "Trotzdem deployen? (j/n)"
    if ($continue -ne "j") { exit 1 }
}

# 3. Backup auf NUC
Write-Host ""
Write-Host "[2/4] Backup auf NUC erstellen..." -ForegroundColor Yellow
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = "backup_before_deploy_$timestamp.sql"

ssh root@$NUC_IP "docker exec picocalc-db pg_dump -U printuser printcalc > /mnt/user/backups/picocalc/$backupFile 2>/dev/null || docker exec picocalc-db pg_dump -U printuser printcalc > /tmp/$backupFile"
if ($LASTEXITCODE -eq 0) {
    Write-Host "      ✓ Backup erstellt: $backupFile" -ForegroundColor Green
} else {
    Write-Host "      ⚠️ Backup fehlgeschlagen!" -ForegroundColor Red
    $continue = Read-Host "Trotzdem fortfahren? (j/n)"
    if ($continue -ne "j") { exit 1 }
}

# 4. Auf NUC deployen
Write-Host ""
Write-Host "[3/4] Deploye auf NUC..." -ForegroundColor Yellow

# Code aktualisieren (via Git Pull auf NUC)
Write-Host "      Führe git pull auf NUC aus..." -ForegroundColor Gray
ssh root@$NUC_IP "cd $NUC_PATH && git pull origin main"
if ($LASTEXITCODE -ne 0) {
    Write-Host "      ✗ Git Pull fehlgeschlagen!" -ForegroundColor Red
    exit 1
}

# Container neustarten
Write-Host "      Starte Container neu..." -ForegroundColor Gray
ssh root@$NUC_IP "cd $NUC_PATH && docker compose -f docker-compose.prod.yml up -d --build"
if ($LASTEXITCODE -ne 0) {
    Write-Host "      ✗ Container-Neustart fehlgeschlagen!" -ForegroundColor Red
    exit 1
}

# Migrationen ausführen
Write-Host "      Warte auf Container..." -ForegroundColor Gray
Start-Sleep -Seconds 5
Write-Host "      Führe Migrationen aus..." -ForegroundColor Gray
ssh root@$NUC_IP "cd $NUC_PATH && docker compose -f docker-compose.prod.yml exec -T web alembic upgrade head"
if ($LASTEXITCODE -eq 0) {
    Write-Host "      ✓ Migrationen erfolgreich" -ForegroundColor Green
} else {
    Write-Host "      ⚠️ Migrationen fehlgeschlagen!" -ForegroundColor Red
}

# 5. Post-Deployment Check
Write-Host ""
Write-Host "[4/4] Post-Deployment Check..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Prüfe ob NUC App erreichbar
try {
    $response = Invoke-WebRequest -Uri "http://$NUC_IP`:5000" -TimeoutSec 10 -ErrorAction Stop
    Write-Host "      ✓ NUC App erreichbar (Status: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "      ✗ NUC App NICHT erreichbar!" -ForegroundColor Red
}

# Container-Status
Write-Host ""
Write-Host "Container-Status auf NUC:" -ForegroundColor Yellow
ssh root@$NUC_IP "docker compose -f $NUC_PATH/docker-compose.prod.yml ps"

# Fertig
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Deployment abgeschlossen!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Links:" -ForegroundColor Yellow
Write-Host "  🌐 App:    http://$NUC_IP`:5000" -ForegroundColor Cyan
Write-Host "  🐳 Logs:   ssh root@$NUC_IP 'docker logs -f picocalc-app'" -ForegroundColor Gray
Write-Host ""
Write-Host "Rollback bei Problemen:" -ForegroundColor Yellow
Write-Host "  ssh root@$NUC_IP" -ForegroundColor Gray
Write-Host "  cd $NUC_PATH" -ForegroundColor Gray
Write-Host "  git log --oneline -5   # Finde alten Commit" -ForegroundColor Gray
Write-Host "  git checkout <commit-hash>   # Rollback" -ForegroundColor Gray
Write-Host "  docker compose -f docker-compose.prod.yml up -d --build" -ForegroundColor Gray
Write-Host ""
