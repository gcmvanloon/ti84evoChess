$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$minifier = Join-Path $projectRoot ".venv\Scripts\pyminify.exe"
$source = Join-Path $projectRoot "chess_evo.py"
$output = Join-Path $projectRoot "chess_evo_min.py"
$preprocessor = Join-Path $projectRoot "tools\ast_preprocessor.py"
$metricsRecorder = Join-Path $projectRoot "tools\build_metrics.py"
$metricsHistory = Join-Path $projectRoot "BUILD_METRICS.csv"
$pythonVersionFile = Join-Path $projectRoot ".python-version"
$requirements = Join-Path $projectRoot "requirements-dev.txt"
$preprocessedOutput = Join-Path $projectRoot "chess_evo_preprocessed.py.tmp"
$temporaryOutput = Join-Path $projectRoot "chess_evo_min.py.tmp"

if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $minifier)) {
    throw "The minifier is not set up. Run the VS Code task 'Chess: setup minifier' first."
}

try {
    & $python $preprocessor $source $preprocessedOutput
    if ($LASTEXITCODE -ne 0) {
        throw "AST preprocessing failed."
    }

    # python-minifier preserves callable parameter names for keyword arguments
    # by assigning them to short local aliases. Those extra assignments save
    # bytes but add substantial AST/compiler pressure. Preserve all argument
    # names so non-argument locals are still renamed without creating aliases.
    $arguments = "import ast,sys; tree=ast.parse(open(sys.argv[1],encoding='utf-8').read()); print(','.join(sorted({node.arg for node in ast.walk(tree) if isinstance(node,ast.arg)})))"
    $preservedLocals = & $python -c $arguments $preprocessedOutput
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to collect function argument names."
    }

    # Effective python-minifier API settings:
    #   hoist_literals=False, rename_locals=True, rename_globals=True,
    #   preserve_locals=<all function argument names>
    # rename_locals=True is the default in pinned python-minifier 3.2.0; its CLI
    # only provides the inverse --no-rename-locals switch.
    & $minifier $preprocessedOutput --output $temporaryOutput --rename-globals --preserve-locals $preservedLocals --remove-literal-statements --prefer-single-line --no-hoist-literals
    if ($LASTEXITCODE -ne 0) {
        throw "python-minifier failed."
    }

    # Parse/compile all files without importing calculator-only ti_* modules.
    $compile = "import sys; compile(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1], 'exec')"
    & $python -c $compile $source
    if ($LASTEXITCODE -ne 0) {
        throw "Readable source compile check failed."
    }
    & $python -c $compile $preprocessedOutput
    if ($LASTEXITCODE -ne 0) {
        throw "Preprocessed source compile check failed."
    }
    & $python -c $compile $temporaryOutput
    if ($LASTEXITCODE -ne 0) {
        throw "Minified build compile check failed."
    }

    Move-Item -LiteralPath $temporaryOutput -Destination $output -Force

    $sourceBytes = (Get-Item -LiteralPath $source).Length
    $preprocessedBytes = (Get-Item -LiteralPath $preprocessedOutput).Length
    $outputBytes = (Get-Item -LiteralPath $output).Length
    $savedPercent = [math]::Round((1 - $outputBytes / $sourceBytes) * 100, 1)
    $astMetrics = "import ast,sys; tree=ast.parse(open(sys.argv[1],encoding='utf-8').read()); print(str(sum(1 for _ in ast.walk(tree)))+' AST nodes, '+str(sum(isinstance(node,ast.stmt) for node in ast.walk(tree)))+' statements')"
    $minifiedAstMetrics = & $python -c $astMetrics $output
    Write-Host "Built chess_evo_min.py: $outputBytes bytes from $preprocessedBytes preprocessed bytes ($savedPercent% smaller than $sourceBytes readable bytes)."
    Write-Host "Minified structure: $minifiedAstMetrics."

    # Record one row for each distinct successful build. Including all files
    # that control generated output makes the input hash useful across tool and
    # configuration changes, not only chess_evo.py edits.
    & $python $metricsRecorder `
        --history $metricsHistory `
        --source $source `
        --preprocessed $preprocessedOutput `
        --minified $output `
        --inputs $source $preprocessor $metricsRecorder $PSCommandPath $pythonVersionFile $requirements
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to record build metrics."
    }
}
finally {
    if (Test-Path -LiteralPath $preprocessedOutput) {
        Remove-Item -LiteralPath $preprocessedOutput
    }
    if (Test-Path -LiteralPath $temporaryOutput) {
        Remove-Item -LiteralPath $temporaryOutput
    }
}
