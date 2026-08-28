$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$minifier = Join-Path $projectRoot ".venv\Scripts\pyminify.exe"
$source = Join-Path $projectRoot "chess_evo.py"
$output = Join-Path $projectRoot "chess_evo_min.py"
$temporaryOutput = Join-Path $projectRoot "chess_evo_min.py.tmp"

if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $minifier)) {
    throw "The minifier is not set up. Run the VS Code task 'Chess: setup minifier' first."
}

try {
    # Effective python-minifier API settings:
    #   hoist_literals=False, rename_locals=True, rename_globals=True
    # rename_locals=True is the default in pinned python-minifier 3.2.0; its CLI
    # only provides the inverse --no-rename-locals switch.
    & $minifier $source --output $temporaryOutput --rename-globals --remove-literal-statements --prefer-single-line --no-hoist-literals
    if ($LASTEXITCODE -ne 0) {
        throw "python-minifier failed."
    }

    # Parse/compile both files without importing calculator-only ti_* modules.
    $compile = "import sys; compile(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1], 'exec')"
    & $python -c $compile $source
    if ($LASTEXITCODE -ne 0) {
        throw "Readable source compile check failed."
    }
    & $python -c $compile $temporaryOutput
    if ($LASTEXITCODE -ne 0) {
        throw "Minified build compile check failed."
    }

    Move-Item -LiteralPath $temporaryOutput -Destination $output -Force

    $sourceBytes = (Get-Item -LiteralPath $source).Length
    $outputBytes = (Get-Item -LiteralPath $output).Length
    $savedPercent = [math]::Round((1 - $outputBytes / $sourceBytes) * 100, 1)
    Write-Host "Built chess_evo_min.py: $outputBytes bytes ($savedPercent% smaller than $sourceBytes bytes)."
}
finally {
    if (Test-Path -LiteralPath $temporaryOutput) {
        Remove-Item -LiteralPath $temporaryOutput
    }
}
