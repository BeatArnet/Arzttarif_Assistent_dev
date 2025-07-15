﻿<#
.SYNOPSIS
    Ein PowerShell-Skript, um einen Feature-Branch sicher in einen Ziel-Branch (z.B. 'main') zu mergen,
    die Änderungen zu pushen und optional den alten Branch zu löschen.

.DESCRIPTION
    Das Skript führt den Benutzer durch folgende Schritte:
    1. Abrufen der neuesten Änderungen vom Remote-Repository.
    2. Anzeigen aller lokalen Branches zur Auswahl.
    3. Abfragen des zu mergenden Branch-Namens (bereinigt die Eingabe automatisch).
    4. Durchführen von Sicherheitsprüfungen (Branch existiert? Nicht der Ziel-Branch selbst?).
    5. Wechseln zum Ziel-Branch.
    6. Mergen des ausgewählten Branches.
    7. Pushen der Änderungen zum Remote-Repository.
    8. Anbieten, den nun überflüssigen lokalen Branch zu löschen.
#>

# Stellt sicher, dass die Ausgabe in der Konsole korrekt (mit Umlauten etc.) dargestellt wird.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# --- Konfiguration ---
# Den Ziel-Branch hier definieren, um das Skript einfacher anzupassen (z.B. für 'master' oder 'develop')
$targetBranch = 'main'
# --------------------

# 1. Git-Änderungen von allen Remotes abrufen
Write-Host "Rufe neueste Git-Änderungen ab (git fetch)..." -ForegroundColor Yellow
git fetch --all

# 2. Lokale Branches anzeigen, damit der Benutzer eine Auswahl hat
Write-Host "Verfügbare lokale Branches:" -ForegroundColor Cyan
git branch

# 3. Benutzer nach dem zu mergenden Branch fragen
$userInput = Read-Host "Welchen Branch möchten Sie in '$targetBranch' mergen?"

# Eingabe bereinigen: Sternchen (*) und Leerzeichen am Anfang/Ende entfernen
$branchName = $userInput.Replace('*', '').Trim()

# 4. Sicherheitsprüfungen
# Prüfen, ob eine Eingabe gemacht wurde
if ([string]::IsNullOrWhiteSpace($branchName)) {
    Write-Host "Fehler: Es wurde kein Branch-Name eingegeben." -ForegroundColor Red
    exit
}

# Prüfen, ob der Benutzer versucht, den Branch in sich selbst zu mergen
if ($branchName -eq $targetBranch) {
    Write-Host "Fehler: Sie können den Branch '$targetBranch' nicht in sich selbst mergen." -ForegroundColor Red
    exit
}

# Prüfen, ob der eingegebene Branch lokal existiert
if (-not (git branch --list $branchName | Select-String -Quiet .)) {
    Write-Host "Fehler: Der lokale Branch '$branchName' wurde nicht gefunden." -ForegroundColor Red
    Write-Host "Stellen Sie sicher, dass der Branch lokal existiert und kein Tippfehler vorliegt." -ForegroundColor Yellow
    exit
}

# 5. Zum Ziel-Branch wechseln
Write-Host "Wechsle zu Branch '$targetBranch'..."
git checkout $targetBranch
if ($LASTEXITCODE -ne 0) {
    Write-Host "Fehler beim Wechseln zum Branch '$targetBranch'." -ForegroundColor Red
    exit
}

# 6. Den ausgewählten Branch mergen
Write-Host "Merge Branch '$branchName' in '$targetBranch'..."
git merge --no-ff $branchName
if ($LASTEXITCODE -ne 0) {
    Write-Host "Fehler beim Mergen. Bitte beheben Sie die Konflikte manuell und schließen Sie den Merge ab." -ForegroundColor Red
    exit
}

# 7. Die Änderungen zum Remote-Repository pushen
Write-Host "Pushe Änderungen zu 'origin/$targetBranch'..."
git push origin $targetBranch
if ($LASTEXITCODE -ne 0) {
    Write-Host "Fehler beim Pushen zu 'origin/$targetBranch'." -ForegroundColor Red
    exit
}

Write-Host "Merge und Push erfolgreich abgeschlossen." -ForegroundColor Green

# 8. Optionales Löschen des alten Branches
$delete = Read-Host "Möchten Sie den Branch '$branchName' lokal löschen? (j/n)"
if ($delete -eq 'j') {
    git branch -d $branchName
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Fehler beim Löschen des Branches '$branchName'. Möglicherweise sind nicht alle Änderungen gemerged (git branch -d schlägt dann fehl)." -ForegroundColor Red
        Write-Host "Versuchen Sie 'git branch -D $branchName', um das Löschen zu erzwingen, falls Sie sicher sind." -ForegroundColor Yellow
    } else {
        Write-Host "Branch '$branchName' wurde lokal gelöscht." -ForegroundColor Green
    }
}

Write-Host "Skript beendet."