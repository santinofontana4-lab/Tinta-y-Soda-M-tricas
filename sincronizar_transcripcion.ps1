# Script para sincronizar los timestamps de ep 02.09.txt con el archivo MP4 local (+118 segundos / +01:58)
$backupFile = "c:\Users\santi\Documents\antigravity\radiant-hawking\ep 02.09_ORIGINAL_YOUTUBE.txt"
$outputFile = "c:\Users\santi\Documents\antigravity\radiant-hawking\ep 02.09.txt"

if (-not (Test-Path $backupFile)) {
    Write-Error "No se encontro el archivo de respaldo $backupFile"
    exit 1
}

$lines = Get-Content -Path $backupFile -Encoding UTF8
$outputLines = [System.Collections.Generic.List[string]]::new()
$offsetSec = 118 # +01:58 (diferencia entre 03:29 y 05:27)

foreach ($line in $lines) {
    if ([string]::IsNullOrWhiteSpace($line)) {
        $outputLines.Add("")
        continue
    }

    # Detectar el timestamp al inicio de la linea (ej: 0:07, 3:29, 1:00:01)
    if ($line -match "^(?:(\d+):)?(\d+):(\d{2})(?:(?:\d+\s*(?:horas?|minutos?|segundos?))+(?:\s*y\s*\d+\s*segundos?)?)?(.*)$") {
        $hours = if ($matches[1]) { [int]$matches[1] } else { 0 }
        $minutes = [int]$matches[2]
        $seconds = [int]$matches[3]
        $restOfText = $matches[4].Trim()

        $totalSec = ($hours * 3600) + ($minutes * 60) + $seconds
        $newSec = $totalSec + $offsetSec

        $ts = [TimeSpan]::FromSeconds($newSec)
        if ($ts.Hours -gt 0) {
            $formattedTime = "{0}:{1:d2}:{2:d2}" -f [int]$ts.Hours, [int]$ts.Minutes, [int]$ts.Seconds
        } else {
            $formattedTime = "{0:d2}:{1:d2}" -f [int]$ts.Minutes, [int]$ts.Seconds
        }

        # Formato limpio: MM:SS - Texto
        $cleanLine = "$formattedTime - $restOfText"
        $outputLines.Add($cleanLine)
    } else {
        $outputLines.Add($line)
    }
}

Set-Content -Path $outputFile -Value $outputLines -Encoding UTF8
Write-Host "=========================================================="
Write-Host "  EXITO: ep 02.09.txt sincronizado correctamente (+01:58)!"
Write-Host "  Ejemplo linea 28: 05:27 - Buenas tardes. Buenas tardes..."
Write-Host "=========================================================="
