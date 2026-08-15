# Makefile — AI Data Analyst
#
# Placeholders documentados para Fase 0. La mayoría de estos targets todavía no
# tienen nada real que ejecutar (no existe docker-compose.yml ni scaffolding de
# app) — devuelven un mensaje explícito en vez de fallar de forma confusa.
# Se activan a medida que avanza el roadmap (docs/SRS.md, sección 13).

.PHONY: up down logs test lint deploy-staging deploy-production smoke-test

up: ## Levanta el stack local (pendiente: requiere docker-compose.yml, Fase 0.2)
	@echo "Pendiente: docker-compose.yml aún no existe. Ver docs/architecture.md."

down: ## Baja el stack local (pendiente: requiere docker-compose.yml)
	@echo "Pendiente: docker-compose.yml aún no existe."

logs: ## Logs del stack local (pendiente)
	@echo "Pendiente: docker-compose.yml aún no existe."

test: ## Corre la suite de tests completa (pendiente: requiere scaffolding de backend/frontend)
	@echo "Pendiente: aún no hay backend/frontend/workers con tests que ejecutar."

lint: ## Lint + format de todo el repo (pendiente: requiere pyproject.toml/package.json)
	@echo "Pendiente: aún no hay configuración de lint (ruff/eslint) instalada."

deploy-staging: ## Despliega a staging (pendiente: ver docs/deployment.md)
	@bash infrastructure/scripts/deploy-staging.sh

deploy-production: ## Despliega a producción (pendiente: ver docs/deployment.md)
	@bash infrastructure/scripts/deploy-production.sh

smoke-test: ## Ejecuta smoke tests post-deploy (SRS sección 11.1)
	@bash infrastructure/scripts/smoke-test.sh
