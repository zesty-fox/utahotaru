$ErrorActionPreference = "Stop"
$version = if ($env:APP_VERSION) { $env:APP_VERSION } else { throw "APP_VERSION is required" }
$files = @(
    "dist\StrangeUtaGame\StrangeUtaGame.exe",
    "dist\release\StrangeUtaGame-$version-windows-x86_64.exe"
)

foreach ($file in $files) {
    $signature = Get-AuthenticodeSignature $file
    if ($signature.Status -ne 'Valid') {
        throw "Invalid Authenticode signature for $file: $($signature.Status)"
    }
}
