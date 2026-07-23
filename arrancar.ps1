# Comando PM — arranque de un solo clic.
# Levanta el backend (que ya sirve la app compilada) y abre el navegador.
# Uso: clic derecho > "Ejecutar con PowerShell", o crear un acceso directo a:
#   powershell -ExecutionPolicy Bypass -File "D:\ClaudIA\ComandoPM\arrancar.ps1"

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$uvicorn = Join-Path $raiz "backend\.venv\Scripts\uvicorn.exe"
$dist = Join-Path $raiz "frontend\dist"

if (-not (Test-Path $uvicorn)) {
    Write-Host "No existe el entorno virtual. Corre primero:" -ForegroundColor Red
    Write-Host "  cd backend; python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
    Read-Host "Enter para salir"
    exit 1
}
if (-not (Test-Path $dist)) {
    Write-Host "No existe frontend\dist (la app compilada). Corre primero:" -ForegroundColor Yellow
    Write-Host "  cd frontend; npm run build"
    Read-Host "Enter para salir"
    exit 1
}

# Si ya está corriendo, solo abrir el navegador
$activo = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($activo) {
    Start-Process "http://localhost:8000"
    exit 0
}

Write-Host "Arrancando Comando PM en http://localhost:8000 ..." -ForegroundColor Green
Start-Process "http://localhost:8000"
& $uvicorn app.main:app --app-dir (Join-Path $raiz "backend") --host 127.0.0.1 --port 8000
