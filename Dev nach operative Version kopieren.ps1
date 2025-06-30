Neu
+46
-0

<#
    Deploy-V1.1.ps1
    Kopiert die aktuelle Entwicklerversion in das lokale Produktionsrepo
    und entfernt zuvor alle alten Dateien. Wird das Entwicklungsverzeichnis
    nicht gefunden, bricht das Skript ab.
#>

param(
    [string]$DevPath  = $PSScriptRoot,
    [string]$ProdPath = "C:\Repos\Arzttarif-Assistent",
    [string]$Branch   = "main"
)

$RepoUrl = "https://github.com/BeatArnet/Arzttarif-Assistent"

if (-not (Test-Path $DevPath)) {
    Write-Error "Entwicklungsverzeichnis '$DevPath' wurde nicht gefunden."
    exit 1
}

if (-not (Test-Path $ProdPath)) {
    git clone $RepoUrl $ProdPath
}

Set-Location $ProdPath
git fetch origin
git checkout $Branch
git pull origin $Branch

Get-ChildItem -Force | Where-Object { $_.Name -ne '.git' } | Remove-Item -Recurse -Force
git clean -xdf

try {
    Copy-Item -Path (Join-Path $DevPath '*') -Destination $ProdPath -Recurse -Force -Exclude '.git' -ErrorAction Stop
} catch {
    Write-Error "Kopieren fehlgeschlagen: $_"
    exit 1
}

git add .
git commit -m "Release Version V1.1"
git push origin $Branch
git tag v1.1
git push origin v1.1

Write-Host "Deployment von Version V1.1 abgeschlossen."