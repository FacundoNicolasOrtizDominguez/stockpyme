# ============================================================================
# build_windows.ps1 — Genera el instalador de STOCKPYME para Windows
#
# Uso (PowerShell, desde la raíz del proyecto, con el entorno virtual activado):
#     .\build_windows.ps1
#
# Pasos:  1) corre los tests   2) empaqueta con PyInstaller (carpeta dist\StockPyME)
#         3) si está instalado Inno Setup, genera instalador\StockPyME-Setup-<versión>.exe
# Requisitos: pip install -r requirements.txt -r requirements-build.txt
#             Inno Setup 6 (gratis): https://jrsoftware.org/isinfo.php
# ============================================================================
param([switch]$Consola)   # .\build_windows.ps1 -Consola  → el .exe muestra una consola con los errores (solo para depurar)
$ErrorActionPreference = "Stop"
$ventana = if ($Consola) { "--console" } else { "--windowed" }

Write-Host "==> 1/3 Corriendo tests..." -ForegroundColor Cyan
python -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) { throw "Los tests fallaron: no se genera el instalador." }

Write-Host "==> 2/3 Empaquetando con PyInstaller..." -ForegroundColor Cyan
pip install -r requirements-build.txt | Out-Null
pyinstaller --noconfirm --clean $ventana --name StockPyME `
    --collect-submodules backend --collect-submodules interfaz --collect-submodules reportes `
    --collect-submodules reportlab --collect-data reportlab `
    --hidden-import sqlalchemy.dialects.sqlite `
    main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falló." }

Write-Host "==> 3/3 Generando el instalador con Inno Setup..." -ForegroundColor Cyan
$iscc = @(
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($iscc) {
    & $iscc instalador.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup falló." }
    Write-Host "Listo: carpeta 'instalador\'" -ForegroundColor Green
} else {
    Write-Host "Inno Setup no está instalado: la aplicación quedó en dist\StockPyME (se puede copiar tal cual)." -ForegroundColor Yellow
}
