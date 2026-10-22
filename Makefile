# Bursa: one entry point for the checks. The backend runs in Docker (its test
# image), the frontend with the local Node install.
#
#   make check        everything CI runs: types, lint, format, tests, API types
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
TMP := $(shell mktemp -d 2>/dev/null || echo /tmp/bursa-make)

.PHONY: check check-fast backend-image backend-check backend-check-fast \
	frontend-check api-types api-types-check hooks

check: backend-check frontend-check api-types-check

check-fast: backend-check-fast frontend-check

backend-image:
	docker build -q --target test -t $(BACKEND_IMAGE) backend >/dev/null

backend-check: backend-image
	docker run --rm $(BACKEND_IMAGE) sh -c "ruff check . && pyright && python -m pytest -q"

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
