.PHONY: help test lint docs deploy

help:
	@echo "Available commands:"
	@echo "  make test          - Run all tests"
	@echo "  make lint          - Run linting and formatting"
	@echo "  make docs          - Generate documentation"
	@echo "  make check         - Run all quality checks"
	@echo "  make deploy-staging - Deploy to staging"

# Testing
test:
	pytest tests/ -v --cov=src --cov-report=html

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

# Code quality
lint:
	black src/ tests/
	isort src/ tests/
	flake8 src/ tests/
	mypy src/

security:
	bandit -r src/
	safety check

# Documentation
docs:
	python scripts/development/generate_api_docs.py
	python scripts/development/update_diagrams.py
	mkdocs build

# Development
dev-setup:
	pip install -r requirements-dev.txt
	pre-commit install
	cp .env.example .env
	@echo "Remember to update .env with your values!"

# Quality checks
check: lint test security
	python scripts/development/continuous_checks.py

# Database
db-migrate:
	python scripts/setup/init_database.py
	psql -f scripts/setup/create_indexes.sql

db-seed:
	python scripts/setup/seed_data.py

# Deployment
deploy-staging:
	./scripts/deployment/deploy.sh staging
	python scripts/deployment/smoke_test.py staging

deploy-prod:
	@echo "Production deployment requires approval"
	./scripts/deployment/deploy.sh production --require-approval
	python scripts/deployment/smoke_test.py production
