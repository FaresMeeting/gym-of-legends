@echo off
title Gym Of Legends - lanceur
cd /d "%~dp0"

REM --- Choix de l'interpreteur Python -------------------------------------
REM 1) Chemin explicite (celui ou pygame est installe)
REM 2) Repli sur le PATH, puis sur le lanceur py
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" (
    where python >nul 2>&1 && set "PY=python"
)
if not exist "%PY%" if not "%PY%"=="python" (
    where py >nul 2>&1 && set "PY=py"
)

if not exist "gym_of_legends.py" (
    echo [ERREUR] gym_of_legends.py est introuvable dans ce dossier :
    echo    %CD%
    echo Place ce .bat a cote du jeu.
    echo.
    pause
    exit /b 1
)

echo Lancement de Gym Of Legends...
echo (cette fenetre peut rester ouverte en arriere-plan, c'est normal)
echo.

"%PY%" gym_of_legends.py

if errorlevel 1 (
    echo.
    echo ============================================================
    echo  Le jeu s'est arrete sur une erreur. Le detail est ci-dessus.
    echo  Si pygame manque :  pip install pygame
    echo ============================================================
    echo.
    pause
)

exit /b 0
