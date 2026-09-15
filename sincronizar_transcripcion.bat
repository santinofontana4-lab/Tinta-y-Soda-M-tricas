@echo off
chcp 65001 >nul
echo ========================================================
echo   SINCRONIZANDO TRANSCRIPCION EP 02.09 CON MP4 LOCAL
echo   Sumando +01:58 (+118 segundos) a todas las marcas...
echo ========================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0sincronizar_transcripcion.ps1"

echo.
echo ========================================================
echo   PROCESO TERMINADO: ep 02.09.txt actualizado con exito!
echo   Se guardo una copia de respaldo en:
echo   ep 02.09_ORIGINAL_YOUTUBE.txt
echo ========================================================
echo.
pause
