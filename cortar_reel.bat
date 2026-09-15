@echo off
chcp 65001 >nul
echo ========================================================
echo   EDICION QUIRURGICA: PERONISMO Y JUECES (REEL)
echo ========================================================
echo.

set FFMPEG="C:\Users\santi\AppData\Local\CapCut\Apps\9.3.0.3970\ffmpeg.exe"
set INPUT="Peronismo_y_jueces.mp4"

if not exist %INPUT% (
    echo [ERROR] No se encuentra el archivo %INPUT% en esta carpeta.
    pause
    exit /b
)

echo [1/4] Cortando Segmento 1: Senado y CFK (00:01.20 a 00:51.50)...
%FFMPEG% -y -ss 00:00:01.20 -to 00:00:51.50 -i %INPUT% -c copy seg1.mp4 >nul 2>&1

echo [2/4] Cortando Segmento 2: Ascenso judicial (01:28.00 a 01:44.50)...
%FFMPEG% -y -ss 00:01:28.00 -to 00:01:44.50 -i %INPUT% -c copy seg2.mp4 >nul 2>&1

echo [3/4] Cortando Segmento 3: Remate y pregunta (01:53.00 a 02:18.00)...
%FFMPEG% -y -ss 00:01:53.00 -to 00:02:18.00 -i %INPUT% -c copy seg3.mp4 >nul 2>&1

echo [4/4] Uniendo los 3 cortes en continuidad fluida...
(echo file 'seg1.mp4' & echo file 'seg2.mp4' & echo file 'seg3.mp4') > concat_list.txt
%FFMPEG% -y -f concat -safe 0 -i concat_list.txt -c copy "Peronismo_y_jueces_EDITADO.mp4" >nul 2>&1

del seg1.mp4 seg2.mp4 seg3.mp4 concat_list.txt >nul 2>&1

echo.
echo ========================================================
echo   EXITO: Video generado como 'Peronismo_y_jueces_EDITADO.mp4'
echo   Listo para importar a CapCut / Premiere!
echo ========================================================
echo.
pause


