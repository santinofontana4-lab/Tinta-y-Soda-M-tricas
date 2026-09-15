$ffmpeg = "C:\Users\santi\AppData\Local\CapCut\Apps\9.3.0.3970\ffmpeg.exe"
$video = "c:\Users\santi\Documents\antigravity\radiant-hawking\Peronismo_y_jueces.mp4"
$outFile = "c:\Users\santi\Documents\antigravity\radiant-hawking\silencios.txt"

& $ffmpeg -i $video -af "silencedetect=noise=-30dB:d=0.35" -f null - 2>&1 | Select-String "silence_" | Out-File -FilePath $outFile -Encoding utf8
Write-Host "Analisis de silencios completado."
