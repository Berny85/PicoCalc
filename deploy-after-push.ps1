# Deployment nach Git Push (wenn Auto-Deploy deaktiviert ist)

$NUC_IP = "192.168.50.8"
$NUC_PATH = "/mnt/user/appdata/picocalc"

Write-Host "========================================" -ForegroundColor Green
Write-Host "Manuelles Deployment (nach Git Push)" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Voraussetzung: Code wurde zu GitHub gepusht" -ForegroundColor Yellow
Write-Host "Auto-Deploy ist deaktiviert (Crontab auskommentiert)" -ForegroundColor Yellow
Write-Host ""

$confirm = Read-Host "Deployment auf NUC starten? (j/n)"
if ($confirm -ne "j") { exit 0 }

# 1. Backup
Write-Host ""
Write-Host "[1/4] Erstelle Backup..." -ForegroundColor Yellow
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
ssh root@$NUC_IP "docker exec picocalc-db pg_dump -U printuser printcalc > /mnt/user/backups/picocalc/backup_$timestamp.sql"
Write-Host "      ✓ Backup erstellt" -ForegroundColor Green

# 2. Git Pull auf NUC
Write-Host ""
Write-Host "[2/4] Git Pull auf NUC..." -ForegroundColor Yellow
ssh root@$NUC_IP "cd $NUC_PATH && git pull origin main"
if ($LASTEXITCODE -ne 0) {
    Write-Host "      ✗ Git Pull fehlgeschlagen!" -ForegroundColor Red
    exit 1
}
Write-Host "      ✓ Code aktualisiert" -ForegroundColor Green

# 3. Container neustarten
Write-Host ""
Write-Host "[3/4] Starte Container neu..." -ForegroundColor Yellow
ssh root@$NUC_IP "cd $NUC_PATH && docker compose -f docker-compose.prod.yml up -d --build"
Write-Host "      ✓ Container neu gestartet" -ForegroundColor Green

# 4. Migrationen
Write-Host ""
Write-Host "[4/4] Führe Migrationen aus..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
ssh root@$NUC_IP "cd $NUC_PATH && docker compose -f docker-compose.prod.yml exec -T web alembic upgrade head"
Write-Host "      ✓ Migrationen abgeschlossen" -ForegroundColor Green

# Check
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "✅ Deployment erfolgreich!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Prüfen: http://$NUC_IP`:5000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Container-Status:" -ForegroundColor Yellow
ssh root@$NUC_IP "docker compose -f $NUC_PATH/docker-compose.prod.yml ps"
