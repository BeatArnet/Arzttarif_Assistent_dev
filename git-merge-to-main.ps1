# Stellt sicher, dass die Ausgabe korrekt (mit Umlauten etc.) dargestellt wird.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# --- Konfiguration ---
# Den Ziel-Branch hier definieren, um das Skript einfacher anzupassen (z.B. für 'master' oder 'develop')
$targetBranch = 'main'
# --------------------

# Git-Änderungen von allen Remotes abrufen
git fetch --all

# Lokale Branches anzeigen, damit der Benutzer eine Auswahl hat
Write-Host "Verfuegbare lokale Branches:" -ForegroundColor Cyan
git branch

# Benutzer nach dem zu mergenden Branch fragen
$userInput = Read-Host "Welchen Branch moechten Sie in '$targetBranch' mergen?"

# Eingabe bereinigen: Sternchen (*) und Leerzeichen am Anfang/Ende entfernen
$branchName = $userInput.Replace('*', '').Trim()

# Prüfen, ob eine Eingabe gemacht wurde
if ([string]::IsNullOrWhiteSpace($branchName)) {
    Write-Host "Fehler: Es wurde kein Branch-Name eingegeben." -ForegroundColor Red
    exit
}

# Prüfen, ob der Benutzer versucht, den Branch in sich selbst zu mergen
if ($branchName -eq $targetBranch) {
    Write-Host "Fehler: Sie koennen den Branch '$targetBranch' nicht in sich selbst mergen." -ForegroundColor Red
    exit
}

# Prüfen, ob der eingegebene Branch lokal existiert
# `git branch --list` filtert die Branches und gibt den Namen aus, wenn er existiert.
if (-not (git branch --list $branchName | Select-String -Quiet .)) {
    Write-Host "Fehler: Der lokale Branch '$branchName' wurde nicht gefunden." -ForegroundColor Red
    Write-Host "Stellen Sie sicher, dass der Branch lokal existiert und kein Tippfehler vorliegt." -ForegroundColor Yellow
    exit
}

# Zum Ziel-Branch wechseln
Write-Host "Wechsle zu Branch '$targetBranch'..."
git checkout $targetBranch
if ($LASTEXITCODE -ne 0) {
    Write-Host "Fehler beim Wechseln zum Branch '$targetBranch'." -ForegroundColor Red
    exit
}

# Den ausgewählten Branch mergen
Write-Host "Merge Branch '$branchName' in '$targetBranch'..."
git merge $branchName
if ($LASTEXITCODE -ne 0) {
    Write-Host "Fehler beim Mergen. Bitte beheben Sie die Konflikte manuell und schliessen Sie den Merge ab." -ForegroundColor Red
    exit
}

# Die Änderungen zum Remote-Repository pushen
Write-Host "Pushe Änderungen zu 'origin/$targetBranch'..."
git push origin $targetBranch
if ($LASTEXITCODE -ne 0) {
    Write-Host "Fehler beim Pushen zu 'origin/$targetBranch'." -ForegroundColor Red
    exit
}

Write-Host "Merge und Push erfolgreich abgeschlossen." -ForegroundColor Green

# Optionales Löschen des alten Branches
$delete = Read-Host "Moechten Sie den Branch '$branchName' lokal loeschen? (j/n)"
if ($delete -eq 'j') {
    git branch -d $branchName
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Fehler beim Loeschen des Branches '$branchName'. Moeglicherweise sind nicht alle Aenderungen gemerged." -ForegroundColor Red
    } else {
        Write-Host "Branch '$branchName' wurde lokal geloescht." -ForegroundColor Green
    }
}

Write-Host "Skript beendet."