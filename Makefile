COMPOSE = docker compose -f infra/docker-compose.yml

.PHONY: up down logs ps migrate test-core test-api test-web e2e screenshots lint

## Analysis engine: no database
test-core:
	cd packages/ygg-core && pytest -q && mypy

## Starts postgres + redis + api + worker + web (applies the migrations on startup)
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

## API tests against the docker compose postgres
test-api:
	cd apps/api && DATABASE_URL=postgresql://ygg:ygg@localhost:5432/ygg SECRET_KEY=test pytest -q

## Web client: lint, types, unit tests, build and initial JS budget
test-web:
	cd apps/web && npm run lint && npm test && npm run build && node scripts/bundle-budget.mjs

## Critical browser flow (simulated API, no docker needed)
e2e:
	cd apps/web && npm run test:e2e

## Regenerates the README screenshots (docs/img) with the simulated API. With a network: SCREENSHOTS_CDN=1 uses Riot's real art
screenshots:
	cd apps/web && SCREENSHOTS=1 SCREENSHOTS_DIR=../../docs/img npm run test:e2e -- screenshots

lint:
	ruff check .
	cd apps/web && npm run lint
