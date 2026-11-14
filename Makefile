SHELL := /bin/bash
.DEFAULT_GOAL := help

SENSOR_SOURCE ?= sim
export SENSOR_SOURCE
export DB_PATH

BACKEND := backend
FRONTEND := frontend
HAS_FRONTEND := $(wildcard $(FRONTEND)/package.json)
SCRIPT_ENV := PYTHONPATH=$(CURDIR)/$(BACKEND) uv run --project $(BACKEND) python
DEMO_DB := $(CURDIR)/$(BACKEND)/data/demo.db
SEED_DB := $(BACKEND)/data/tremorlab.db

# Runs scripts/$(1) with the backend env, or fails clearly if the script isn't written yet.
define run_script
	@test -f scripts/$(1) || { echo "scripts/$(1): file not found (it is built in a later task)"; exit 1; }
	$(SCRIPT_ENV) scripts/$(1) $(2)
endef

.PHONY: help dev board-link seed demo test test-e2e lint typecheck build doctor rate dump-ws

help:
	@echo "make dev [SENSOR_SOURCE=sim|board|replay]  backend :8000 + frontend :5173"
	@echo "make board-link                            adb forward tcp:7700 tcp:7700"
	@echo "make seed | demo                           demo data / rehearsal mode (replay + seeded DB)"
	@echo "make test | test-e2e | lint | typecheck | build"
	@echo "make doctor | rate | dump-ws               hardware checks / measured Hz / /ws sample"

dev: $(if $(filter board,$(SENSOR_SOURCE)),board-link)
	@trap 'kill 0' EXIT; \
	(cd $(BACKEND) && uv run uvicorn tremorlab.main:create_app --factory --reload --port 8000) & \
	$(if $(HAS_FRONTEND),(cd $(FRONTEND) && pnpm dev) &,echo "frontend/ not present yet: backend only";) \
	wait

board-link:
	adb forward tcp:7700 tcp:7700

seed:
	$(call run_script,seed.py,--db $(SEED_DB) --reset)

demo:
	@test -f $(SEED_DB) || $(MAKE) seed
	cp $(SEED_DB) $(DEMO_DB)
	$(MAKE) dev SENSOR_SOURCE=replay DB_PATH=$(DEMO_DB)

test:
	cd $(BACKEND) && uv run pytest
	$(if $(HAS_FRONTEND),cd $(FRONTEND) && pnpm test,@echo "frontend/ not present yet: skipping pnpm test")

test-e2e:
	$(if $(HAS_FRONTEND),cd $(FRONTEND) && pnpm test:e2e,@echo "frontend/ not present yet: skipping e2e")

lint:
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check .
	$(if $(HAS_FRONTEND),cd $(FRONTEND) && pnpm lint,@echo "frontend/ not present yet: skipping pnpm lint")

typecheck:
	cd $(BACKEND) && uv run mypy tremorlab
	$(if $(HAS_FRONTEND),cd $(FRONTEND) && pnpm typecheck,@echo "frontend/ not present yet: skipping pnpm typecheck")

build:
	$(if $(HAS_FRONTEND),cd $(FRONTEND) && pnpm build,@echo "frontend/ not present yet: nothing to build")

doctor:
	$(call run_script,doctor.py,)

rate:
	$(call run_script,rate_probe.py,)

dump-ws:
	$(call run_script,dump_ws.py,)
