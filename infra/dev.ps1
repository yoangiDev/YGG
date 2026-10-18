<#
Local development environment:
  - Postgres and Redis in Docker
  - API with automatic reload on save (uvicorn --reload)
  - Analysis worker, with automatic reload through watchfiles: arq's --watch sends SIGUSR1, which doesn't
    exist on Windows, and they crashed
  - Web with hot reload (Vite)

Usage, from the repo root:
  powershell -ExecutionPolicy Bypass -File infra\dev.ps1

It opens three windows (API, worker and web). To stop, close them; the databases
keep running in Docker until you run:
  docker compose -f infra\docker-compose.yml stop
#>
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$compose = Join-Path $root "infra\docker-compose.yml"
$api = Join-Path $root "apps\api"
$web = Join-Path $root "apps\web"

if (-not (Test-Path $python)) { throw "Cannot find the venv at $python" }
if (-not (Test-Path (Join-Path $api ".env"))) { throw "Missing apps\api\.env (copy it from apps\api\.env.example)" }
if (-not (Test-Path (Join-Path $web "node_modules"))) { throw "The web dependencies are missing: run 'npm ci' in apps\web" }

# The app's containers would take ports 8000 and 5173.
docker compose -f $compose stop api worker web | Out-Null
docker compose -f $compose up -d --wait postgres redis

Start-Process powershell -WorkingDirectory $api -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'YGG API'; & '$python' -m alembic upgrade head; & '$python' -m uvicorn main:app --reload --port 8000"
Start-Process powershell -WorkingDirectory $api -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'YGG worker'; & '$python' -m watchfiles --filter python app.jobs.worker.main app"
Start-Process powershell -WorkingDirectory $web -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'YGG web'; npm run dev"

Write-Host ""
Write-Host "Web: http://localhost:5173"
Write-Host "API: http://localhost:8000/docs"
