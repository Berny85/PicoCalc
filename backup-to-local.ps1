# Backup vom NUC auf lokalen Rechner ziehen
$NUC_IP = "192.168.50.8"
$BACKUP_DIR = "$env:USERPROFILE\Documents\PicoCalc-Backups"
$DATE = Get-Date -Format "yyyy-MM-dd_HH-mm"

Write-Host "========================================" -ForegroundColor Green
Write-Host "PicoCalc Backup Tool" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Backup-Verzeichnis erstellen
New-Item -ItemType Directory -Force -Path $BACKUP_DIR | Out-Null

# Backup erstellen auf NUC
Write-Host "[1/3] Erstelle Backup auf NUC..." -ForegroundColor Yellow
ssh root@$NUC_IP "docker exec picocalc-db pg_dump -U printuser -Fc printcalc > /tmp/backup_$DATE.dump"

# Backup herunterladen
Write-Host "[2/3] Lade Backup herunter..." -ForegroundColor Yellow
scp root@${NUC_IP}:/tmp/backup_$DATE.dump "$BACKUP_DIR\backup_$DATE.dump"

# Aufräumen auf NUC
Write-Host "[3/3] Räume auf..." -ForegroundColor Yellow
ssh root@$NUC_IP "rm /tmp/backup_$DATE.dump"

Write-Host "========================================" -ForegroundColor Green
Write-Host "Backup gespeichert unter:" -ForegroundColor Green
Write-Host "$BACKUP_DIR\backup_$DATE.dump" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Green
