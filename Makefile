.PHONY: up down logs test lint build verify soak backtest paper reconcile diagnose backup

COMPOSE_LOCAL = docker compose -f docker-compose.yml -f deploy/docker-compose.local.yml

up:
	$(COMPOSE_LOCAL) up -d --build

down:
	$(COMPOSE_LOCAL) down

logs:
	$(COMPOSE_LOCAL) logs --tail=120 -f api trader dashboard

test:
	docker run --rm -v "$(CURDIR)/apps/trader:/workspace" -w /workspace algodesk-trader python -m pytest -q tests

lint:
	npm run lint

build:
	npm run build

verify:
	python scripts/verify_runtime.py --base-url http://127.0.0.1:8000

soak:
	python scripts/soak_runtime.py --base-url http://127.0.0.1:8000 --cycles 12 --interval 5

backtest:
	python scripts/backtest.py --symbol BTCUSDT --interval 1h --limit 500

paper:
	python scripts/paper.py

reconcile:
	python scripts/reconcile.py --symbol BTCUSDT

diagnose:
	powershell -ExecutionPolicy Bypass -File .\scripts\diagnose.ps1

backup:
	powershell -ExecutionPolicy Bypass -File .\scripts\backup-postgres.ps1
