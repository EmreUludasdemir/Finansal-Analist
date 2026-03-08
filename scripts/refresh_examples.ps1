param(
    [string]$TweetUrl = "https://x.com/quantscience_/status/2023750362184724759?s=20",
    [string]$CapturedAtUtc = "2026-03-08T00:00:00Z"
)

$ErrorActionPreference = "Stop"

python -m tweet_reader $TweetUrl

New-Item -ItemType Directory -Force examples | Out-Null

$report = Get-Content output\tweet.md -Raw
$report = $report -replace "Captured At \(UTC\): .+", "Captured At (UTC): $CapturedAtUtc"
$report | Set-Content examples\quantscience_red_report.md

$summary = Get-Content output\summary.json -Raw
$summary = $summary -replace '"captured_at_utc":\s*"[^"]+"', "`"captured_at_utc`": `"$CapturedAtUtc`""
$summary | Set-Content examples\quantscience_red_summary.json

Write-Host "Examples refreshed from $TweetUrl"
