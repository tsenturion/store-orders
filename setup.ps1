# Подготовка приложения. Адреса PostgreSQL и Kafka задаются в .env.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Команда завершилась с ошибкой: $Program" }
}
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    Invoke-Checked 'python' @('-m', 'venv', '.venv')
}
$taskPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
$env:PYTHONIOENCODING = 'utf-8'
Invoke-Checked $taskPython @('-m', 'pip', 'install', '-r', 'requirements.lock.txt')
Invoke-Checked 'npm.cmd' @('ci', '--prefix', 'frontend', '--no-audit', '--no-fund')
Invoke-Checked 'npm.cmd' @('run', 'build', '--prefix', 'frontend')
Invoke-Checked $taskPython @('-m', 'polka.cli', 'init')
Invoke-Checked $taskPython @('-m', 'polka.cli', 'topic')
Write-Host 'Подготовка завершена. Запуск: .\start.ps1'
