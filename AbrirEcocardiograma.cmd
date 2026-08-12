@echo off
rem Lanzador de Ecocardiograma Local.
rem Abre la aplicacion compilada en dist\EcocardiogramaLocal.
rem Si no existe, muestra como compilarla o usar el instalador.
setlocal
set "APP=%~dp0dist\EcocardiogramaLocal\EcocardiogramaLocal.exe"
if exist "%APP%" (
    start "" "%APP%"
    exit /b 0
)
echo No se encontro la aplicacion compilada en: %APP%
echo.
echo Opciones:
echo   1) Instalar: dist\installer\EcocardiogramaLocal-Setup-*.exe
echo   2) Compilar: powershell -ExecutionPolicy Bypass -File scripts\build.ps1
pause
