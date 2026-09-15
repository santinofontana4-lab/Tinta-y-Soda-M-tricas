<#
.SYNOPSIS
  actualizar_metricas.ps1
  Script de automatización nativo en PowerShell para @tintaysoda.stream
  No requiere Python. Funciona en cualquier Windows 10 u 11.
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$MetricasDir = Join-Path $ScriptDir "metricas"
$JsonOutput = Join-Path $MetricasDir "historico_metricas.json"
$HtmlDashboard = Join-Path $MetricasDir "dashboard.html"
$HtmlIndex = Join-Path $MetricasDir "index.html"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  ACTUALIZADOR DE MÉTRICAS NATIVO (PowerShell)" -ForegroundColor Cyan
Write-Host "  Canal: @tintaysoda.stream" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $MetricasDir)) {
    Write-Host "[ERROR] No existe la carpeta metricas/ en: $MetricasDir" -ForegroundColor Red
    exit 1
}

$csvFiles = Get-ChildItem -Path $MetricasDir -Filter "*.csv"
if ($csvFiles.Count -eq 0) {
    Write-Host "[ERROR] No se encontraron archivos .csv en metricas/" -ForegroundColor Red
    exit 1
}

Write-Host "[INFO] Archivos encontrados:" -ForegroundColor Yellow
$csvFiles | ForEach-Object { Write-Host " - $($_.Name)" }
Write-Host ""

function Normalize-String($str) {
    if (-not $str) { return "" }
    $s = $str.ToString().ToLower().Trim()
    $s = $s -replace "á","a" -replace "é","e" -replace "í","i" -replace "ó","o" -replace "ú","u"
    $s = $s -replace "[^a-z0-9]", "_"
    $s = $s -replace "_+", "_"
    return $s.Trim("_")
}

function Classify-Topic($title, $fullText) {
    $txt = ($title + " " + $fullText).ToLower()
    if ($txt -match "gamer|drones|thiel|palantir|gotham|armas|guerra|ucrania|mendoza|refugio|paypal") {
        return "Tecnodistopía & Geopolítica"
    } elseif ($txt -match "indec|milei|natalidad|hijo|crianza|tierras|la plata|uca|sifilis|salud") {
        return "Datos Duros & Desmitificación"
    } elseif ($txt -match "ansiedad|hora|plata virtual|billeteras|apuestas|esperar|concentrarte|tiktok") {
        return "Hábitos & Ansiedad Digital"
    } else {
        return "Rosca Política & Sociedad"
    }
}

$postsById = @{}

foreach ($file in $csvFiles) {
    try {
        $rows = Import-Csv -Path $file.FullName -Encoding UTF8
    } catch {
        $rows = Import-Csv -Path $file.FullName -Encoding Default
    }

    foreach ($row in $rows) {
        $rowProps = $row.PSObject.Properties

        function Get-ColVal($patterns, $default = "") {
            foreach ($p in $patterns) {
                $normP = Normalize-String $p
                foreach ($prop in $rowProps) {
                    $normCol = Normalize-String $prop.Name
                    if ($normCol -eq $normP -or $normCol -like "*$normP*") {
                        if ($prop.Value) { return $prop.Value }
                    }
                }
            }
            return $default
        }

        $id = (Get-ColVal @("identificador_de_la_publicacion", "post_id", "id")).Trim()
        if (-not $id -or $id -eq "0") { continue }

        $rawDesc = Get-ColVal @("descripcion", "description", "title", "titulo")
        $title = ""
        $lines = $rawDesc -split "`r?`n"
        foreach ($l in $lines) {
            $trimmed = $l.Trim()
            if ($trimmed -and -not $trimmed.StartsWith("#")) {
                $title = $trimmed
                break
            }
        }
        if (-not $title) { $title = "Publicación #$($id.Substring([Math]::Max(0, $id.Length - 6)))" }

        $dateRaw = Get-ColVal @("hora_de_publicacion", "publish_time", "fecha")
        $dtArg = $null
        $dateStr = $dateRaw
        $dateSort = "1970-01-01"

        if ($dateRaw) {
            $parsed = $false
            foreach ($fmt in @("M/d/yyyy H:m", "MM/dd/yyyy HH:mm", "yyyy-MM-dd HH:mm:ss", "dd/MM/yyyy HH:mm")) {
                try {
                    $dt = [datetime]::ParseExact($dateRaw, $fmt, [System.Globalization.CultureInfo]::InvariantCulture)
                    $dtArg = $dt.AddHours(4) # PDT a UTC-3
                    $dateStr = $dtArg.ToString("dd/MM/yyyy HH:mm") + " hs"
                    $dateSort = $dtArg.ToString("yyyy-MM-dd HH:mm")
                    $parsed = $true
                    break
                } catch {}
            }
        }

        function To-Int($val) {
            if (-not $val) { return 0 }
            $clean = $val.ToString() -replace "[^\d]", ""
            if ($clean) { return [int64]$clean }
            return 0
        }

        $views = To-Int (Get-ColVal @("visualizaciones", "views", "plays"))
        $reach = To-Int (Get-ColVal @("alcance", "reach"))
        $likes = To-Int (Get-ColVal @("me_gusta", "likes"))
        $shares = To-Int (Get-ColVal @("veces_que_se_compartio", "shares"))
        $saves = To-Int (Get-ColVal @("veces_que_se_guardo", "saves"))
        $comments = To-Int (Get-ColVal @("comentarios", "comments"))
        $follows = To-Int (Get-ColVal @("seguimientos", "follows"))
        $durSec = To-Int (Get-ColVal @("duracion_segundos", "duracion"))
        $durStr = if ($durSec -gt 0) { "$durSec seg" } else { "-" }

        $permalink = Get-ColVal @("enlace_permanente", "permalink")
        $postType = Get-ColVal @("tipo_de_publicacion", "post_type")
        $cleanType = if ($postType -match "reel|video") { "Reel" } else { "Carrusel" }

        # Asignación de mes y semana
        $monthLabel = "Desconocido"
        $weekLabel = "Semana Desconocida"
        if ($dtArg) {
            $mNames = @{ 1="Enero"; 2="Febrero"; 3="Marzo"; 4="Abril"; 5="Mayo"; 6="Junio"; 7="Julio"; 8="Agosto"; 9="Septiembre"; 10="Octubre"; 11="Noviembre"; 12="Diciembre" }
            $mShort = @{ 1="Ene"; 2="Feb"; 3="Mar"; 4="Abr"; 5="May"; 6="Jun"; 7="Jul"; 8="Ago"; 9="Sep"; 10="Oct"; 11="Nov"; 12="Dic" }
            $mName = $mNames[$dtArg.Month]
            $monthLabel = "$mName 2026"

            # Normalizar a 2026 para cálculo Lunes a Domingo
            $dtNorm = Get-Date -Year 2026 -Month $dtArg.Month -Day $dtArg.Day -Hour $dtArg.Hour -Minute $dtArg.Minute -Second $dtArg.Second
            $dayOfWeek = [int]$dtNorm.DayOfWeek # 0=Sunday, 1=Monday...
            $daysSinceMon = if ($dayOfWeek -eq 0) { 6 } else { $dayOfWeek - 1 }
            $monday = $dtNorm.AddDays(-$daysSinceMon)
            $sunday = $monday.AddDays(6)

            $baseMonday = [datetime]"2026-08-10"
            $diffDays = ($monday.Date - $baseMonday.Date).TotalDays
            $weekNum = [int][Math]::Floor($diffDays / 7) + 1

            $mMon = $mShort[$monday.Month]
            $mSun = $mShort[$sunday.Month]
            $rangeStr = if ($mMon -eq $mSun) { "$($monday.ToString('dd'))-$($sunday.ToString('dd')) $mMon" } else { "$($monday.ToString('dd')) $mMon - $($sunday.ToString('dd')) $mSun" }

            if ($weekNum -ge 1) {
                $weekLabel = "Semana $weekNum ($rangeStr)"
            } else {
                $weekLabel = "Semana ($rangeStr)"
            }
        }

        $interactions = $likes + $shares + $saves + $comments
        $saveRate = if ($views -gt 0) { [Math]::Round(($saves / $views) * 100, 2) } else { 0 }
        $shareRate = if ($views -gt 0) { [Math]::Round(($shares / $views) * 100, 2) } else { 0 }
        $engRate = if ($views -gt 0) { [Math]::Round(($interactions / $views) * 100, 2) } else { 0 }

        $topic = Classify-Topic $title $rawDesc

        $postObj = [ordered]@{
            post_id = $id
            title = $title
            full_text = $rawDesc
            date = $dateStr
            date_dt = $dateSort
            month = $monthLabel
            week = $weekLabel
            topic = $topic
            type = $cleanType
            permalink = $permalink
            duration_sec = $durSec
            duration_str = $durStr
            views = $views
            reach = $reach
            interactions = $interactions
            likes = $likes
            comments = $comments
            shares = $shares
            saves = $saves
            follows = $follows
            save_rate_pct = $saveRate
            share_rate_pct = $shareRate
            engagement_rate_pct = $engRate
        }

        if ($postsById.ContainsKey($id)) {
            if ($views -ge $postsById[$id].views) {
                $postsById[$id] = $postObj
            }
        } else {
            $postsById[$id] = $postObj
        }
    }
}

$now = (Get-Date).AddYears(2026 - (Get-Date).Year)
$dayOfWeek = [int]$now.DayOfWeek
$daysSinceSunday = if ($dayOfWeek -ne 0) { $dayOfWeek } else { 7 }
$lastSunday = $now.AddDays(-$daysSinceSunday)
$cutoffDateStr = "$($lastSunday.ToString('yyyy-MM-dd')) 23:59"

$rawPosts = @($postsById.Values)
$allPosts = @($rawPosts | Where-Object { -not $_.date_dt -or $_.date_dt -eq "1970-01-01" -or $_.date_dt -le $cutoffDateStr } | Sort-Object -Property @{Expression={$_.views}; Descending=$true})
for ($i = 0; $i -lt $allPosts.Count; $i++) {
    $allPosts[$i]["rank"] = $i + 1
}

# Meses ordenados cronológicamente
$monthsMap = @{ "enero"=1; "febrero"=2; "marzo"=3; "abril"=4; "mayo"=5; "junio"=6; "julio"=7; "agosto"=8; "septiembre"=9; "octubre"=10; "noviembre"=11; "diciembre"=12 }
$detectedMonths = @($allPosts | ForEach-Object { $_.month } | Select-Object -Unique | Where-Object { $_ -ne "Desconocido" })
$sortedMonths = $detectedMonths | Sort-Object {
    $parts = $_ -split "\s+"
    $mNum = if ($monthsMap.ContainsKey($parts[0].ToLower())) { $monthsMap[$parts[0].ToLower()] } else { 0 }
    $yNum = if ($parts.Count -gt 1) { [int]$parts[1] } else { 2026 }
    return ($yNum * 100) + $mNum
}

$monthlyStats = [ordered]@{}
for ($idx = 0; $idx -lt $sortedMonths.Count; $idx++) {
    $m = $sortedMonths[$idx]
    $mPosts = @($allPosts | Where-Object { $_.month -eq $m })
    $mCount = $mPosts.Count
    $mViews = ($mPosts | Measure-Object -Property views -Sum).Sum
    $mReach = ($mPosts | Measure-Object -Property reach -Sum).Sum
    $mInter = ($mPosts | Measure-Object -Property interactions -Sum).Sum
    $mLikes = ($mPosts | Measure-Object -Property likes -Sum).Sum
    $mShares = ($mPosts | Measure-Object -Property shares -Sum).Sum
    $mSaves = ($mPosts | Measure-Object -Property saves -Sum).Sum
    $mComms = ($mPosts | Measure-Object -Property comments -Sum).Sum
    $mFollows = ($mPosts | Measure-Object -Property follows -Sum).Sum

    $avgViews = if ($mCount -gt 0) { [Math]::Round($mViews / $mCount) } else { 0 }
    $avgShares = if ($mCount -gt 0) { [Math]::Round($mShares / $mCount, 1) } else { 0 }
    $avgSaves = if ($mCount -gt 0) { [Math]::Round($mSaves / $mCount, 1) } else { 0 }
    $avgComms = if ($mCount -gt 0) { [Math]::Round($mComms / $mCount, 1) } else { 0 }

    $topP = $mPosts | Sort-Object -Property views -Descending | Select-Object -First 1

    $mom = $null
    if ($idx -gt 0) {
        $prevM = $sortedMonths[$idx - 1]
        $prevStat = $monthlyStats[$prevM]
        $prevAvgViews = $prevStat.avg_views_per_post
        $prevAvgShares = $prevStat.avg_shares_per_post
        $prevAvgSaves = $prevStat.avg_saves_per_post
        $prevAvgComms = $prevStat.avg_comments_per_post

        function Calc-Var($curr, $prev) {
            if ($prev -gt 0) {
                $v = [Math]::Round((($curr - $prev) / $prev) * 100, 1)
                if ($v -gt 0) { return "+$v%" } else { return "$v%" }
            }
            return "+100%"
        }

        $mom = [ordered]@{
            mes_referencia = $prevM
            views_promedio = Calc-Var $avgViews $prevAvgViews
            shares_promedio = Calc-Var $avgShares $prevAvgShares
            saves_promedio = Calc-Var $avgSaves $prevAvgSaves
            comments_promedio = Calc-Var $avgComms $prevAvgComms
        }
    }

    $monthlyStats[$m] = [ordered]@{
        month = $m
        posts_count = $mCount
        total_views = $mViews
        avg_views_per_post = $avgViews
        total_reach = $mReach
        total_interactions = $mInter
        total_likes = $mLikes
        total_shares = $mShares
        avg_shares_per_post = $avgShares
        total_saves = $mSaves
        avg_saves_per_post = $avgSaves
        total_comments = $mComms
        avg_comments_per_post = $avgComms
        total_follows = $mFollows
        crecimiento_vs_mes_anterior = $mom
        top_title = if ($topP) { $topP.title } else { "-" }
        top_views = if ($topP) { $topP.views } else { 0 }
        top_shares = if ($topP) { $topP.shares } else { 0 }
        top_saves = if ($topP) { $topP.saves } else { 0 }
    }
}

# Semanas
$detectedWeeks = @($allPosts | ForEach-Object { $_.week } | Select-Object -Unique | Where-Object { $_ -ne "Semana Desconocida" })
$sortedWeeks = $detectedWeeks | Sort-Object {
    $wPosts = @($allPosts | Where-Object { $_.week -eq $_ })
    ($wPosts | Sort-Object -Property date_dt | Select-Object -First 1).date_dt
}

$weeksStats = [ordered]@{}
foreach ($w in $sortedWeeks) {
    $wPosts = @($allPosts | Where-Object { $_.week -eq $w })
    $wCount = $wPosts.Count
    $wViews = ($wPosts | Measure-Object -Property views -Sum).Sum
    $wReach = ($wPosts | Measure-Object -Property reach -Sum).Sum
    $wInter = ($wPosts | Measure-Object -Property interactions -Sum).Sum
    $wShares = ($wPosts | Measure-Object -Property shares -Sum).Sum
    $wLikes = ($wPosts | Measure-Object -Property likes -Sum).Sum
    $wSaves = ($wPosts | Measure-Object -Property saves -Sum).Sum
    $wComms = ($wPosts | Measure-Object -Property comments -Sum).Sum
    $wFollows = ($wPosts | Measure-Object -Property follows -Sum).Sum
    $topW = $wPosts | Sort-Object -Property views -Descending | Select-Object -First 1

    $weeksStats[$w] = [ordered]@{
        week = $w
        posts_count = $wCount
        total_views = $wViews
        avg_views_per_post = if ($wCount -gt 0) { [Math]::Round($wViews / $wCount) } else { 0 }
        total_reach = $wReach
        total_interactions = $wInter
        total_likes = $wLikes
        avg_likes_per_post = if ($wCount -gt 0) { [Math]::Round($wLikes / $wCount, 1) } else { 0 }
        total_shares = $wShares
        avg_shares_per_post = if ($wCount -gt 0) { [Math]::Round($wShares / $wCount, 1) } else { 0 }
        total_saves = $wSaves
        avg_saves_per_post = if ($wCount -gt 0) { [Math]::Round($wSaves / $wCount, 1) } else { 0 }
        total_comments = $wComms
        avg_comments_per_post = if ($wCount -gt 0) { [Math]::Round($wComms / $wCount, 1) } else { 0 }
        total_follows = $wFollows
        top_video = if ($topW) { $topW.title } else { "-" }
        top_views = if ($topW) { $topW.views } else { 0 }
    }
}

# Pilares Temáticos
$topicsList = @(
    "Tecnodistopía & Geopolítica",
    "Datos Duros & Desmitificación",
    "Hábitos & Ansiedad Digital",
    "Rosca Política & Sociedad"
)
$topicStats = [ordered]@{}
foreach ($t in $topicsList) {
    $tPosts = @($allPosts | Where-Object { $_.topic -eq $t })
    $tCount = $tPosts.Count
    $tViews = ($tPosts | Measure-Object -Property views -Sum).Sum
    $tShares = ($tPosts | Measure-Object -Property shares -Sum).Sum
    $topicStats[$t] = [ordered]@{
        topic = $t
        count = $tCount
        total_views = $tViews
        avg_views = if ($tCount -gt 0) { [Math]::Round($tViews / $tCount) } else { 0 }
        total_shares = $tShares
    }
}

$totalViews = ($allPosts | Measure-Object -Property views -Sum).Sum
$totalInter = ($allPosts | Measure-Object -Property interactions -Sum).Sum
$totalLikes = ($allPosts | Measure-Object -Property likes -Sum).Sum
$totalShares = ($allPosts | Measure-Object -Property shares -Sum).Sum
$totalSaves = ($allPosts | Measure-Object -Property saves -Sum).Sum
$totalComms = ($allPosts | Measure-Object -Property comments -Sum).Sum
$totalReach = ($allPosts | Measure-Object -Property reach -Sum).Sum
$totalFollows = ($allPosts | Measure-Object -Property follows -Sum).Sum

$summary = [ordered]@{
    metadata = [ordered]@{
        account = "@tintaysoda.stream"
        generated_at = (Get-Date).ToString("dd/MM/yyyy HH:mm:ss")
        total_posts = $allPosts.Count
        fuente = "Meta Business Suite (PowerShell Nativo)"
    }
    kpis = [ordered]@{
        total_views = $totalViews
        total_reach = $totalReach
        total_follows = $totalFollows
        total_likes = $totalLikes
        total_shares = $totalShares
        total_saves = $totalSaves
        total_comments = $totalComms
        total_interactions = $totalInter
    }
    monthly_stats = $monthlyStats
    weeks_stats = $weeksStats
    topic_stats = $topicStats
    posts = $allPosts
}

# Guardar JSON
$jsonStr = $summary | ConvertTo-Json -Depth 6
[System.IO.File]::WriteAllText($JsonOutput, $jsonStr, [System.Text.Encoding]::UTF8)
Write-Host "[OK] JSON guardado en: $JsonOutput" -ForegroundColor Green

# Inyectar en dashboard.html e index.html
foreach ($targetHtml in @($HtmlDashboard, $HtmlIndex)) {
    if (Test-Path $targetHtml) {
        $htmlCode = [System.IO.File]::ReadAllText($targetHtml, [System.Text.Encoding]::UTF8)
        $pattern = "(?s)(const METRICS_SUMMARY\s*=\s*)\{.*?\n\s*\};"
        if ($htmlCode -match $pattern) {
            $newCode = [regex]::Replace($htmlCode, $pattern, "`${1}$jsonStr;")
            [System.IO.File]::WriteAllText($targetHtml, $newCode, [System.Text.Encoding]::UTF8)
            Write-Host "[OK] Actualizado con éxito: $(Split-Path -Leaf $targetHtml)" -ForegroundColor Green
        }
    }
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  PROCESO FINALIZADO EXITOSAMENTE" -ForegroundColor Green
Write-Host "  Posts procesados: $($allPosts.Count)" -ForegroundColor White
Write-Host "  Visualizaciones totales: $($totalViews.ToString('N0'))" -ForegroundColor White
Write-Host "  Nuevos seguidores totales: $totalFollows" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Cyan
