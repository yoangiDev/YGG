<#
Entorno de desarrollo local:
  - Postgres y Redis en Docker
  - API con recarga automática al guardar (uvicorn --reload)
  - Worker de análisis con recarga automática (arq --watch)
  - Web con recarga en caliente (Vite)

Uso, desde la raíz del repo:
  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1

Abre tres ventanas (API, worker y web). Para parar, ciérralas; las bases de datos
siguen en Docker hasta que hagas:
  docker compose -f infra\docker-compose.yml stop
#>
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$compose = Join-Path $root "infra\docker-compose.yml"
$api = Join-Path $root "apps\api"
$web = Join-Path $root "apps\web"

if (-not (Test-Path $python)) { throw "No encuentro el venv en $python" }
if (-not (Test-Path (Join-Path $api ".env"))) { throw "Falta apps\api\.env (cópialo de apps\api\.env.example)" }
if (-not (Test-Path (Join-Path $web "node_modules"))) { throw "Faltan las dependencias de la web: ejecuta 'npm ci' en apps\web" }

# Los contenedores de la app ocuparían los puertos 8000 y 5173.
docker compose -f $compose stop api worker web | Out-Null
docker compose -f $compose up -d --wait postgres redis

Start-Process powershell -WorkingDirectory $api -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'YGG API'; & '$python' -m alembic upgrade head; & '$python' -m uvicorn main:app --reload --port 8000"
Start-Process powershell -WorkingDirectory $api -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'YGG worker'; & '$python' -m arq app.jobs.worker.WorkerSettings --watch app"
Start-Process powershell -WorkingDirectory $web -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'YGG web'; npm run dev"

Write-Host ""
Write-Host "Web: http://localhost:5173"
Write-Host "API: http://localhost:8000/docs"
