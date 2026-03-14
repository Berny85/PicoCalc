# Manuelles Deployment Script für PicoCalc (Windows PowerShell)
# Wird auf dem DEV-PC ausgeführt, verbindet sich per SSH mit dem NUC
# Verwendung: .\deploy-manual.ps1

# Konfiguration
$NUC_IP = "192.168.50.8"
$NUC_USER = "root"
$NUC_PATH = "/mnt/user/appdata/picocalc"
$LOG_FILE = "deploy-manual.log"

# Farben
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"
$Cyan = "Cyan"
$Blue = "Blue"

# Logging-Funktion
function Write-Log {
    param(
        [string]$Message,
        [string]$Color = "White",
        [switch]$NoConsole
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] $Message"
    
    if (-not $NoConsole) {
        Write-Host $logEntry -ForegroundColor $Color
    }
    Add-Content -Path $LOG_FILE -Value $logEntry
}

# Header
Write-Host "========================================" -ForegroundColor $Blue
Write-Host "PicoCalc Manuelles Deployment" -ForegroundColor $Blue
Write-Host "========================================" -ForegroundColor $Blue
Write-Host ""

Write-Log "Starte Deployment zu NUC ($NUC_IP)..." -Color $Cyan
Write-Log ""

# Prüfe Git
Write-Log "Prüfe Git-Status..." -Color $Cyan

try {
    $gitDir = git rev-parse --git-dir 2>$null
    if (-not $gitDir) {
        Write-Log "✗ Fehler: Kein Git-Repository gefunden!" -Color $Red
        exit 1
    }
} catch {
    Write-Log "✗ Git nicht gefunden oder kein Repository!" -Color $Red
    exit 1
}

# Prüfe auf uncommitted Changes
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Log "⚠ Warnung: Ungespeicherte Änderungen vorhanden:" -Color $Yellow
    $gitStatus | ForEach-Object { Write-Log "  $_" }
    Write-Log ""
    $answer = Read-Host "Möchten Sie trotzdem fortfahren? (j/n)"
    if ($answer -ne "j" -and $answer -ne "ja") {
        Write-Log "Abbruch durch Benutzer" -Color $Yellow
        exit 0
    }
    Write-Log ""
}

# Zeige aktuellen Commit
$localCommit = git rev-parse --short HEAD
$localBranch = git branch --show-current
Write-Log "Aktueller Branch: $localBranch" -Color $Cyan
Write-Log "Aktueller Commit: $localCommit" -Color $Cyan
Write-Log ""

# 1. Push zu GitHub
Write-Log "[1/4] Push zu GitHub..." -Color $Cyan
Write-Log ""

try {
    git push origin $localBranch 2>&1 | ForEach-Object {
        Write-Host $_
        Add-Content -Path $LOG_FILE -Value $_
    }
    $exitCode = $LASTEXITCODE
    
    if ($exitCode -eq 0) {
        Write-Log ""
        Write-Log "✓ Code erfolgreich gepusht" -Color $Green
    } else {
        Write-Log ""
        Write-Log "✗ Push fehlgeschlagen!" -Color $Red
        exit 1
    }
} catch {
    Write-Log "✗ Fehler beim Push: $_" -Color $Red
    exit 1
}

Write-Log ""
Write-Log "[2/4] Verbinde mit NUC ($NUC_IP)..." -Color $Cyan
Write-Log ""

# Prüfe SSH-Verbindung
try {
    $sshTest = ssh -o ConnectTimeout=5 "$NUC_USER@$NUC_IP" "echo 'SSH-Verbindung OK'" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Log "✓ SSH-Verbindung erfolgreich" -Color $Green
    } else {
        throw "SSH fehlgeschlagen"
    }
} catch {
    Write-Log "✗ SSH-Verbindung zum NUC fehlgeschlagen!" -Color $Red
    Write-Log "Bitte prüfen Sie:" -Color $Yellow
    Write-Log "  - Ist der NUC erreichbar? (ping $NUC_IP)"
    Write-Log "  - Ist SSH aktiviert?"
    Write-Log "  - Ist der SSH-Key eingerichtet? (ssh-keygen + ssh-copy-id)"
    exit 1
}

Write-Log ""
Write-Log "[3/4] Starte Deployment auf NUC..." -Color $Cyan
Write-Log ""

# Führe deploy.sh auf dem NUC aus
$deployOutput = ssh "$NUC_USER@$NUC_IP" "bash $NUC_PATH/deploy.sh" 2>&1
$deployExitCode = $LASTEXITCODE

$deployOutput | ForEach-Object {
    Write-Host "[NUC] $_"
    Add-Content -Path $LOG_FILE -Value "[NUC] $_"
}

if ($deployExitCode -ne 0) {
    Write-Log ""
    Write-Log "✗ Deployment auf NUC fehlgeschlagen! (Exit Code: $deployExitCode)" -Color $Red
    exit 1
}

Write-Log ""
Write-Log "[4/4] Prüfe Deployment-Status..." -Color $Cyan
Write-Log ""

# Warte kurz und prüfe Container-Status
Start-Sleep -Seconds 2

$webRunning = ssh "$NUC_USER@$NUC_IP" "docker compose -f $NUC_PATH/docker-compose.prod.yml ps web --status running -q" 2>$null
$dbRunning = ssh "$NUC_USER@$NUC_IP" "docker compose -f $NUC_PATH/docker-compose.prod.yml ps db --status running -q" 2>$null

if ($webRunning -and $dbRunning) {
    Write-Log "✓ Alle Container laufen" -Color $Green
    Write-Log "  - Web: OK"
    Write-Log "  - DB:  OK"
} else {
    Write-Log "⚠ Warnung: Nicht alle Container laufen!" -Color $Yellow
    if (-not $webRunning) { Write-Log "  - Web: FEHLER" -Color $Red }
    if (-not $dbRunning) { Write-Log "  - DB:  FEHLER" -Color $Red }
}

Write-Log ""
Write-Host "========================================" -ForegroundColor $Green
Write-Host "✓ Deployment abgeschlossen!" -ForegroundColor $Green
Write-Host "========================================" -ForegroundColor $Green
Write-Log ""
Write-Log "Log-Datei: $LOG_FILE"
Write-Log "NUC URL: http://$NUC_IP:5000"
Write-Log ""

# Frage ob Logs angezeigt werden sollen
$showLogs = Read-Host "Logs anzeigen? (j/n)"
if ($showLogs -eq "j" -or $showLogs -eq "ja") {
    Write-Host ""
    Write-Host "--- Letzte 30 Zeilen aus $LOG_FILE ---" -ForegroundColor $Cyan
    Get-Content -Path $LOG_FILE -Tail 30
}
