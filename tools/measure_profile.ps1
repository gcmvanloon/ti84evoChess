param(
    [Parameter(Mandatory = $true)]
    [string]$Profile
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$profilesTool = Join-Path $projectRoot "tools\build_profiles.py"
$profilesConfig = Join-Path $projectRoot "build_profiles.json"
$buildScript = Join-Path $projectRoot "tools\build_minified.ps1"

if (-not (Test-Path -LiteralPath $python)) {
    throw "The minifier is not set up. Run the VS Code task 'Chess: setup minifier' first."
}

$validatedProfile = & $python $profilesTool $profilesConfig --profile $Profile
if ($LASTEXITCODE -ne 0) {
    throw "Build profile validation failed."
}

$normalizedName = $validatedProfile.ToUpperInvariant().Replace("-", "_")
$history = Join-Path $projectRoot ("BUILD_METRICS_" + $normalizedName + ".csv")
$temporaryDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("ti84evoChess-profile-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $temporaryDirectory | Out-Null
try {
    $temporaryOutput = Join-Path $temporaryDirectory ($validatedProfile + ".py")
    & $buildScript -Profile $validatedProfile -Output $temporaryOutput -MetricsHistory $history
    if ($LASTEXITCODE -ne 0) {
        throw "Build failed for profile '$validatedProfile'."
    }
}
finally {
    if (Test-Path -LiteralPath $temporaryDirectory) {
        Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force
    }
}
