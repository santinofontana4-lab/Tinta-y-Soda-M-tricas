# ========================================================
# subir_a_github.ps1
# Script de sincronizacion con GitHub para @tintaysoda.stream
# ========================================================

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   SUBIR METRICAS A GITHUB & NETLIFY" -ForegroundColor Cyan
Write-Host "   Canal: @tintaysoda.stream" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verificacion instantanea de Git (sin busquedas lentas)
$gitPath = $null

if (Get-Command "git" -ErrorAction SilentlyContinue) {
    $gitPath = "git"
} elseif (Test-Path "$env:ProgramFiles\Git\cmd\git.exe") {
    $gitPath = "$env:ProgramFiles\Git\cmd\git.exe"
} elseif (Test-Path "${env:ProgramFiles(x86)}\Git\cmd\git.exe") {
    $gitPath = "${env:ProgramFiles(x86)}\Git\cmd\git.exe"
} elseif (Test-Path "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe") {
    $gitPath = "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe"
}

if (-not $gitPath) {
    Write-Host "[INFO] Git no está configurado en tu terminal de Windows." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Para no tener que entrar a páginas web ni instalar nada a mano," -ForegroundColor White
    Write-Host "Windows puede autoconfigurarlo en 30 segundos usando 'winget' (nativamente)." -ForegroundColor White
    Write-Host ""
    $autoInstall = Read-Host "¿Querés que Windows lo configure automáticamente ahora? (S/N) [Presiona ENTER para Sí]"
    if (-not $autoInstall -or $autoInstall.Trim().ToLower() -eq "s" -or $autoInstall.Trim().ToLower() -eq "si" -or $autoInstall.Trim().ToLower() -eq "y") {
        Write-Host ""
        Write-Host "Configurando Git automáticamente en segundo plano..." -ForegroundColor Cyan
        try {
            winget install --id Git.Git -e --source winget --accept-source-agreements --accept-package-agreements --silent
            Start-Sleep -Seconds 3
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            $cmdTest = Get-Command "git" -ErrorAction SilentlyContinue
            if ($cmdTest) {
                $gitPath = "git"
            } elseif (Test-Path "$env:ProgramFiles\Git\cmd\git.exe") {
                $gitPath = "$env:ProgramFiles\Git\cmd\git.exe"
            }
        } catch {
            Write-Host "[AVISO] winget no pudo completar la configuración automática." -ForegroundColor Yellow
        }
    }
}

if (-not $gitPath) {
    Write-Host ""
    Write-Host "Tenés dos opciones muy sencillas para que se actualice tu link de Netlify:" -ForegroundColor White
    Write-Host ""
    Write-Host "--------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host "OPCIÓN A (Más rápida, sin instalar nada): SUBIR POR LA WEB" -ForegroundColor Green
    Write-Host "--------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host " 1. Entrá a tu repositorio en https://github.com" -ForegroundColor White
    Write-Host " 2. Hacé clic en el botón 'Add file' -> 'Upload files'" -ForegroundColor White
    Write-Host " 3. Arrastrá los archivos de la carpeta 'metricas':" -ForegroundColor Yellow
    Write-Host "    - metricas/dashboard.html" -ForegroundColor Yellow
    Write-Host "    - metricas/index.html" -ForegroundColor Yellow
    Write-Host "    - metricas/historico_metricas.json" -ForegroundColor Yellow
    Write-Host " 4. Hacé clic en el botón verde 'Commit changes' al final de la página." -ForegroundColor White
    Write-Host " ¡Y listo! Netlify detecta el cambio y actualiza tu página en vivo." -ForegroundColor Green
    Write-Host ""
    Write-Host "--------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host "OPCIÓN B (Descargar instalador oficial):" -ForegroundColor Cyan
    Write-Host "--------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host " Descargá e instalá Git gratis desde: https://git-scm.com/download/win" -ForegroundColor White
    Write-Host " Una vez instalado, este archivo 'subir_a_github.bat' subirá todo solo." -ForegroundColor White
    Write-Host ""
    exit 0
}

Write-Host "[OK] Git detectado: $gitPath" -ForegroundColor Green
Write-Host ""

# 2. Verificar repositorio local y remote
if (-not (Test-Path (Join-Path $ScriptDir ".git"))) {
    Write-Host "[PASO 1] Inicializando repositorio Git local..." -ForegroundColor Yellow
    & $gitPath init
    & $gitPath branch -M main
}

$existingRemotes = & $gitPath remote
if ($existingRemotes -notcontains "origin") {
    $repoUrl = Read-Host "Pegá acá el enlace de tu repositorio de GitHub (ej: https://github.com/tu-usuario/nombre-repo.git)"
    if ($repoUrl) {
        & $gitPath remote add origin $repoUrl.Trim()
    } else {
        Write-Host "[ERROR] No ingresaste la URL del repositorio." -ForegroundColor Red
        exit 1
    }
}

# 3. Guardar cambios y subir a GitHub
Write-Host "[PASO 2] Seleccionando archivos actualizados..." -ForegroundColor Yellow

# Asegurar que se agreguen las métricas y los archivos del sitio
& $gitPath add .gitignore netlify.toml metricas/ scripts/ .github/ actualizar_metricas.py

# Si hay otros archivos de texto/documentación modificados, agregarlos
& $gitPath add *.md *.bat *.ps1 2>$null

Write-Host "[PASO 3] Creando commit con la actualización..." -ForegroundColor Yellow
$fecha = (Get-Date).ToString("dd/MM/yyyy HH:mm")
& $gitPath commit -m "Actualizacion dashboard metricas ($fecha) - @tintaysoda.stream"

Write-Host ""
Write-Host "[PASO 4] Subiendo cambios a GitHub..." -ForegroundColor Yellow
$currentBranch = (& $gitPath branch --show-current).Trim()
if (-not $currentBranch) { $currentBranch = "main" }
& $gitPath push origin $currentBranch

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Green
    Write-Host "  ¡ÉXITO TOTAL! Los archivos se subieron a GitHub." -ForegroundColor Green
    Write-Host "  Netlify actualizará tu enlace en vivo en unos segundos." -ForegroundColor Green
    Write-Host "========================================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[AVISO] Si es la primera vez que subís, puede que necesites" -ForegroundColor Yellow
    Write-Host "configurar tus credenciales de GitHub o verificar la rama." -ForegroundColor Yellow
    Write-Host "También podés subir los archivos directamente arrastrándolos en github.com" -ForegroundColor White
}
Write-Host ""
