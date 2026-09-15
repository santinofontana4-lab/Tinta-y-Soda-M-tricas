@echo off
chcp 65001 > nul
title Actualizador de Metricas - @tintaysoda.stream

echo ========================================================
echo   ACTUALIZADOR DE METRICAS META - @tintaysoda.stream
echo ========================================================
echo.
echo Iniciando proceso de actualizacion nativo...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0actualizar_metricas.ps1"

echo.
echo Presiona cualquier tecla para cerrar esta ventana...
pause > nul
