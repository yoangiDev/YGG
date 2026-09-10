COMPOSE = docker compose -f infra/docker-compose.yml

.PHONY: up down logs ps migrate test-core test-api test-web e2e lint

## Motor de análisis: sin base de datos
test-core:
	cd packages/ygg-core && pytest -q && mypy

## Levanta postgres + redis + api + worker + web (aplica las migraciones al arrancar)
up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f api worker

ps:
	$(COMPOSE) ps

migrate:
	$(COMPOSE) exec api alembic upgrade head

## Tests de la API contra el postgres de docker compose
test-api:
	cd apps/api && DATABASE_URL=postgresql://ygg:ygg@localhost:5432/ygg SECRET_KEY=test pytest -q

## Cliente web: lint, tipos, tests unitarios, build y presupuesto de JS inicial
test-web:
	cd apps/web && npm run lint && npm test && npm run build && node scripts/bundle-budget.mjs

## Flujo crítico en navegador (API simulada, no necesita docker)
e2e:
	cd apps/web && npm run test:e2e

lint:
	ruff check .
	cd apps/web && npm run lint
