param([switch]$Stop)
$ErrorActionPreference = 'Stop'
$newsRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$newsPython = Join-Path $newsRoot '.venv\Scripts\python.exe'
$newsPidFile = Join-Path $newsRoot 'source-cache\market-news-worker.pid'
if (Test-Path -LiteralPath $newsPidFile) {
    $newsPidValue = [int](Get-Content -LiteralPath $newsPidFile)
    $newsProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$newsPidValue"
    if ($newsProcess -and $newsProcess.CommandLine -match '-m engine\.news' -and $newsProcess.ExecutablePath -eq $newsPython) {
        if ($Stop) {
            Get-CimInstance Win32_Process -Filter "ParentProcessId=$newsPidValue" | Where-Object { $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match '-m engine\.news' } | ForEach-Object { Stop-Process -Id $_.ProcessId }
            if (Get-Process -Id $newsPidValue -ErrorAction SilentlyContinue) { Stop-Process -Id $newsPidValue }
            Write-Output 'Market news worker stopped.'
        }
        else { Write-Output 'Market news worker already running.' }
        exit 0
    }
}
if ($Stop) { Write-Output 'No matching market news worker running.'; exit 0 }
if (-not (Test-Path -LiteralPath (Join-Path $newsRoot 'rie-dev-feed.db'))) { throw 'Private database missing; migrate before starting.' }
$env:DATABASE_URL = 'sqlite:///rie-dev-feed.db'
$env:SEND_NOTIFICATIONS = 'false'
$env:ALLOW_SYNTHETIC_LIVE = 'false'
$env:LLM_MODE = 'none'
$env:NEWS_ENABLE_X = 'false'
$newsWorker = Start-Process -FilePath $newsPython -ArgumentList '-m','engine.news' -WorkingDirectory $newsRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $newsRoot 'source-cache\market-news.stdout.log') -RedirectStandardError (Join-Path $newsRoot 'source-cache\market-news.stderr.log')
$newsWorker.Id | Set-Content -LiteralPath $newsPidFile
Write-Output "Market news worker started (PID $($newsWorker.Id)); RSS only, notifications disabled."
