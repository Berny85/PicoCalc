#Requires -Version 5.1
<#
.SYNOPSIS
    Datenbank-Migrationsskript für PicoCalc mit Alembic
.DESCRIPTION
    Dieses Skript führt Alembic-Migrationen aus und bietet hilfreiche Befehle.
    
.PARAMETER Command
    Der auszuführende Befehl:
    - migrate: Führt alle ausstehenden Migrationen aus (Standard)
    - create: Erstellt eine neue Migration (--autogenerate)
    - downgrade: Setzt die letzte Migration zurück
    - history: Zeigt die Migrationshistorie an
    - current: Zeigt die aktuelle Migration an
    - stamp: Markiert die Datenbank als aktuell (ohne Migration)
    
.PARAMETER Message
    Die Nachricht für eine neue Migration (nur bei 'create')
    
.EXAMPLES
    .\migrate.ps1
    .\migrate.ps1 -Command migrate
    .\migrate.ps1 -Command create -Message "Added new column"
    .\migrate.ps1 -Command history
#>

param(
    [Parameter()]
    [ValidateSet("migrate", "create", "downgrade", "history", "current", "stamp")]
    [string]$Command = "migrate",
    
    [Parameter()]
    [string]$Message = ""
)

$ErrorActionPreference = "Stop"

function Test-DockerCompose {
    try {
        $null = docker-compose ps 2>$null
        return $true
    } catch {
        return $false
    }
}

function Invoke-Alembic {
    param([string]$Arguments)
    docker-compose exec -T web alembic $Arguments.Split(' ')
}

# Prüfe ob Container laufen
if (-not (Test-DockerCompose)) {
    Write-Host "❌ Fehler: Docker-Container sind nicht gestartet!" -ForegroundColor Red
    Write-Host "Bitte zuerst ausführen: docker-compose up -d" -ForegroundColor Yellow
    exit 1
}

Write-Host "🔄 PicoCalc Datenbank-Migration" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan

switch ($Command) {
    "migrate" {
        Write-Host "⬆️  Führe Migrationen aus..." -ForegroundColor Yellow
        Invoke-Alembic "upgrade head"
        Write-Host "`n✅ Migration erfolgreich abgeschlossen!" -ForegroundColor Green
    }
    
    "create" {
        if ([string]::IsNullOrWhiteSpace($Message)) {
            Write-Host "❌ Fehler: Bitte eine Nachricht angeben!" -ForegroundColor Red
            Write-Host "Beispiel: .\migrate.ps1 -Command create -Message 'Added user table'" -ForegroundColor Yellow
            exit 1
        }
        Write-Host "📝 Erstelle neue Migration: '$Message'..." -ForegroundColor Yellow
        Invoke-Alembic "revision --autogenerate -m `"$Message`""
        
        # Kopiere neue Migration in das lokale Verzeichnis
        Write-Host "`n📥 Kopiere neue Migrationsdatei..." -ForegroundColor Yellow
        docker cp "picocalc-web-1:/app/alembic/versions/." alembic/versions/ 2>$null
        
        Write-Host "`n✅ Migration erstellt! Führe jetzt aus mit: .\migrate.ps1" -ForegroundColor Green
    }
    
    "downgrade" {
        Write-Host "⬇️  Setze letzte Migration zurück..." -ForegroundColor Yellow
        Invoke-Alembic "downgrade -1"
        Write-Host "`n✅ Downgrade erfolgreich!" -ForegroundColor Green
    }
    
    "history" {
        Write-Host "📜 Migrationshistorie:" -ForegroundColor Yellow
        Invoke-Alembic "history --verbose"
    }
    
    "current" {
        Write-Host "📍 Aktuelle Migration:" -ForegroundColor Yellow
        Invoke-Alembic "current"
    }
    
    "stamp" {
        Write-Host "🔖 Markiere Datenbank als aktuell..." -ForegroundColor Yellow
        Invoke-Alembic "stamp head"
        Write-Host "`n✅ Datenbank markiert!" -ForegroundColor Green
    }
}

Write-Host ""
