param(
    [Parameter(Mandatory = $true)][string]$LauncherPath,
    [Parameter(Mandatory = $true)][string]$EvidenceDirectory
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$LauncherPath = (Resolve-Path $LauncherPath).Path
$EvidenceDirectory = [IO.Path]::GetFullPath($EvidenceDirectory)
New-Item -ItemType Directory -Force $EvidenceDirectory | Out-Null
$sandbox = Join-Path ([IO.Path]::GetTempPath()) ('gui launcher smoke ' + [guid]::NewGuid())
$bundle = Join-Path $sandbox 'assembled release'
$bin = Join-Path $bundle 'bin'
$working = Join-Path $sandbox 'unrelated working directory'
New-Item -ItemType Directory -Force $bin, $working | Out-Null
$launcher = Join-Path $bundle 'run_counter_risk_gui.cmd'
Copy-Item $LauncherPath $launcher
$original = [IO.File]::ReadAllText($launcher)
$savedPath = $env:PATH
$savedTemp = $env:TEMP
$savedNoPause = $env:COUNTER_RISK_NO_PAUSE
$savedLog = $env:COUNTER_RISK_SMOKE_INVOCATIONS
$savedExit = $env:COUNTER_RISK_SMOKE_EXIT

function Invoke-LauncherCase([string]$Name, [int]$ChildExit) {
    $caseDirectory = Join-Path $EvidenceDirectory $Name
    New-Item -ItemType Directory -Force $caseDirectory | Out-Null
    $env:TEMP = $caseDirectory
    $env:COUNTER_RISK_SMOKE_INVOCATIONS = Join-Path $caseDirectory 'invocations.txt'
    $env:COUNTER_RISK_SMOKE_EXIT = [string]$ChildExit
    # A closed stdin lets the interactive failure pause finish without a keyboard.
    & $env:ComSpec /d /c "call `"$launcher`" <nul" *> (Join-Path $caseDirectory 'console.log')
    $launcherExit = $LASTEXITCODE
    $calls = @()
    if (Test-Path $env:COUNTER_RISK_SMOKE_INVOCATIONS) {
        $calls = @(Get-Content $env:COUNTER_RISK_SMOKE_INVOCATIONS)
    }
    return @{ Directory = $caseDirectory; Exit = $launcherExit; Calls = $calls }
}

try {
    # Compile a real Windows console recorder; the test does not use Python or a GUI.
    $source = Join-Path $sandbox 'Recorder.cs'
    @'
using System;
using System.IO;
class Recorder {
    static int Main(string[] args) {
        File.AppendAllText(Environment.GetEnvironmentVariable("COUNTER_RISK_SMOKE_INVOCATIONS"),
                          string.Join(" ", args) + Environment.NewLine);
        return int.Parse(Environment.GetEnvironmentVariable("COUNTER_RISK_SMOKE_EXIT"));
    }
}
'@ | Set-Content $source
    $compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
    if (-not (Test-Path -LiteralPath $compiler -PathType Leaf)) {
        throw "Command recorder C# compiler not found: $compiler"
    }
    & $compiler /nologo /target:exe "/out:$bin\counter-risk.exe" $source
    if ($LASTEXITCODE -ne 0) {
        throw "Command recorder compilation failed with exit code $LASTEXITCODE ($compiler)"
    }
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $env:COUNTER_RISK_NO_PAUSE = '1'
    Push-Location $working
    try {
        foreach ($childExit in @(0, 37)) {
            $result = Invoke-LauncherCase "child-$childExit" $childExit
            if ($result.Calls.Count -ne 1 -or $result.Calls[0] -cne 'gui') {
                throw "Expected exactly one gui invocation for child exit $childExit"
            }
            if ($result.Exit -ne $childExit) { throw "Lost child exit code $childExit" }
            $log = Get-Content (Join-Path $result.Directory 'counter-risk-gui-launcher.log') -Raw
            if (-not $log.Contains("Exit code: $childExit")) { throw 'Child exit missing from launcher log' }
            $console = Get-Content (Join-Path $result.Directory 'console.log') -Raw
            if ($childExit -ne 0 -and -not $console.Contains("exited with error code $childExit")) {
                throw 'Nonzero child result was not reported as failure'
            }
        }

        # Deliberately remove only the assembled-bin lookup. The real launcher must
        # now fail to find a command; this proves the smoke detects the original bug.
        $pattern = '(?ms)^if exist "%~dp0bin\\counter-risk\.exe" \(\r?\n.*?^\)\r?\n\r?\n'
        $broken = [regex]::Replace($original, $pattern, '')
        if ($broken -eq $original) { throw 'Mutation did not remove the bin branch' }
        [IO.File]::WriteAllText($launcher, $broken)
        $mutation = Invoke-LauncherCase 'removed-bin-branch' 0
        if ($mutation.Calls.Count -ne 0 -or $mutation.Exit -ne 9009) {
            throw 'Removing the bin branch did not produce the expected missing-command failure'
        }
        [IO.File]::WriteAllText($launcher, $original)
        $restored = Invoke-LauncherCase 'restored-bin-branch' 0
        if ($restored.Calls.Count -ne 1 -or $restored.Calls[0] -cne 'gui' -or $restored.Exit -ne 0) {
            throw 'Restored bin branch did not launch exactly once'
        }
        'PASS: one gui invocation; child exit 37 reported; removed branch fails; restored branch passes' |
            Set-Content (Join-Path $EvidenceDirectory 'result.txt')
    } finally {
        Pop-Location
    }
} catch {
    "FAIL: $($_.Exception.Message)" | Set-Content (Join-Path $EvidenceDirectory 'result.txt')
    throw
} finally {
    $env:PATH = $savedPath
    $env:TEMP = $savedTemp
    $env:COUNTER_RISK_NO_PAUSE = $savedNoPause
    $env:COUNTER_RISK_SMOKE_INVOCATIONS = $savedLog
    $env:COUNTER_RISK_SMOKE_EXIT = $savedExit
    Remove-Item -LiteralPath $sandbox -Recurse -Force -ErrorAction SilentlyContinue
}
