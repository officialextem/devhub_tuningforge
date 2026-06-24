param(
    [string]$Name = "DEVHub TuningForge",
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

function Test-PythonExe {
    param([string]$Candidate)
    if ([string]::IsNullOrWhiteSpace($Candidate)) {
        return $false
    }
    if ($Candidate -match "\\WindowsApps\\") {
        return $false
    }
    if (-not (Test-Path -LiteralPath $Candidate)) {
        return $false
    }
    try {
        & $Candidate -c "import sys; print(sys.executable)" *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Resolve-PythonExe {
    param([string]$Requested)

    $candidates = New-Object System.Collections.Generic.List[string]
    if ($Requested) {
        $candidates.Add($Requested)
    }
    if ($env:DEVHUB_PYTHON) {
        $candidates.Add($env:DEVHUB_PYTHON)
    }

    Get-Command python.exe -All -ErrorAction SilentlyContinue |
        ForEach-Object { $candidates.Add($_.Source) }

    $searchRoots = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python"),
        (Join-Path $env:LOCALAPPDATA "Python"),
        "C:\Program Files"
    )
    foreach ($root in $searchRoots) {
        if (Test-Path -LiteralPath $root) {
            Get-ChildItem -LiteralPath $root -Recurse -Filter "python.exe" -ErrorAction SilentlyContinue |
                ForEach-Object { $candidates.Add($_.FullName) }
        }
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-PythonExe $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "Kein ausfuehrbarer Python-Interpreter gefunden. Starte mit -PythonExe `"C:\Pfad\zu\python.exe`" oder setze DEVHUB_PYTHON."
}

$Python = Resolve-PythonExe $PythonExe
Write-Host "Using Python: $Python"

$PythonRoot = (& $Python -c "import sys; print(sys.base_prefix)").Trim()
$PythonDlls = Join-Path $PythonRoot "DLLs"
$PythonTcl = Join-Path $PythonRoot "tcl"

$TkPreflight = @'
import sys
import tkinter as tk

try:
    root = tk.Tk()
    root.withdraw()
    root.destroy()
except Exception as exc:
    print("Tkinter/Tcl preflight failed.", file=sys.stderr)
    print(f"{exc.__class__.__name__}: {exc}", file=sys.stderr)
    print("Repair or reinstall Python with Tcl/Tk support before building the portable EXE.", file=sys.stderr)
    raise SystemExit(1)
'@

$TkPreflight | & $Python -
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $Python -m pip install -r requirements-dev.txt
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name $Name `
    --hidden-import tkinter `
    --hidden-import tkinter.ttk `
    --hidden-import tkinter.font `
    --hidden-import tkinter.filedialog `
    --hidden-import tkinter.constants `
    --add-binary "$PythonDlls\_tkinter.pyd;." `
    --add-binary "$PythonDlls\tcl86t.dll;." `
    --add-binary "$PythonDlls\tk86t.dll;." `
    --add-data "$PythonTcl;tcl" `
    --add-data "packages;packages" `
    --add-data "profiles;profiles" `
    --add-data "tuning;tuning" `
    app/main.py

$OutputDir = Join-Path "dist" $Name
New-Item -ItemType Directory -Force -Path (Join-Path $OutputDir "reports") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $OutputDir "logs") | Out-Null

Write-Host "Portable build created in $OutputDir"
Write-Host "Reports and logs will be written next to the executable."
