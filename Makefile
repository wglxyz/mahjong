VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.DEFAULT_GOAL := help

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

$(VENV): pyproject.toml
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	@touch $(VENV)

.PHONY: install
install: $(VENV) ## Create .venv and install package + dev tools

.PHONY: test
test: $(VENV) ## Run the full test suite (pytest)
	$(PY) -m pytest

.PHONY: lint
lint: $(VENV) ## Lint with ruff
	$(VENV)/bin/ruff check .

.PHONY: format
format: $(VENV) ## Auto-format + autofix with ruff
	$(VENV)/bin/ruff format .
	$(VENV)/bin/ruff check --fix .

.PHONY: typecheck
typecheck: $(VENV) ## Static type check with mypy
	$(VENV)/bin/mypy core mahjong rules server games ui

.PHONY: check
check: lint test ## Lint then test (CI gate)

.PHONY: server
server: $(VENV) ## Run the WebSocket server (RULESET=riichi PORT=8765)
	$(PY) -m server.server --ruleset $(or $(RULESET),riichi) --port $(or $(PORT),8765)

.PHONY: play
play: $(VENV) ## Play a riichi hand vs 3 AIs in the terminal (SEED=7)
	$(PY) -m games.mahjong.play_riichi --seed $(or $(SEED),7)

.PHONY: play-cli
play-cli: $(VENV) ## Play as a human vs 3 AIs (SimpleRuleset)
	$(PY) -m games.mahjong.play_cli

.PHONY: flutter-run
flutter-run: ## Run the Flutter client on macOS
	cd client_flutter && flutter pub get && flutter run -d macos

.PHONY: clean
clean: ## Remove venv and caches
	rm -rf $(VENV) .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
