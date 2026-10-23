# Bursa: one entry point for the checks. The backend runs in Docker (its test
# image), the frontend with the local Node install.
#
#   make check        everything: types, lint, format, tests (SQLite and
#                     PostgreSQL), schema drift, API types
#   make check-fast   the pre-commit subset (no test suite, no rebuild of the types)
#   make api-types    regenerate frontend/src/api/schema.gen.ts from the backend
#   make hooks        use the repo's git hooks (.githooks/)

SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c

BACKEND_IMAGE := bursa-backend-test
# openapi-typescript needs the TypeScript 5 API (the app uses TypeScript 7), so
# it runs through npx with its own pinned copy instead of being a dependency.
OPENAPI_TS := npx -y -p typescript@5.9.3 -p openapi-typescript@7.13.0 openapi-typescript
API_TYPES := frontend/src/api/schema.gen.ts
# Throwaway PostgreSQL for backend-pg: data in memory (tmpfs), so nothing is
# left on disk; the container is removed afterwards, also on failure.
PG_IMAGE := postgres:17-alpine
PG_NAME := bursa-check-pg
PG_URL := postgresql+asyncpg://postgres:test@$(PG_NAME)/bursa_test
TMP := $(shell mktemp -d 2>/dev/null || echo /tmp/bursa-make)

.PHONY: check check-fast backend-image backend-check backend-check-fast backend-pg \
	frontend-check api-types api-types-check hooks

check: backend-check backend-pg frontend-check api-types-check

check-fast: backend-check-fast frontend-check

backend-image:
	docker build -q --target test -t $(BACKEND_IMAGE) backend >/dev/null

backend-check: backend-image
	docker run --rm $(BACKEND_IMAGE) sh -c \
		"ruff check . && pyright && python scripts/check_schema.py && python -m pytest -q"

# The same suite and drift check on PostgreSQL.
backend-pg: backend-image
	@docker rm -fv $(PG_NAME) >/dev/null 2>&1 || true
	@docker network create $(PG_NAME) >/dev/null 2>&1 || true
	@trap 'docker rm -fv $(PG_NAME) >/dev/null 2>&1; docker network rm $(PG_NAME) >/dev/null 2>&1' EXIT; \
	docker run -d --name $(PG_NAME) --network $(PG_NAME) -e POSTGRES_PASSWORD=test \
		-e POSTGRES_DB=bursa_test --tmpfs /var/lib/postgresql/data $(PG_IMAGE) >/dev/null; \
	for _ in $$(seq 60); do \
		docker exec $(PG_NAME) pg_isready -q -U postgres -d bursa_test && break; sleep 1; \
	done; \
	docker run --rm --network $(PG_NAME) -e TEST_DATABASE_URL=$(PG_URL) $(BACKEND_IMAGE) \
		sh -c "python scripts/check_schema.py $(PG_URL) && python -m pytest -q"

# Lints the working tree (mounted), so it needs no image rebuild after edits.
backend-check-fast: backend-image
	docker run --rm -e BURSA_ENV_FILE= -v "$(CURDIR)/backend:/app" $(BACKEND_IMAGE) \
		sh -c "ruff check . && pyright"

frontend-check:
	cd frontend && npm run --silent check

# The OpenAPI document -> TypeScript, formatted like the rest of the frontend.
$(TMP)/openapi.json: backend-image
	docker run --rm -e BURSA_ENV_FILE= -v "$(CURDIR)/backend:/app" $(BACKEND_IMAGE) \
		python scripts/export_openapi.py > $@

$(TMP)/schema.gen.ts: $(TMP)/openapi.json
	$(OPENAPI_TS) $< -o $@ >/dev/null
	cd frontend && npx prettier --stdin-filepath src/api/schema.gen.ts < $@ > $@.fmt
	mv $@.fmt $@

api-types: $(TMP)/schema.gen.ts
	cp $< $(API_TYPES)
	@rm -rf $(TMP)
	@echo "Updated $(API_TYPES)"

api-types-check: $(TMP)/schema.gen.ts
	@diff -q $< $(API_TYPES) >/dev/null || { rm -rf $(TMP); \
		echo "$(API_TYPES) is out of date with the backend's API: run 'make api-types'."; \
		exit 1; }
	@rm -rf $(TMP)
	@echo "API types are up to date."

hooks:
	git config core.hooksPath .githooks
	@echo "Git hooks enabled (.githooks/pre-commit runs 'make check-fast')."
