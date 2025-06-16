@echo off
REM Löscht alle lokalen und Remote-Branches ausser 'main' (auch bei umbenanntem Remote)

REM Hole aktuellen Remote-Namen (nehmen den ersten)
FOR /F "delims=" %%r IN ('git remote') DO (
    SET "REMOTE=%%r"
    GOTO REMOTE_FOUND
)
:REMOTE_FOUND

REM Prüfen, ob Remote korrekt ist
IF "%REMOTE%"=="" (
    echo Kein Remote-Repository gefunden.
    pause
    exit /b
)

REM Remote aktualisieren (verwaiste Branches entfernen)
git remote prune %REMOTE%

REM Wechsel auf main
git checkout main

REM Lokale Branches ausser main löschen
FOR /F "tokens=*" %%b IN ('git branch ^| findstr /V "main"') DO (
    git branch -D %%b
)

REM Remote Branches ausser main löschen
FOR /F "tokens=*" %%b IN ('git branch -r ^| findstr /V "%REMOTE%/main" ^| findstr /V "HEAD"') DO (
    SETLOCAL ENABLEDELAYEDEXPANSION
    SET "rb=%%b"
    SET "branch=!rb:%REMOTE%/=!"
    echo Lösche Remote-Branch: !branch!
    git push %REMOTE% --delete !branch! >nul 2>&1
    ENDLOCAL
)

echo Alle lokalen und entfernten Branches ausser 'main' wurden (soweit möglich) gelöscht.
pause
