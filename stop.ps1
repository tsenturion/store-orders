# Останавливаем только процессы, созданные скриптом этого проекта.
$ErrorActionPreference = 'Stop'
$statePath = Join-Path $PSScriptRoot '.runtime/processes.json'
$taskPython = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '.venv/Scripts/python.exe'))
if (-not (Test-Path -LiteralPath $statePath)) { Write-Host 'Запущенные процессы не зарегистрированы'; return }
$registered = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
foreach ($item in $registered) {
    $current = Get-CimInstance Win32_Process -Filter "ProcessId = $($item.pid)" -ErrorAction SilentlyContinue
    $process = Get-Process -Id $item.pid -ErrorAction SilentlyContinue
    if ($current -and $process -and $current.ExecutablePath -eq $taskPython -and $current.CommandLine -like "*-m polka.cli $($item.command)*" -and $process.StartTime.ToUniversalTime().Ticks -eq ([DateTime]$item.started).ToUniversalTime().Ticks) {
        # Windows запускает базовый Python дочерним процессом оболочки venv.
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $($item.pid)" | Where-Object { $_.CommandLine -eq $current.CommandLine -and $_.CreationDate -ge $current.CreationDate }
        foreach ($child in $children) { Stop-Process -Id $child.ProcessId -ErrorAction SilentlyContinue }
        Stop-Process -Id $item.pid -ErrorAction SilentlyContinue
        Write-Host "Остановлен процесс $($item.command)"
    }
}
Remove-Item -LiteralPath $statePath
