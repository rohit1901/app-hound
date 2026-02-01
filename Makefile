.PHONY: help install start test

# Variables
POETRY := $(shell command -v poetry 2> /dev/null)
PACKAGE_NAME := app_hound

help:  ## Display this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	$(POETRY) install

start:  ## Run the application
	$(POETRY) run app-hound

test: install  ## Run tests with coverage
	$(POETRY) run pytest --cov=$(PACKAGE_NAME) --cov-report=term-missing --cov-report=html
