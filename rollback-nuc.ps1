# Rollback auf NUC (Notfall-Wiederherstellung)

$NUC_IP = "192.168.50.8"
$NUC_PATH = "/mnt/user/appdata/picocalc"

Write-Host "========================================" -ForegroundColor Red
Write-Host "🚨 NUC Rollback (Notfall)" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Red
Write-Host ""

# Letzte Backups anzeigen
Write-Host "Verfügbare Backups auf NUC:" -ForegroundColor Yellow
ssh root@$NUC_IP "ls -lh /mnt/user/backups/picocalc/*.sql 2>/dev/null || ls -lh /tmp/backup*.sql 2>/dev/null || echo 'Keine Backups gefunden'"

Write-Host ""
Write-Host "Letzte Git Commits auf NUC:" -ForegroundColor Yellow
ssh root@$NUC_IP "cd $NUC_PATH && git log --oneline -5"

Write-Host ""
Write-Host "Rollback-Optionen:" -ForegroundColor Yellow
Write-Host "  1 = Datenbank-Restore aus Backup" -ForegroundColor Cyan
Write-Host "  2 = Git Rollback zu vorherigem Commit" -ForegroundColor Cyan
Write-Host "  3 = Container nur neustarten" -ForegroundColor Cyan
Write-Host "  4 = Abbruch" -ForegroundColor Gray
Write-Host ""

$choice = Read-Host "Wählen Sie (1-4)"

switch ($choice) {
    "1" {
        $backup = Read-Host "Backup-Dateiname (z.B. backup_before_deploy_20240314_123000.sql)"
        Write-Host ""
        Write-Host "Stelle Datenbank wieder her..." -ForegroundColor Yellow
        ssh root@$NUC_IP "docker exec -i picocalc-db psql -U printuser printcalc < /mnt/user/backups/picocalc/$backup 2>/dev/null || docker exec -i picocalc-db psql -U printuser printcalc < /tmp/$backup"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Datenbank wiederhergestellt" -ForegroundColor Green
        } else {
            Write-Host "✗ Restore fehlgeschlagen!" -ForegroundColor Red
        }
    }
    "2" {
        $commit = Read-Host "Commit-Hash (z.B. abc1234)"
        Write-Host ""
        Write-Host "Führe Git Rollback durch..." -ForegroundColor Yellow
        ssh root@$NUC_IP "cd $NUC_PATH && git checkout $commit"
        ssh root@$NUC_IP "cd $NUC_PATH && docker compose -f docker-compose.prod.yml up -d --build"
        Write-Host "✓ Rollback durchgeführt" -ForegroundColor Green
    }
    "3" {
        Write-Host ""
        Write-Host "Starte Container neu..." -ForegroundColor Yellow
        ssh root@$NUC_IP "cd $NUC_PATH && docker compose -f docker-compose.prod.yml restart"
        Write-Host "✓ Container neu gestartet" -ForegroundColor Green
    }
    default {
        Write-Host "Abbruch." -ForegroundColor Gray
        exit 0
    }
}

Write-Host ""
Write-Host "Status prüfen: http://$NUC_IP`:5000" -ForegroundColor Cyan
