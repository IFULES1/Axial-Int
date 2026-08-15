.DEFAULT_GOAL := help
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help venv install run lint test migrate makemigration seed-users up down fmt

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

venv: ## Create the virtualenv
	python3 -m venv $(VENV)

install: venv ## Install dependencies
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

run: ## Run the API locally (reload)
	$(VENV)/bin/uvicorn app.main:app --reload --port 8080

worker: ## Run the background worker
	$(PY) -m worker.main

lint: ## Lint with ruff
	$(VENV)/bin/ruff check app worker tests

fmt: ## Auto-format with ruff
	$(VENV)/bin/ruff check --fix app worker tests

test: ## Run the test suite
	$(VENV)/bin/pytest -q

migrate: ## Apply DB migrations
	$(VENV)/bin/alembic upgrade head

makemigration: ## Autogenerate a migration (msg="...")
	$(VENV)/bin/alembic revision --autogenerate -m "$(msg)"

seed-users: ## Create N test accounts (n=10)
	$(PY) scripts/seed_users.py --count $(or $(n),10)

up: ## Start local infra (postgres, qdrant, presidio)
	docker compose up -d

down: ## Stop local infra
	docker compose down
