COMPOSE = docker compose -f infra/docker-compose.yml

.PHONY: up down logs ps migrate test-api lint

## Levanta postgres + redis + api (aplica las migraciones al arrancar)
up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f api

ps:
	$(COMPOSE) ps

migrate:
	$(COMPOSE) exec api alembic upgrade head

## Tests de la API contra el postgres de docker compose
test-api:
	cd apps/api && DATABASE_URL=postgresql://ygg:ygg@localhost:5432/ygg SECRET_KEY=test pytest -q

lint:
	ruff check .
