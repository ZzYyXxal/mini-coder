# Makefile for mini-coder TUI build

.PHONY: help build-all build-linux build-macos build-windows clean verify install test lint format

help:
	@echo "Available targets:"
	@echo "  build-all      - Build for all platforms"
	@echo "  build-linux    - Build for Linux"
	@echo "  build-macos    - Build for macOS"
	@echo "  build-windows  - Build for Windows"
	@echo "  clean          - Remove build artifacts"
	@echo "  verify         - Verify binary"
	@echo "  install        - Install dependencies"
	@echo "  test           - Run tests"
	@echo "  lint           - Run linting"
	@echo "  format         - Format code"

build-all:
	@echo "Building for all platforms..."
	@./scripts/build-tui.sh all

build-linux:
	@echo "Building for Linux..."
	@./scripts/build-tui.sh compile linux && ./scripts/build-tui.sh compress && ./scripts/build-tui.sh package linux && ./scripts/build-tui.sh verify

build-macos:
	@echo "Building for macOS..."
	@./scripts/build-tui.sh compile macos && ./scripts/build-tui.sh compress && ./scripts/build-tui.sh package macos && ./scripts/build-tui.sh verify

build-windows:
	@echo "Building for Windows..."
	@./scripts/build-tui.sh compile windows && ./scripts/build-tui.sh compress && ./scripts/build-tui.sh package windows && ./scripts/build-tui.sh verify

clean:
	@echo "Cleaning build artifacts..."
	@rm -rf build/ dist/ *.spec .coverage coverage.xml htmlcov/
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true

verify:
	@echo "Verifying binary..."
	@./scripts/build-tui.sh verify

install:
	@echo "Installing dependencies..."
	@pip install -r requirements.txt
	@pip install -e .

test:
	@echo "Running tests..."
	@python -m pytest tests/ -v --cov=src/mini_coder --cov-report=term-missing --cov-report=html

lint:
	@echo "Running linting..."
	@mypy src/mini_coder/
	@flake8 src/mini_coder/ tests/

format:
	@echo "Formatting code..."
	@black src/mini_coder/ tests/
	@isort src/mini_coder/ tests/
