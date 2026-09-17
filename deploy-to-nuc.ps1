# Deployment Script für PicoCalc auf Debian NUC
# Dieses Script pusht den Code zu GitHub und deployed auf den NUC

param (
    [string]$NUC_IP = "192.168.50.8",
    [string]$SSH_USER = "berny",
    [string]$NUC_PATH = "/srv/containers/picocalc"
)

Write-Host "========================================" -ForegroundColor Green
Write-Host "PicoCalc Deployment Tool (Debian NUC)   " -ForegroundColor Green
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
Write-Host "      Verbinde mit ${SSH_USER}@$NUC_IP..." -ForegroundColor Gray

# Pull & Rebuild auf NUC
$deployCmd = "cd $NUC_PATH && git pull origin main && docker compose up -d --build"
ssh ${SSH_USER}@$NUC_IP "$deployCmd"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Fehler: Deployment auf NUC fehlgeschlagen!" -ForegroundColor Red
    exit 1
}

Write-Host "      Deployment erfolgreich" -ForegroundColor Green

# 3. Status prüfen
Write-Host "[3/3] Prüfe Container-Status..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
ssh ${SSH_USER}@$NUC_IP "containers status"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Deployment erfolgreich abgeschlossen!   " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Services:" -ForegroundColor Yellow
Write-Host "  PicoCalc:       http://${NUC_IP}:5000" -ForegroundColor Cyan
Write-Host "  PicoAccounting: http://${NUC_IP}:8500" -ForegroundColor Cyan
Write-Host "  Bambuddy:       http://${NUC_IP}:8000" -ForegroundColor Cyan
Write-Host "  Dozzle (Logs):  http://${NUC_IP}:8080" -ForegroundColor Cyan
Write-Host ""
