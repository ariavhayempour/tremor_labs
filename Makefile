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
# adb from PATH, else the copy App Lab bundles.
ADB ?= $(shell command -v adb 2>/dev/null || ls $(HOME)/Library/Arduino15/packages/arduino/tools/adb/*/adb 2>/dev/null | tail -1)

# Runs scripts/$(1) with the backend env, or fails clearly if the script isn't written yet.
define run_script
	@test -f scripts/$(1) || { echo "scripts/$(1): file not found (it is built in a later task)"; exit 1; }
	$(SCRIPT_ENV) scripts/$(1) $(2)
endef

.PHONY: help dev board-link board-sync board-wheels board-deploy seed demo test test-e2e lint typecheck build doctor rate dump-ws

help:
	@echo "make dev [SENSOR_SOURCE=sim|board|replay]  backend :8000 + frontend :5173"
	@echo "make board-link                            adb forward tcp:7700 (stream) + tcp:7701 (analysis)"
	@echo "make board-deploy                          copy analysis + wheels to the UNO Q app and restart it"
	@echo "make seed | demo                           demo data / rehearsal mode (replay + seeded DB)"
	@echo "make test | test-e2e | lint | typecheck | build"
	@echo "make doctor | rate | dump-ws               hardware checks / measured Hz / /ws sample"

dev: $(if $(filter board,$(SENSOR_SOURCE)),board-link)
	@trap 'kill 0' EXIT; \
	(cd $(BACKEND) && uv run uvicorn tremorlab.main:create_app --factory --reload --port 8000) & \
	$(if $(HAS_FRONTEND),(cd $(FRONTEND) && pnpm dev) &,echo "frontend/ not present yet: backend only";) \
	wait

board-link:
	@test -n "$(ADB)" || { echo "adb not found: install App Lab or brew install android-platform-tools"; exit 1; }
	$(ADB) forward tcp:7700 tcp:7700
	$(ADB) forward tcp:7701 tcp:7701

# The board image has no SciPy and no internet, so numpy + scipy wheels are unpacked into python/vendor/.
BOARD_APP := board/tremorlab
BOARD_APP_PATH := /home/arduino/ArduinoApps/tremorlab
BOARD_WHEELS_DIR := board/.wheels
BOARD_VENDOR := $(BOARD_APP)/python/vendor
BOARD_WHEELS := numpy==2.5.4 scipy==1.18.1
BOARD_APP_CLI := export TMPDIR=/tmp; arduino-app-cli app

board-wheels:
	@ls $(BOARD_WHEELS_DIR)/scipy-1.18.1-*.whl >/dev/null 2>&1 && ls $(BOARD_WHEELS_DIR)/numpy-2.5.4-*.whl >/dev/null 2>&1 || \
	uvx pip download --only-binary=:all: --no-deps --python-version 3.13 --implementation cp --abi cp313 \
		--platform manylinux_2_28_aarch64 --platform manylinux_2_17_aarch64 --platform manylinux2014_aarch64 \
		-d $(BOARD_WHEELS_DIR) $(BOARD_WHEELS)

board-sync: board-wheels
	rm -rf $(BOARD_APP)/python/tremorlab $(BOARD_VENDOR)
	mkdir -p $(BOARD_APP)/python/tremorlab $(BOARD_VENDOR)
	cp -R $(BACKEND)/tremorlab/analysis $(BOARD_APP)/python/tremorlab/analysis
	touch $(BOARD_APP)/python/tremorlab/__init__.py
	for w in $(BOARD_WHEELS_DIR)/*.whl; do unzip -q -o "$$w" -d $(BOARD_VENDOR); done
	find $(BOARD_APP)/python -name __pycache__ -type d -prune -exec rm -rf {} +

board-deploy: board-sync
	@test -n "$(ADB)" || { echo "adb not found: install App Lab or brew install android-platform-tools"; exit 1; }
	$(ADB) push $(BOARD_APP)/app.yaml $(BOARD_APP)/python $(BOARD_APP_PATH)/
	-$(ADB) shell '$(BOARD_APP_CLI) stop $(BOARD_APP_PATH)'
	$(ADB) shell '$(BOARD_APP_CLI) start $(BOARD_APP_PATH)'

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
