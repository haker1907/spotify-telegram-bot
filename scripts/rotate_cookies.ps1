param(
    [string]$CookiesPath = "cookies.txt"
)

$ErrorActionPreference = "Stop"

Write-Host "Exporting Firefox cookies..."
python "scripts/extract_firefox_cookies.py" --output $CookiesPath

if (-not (Test-Path $CookiesPath)) {
    throw "cookies file not found: $CookiesPath"
}

$raw = Get-Content $CookiesPath -Raw
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($raw))

Write-Host ""
Write-Host "YOUTUBE_COOKIES_BASE64 value:"
Write-Host $b64
Write-Host ""
Write-Host "Copy this value to Railway environment variable:"
Write-Host "YOUTUBE_COOKIES_BASE64"
