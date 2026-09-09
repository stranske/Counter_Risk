param(
    [Parameter(Mandatory = $true)][string]$Bundle,
    [Parameter(Mandatory = $true)][string]$EvidenceDirectory
)

$ErrorActionPreference = 'Stop'
$Bundle = (Resolve-Path $Bundle).Path
$EvidenceDirectory = [IO.Path]::GetFullPath($EvidenceDirectory)
New-Item -ItemType Directory -Force $EvidenceDirectory | Out-Null
$sandbox = Join-Path ([IO.Path]::GetTempPath()) ('counter-risk-smoke-' + [guid]::NewGuid())
$isolatedBundle = Join-Path $sandbox 'bundle'
$workingDirectory = Join-Path $sandbox 'unrelated-cwd'
$inputs = Join-Path $sandbox 'inputs'
$output = Join-Path $sandbox 'output'
New-Item -ItemType Directory -Force $workingDirectory, $inputs | Out-Null
Copy-Item -Recurse $Bundle $isolatedBundle

# The frozen executable receives no checkout path or installed Python environment.
$keys = @(
    'mosers_all_programs_xlsx', 'mosers_ex_trend_xlsx', 'mosers_trend_xlsx',
    'hist_all_programs_3yr_xlsx', 'hist_ex_llc_3yr_xlsx', 'hist_llc_3yr_xlsx', 'monthly_pptx'
)
$configLines = @('as_of_date: 2025-12-31')
foreach ($key in $keys) {
    $fixture = Join-Path $inputs "$key.json"
    @{ source = $key; values = @(12.5, -7.25, 0) } |
        ConvertTo-Json | Set-Content -Encoding utf8 $fixture
    $configLines += "${key}: '$($fixture.Replace('\', '/').Replace("'", "''"))'"
}
$config = Join-Path $inputs 'smoke.yml'
$configLines | Set-Content -Encoding utf8 $config
$exe = Join-Path $isolatedBundle 'bin/counter-risk.exe'
$savedLocation = Get-Location
$savedEnvironment = @{}
foreach ($key in @('PATH', 'PYTHONPATH', 'PYTHONHOME', 'COUNTER_RISK_BUNDLE_ROOT')) {
    $savedEnvironment[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
}
try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    foreach ($key in @('PYTHONPATH', 'PYTHONHOME', 'COUNTER_RISK_BUNDLE_ROOT')) {
        [Environment]::SetEnvironmentVariable($key, $null, 'Process')
    }
    Set-Location $workingDirectory
    & $exe run --fixture-replay --config $config --output-dir $output *> (Join-Path $EvidenceDirectory 'executable.log')
    if ($LASTEXITCODE -ne 0) {
        throw "Assembled executable failed with exit code $LASTEXITCODE"
    }

    # Validate the existing fixture-replay manifest contract, not the different
    # production-pipeline manifest shape. No runtime format changes are needed.
    $schema = @{
        type = 'object'
        required = @('mode', 'run_date_utc', 'as_of_date', 'config_path', 'outputs')
        additionalProperties = $false
        properties = @{
            mode = @{ const = 'fixture_replay' }
            run_date_utc = @{ type = 'string'; format = 'date-time' }
            as_of_date = @{ const = '2025-12-31' }
            config_path = @{ type = 'string'; minLength = 1 }
            outputs = @{
                type = 'object'; required = $keys
                minProperties = 7; maxProperties = 7
                additionalProperties = @{ type = 'string'; minLength = 1 }
            }
        }
    } | ConvertTo-Json -Depth 10
    $manifestText = Get-Content -Raw (Join-Path $output 'manifest.json')
    if (-not (Test-Json -Json $manifestText -Schema $schema)) {
        throw 'Fixture-replay manifest failed schema validation'
    }
    $manifest = $manifestText | ConvertFrom-Json
    foreach ($key in $keys) {
        $expected = Join-Path $output "$key.json"
        if ([IO.Path]::GetFullPath($manifest.outputs.$key) -ne [IO.Path]::GetFullPath($expected)) {
            throw "Manifest output path mismatch for $key"
        }
        if ((Get-FileHash $expected).Hash -ne (Get-FileHash (Join-Path $inputs "$key.json")).Hash) {
            throw "Fixture content mismatch for $key"
        }
    }
    'PASS: isolated assembled executable; schema-valid manifest; seven exact fixture outputs' |
        Set-Content (Join-Path $EvidenceDirectory 'result.txt')
} finally {
    Set-Location $savedLocation
    foreach ($key in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($key, $savedEnvironment[$key], 'Process')
    }
    if (Test-Path $output) {
        Copy-Item -Recurse $output (Join-Path $EvidenceDirectory 'output')
    }
}
