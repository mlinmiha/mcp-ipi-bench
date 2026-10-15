SHELL := /bin/bash

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@printf "Usage: make <target>\n\nTargets:\n"
	@awk -F ':.*## ' '/^[a-zA-Z0-9_-]+:.*## / { printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

.PHONY: install
install: ## Install project dependencies from the lock file
	uv sync --locked

.PHONY: lint
lint: ## Check code formatting and lint rules
	uv run ruff format --check .
	uv run ruff check .

.PHONY: typecheck
typecheck: ## Check Python types with Pyright
	uv run pyright

.PHONY: format
format: ## Fix lint issues and format code
	uv run ruff check --fix .
	uv run ruff format .

.PHONY: test
test: ## Run tests (excluding live API tests)
	uv run pytest -m "not live and not r"

.PHONY: smoke
smoke: ## Run tests against live API using .env (pass pytest flags with ARGS="...")
	uv run $(if $(wildcard .env),--env-file .env) pytest -m live $(ARGS)
