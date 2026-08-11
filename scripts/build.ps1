<#
    Build reproducible de Ecocardiograma Local.

    Pipeline completo en un solo comando:
      1. Lint (ruff) + tests con cobertura (pytest --cov)
      2. PyInstaller (ecocardiograma.spec) -> dist\EcocardiogramaLocal
      3. Inno Setup (ISCC) -> dist\installer\EcocardiogramaLocal-Setup-X.Y.Z.exe
      4. SHA-256 del instalador
      5. Actualiza la seccion "Ultima version" del README

    Requisitos: venv con dependencias (requirements-dev.txt) e Inno Setup 6.

    Uso:  powershell -ExecutionPolicy Bypass -File scripts\build.ps1
          powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -SkipTests
#>
[CmdletBinding()]
param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$py = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) {
    throw "No se encontro venv\Scripts\python.exe. Cree el entorno e instale requirements-dev.txt."
}

if (-not $SkipTests) {
    Write-Host "==> 1/5 Lint y tests con cobertura" -ForegroundColor Cyan
    & $py -m ruff check src tests
    if ($LASTEXITCODE -ne 0) { throw "Ruff encontro errores." }
    & $py -m pytest --cov=src --cov-report=term
    if ($LASTEXITCODE -ne 0) { throw "La suite de tests fallo." }
}

Write-Host "==> 2/5 PyInstaller" -ForegroundColor Cyan
& $py -m PyInstaller ecocardiograma.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fallo." }

Write-Host "==> 3/5 Inno Setup (ISCC)" -ForegroundColor Cyan
$iscc = $null
foreach ($c in @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
)) {
    if (Test-Path -LiteralPath $c) { $iscc = $c; break }
}
if (-not $iscc) { throw "ISCC.exe no encontrado. Instale Inno Setup 6." }
& $iscc (Join-Path $root "installer\ecocardiograma.iss")
if ($LASTEXITCODE -ne 0) { throw "ISCC fallo." }

Write-Host "==> 4/5 SHA-256" -ForegroundColor Cyan
$setup = Get-ChildItem -Path (Join-Path $root "dist\installer") `
    -Filter "EcocardiogramaLocal-Setup-*.exe" |
    Sort-Object LastWriteTime | Select-Object -Last 1
if (-not $setup) { throw "No se encontro el instalador generado." }
$hash = (Get-FileHash $setup.FullName -Algorithm SHA256).Hash
$version = [regex]::Match($setup.Name, '^EcocardiogramaLocal-Setup-(\d+\.\d+\.\d+)\.exe$').Groups[1].Value
$setupName = $setup.Name
Write-Host "  Instalador : $setupName" -ForegroundColor Green
Write-Host "  SHA-256    : $hash" -ForegroundColor Green

Write-Host "==> 5/5 Actualizar README" -ForegroundColor Cyan
$readme = Join-Path $root "README.md"
# UTF8 explicito: PS 5.1 lee sin BOM como ANSI y corrompe caracteres no ASCII
$text = Get-Content -LiteralPath $readme -Raw -Encoding UTF8

# 1) Reemplazar el nombre del instalador (dos apariciones: inline y en el ejemplo)
$text = $text -replace 'EcocardiogramaLocal-Setup-\d+\.\d+\.\d+\.exe', $setupName
# 2) Actualizar la version mostrada ("Ultima version: vX.Y.Z")
$text = $text -replace 'v\d+\.\d+\.\d+', "v$version"
# 3) Actualizar el hash SHA-256 (bloque de 64 hex)
$text = $text -replace '\b[0-9A-F]{64}\b', $hash

[System.IO.File]::WriteAllText($readme, $text, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "  README actualizado." -ForegroundColor Green
Write-Host ""
Write-Host "Listo. Instalador: $($setup.FullName)" -ForegroundColor Green
