$ErrorActionPreference = "Stop"

$pfx = $env:WINDOWS_CERTIFICATE_PFX
$password = $env:WINDOWS_CERTIFICATE_PASSWORD
if (-not $pfx) { throw "WINDOWS_CERTIFICATE_PFX is required" }
if (-not $password) { throw "WINDOWS_CERTIFICATE_PASSWORD is required" }
$signtool = if ($env:SIGNTOOL_PATH) { $env:SIGNTOOL_PATH } else { "signtool.exe" }
$version = if ($env:APP_VERSION) { $env:APP_VERSION } else { throw "APP_VERSION is required" }
$files = @(
    "dist\StrangeUtaGame\StrangeUtaGame.exe",
    "dist\release\StrangeUtaGame-$version-windows-x86_64.exe"
)

foreach ($file in $files) {
    & $signtool sign /f $pfx /p $password /fd SHA256 /tr https://timestamp.digicert.com /td SHA256 $file
    if ($LASTEXITCODE -ne 0) { throw "signtool failed for $file" }
}
