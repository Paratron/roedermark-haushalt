.PHONY: setup fetch parse normalize validate publish clean help

VENV   := .venv
PYTHON := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Create venv and install dependencies
	uv venv --python 3.12
	uv pip install -e ".[dev]"

fetch: ## Download all PDFs from sources.yaml → data/raw/
	$(PYTHON) -m pipeline.fetch.fetch

fetch-force: ## Re-download all PDFs (overwrite existing)
	$(PYTHON) -m pipeline.fetch.fetch --force

parse: ## Extract tables/text from PDFs → data/extracted/
	$(PYTHON) -m pipeline.parse.parse

normalize: ## Normalize extracted CSVs → unified line_items
	$(PYTHON) -m pipeline.normalize.normalize

validate: ## Run validation checks on extracted + normalized data
	$(PYTHON) pipeline/validate/quick_check.py
	$(PYTHON) pipeline/validate/check_normalize.py

publish: ## Export line_items to Parquet/DuckDB/JSON → data/published/
	$(PYTHON) -m pipeline.publish.publish

pipeline: fetch parse normalize publish ## Run full pipeline end-to-end

test: ## Run tests
	$(PYTHON) -m pytest

lint: ## Run linter (ruff)
	$(VENV)/bin/ruff check pipeline/

clean: ## Remove extracted and published data (keeps raw PDFs)
	rm -rf data/extracted/*
	rm -rf data/published/*
	@echo "Cleaned extracted + published data. Raw PDFs untouched."
