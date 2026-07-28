param(
    [string]$Python = 'py',
    [string]$VenvDir = '.\buildenv',
    [string]$ExeName = 'AttendanceSystem',
    [string]$OutputZip = 'AttendanceSystem-release.zip',
    [string]$DataDir = '.\data'
)

function Run-Command {
    param(
        [string]$Command,
        [string[]]$Args
    )
    Write-Host "`n> $Command $($Args -join ' ')" -ForegroundColor Cyan
    $proc = Start-Process -FilePath $Command -ArgumentList $Args -NoNewWindow -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        throw "Command failed: $Command $($Args -join ' ') (exit $($proc.ExitCode))"
    }
}

Write-Host '=== Build and release script for AttendanceSystem ===' -ForegroundColor Green
Write-Host 'This script sets up a venv, installs dependencies, verifies OpenCV, builds the exe, and packages a zip bundle.'

if (-Not (Test-Path $VenvDir)) {
    Run-Command $Python @('-m', 'venv', $VenvDir)
}

$PythonExe = Join-Path $VenvDir 'Scripts\python.exe'
$PyInstallerExe = Join-Path $VenvDir 'Scripts\pyinstaller.exe'

Run-Command $PythonExe @('-m', 'pip', 'install', '--upgrade', 'pip')
Run-Command $PythonExe @('-m', 'pip', 'install', '-r', 'requirements.txt', 'pyinstaller')

Write-Host '\nVerifying OpenCV import and required APIs...' -ForegroundColor Yellow
& $PythonExe -c "import cv2; print(cv2.__file__); print(cv2.__version__); print(hasattr(cv2,'CascadeClassifier'), hasattr(cv2,'VideoCapture'), hasattr(cv2,'face'))"
if ($LASTEXITCODE -ne 0) {
    throw 'OpenCV verification failed. Fix the build environment before continuing.'
}

Write-Host '\nBuilding the executable with PyInstaller...' -ForegroundColor Yellow
Run-Command $PyInstallerExe @('--onefile', '--windowed', '--name', $ExeName, '--collect-data', 'cv2', 'app.py')

Write-Host '\nCreating the release zip bundle...' -ForegroundColor Yellow
Run-Command $PythonExe @('release_bundle.py', '--exe', "dist\$ExeName.exe", '--data', $DataDir, '--output', $OutputZip)

Write-Host "\nRelease bundle created: $OutputZip" -ForegroundColor Green
Write-Host 'If you want to publish this artifact, upload the zip file; end users should unzip it and keep AttendanceSystem.exe next to data\'.' -ForegroundColor Green
