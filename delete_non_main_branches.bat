@echo off
REM Löscht alle lokalen und Remote-Branches ausser 'main', auch wenn Remote nicht 'origin' heisst

REM Hole aktuellen Remote-Namen
FOR /F "tokens=*" %%r IN ('git remote') DO (
    SET "REMOTE=%%r"
)

REM Sicherstellen, dass wir auf main sind
git checkout main

REM Lokale Branches ausser main löschen
FOR /F "tokens=*" %%b IN ('git branch ^| findstr /V "main"') DO (
    git branch -D %%b
)

REM Remote Branches ausser main löschen
FOR /F "tokens=*" %%b IN ('git branch -r ^| findstr /V "!REMOTE!/main" ^| findstr /V "HEAD"') DO (
    SETLOCAL ENABLEDELAYEDEXPANSION
    SET "branch=%%b"
    REM Entferne das Remote-Präfix
    SET "branch=!branch:%REMOTE%/=!"
    git push !REMOTE! --delete !branch!
    ENDLOCAL
)

echo Alle Branches ausser 'main' wurden gelöscht (lokal und remote).
pause
