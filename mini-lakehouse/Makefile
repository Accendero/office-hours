# Laptop-only mini-lakehouse. Test in stages -- see CLAUDE.md.
SHELL := /bin/bash
.DEFAULT_GOAL := help
export
-include .env

DBT := cd dbt && DBT_PROFILES_DIR=. dbt

help:  ## show targets
	@grep -hE "^[a-z-]+:.*##" $(MAKEFILE_LIST) | sed "s/:.*##/\t/" | column -t -s$$"\t"

## ---------- stage 1: infrastructure (the risky part) ----------
up:  ## start the stack
	@test -f .env || cp .env.example .env
	docker compose up -d
	@echo "waiting for health checks..."; sleep 5; docker compose ps

init:  ## create the S3 bucket (idempotent)
	bash scripts/00_init_object_store.sh

smoke: init  ## STAGE 1 GATE -- seven hops, stops at first failure
	bash scripts/smoke.sh

logs:  ## tail everything
	docker compose logs -f --tail=80

down:  ## stop, keep volumes
	docker compose down

reset:  ## stop and DESTROY all state
	docker compose down -v
	rm -rf dbt/target dbt/logs data/bronze_*.parquet data/*CORRUPT*

## ---------- stage 2: data and transforms ----------
data:  ## download the four real source files (~150 MB)
	bash scripts/01_download_data.sh

deps:  ## install python + dbt packages
	pip install -r requirements.txt
	$(DBT) deps

bronze:  ## land all three sources
	python3 scripts/03a_load_trips.py
	python3 scripts/03b_load_weather.py
	python3 scripts/03c_load_zone_lookup.py

silver-gold:  ## dbt build (silver + gold)
	$(DBT) build

gate:  ## THE PROMOTION GATE -- nonzero exit halts promotion
	$(DBT) test

break:  ## land corrupt data upstream; the gate MUST close
	python3 scripts/07_break_the_data.py

maintain:  ## Iceberg compaction + snapshot expiry (the step everyone skips)
	@echo "ALTER TABLE iceberg.gold.fct_trips EXECUTE optimize;"
	@echo "ALTER TABLE iceberg.gold.fct_trips EXECUTE expire_snapshots(retention_threshold => '7d');"

## ---------- stage 3: train, track, decide ----------
train:  ## train and log to MLflow with the Iceberg snapshot id
	python3 scripts/08_train.py

lift:  ## the open experiment -- keep or cut the weather source
	python3 scripts/10_weather_lift.py

validate-offline:  ## re-run the proven offline reference (no Docker needed)
	cd validated && python3 make_fake_tlc.py && python3 run_pipeline.py && python3 quality_gate.py

.PHONY: help up init smoke logs down reset data deps bronze silver-gold gate break maintain train lift validate-offline
