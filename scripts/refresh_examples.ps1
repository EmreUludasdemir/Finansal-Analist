param(
    [string]$TweetUrl = "https://x.com/quantscience_/status/2023750362184724759?s=20"
)

$ErrorActionPreference = "Stop"

python -m tweet_reader $TweetUrl

New-Item -ItemType Directory -Force examples | Out-Null
Copy-Item output\tweet.md examples\quantscience_red_report.md -Force
Copy-Item output\summary.json examples\quantscience_red_summary.json -Force

Write-Host "Examples refreshed from $TweetUrl"
