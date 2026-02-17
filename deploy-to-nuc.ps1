# Deployment Script für PicoCalc
# Dieses Script pusht den Code zu GitHub und deployed auf den NUC

$NUC_IP = "192.168.50.8"
$NUC_PATH = "/mnt/user/appdata/picocalc"

Write-Host "========================================" -ForegroundColor Green
Write-Host "PicoCalc Deployment Tool" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Prüfe ob Git Changes existieren
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Host "Ungespeicherte Änderungen gefunden:" -ForegroundColor Yellow
    Write-Host $gitStatus -ForegroundColor Cyan
    Write-Host ""
    
    $commit = Read-Host "Möchtest du die Änderungen commiten? (j/n)"
    if ($commit -eq "j" -or $commit -eq "ja") {
        $message = Read-Host "Commit-Nachricht"
        git add .
        git commit -m "$message"
    } else {
        Write-Host "Abbruch: Bitte committe oder stash deine Änderungen zuerst." -ForegroundColor Red
        exit 1
    }
}

# 1. Push zu GitHub
Write-Host "[1/3] Pushe Code zu GitHub..." -ForegroundColor Yellow
git push origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "Fehler: Push zu GitHub fehlgeschlagen!" -ForegroundColor Red
    exit 1
}
Write-Host "      Code erfolgreich gepusht" -ForegroundColor Green

# 2. Deploy auf NUC
Write-Host "[2/3] Deploye auf NUC..." -ForegroundColor Yellow
Write-Host "      Verbinde mit $NUC_IP..." -ForegroundColor Gray

# Führe Deploy-Script auf NUC aus
ssh root@$NUC_IP "bash $NUC_PATH/deploy.sh"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Fehler: Deployment auf NUC fehlgeschlagen!" -ForegroundColor Red
    exit 1
}

Write-Host "      Deployment erfolgreich" -ForegroundColor Green

# 3. Status prüfen
Write-Host "[3/3] Prüfe Container-Status..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
$status = ssh root@$NUC_IP "docker compose -f $NUC_PATH/docker-compose.prod.yml ps --services --filter 'status=running' | wc -l"
$status = [int]$status.Trim()

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Deployment erfolgreich!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Services:" -ForegroundColor Yellow
Write-Host "  PicoCalc App: http://$NUC_IP`:5000" -ForegroundColor Cyan
Write-Host "  Portainer:    http://$NUC_IP`:9000" -ForegroundColor Cyan
Write-Host "  Dozzle:       http://$NUC_IP`:8080" -ForegroundColor Cyan
Write-Host "  pgAdmin:      http://$NUC_IP`:5050" -ForegroundColor Cyan
Write-Host ""

if ($status -ge 4) {
    Write-Host "Container Status: $status/5 laufen" -ForegroundColor Green
} else {
    Write-Host "Container Status: $status/5 laufen" -ForegroundColor Red
}

Write-Host ""
