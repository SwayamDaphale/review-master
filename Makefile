.PHONY: help up down logs ps build migrate shell-backend test golden lint fmt openapi rag local-llm gateway observability clean

help:  ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

up:  ## Start the core stack
	docker compose up -d --build

down:  ## Stop the stack (keep data)
	docker compose down

logs:  ## Follow backend and worker logs
	docker compose logs -f backend worker

ps:  ## Show service status
	docker compose ps

build:  ## Build images
	docker compose build

migrate:  ## Apply database migrations
	docker compose run --rm migrate

shell-backend:  ## Shell in the backend container
	docker compose exec backend bash

test:  ## Backend tests (excluding golden)
	docker compose exec backend pytest -q -m "not golden"

golden:  ## Determinism gate: golden evaluation fixtures
	docker compose exec backend pytest -q -m golden

lint:  ## Lint and type check
	docker compose exec backend sh -c "ruff check . && ruff format --check . && mypy app"

fmt:  ## Auto-format backend code
	docker compose exec backend ruff format .

openapi:  ## Export the generated OpenAPI document
	docker compose exec backend python -m app.tools.export_openapi openapi.json

rag:  ## Start with Qdrant (RAG profile)
	docker compose --profile rag up -d

local-llm:  ## Start Ollama and pull models
	docker compose --profile local-llm up -d

gateway:  ## Start the LiteLLM gateway
	docker compose --profile llm-gateway up -d

observability:  ## Start Prometheus and Grafana
	docker compose --profile observability up -d

clean:  ## Stop and DELETE all volumes (destroys local data)
	docker compose down -v
