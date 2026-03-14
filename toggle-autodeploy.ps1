# Auto-Deployment an/aus schalten

$NUC_IP = "192.168.50.8"

Write-Host "========================================" -ForegroundColor Green
Write-Host "Auto-Deployment Verwaltung" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Aktuellen Status prüfen
$cronStatus = ssh root@$NUC_IP "crontab -l | grep -v '^#' | grep auto-deploy || echo 'INAKTIV'"

if ($cronStatus -eq "INAKTIV") {
    Write-Host "Status: Auto-Deployment ist INAKTIV" -ForegroundColor Yellow
    Write-Host ""
    $enable = Read-Host "Auto-Deployment aktivieren? (j/n)"
    if ($enable -eq "j") {
        ssh root@$NUC_IP "crontab -l | sed 's/^#.*auto-deploy.*/\*\/5 \* \* \* \* \/mnt\/user\/appdata\/picocalc\/auto-deploy.sh >> \/mnt\/user\/appdata\/picocalc\/auto-deploy.log 2>\&1/' | crontab -"
        Write-Host "✓ Auto-Deployment aktiviert" -ForegroundColor Green
    }
} else {
    Write-Host "Status: Auto-Deployment ist AKTIV" -ForegroundColor Green
    Write-Host "Crontab: $cronStatus" -ForegroundColor Gray
    Write-Host ""
    $disable = Read-Host "Auto-Deployment deaktivieren? (j/n)"
    if ($disable -eq "j") {
        ssh root@$NUC_IP "crontab -l | sed 's/^\(.*auto-deploy.*\)/# \1/' | crontab -"
        Write-Host "✓ Auto-Deployment deaktiviert" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Neuer Status:" -ForegroundColor Yellow
ssh root@$NUC_IP "crontab -l | grep auto-deploy || echo 'Kein Eintrag gefunden'"
