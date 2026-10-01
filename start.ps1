# Два фоновых процесса: API с интерфейсом и обработчики событий.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '.venv/Scripts/python.exe'))
$statePath = Join-Path $PSScriptRoot '.runtime/processes.json'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Сначала выполните .\setup.ps1' }
if (-not (Test-Path -LiteralPath 'polka/static/index.html')) { throw 'Сначала соберите интерфейс: npm run build --prefix frontend' }
if (Test-Path -LiteralPath $statePath) {
    $previous = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    foreach ($item in $previous) {
        $current = Get-CimInstance Win32_Process -Filter "ProcessId = $($item.pid)" -ErrorAction SilentlyContinue
        if ($current -and $current.ExecutablePath -eq $taskPython -and $current.CommandLine -like "*-m polka.cli $($item.command)*") {
            throw 'Приложение уже запущено. Для перезапуска сначала выполните .\stop.ps1'
        }
    }
}
$env:PYTHONIOENCODING = 'utf-8'
$settingsJson = & $taskPython -c 'import json; from polka.config import settings; s=settings(); print(json.dumps({"host": s.host, "port": s.port}))'
if ($LASTEXITCODE -ne 0) { throw 'Не удалось прочитать .env' }
$configuration = $settingsJson | ConvertFrom-Json
$urlHost = if ($configuration.host -eq '0.0.0.0') { '127.0.0.1' } else { $configuration.host }
$url = "http://${urlHost}:$($configuration.port)"
$listener = Get-NetTCPConnection -State Listen -LocalPort $configuration.port -ErrorAction SilentlyContinue
if ($listener) { throw "Порт $($configuration.port) уже занят" }
New-Item -ItemType Directory -Path (Split-Path $statePath) -Force | Out-Null
$previousBackground = $env:POLKA_BACKGROUND
$env:POLKA_BACKGROUND = '1'
Get-ChildItem -LiteralPath (Split-Path $statePath) -Filter '*.log' | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item
$launched = @()
try {
    foreach ($command in @('serve', 'worker')) {
        $process = Start-Process -FilePath $taskPython -ArgumentList @('-m', 'polka.cli', $command) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $PSScriptRoot ".runtime/$command.stdout.log") -RedirectStandardError (Join-Path $PSScriptRoot ".runtime/$command.stderr.log")
        $launched += @{ pid = $process.Id; command = $command; started = $process.StartTime.ToUniversalTime().ToString('o') }
        $launched | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
    }
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        foreach ($item in $launched) {
            if (-not (Get-Process -Id $item.pid -ErrorAction SilentlyContinue)) { throw "Процесс $($item.command) завершился. Проверьте logs/$($item.command -replace 'serve','api').log" }
        }
        try {
            $healthJson = & $taskPython -c 'import httpx, sys; print(httpx.get(sys.argv[1], timeout=2, trust_env=False).text)' "$url/health/ready" 2>$null
            if ($LASTEXITCODE -ne 0) { throw 'Сервер ещё запускается' }
            $health = $healthJson | ConvertFrom-Json
            if ($health.status -eq 'ok') { $ready = $true; break }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ready) { throw 'API не готово. Проверьте доступность PostgreSQL и logs/api.log' }
    Write-Host "Магазин: $url"
    Write-Host 'Остановка: .\stop.ps1'
} catch {
    & (Join-Path $PSScriptRoot 'stop.ps1')
    throw
} finally {
    $env:POLKA_BACKGROUND = $previousBackground
}
