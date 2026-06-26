# run_bots.ps1 - Chay tat ca bots song song, hien log truc tiep
# Usage: .\run_bots.ps1
# Ctrl+C de dung het

$ErrorActionPreference = "SilentlyContinue"
$python = "e:\Project\BotForex\.venv\Scripts\python.exe"
$runner = "src/bot_runner.py"
$base    = @("--user", "admin", "--test", "0", "--interval", "60")

$bots = @(
    @{ symbol = "XAUUSDm"; extra = @() }
    @{ symbol = "ETHUSDm"; extra = @() }
    @{ symbol = "EURUSDm"; extra = @() }
    @{ symbol = "GBPUSDm"; extra = @() }
)

Write-Host "Starting $($bots.Count) bots... Ctrl+C to stop all." -ForegroundColor Cyan

$jobs = @()
foreach ($bot in $bots) {
    $args = @("-u", $runner, "--strategy", "feg_ema21", "--symbol", $bot.symbol) + $base + $bot.extra
    $job = Start-Job -ScriptBlock {
        param($py, $a)
        Set-Location "e:\Project\BotForex"
        & $py @a 2>&1
    } -ArgumentList $python, $args
    $jobs += @{ job = $job; symbol = $bot.symbol }
    Write-Host "  [$($bot.symbol)] started (job $($job.Id))" -ForegroundColor Green
}

Write-Host ""
Write-Host "--- Live output (all symbols) ---" -ForegroundColor Yellow

try {
    while ($true) {
        foreach ($b in $jobs) {
            $lines = Receive-Job $b.job 2>$null
            foreach ($line in $lines) {
                if ($line -match "\[INFO\]|\[WARN\]|\[ERROR\]") {
                    $color = if ($line -match "Signal|Order|Exit") { "Cyan" }
                             elseif ($line -match "\[ERROR\]|\[WARN\]") { "Red" }
                             else { "Gray" }
                    Write-Host "[$($b.symbol)] $line" -ForegroundColor $color
                }
            }
        }
        Start-Sleep -Seconds 5
    }
} finally {
    Write-Host "`nStopping all bots..." -ForegroundColor Yellow
    $jobs | ForEach-Object { Stop-Job $_.job; Remove-Job $_.job }
    Write-Host "All bots stopped." -ForegroundColor Red
}
