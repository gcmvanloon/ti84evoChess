$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

function Find-Uv {
    $command = Get-Command "uv" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $userInstall = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
    if (Test-Path -LiteralPath $userInstall) {
        return $userInstall
    }

    throw "uv is not installed. Install it with VS Code's Python environment tools, restart VS Code, and run this task again."
}

$uv = Find-Uv
$pythonVersion = (Get-Content -LiteralPath (Join-Path $projectRoot ".python-version") -Raw).Trim()

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Creating project virtual environment with Python $pythonVersion..."
    & $uv venv --python $pythonVersion $venv
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the virtual environment."
    }
}

Write-Host "Synchronizing pinned development tools..."
& $uv pip sync --python $venvPython (Join-Path $projectRoot "requirements-dev.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install development tools."
}

Write-Host "Minifier setup complete."
