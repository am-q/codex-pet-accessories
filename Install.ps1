$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    $pythonArgs = @('-3')
    if (-not $launcher) {
        $launcher = Get-Command python -ErrorAction SilentlyContinue
        $pythonArgs = @()
    }
    if (-not $launcher) { throw 'Install Python 3.12 or later with Tcl/Tk first.' }
    & $launcher.Source @pythonArgs -c 'import sys, tkinter; assert sys.version_info >= (3, 12), "Python 3.12+ is required"'
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ with Tcl/Tk is required.' }
    & $launcher.Source @pythonArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtual environment.' }
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the network and retry.' }
    Write-Host 'Ready. Double-click Launch.vbs to start, or Stop.vbs to stop.'
} finally {
    Pop-Location
}
