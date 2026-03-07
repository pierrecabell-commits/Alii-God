.PHONY: install dev test lint typecheck format security run docker-up docker-down clean

install:
	pip install -r requirements.txt

dev:
	pip install -e ".[dev]"

test:
	ALII_WORKDIR=$(PWD) pytest tests/ -v --tb=short

test-cov:
	ALII_WORKDIR=$(PWD) pytest tests/ -v --cov=. --cov-report=term-missing --cov-report=html

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy --ignore-missing-imports config.py alii_model_router.py base_agent.py alii_logging.py alii_sqlite_memory.py

security:
	detect-secrets scan --all-files --exclude-files '\.env' --exclude-files 'deleted_archive/'

run:
	ALII_WORKDIR=$(PWD) python3 alfred.py

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .mypy_cache .ruff_cache
