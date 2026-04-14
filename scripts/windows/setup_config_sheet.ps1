<#
.SYNOPSIS
    One-time setup: updates the VBA module in counter_risk_template.xlsm from
    assets/vba/RunnerLaunch.bas and verifies the Config sheet is present.

.DESCRIPTION
    Run this script once on the maintainer machine after updating RunnerLaunch.bas.
    It opens the template XLSM via Excel COM, replaces the RunnerLaunch VBA module
    with the current source, saves, and closes.

    Requires: Excel installed; macro programmatic access enabled in Excel Trust Center
    (File > Options > Trust Center > Macro Settings > "Trust access to the VBA project
    object model").

.PARAMETER TemplatePath
    Path to counter_risk_template.xlsm. Defaults to
    assets\templates\counter_risk_template.xlsm relative to this script's grandparent.

.PARAMETER VbaSourcePath
    Path to RunnerLaunch.bas. Defaults to assets\vba\RunnerLaunch.bas relative to
    this script's grandparent.

.EXAMPLE
    .\setup_config_sheet.ps1
#>
param(
    [string]$TemplatePath = "",
    [string]$VbaSourcePath = ""
)

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

if (-not $TemplatePath) {
    $TemplatePath = Join-Path $repoRoot "assets\templates\counter_risk_template.xlsm"
}
if (-not $VbaSourcePath) {
    $VbaSourcePath = Join-Path $repoRoot "assets\vba\RunnerLaunch.bas"
}

if (-not (Test-Path $TemplatePath)) {
    Write-Error "Template not found: $TemplatePath"
    exit 1
}
if (-not (Test-Path $VbaSourcePath)) {
    Write-Error "VBA source not found: $VbaSourcePath"
    exit 1
}

Write-Host "Template : $TemplatePath"
Write-Host "VBA source: $VbaSourcePath"

$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false

try {
    $workbook = $excel.Workbooks.Open((Resolve-Path $TemplatePath).Path)

    try {
        $vbaProject = $workbook.VBProject
    } catch {
        Write-Error @"
Cannot access VBA project. Enable 'Trust access to the VBA project object model':
  Excel > File > Options > Trust Center > Trust Center Settings > Macro Settings
"@
        $workbook.Close($false)
        exit 1
    }

    $module = $null
    foreach ($component in $vbaProject.VBComponents) {
        if ($component.Name -eq "RunnerLaunch") {
            $module = $component
            break
        }
    }

    if ($null -eq $module) {
        Write-Error "RunnerLaunch module not found in workbook VBA project."
        $workbook.Close($false)
        exit 1
    }

    $sourceCode = [IO.File]::ReadAllText((Resolve-Path $VbaSourcePath).Path)
    $codeModule = $module.CodeModule
    if ($codeModule.CountOfLines -gt 0) {
        $codeModule.DeleteLines(1, $codeModule.CountOfLines)
    }
    $codeModule.InsertLines(1, $sourceCode)

    $workbook.Save()
    $workbook.Close($false)
    Write-Host "VBA module updated and workbook saved."
} finally {
    $excel.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
}
