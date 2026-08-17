.PHONY: up down migrate environment

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	docker compose exec api alembic upgrade head

environment:
	docker compose up -d --build
	docker compose exec api alembic upgrade head
	docker compose exec api python -m app.db.seed
